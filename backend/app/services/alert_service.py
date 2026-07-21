"""
Alert service — creates admin_alerts rows and optionally sends emails.

Alert types & triggers:
  overreaching   critical   TSB < -25
  no_workout     warning    3+ consecutive days without any workout
  no_metrics     info       No daily_metrics recorded today
  sync_failure   warning    Platform connection has consecutive_failures >= 3

Deduplication: only one unread alert per (admin_id, athlete_id, alert_type) per
calendar day to avoid flooding the admin inbox.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.models.alert import AdminAlert
from app.models.athlete import Athlete, PlatformConnection
from app.models.metric import DailyMetric
from app.models.training_load import TrainingLoad
from app.models.workout import Workout
from app.models.strength import StrengthSession

logger = logging.getLogger(__name__)


# ── Deduplication helper ──────────────────────────────────────────────────────

async def _alert_exists_today(
    db: AsyncSession,
    admin_id,
    athlete_id,
    alert_type: str,
    today: date,
) -> bool:
    """Return True if an unread alert of this type was already created today."""
    from sqlalchemy import cast, Date as SADate
    result = await db.execute(
        select(AdminAlert).where(
            AdminAlert.admin_id == admin_id,
            AdminAlert.athlete_id == athlete_id,
            AdminAlert.alert_type == alert_type,
            AdminAlert.is_read == False,
            func.date(AdminAlert.created_at) == today,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _create_alert(
    db: AsyncSession,
    admin_id,
    athlete_id,
    alert_type: str,
    severity: str,
    title: str,
    body: str,
) -> AdminAlert:
    alert = AdminAlert(
        admin_id=admin_id,
        athlete_id=athlete_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        body=body,
    )
    db.add(alert)
    return alert


# ── Per-athlete alert checks ──────────────────────────────────────────────────

async def check_overreaching(
    db: AsyncSession,
    athlete: Athlete,
    today: date,
) -> AdminAlert | None:
    """Create critical alert when TSB drops below -25."""
    load_result = await db.execute(
        select(TrainingLoad)
        .where(TrainingLoad.athlete_id == athlete.id)
        .order_by(desc(TrainingLoad.load_date))
        .limit(1)
    )
    load = load_result.scalar_one_or_none()
    if not load or load.tsb is None:
        return None

    tsb = float(load.tsb)
    if tsb >= -25:
        return None

    if await _alert_exists_today(db, athlete.admin_id, athlete.id, "overreaching", today):
        return None

    alert = await _create_alert(
        db,
        admin_id=athlete.admin_id,
        athlete_id=athlete.id,
        alert_type="overreaching",
        severity="critical",
        title=f"⚠️ Overtraining: {athlete.name}",
        body=(
            f"{athlete.name} está com TSB = {tsb:.1f} (abaixo de −25). "
            f"CTL = {float(load.ctl):.1f}, ATL = {float(load.atl):.1f}. "
            "Recomendado prescrever descanso ou sessão muito leve amanhã."
        ),
    )
    logger.warning("Created overreaching alert for athlete %s (TSB=%.1f)", athlete.id, tsb)

    # fire-and-forget email
    from app.services.email_service import send_alert_email
    admin_result = await db.execute(select(AdminUser).where(AdminUser.id == athlete.admin_id))
    admin = admin_result.scalar_one_or_none()
    if admin:
        import asyncio
        asyncio.create_task(
            send_alert_email(
                to_email=admin.email,
                admin_name=admin.name,
                athlete_name=athlete.name,
                title=alert.title,
                body=alert.body or "",
                severity="critical",
            )
        )

    return alert


async def check_no_workout(
    db: AsyncSession,
    athlete: Athlete,
    today: date,
    days_threshold: int = 3,
) -> AdminAlert | None:
    """Create warning alert when athlete has no workout for 3+ consecutive days."""
    cutoff = today - timedelta(days=days_threshold)

    # Check workouts (endurance)
    workout_result = await db.execute(
        select(func.count()).select_from(Workout).where(
            Workout.athlete_id == athlete.id,
            func.date(Workout.start_time) >= cutoff,
        )
    )
    workout_count = workout_result.scalar() or 0

    # Check strength sessions
    strength_result = await db.execute(
        select(func.count()).select_from(StrengthSession).where(
            StrengthSession.athlete_id == athlete.id,
            StrengthSession.session_date >= cutoff,
        )
    )
    strength_count = strength_result.scalar() or 0

    if workout_count + strength_count > 0:
        return None

    if await _alert_exists_today(db, athlete.admin_id, athlete.id, "no_workout", today):
        return None

    alert = await _create_alert(
        db,
        admin_id=athlete.admin_id,
        athlete_id=athlete.id,
        alert_type="no_workout",
        severity="warning",
        title=f"Sem treino: {athlete.name}",
        body=(
            f"{athlete.name} não registrou nenhum treino nos últimos {days_threshold} dias "
            f"(desde {cutoff.strftime('%d/%m/%Y')}). Verifique se a integração Strava está ativa "
            "ou entre em contato com o atleta."
        ),
    )
    logger.info("Created no_workout alert for athlete %s", athlete.id)
    return alert


async def check_no_metrics(
    db: AsyncSession,
    athlete: Athlete,
    today: date,
) -> AdminAlert | None:
    """Create info alert when athlete hasn't filled daily metrics today."""
    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.athlete_id == athlete.id,
            DailyMetric.metric_date == today,
        ).limit(1)
    )
    if metrics_result.scalar_one_or_none():
        return None

    if await _alert_exists_today(db, athlete.admin_id, athlete.id, "no_metrics", today):
        return None

    alert = await _create_alert(
        db,
        admin_id=athlete.admin_id,
        athlete_id=athlete.id,
        alert_type="no_metrics",
        severity="info",
        title=f"Métricas pendentes: {athlete.name}",
        body=(
            f"{athlete.name} ainda não registrou as métricas do dia "
            f"({today.strftime('%d/%m/%Y')}). "
            "Fadiga, sono e HRV são importantes para as recomendações da IA."
        ),
    )
    return alert


