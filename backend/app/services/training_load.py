"""
Orchestrates CTL/ATL/TSB calculation and persistence for a given athlete.
Reads workouts + strength sessions from DB, computes TSS for each,
then upserts the training_load table.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta, datetime, timezone

from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.workout import Workout
from app.models.strength import StrengthSession
from app.models.training_load import TrainingLoad
from app.utils.calculations import (
    calculate_tss_cycling,
    calculate_tss_from_hr,
    calculate_strength_tss,
    calculate_training_load_series,
    LoadPoint,
)

logger = logging.getLogger(__name__)


# ── Per-session TSS helpers ───────────────────────────────────────────────────

def _tss_for_workout(workout: Workout, athlete: Athlete) -> float:
    """Return TSS for an endurance workout using power data or HR fallback."""
    # Power-based (preferred)
    if (
        workout.normalized_power_watts
        and athlete.ftp_watts
        and workout.duration_seconds
    ):
        try:
            return calculate_tss_cycling(
                workout.duration_seconds,
                workout.normalized_power_watts,
                athlete.ftp_watts,
            )
        except ValueError:
            pass

    # HR-based fallback
    if (
        workout.avg_heart_rate
        and athlete.max_hr
        and athlete.resting_hr
        and workout.duration_seconds
    ):
        try:
            return calculate_tss_from_hr(
                workout.duration_seconds,
                workout.avg_heart_rate,
                athlete.max_hr,
                athlete.resting_hr,
            )
        except ValueError:
            pass

    # Last resort: if TSS was stored directly (e.g. imported from TrainingPeaks)
    if workout.tss is not None:
        return float(workout.tss)

    return 0.0


def _tss_for_strength(session: StrengthSession) -> float:
    if session.tss is not None:
        return float(session.tss)
    if session.duration_minutes and session.rpe_overall:
        try:
            return calculate_strength_tss(session.duration_minutes, session.rpe_overall)
        except ValueError:
            pass
    return 0.0


# ── Main service functions ────────────────────────────────────────────────────

async def recalculate_athlete_load(
    db: AsyncSession,
    athlete_id: str,
    days_back: int = 90,
) -> None:
    """
    Recalculates CTL/ATL/TSB for the last `days_back` calendar days and
    upserts rows into training_load.
    Uses the last CTL/ATL before the window as initial values (continuity).
    """
    athlete_result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        logger.warning("recalculate_athlete_load: athlete %s not found", athlete_id)
        return

    cutoff = date.today() - timedelta(days=days_back)

    # Find the most recent training_load entry before the window for continuity
    seed_result = await db.execute(
        select(TrainingLoad)
        .where(TrainingLoad.athlete_id == athlete_id, TrainingLoad.load_date < cutoff)
        .order_by(TrainingLoad.load_date.desc())
        .limit(1)
    )
    seed = seed_result.scalar_one_or_none()
    initial_ctl = float(seed.ctl) if seed and seed.ctl else 0.0
    initial_atl = float(seed.atl) if seed and seed.atl else 0.0

    # Fetch all workouts in window
    workouts_result = await db.execute(
        select(Workout).where(
            Workout.athlete_id == athlete_id,
            Workout.is_completed == True,
            func.date(Workout.start_time) >= cutoff,
        )
    )
    workouts = workouts_result.scalars().all()

    # Fetch all strength sessions in window
    strength_result = await db.execute(
        select(StrengthSession).where(
            StrengthSession.athlete_id == athlete_id,
            func.date(StrengthSession.session_date) >= cutoff,
        )
    )
    strength_sessions = strength_result.scalars().all()

    # Build TSS series
    tss_entries: list[dict] = []
    for w in workouts:
        tss_val = _tss_for_workout(w, athlete)
        if tss_val > 0:
            d = w.start_time.date() if isinstance(w.start_time, datetime) else w.start_time
            tss_entries.append({"date": d, "tss": tss_val})

    for s in strength_sessions:
        tss_val = _tss_for_strength(s)
        if tss_val > 0:
            d = s.session_date.date() if isinstance(s.session_date, datetime) else s.session_date
            tss_entries.append({"date": d, "tss": tss_val})

    if not tss_entries:
        logger.info("No TSS data found for athlete %s in the last %d days", athlete_id, days_back)
        return

    series = calculate_training_load_series(tss_entries, initial_ctl, initial_atl)

    # Compute weekly TSS rolling sum (7-day window ending each day)
    daily_map: dict[date, float] = {p.load_date: p.daily_tss for p in series}

    for point in series:
        weekly_tss = sum(
            daily_map.get(point.load_date - timedelta(days=i), 0.0)
            for i in range(7)
        )
        # Upsert into training_load
        stmt = pg_insert(TrainingLoad.__table__).values(
            athlete_id=athlete_id,
            load_date=point.load_date,
            ctl=point.ctl,
            atl=point.atl,
            tsb=point.tsb,
            daily_tss=point.daily_tss,
            weekly_tss=round(weekly_tss, 2),
        ).on_conflict_do_update(
            index_elements=["athlete_id", "load_date"],
            set_={
                "ctl": point.ctl,
                "atl": point.atl,
                "tsb": point.tsb,
                "daily_tss": point.daily_tss,
                "weekly_tss": round(weekly_tss, 2),
            },
        )
        await db.execute(stmt)

    await db.commit()
    logger.info("Training load recalculated for athlete %s (%d days)", athlete_id, len(series))


async def get_current_load(db: AsyncSession, athlete_id: str) -> dict | None:
    """Returns the most recent CTL/ATL/TSB row for an athlete."""
    result = await db.execute(
        select(TrainingLoad)
        .where(TrainingLoad.athlete_id == athlete_id)
        .order_by(TrainingLoad.load_date.desc())
        .limit(1)
    )
    load = result.scalar_one_or_none()
    if not load:
        return None
    return {
        "load_date": load.load_date.isoformat(),
        "ctl": float(load.ctl) if load.ctl else 0.0,
        "atl": float(load.atl) if load.atl else 0.0,
        "tsb": float(load.tsb) if load.tsb else 0.0,
        "daily_tss": float(load.daily_tss) if load.daily_tss else 0.0,
        "weekly_tss": float(load.weekly_tss) if load.weekly_tss else 0.0,
    }


async def get_load_history(
    db: AsyncSession,
    athlete_id: str,
    days: int = 90,
) -> list[dict]:
    """Returns CTL/ATL/TSB history for chart rendering."""
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(TrainingLoad)
        .where(TrainingLoad.athlete_id == athlete_id, TrainingLoad.load_date >= cutoff)
        .order_by(TrainingLoad.load_date.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "load_date": r.load_date.isoformat(),
            "ctl": float(r.ctl) if r.ctl else 0.0,
            "atl": float(r.atl) if r.atl else 0.0,
            "tsb": float(r.tsb) if r.tsb else 0.0,
            "daily_tss": float(r.daily_tss) if r.daily_tss else 0.0,
            "weekly_tss": float(r.weekly_tss) if r.weekly_tss else 0.0,
        }
        for r in rows
    ]
