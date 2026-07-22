"""
Weekly report service — generates a plain-language AI summary of each athlete's
training week and emails it to the admin every Friday at 20:00 BRT.

The report covers the last 7 days and includes:
  • Total workouts + TSS breakdown
  • CTL/ATL/TSB evolution
  • Adherence to recommended sessions
  • Subjective metrics trends (fatigue, sleep, HRV)
  • AI narrative summary with highlights and concerns
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

import anthropic
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.admin import AdminUser
from app.models.athlete import Athlete
from app.models.metric import DailyMetric
from app.models.recommendation import AIRecommendation
from app.models.training_load import TrainingLoad
from app.models.workout import Workout
from app.models.strength import StrengthSession

logger = logging.getLogger(__name__)

_REPORT_SYSTEM = """
You are a sports science expert writing a weekly training review for a coach (educador físico / trainer).
Write in Brazilian Portuguese. Be concise, factual, and actionable.
Output must be valid JSON with the structure shown below — no markdown, no prose outside the JSON.

{
  "week_summary": "2-3 sentence overview of the week",
  "highlights": ["achievement 1", "achievement 2"],
  "concerns": ["concern 1"],
  "load_analysis": "1-2 sentences on CTL/ATL/TSB trend",
  "subjective_trend": "1 sentence on fatigue/sleep/HRV trend",
  "adherence_comment": "1 sentence on recommendation adherence",
  "next_week_focus": "1-2 sentences on what to prioritize next week"
}
"""


async def _build_week_context(db: AsyncSession, athlete_id: str, today: date) -> dict | None:
    week_start = today - timedelta(days=7)

    athlete_result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        return None

    # Workouts this week
    workouts_result = await db.execute(
        select(Workout).where(
            Workout.athlete_id == athlete_id,
            func.date(Workout.start_time) >= week_start,
        ).order_by(Workout.start_time)
    )
    workouts = workouts_result.scalars().all()

    # Strength sessions this week
    strength_result = await db.execute(
        select(StrengthSession).where(
            StrengthSession.athlete_id == athlete_id,
            StrengthSession.session_date >= week_start,
        )
    )
    strength = strength_result.scalars().all()

    # CTL/ATL/TSB range this week
    load_result = await db.execute(
        select(TrainingLoad).where(
            TrainingLoad.athlete_id == athlete_id,
            TrainingLoad.load_date >= week_start,
        ).order_by(TrainingLoad.load_date)
    )
    loads = load_result.scalars().all()

    # Daily metrics this week
    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.athlete_id == athlete_id,
            DailyMetric.metric_date >= week_start,
        ).order_by(DailyMetric.metric_date)
    )
    metrics = metrics_result.scalars().all()

    # AI recommendations this week
    recs_result = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.athlete_id == athlete_id,
            AIRecommendation.recommendation_date >= week_start,
        )
    )
    recs = recs_result.scalars().all()

    total_tss = sum(float(w.tss or 0) for w in workouts)
    total_tss += sum(float(s.tss or 0) for s in strength if hasattr(s, "tss") and s.tss)

    recs_followed = [r for r in recs if r.was_followed is True]
    adherence_pct = round(len(recs_followed) / len(recs) * 100) if recs else None

    avg_sleep = None
    avg_fatigue = None
    avg_hrv = None
    if metrics:
        sleeps = [float(m.sleep_hours) for m in metrics if m.sleep_hours]
        fatigue = [m.fatigue_score for m in metrics if m.fatigue_score]
        hrvs = [m.hrv_ms for m in metrics if m.hrv_ms]
        avg_sleep = round(sum(sleeps) / len(sleeps), 1) if sleeps else None
        avg_fatigue = round(sum(fatigue) / len(fatigue), 1) if fatigue else None
        avg_hrv = round(sum(hrvs) / len(hrvs)) if hrvs else None

    load_start = {"ctl": float(loads[0].ctl), "atl": float(loads[0].atl), "tsb": float(loads[0].tsb)} if loads else None
    load_end = {"ctl": float(loads[-1].ctl), "atl": float(loads[-1].atl), "tsb": float(loads[-1].tsb)} if loads else None

    return {
        "athlete_name": athlete.name,
        "week": f"{week_start.strftime('%d/%m')} – {today.strftime('%d/%m/%Y')}",
        "workouts_count": len(workouts),
        "strength_count": len(strength),
        "total_tss": round(total_tss, 1),
        "load_start": load_start,
        "load_end": load_end,
        "avg_sleep_hours": avg_sleep,
        "avg_fatigue_score": avg_fatigue,
        "avg_hrv_ms": avg_hrv,
        "metrics_days_recorded": len(metrics),
        "recommendations_generated": len(recs),
        "adherence_pct": adherence_pct,
        "workout_titles": [w.title or w.sport_type for w in workouts],
    }


async def generate_weekly_report(db: AsyncSession, athlete_id: str, today: date) -> dict | None:
    """
    Generate an AI-powered weekly report for one athlete.
    Returns the parsed report dict or None if the athlete has no data.
    """
    ctx = await _build_week_context(db, athlete_id, today)
    if not ctx:
        return None

    user_msg = (
        f"Gere o relatório semanal do atleta {ctx['athlete_name']}.\n\n"
        f"Dados da semana {ctx['week']}:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}"
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            temperature=0.4,
            system=_REPORT_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        report = json.loads(raw)
        report["_context"] = ctx
        return report
    except Exception as exc:
        logger.exception("Weekly report AI call failed for athlete %s: %s", athlete_id, exc)
        return {
            "week_summary": f"Semana {ctx['week']}: {ctx['workouts_count']} treinos, TSS total {ctx['total_tss']}.",
            "highlights": [],
            "concerns": [],
            "load_analysis": "",
            "subjective_trend": "",
            "adherence_comment": "",
            "next_week_focus": "",
            "_context": ctx,
        }


async def run_weekly_reports_for_admin(admin_id: str) -> None:
    """
    Generate reports for all active athletes of one admin and send summary email.
    Called by the scheduler on Friday at 20:00 BRT.
    """
    from app.database import AsyncSessionLocal
    from app.services.email_service import send_weekly_report_email

    async with AsyncSessionLocal() as db:
        admin_result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
        admin = admin_result.scalar_one_or_none()
        if not admin:
            return

        athletes_result = await db.execute(
            select(Athlete).where(
                Athlete.admin_id == admin_id,
                Athlete.is_active == True,
                Athlete.onboarding_complete == True,
            )
        )
        athletes = athletes_result.scalars().all()

        if not athletes:
            return

        today = date.today()
        reports: list[dict] = []

        for athlete in athletes:
            try:
                report = await generate_weekly_report(db, str(athlete.id), today)
                if report:
                    reports.append(report)
                    logger.info("Weekly report generated for athlete %s", athlete.id)
            except Exception as exc:
                logger.exception("Failed weekly report for athlete %s: %s", athlete.id, exc)

        if reports:
            await send_weekly_report_email(
                to_email=admin.email,
                admin_name=admin.name,
                reports=reports,
                week_end=today,
            )
