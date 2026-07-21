"""
APScheduler daily job — runs at 06:00 BRT (UTC-3 = 09:00 UTC).

Flow for each active athlete:
  1. Sync Strava (last 24h)
  2. Sync TrainingPeaks completed workouts (last 3 days)
  3. Recalculate CTL/ATL/TSB
  4. Generate AI recommendation if not yet generated today
  5. Push recommendation to TrainingPeaks (→ auto-syncs to Garmin)
  6. Create admin alerts for overreaching or no-metrics athletes

Concurrency: asyncio.gather with a semaphore of 5 to avoid overloading external APIs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
_semaphore = asyncio.Semaphore(5)


# ── Per-athlete job ───────────────────────────────────────────────────────────

async def _process_athlete(athlete_id: str) -> None:
    async with _semaphore:
        async with AsyncSessionLocal() as db:
            try:
                await _run_athlete_pipeline(db, athlete_id)
            except Exception as e:
                logger.exception("Daily job failed for athlete %s: %s", athlete_id, e)


async def _run_athlete_pipeline(db, athlete_id: str) -> None:
    from app.models.athlete import Athlete, PlatformConnection
    from app.models.metric import DailyMetric
    from app.models.recommendation import AIRecommendation
    from app.services.strava_service import StravaService, get_valid_access_token
    from app.services.training_load import recalculate_athlete_load
    from app.services.ai_service import AIService, build_athlete_context
    from app.services.tp_sync import sync_completed_workouts_from_tp, push_recommendation_to_trainingpeaks

    logger.info("Processing athlete %s", athlete_id)

    # 1. Strava sync (last 24h)
    strava_conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete_id,
            PlatformConnection.provider == "strava",
            PlatformConnection.is_active == True,
        )
    )
    strava_conn = strava_conn_result.scalar_one_or_none()
    if strava_conn:
        token = await get_valid_access_token(db, strava_conn)
        if token:
            athlete_result = await db.execute(
                select(Athlete).where(Athlete.id == athlete_id)
            )
            athlete = athlete_result.scalar_one_or_none()
            svc = StravaService()
            try:
                imported = await svc.sync_recent_activities(
                    db, athlete_id, token, days_back=1,
                    ftp=athlete.ftp_watts if athlete else None,
                    max_hr=athlete.max_hr if athlete else None,
                    resting_hr=athlete.resting_hr if athlete else None,
                )
                if imported:
                    logger.info("Strava: %d new workouts for athlete %s", len(imported), athlete_id)
            except Exception as e:
                logger.warning("Strava sync failed for %s: %s", athlete_id, e)

    # 2. TrainingPeaks sync (last 3 days)
    try:
        await sync_completed_workouts_from_tp(db, athlete_id, days_back=3)
    except Exception as e:
        logger.warning("TP sync failed for %s: %s", athlete_id, e)

    # 3. Recalculate training load
    await recalculate_athlete_load(db, athlete_id, days_back=90)

    # 4. Generate AI recommendation if not yet done today
    today = date.today()
    existing = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.athlete_id == athlete_id,
            AIRecommendation.recommendation_date == today,
        )
    )
    rec = existing.scalar_one_or_none()

    if not rec:
        ctx = await build_athlete_context(db, athlete_id)
        if ctx:
            ai_svc = AIService()
            recommendation = await ai_svc.generate_recommendation(ctx)

            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(AIRecommendation.__table__).values(
                athlete_id=athlete_id,
                recommendation_date=today,
                ai_provider=recommendation.ai_provider,
                ai_model=recommendation.ai_model,
                workout_type=recommendation.workout_type,
                title=recommendation.title,
                recommendation_text=recommendation.recommendation_text,
                structured_plan=recommendation.structured_plan,
                nutrition_plan=recommendation.nutrition_plan,
                rationale=recommendation.rationale,
                tokens_used=recommendation.tokens_used,
                generation_time_ms=recommendation.generation_time_ms,
                input_context={"tsb": ctx.tsb, "ctl": ctx.ctl, "atl": ctx.atl},
            ).on_conflict_do_nothing()
            result = await db.execute(stmt)
            await db.commit()

            # Re-fetch to get ID
            new_rec = await db.execute(
                select(AIRecommendation).where(
                    AIRecommendation.athlete_id == athlete_id,
                    AIRecommendation.recommendation_date == today,
                )
            )
            rec = new_rec.scalar_one_or_none()
            logger.info("Generated recommendation for athlete %s (type: %s)", athlete_id, recommendation.workout_type)

    # 5. Push recommendation to TrainingPeaks (→ Garmin relay)
    if rec and rec.workout_type != "rest":
        try:
            await push_recommendation_to_trainingpeaks(db, athlete_id, str(rec.id))
        except Exception as e:
            logger.warning("TP push failed for athlete %s: %s", athlete_id, e)

    # 6. Admin alerts — overreaching, no workout, no metrics, sync failures
    from app.services.alert_service import create_athlete_alerts
    created = await create_athlete_alerts(db, athlete_id, today)
    if created:
        logger.info("Created %d alert(s) for athlete %s", created, athlete_id)


# ── Scheduler lifecycle ───────────────────────────────────────────────────────

async def _daily_job() -> None:
    """Main daily job: processes all active athletes."""
    logger.info("Daily job started at %s", datetime.now(timezone.utc).isoformat())

    async with AsyncSessionLocal() as db:
        from app.models.athlete import Athlete
        result = await db.execute(
            select(Athlete.id).where(Athlete.is_active == True)
        )
        athlete_ids = [str(row[0]) for row in result.all()]

    logger.info("Processing %d active athletes", len(athlete_ids))

    tasks = [_process_athlete(aid) for aid in athlete_ids]
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Daily job completed. Processed %d athletes.", len(athlete_ids))


async def _metrics_reminder_job() -> None:
    """07:00 BRT (10:00 UTC) Mon-Fri: push reminder to athletes who haven't filled metrics today."""
    from app.models.metric import DailyMetric
    today = date.today()
    logger.info("Metrics reminder job started for %s", today)

    async with AsyncSessionLocal() as db:
        from app.models.athlete import Athlete
        result = await db.execute(
            select(Athlete.id).where(Athlete.is_active == True, Athlete.onboarding_complete == True)
        )
        athlete_ids = [str(row[0]) for row in result.all()]

    from app.routers.push_notifications import send_push_to_athlete

    sent_count = 0
    async with AsyncSessionLocal() as db:
        for aid in athlete_ids:
            # Skip if they already filled metrics today
            metrics = await db.execute(
                select(DailyMetric).where(
                    DailyMetric.athlete_id == aid,
                    DailyMetric.metric_date == today,
                ).limit(1)
            )
            if metrics.scalar_one_or_none():
                continue

            try:
                n = await send_push_to_athlete(
                    db, aid,
                    title="FitCoach AI — Como você está?",
                    body="Registre seu sono, fadiga e HRV de hoje para melhores recomendações. 📊",
                    url="/metrics",
                    tag="daily-metrics",
                )
                sent_count += n
            except Exception as exc:
                logger.warning("Metrics reminder push failed for athlete %s: %s", aid, exc)

    logger.info("Metrics reminder job completed — sent %d push(es)", sent_count)