async def check_sync_failure(
    db: AsyncSession,
    athlete: Athlete,
    today: date,
    failure_threshold: int = 3,
) -> AdminAlert | None:
    """Create warning alert when a platform connection has too many consecutive failures."""
    connections_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete.id,
            PlatformConnection.is_active == True,
            PlatformConnection.consecutive_failures >= failure_threshold,
        )
    )
    failing = connections_result.scalars().all()
    if not failing:
        return None

    if await _alert_exists_today(db, athlete.admin_id, athlete.id, "sync_failure", today):
        return None

    providers = ", ".join(c.provider for c in failing)
    alert = await _create_alert(
        db,
        admin_id=athlete.admin_id,
        athlete_id=athlete.id,
        alert_type="sync_failure",
        severity="warning",
        title=f"Falha de sync: {athlete.name}",
        body=(
            f"A integração de {athlete.name} com {providers} falhou "
            f"{failure_threshold}+ vezes consecutivas. "
            "Os treinos podem não estar sendo importados automaticamente."
        ),
    )
    logger.warning("Created sync_failure alert for athlete %s (providers: %s)", athlete.id, providers)
    return alert


# ── Main entry point (called from scheduler) ─────────────────────────────────

async def create_athlete_alerts(db: AsyncSession, athlete_id: str, today: date) -> int:
    """
    Run all alert checks for a given athlete and commit new alerts.
    Returns the number of alerts created.
    """
    athlete_result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        return 0

    created = 0
    for check_fn in (check_overreaching, check_no_workout, check_no_metrics, check_sync_failure):
        try:
            alert = await check_fn(db, athlete, today)
            if alert:
                created += 1
        except Exception as exc:
            logger.exception("Alert check %s failed for athlete %s: %s", check_fn.__name__, athlete_id, exc)

    if created:
        await db.commit()

    return created