async def _weekly_report_job() -> None:
    """Friday at 23:00 UTC (20:00 BRT): generate weekly reports for all admins."""
    logger.info("Weekly report job started at %s", datetime.now(timezone.utc).isoformat())
    async with AsyncSessionLocal() as db:
        from app.models.admin import AdminUser
        result = await db.execute(select(AdminUser.id).where(AdminUser.is_active == True))
        admin_ids = [str(row[0]) for row in result.all()]

    from app.services.weekly_report import run_weekly_reports_for_admin
    tasks = [run_weekly_reports_for_admin(aid) for aid in admin_ids]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Weekly report job completed for %d admin(s).", len(admin_ids))


def start_scheduler() -> None:
    _scheduler.add_job(
        _daily_job,
        trigger=CronTrigger(hour=9, minute=0),  # 09:00 UTC = 06:00 BRT
        id="daily_update",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _weekly_report_job,
        trigger=CronTrigger(day_of_week="fri", hour=23, minute=0),  # Friday 23:00 UTC = 20:00 BRT
        id="weekly_report",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _metrics_reminder_job,
        trigger=CronTrigger(day_of_week="mon-fri", hour=10, minute=0),  # 10:00 UTC = 07:00 BRT
        id="metrics_reminder",
        replace_existing=True,
        misfire_grace_time=1800,
    )
    _scheduler.start()
    logger.info(
        "APScheduler started — daily 09:00 UTC · metrics reminder Mon-Fri 10:00 UTC · weekly report Fri 23:00 UTC"
    )


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
