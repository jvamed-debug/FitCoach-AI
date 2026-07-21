"""
TrainingPeaks sync orchestration.
  - push_recommendation: send AI plan → TP calendar → auto-syncs to Garmin
  - sync_completed_workouts: poll TP for executed workouts → import to DB
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete, PlatformConnection
from app.models.recommendation import AIRecommendation
from app.models.workout import Workout
from app.services.tp_service import TrainingPeaksService
from app.services.training_load import recalculate_athlete_load
from app.utils.crypto import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)
_tp = TrainingPeaksService()


async def _get_valid_tp_token(db: AsyncSession, connection: PlatformConnection) -> str | None:
    """Refresh TP token if needed and return valid access token."""
    from datetime import timezone as _tz
    now = datetime.now(_tz.utc)
    expires_at = connection.token_expires_at

    needs_refresh = expires_at is None or (
        expires_at.replace(tzinfo=_tz.utc) - now < timedelta(minutes=5)
    )

    if needs_refresh and connection.refresh_token_enc:
        try:
            refresh_token = decrypt_token(connection.refresh_token_enc)
            new_tokens = await _tp.refresh_access_token(refresh_token)
            expires_in = new_tokens.get("expires_in", 3600)

            connection.access_token_enc = encrypt_token(new_tokens["access_token"])
            connection.refresh_token_enc = encrypt_token(new_tokens["refresh_token"])
            connection.token_expires_at = now + timedelta(seconds=expires_in)
            connection.consecutive_failures = 0
            connection.sync_error = None
            db.add(connection)
            await db.commit()
            return new_tokens["access_token"]
        except Exception as e:
            connection.consecutive_failures = (connection.consecutive_failures or 0) + 1
            connection.sync_error = str(e)[:255]
            if connection.consecutive_failures >= 3:
                connection.is_active = False
            db.add(connection)
            await db.commit()
            return None

    if connection.access_token_enc:
        return decrypt_token(connection.access_token_enc)
    return None


async def push_recommendation_to_trainingpeaks(
    db: AsyncSession,
    athlete_id: str,
    recommendation_id: str,
) -> dict | None:
    """
    Push an AI recommendation as a planned workout to TrainingPeaks.
    Returns TP workout dict on success, None if TP not connected or error.
    """
    # Get TP connection
    conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete_id,
            PlatformConnection.provider == "trainingpeaks",
            PlatformConnection.is_active == True,
        )
    )
    conn = conn_result.scalar_one_or_none()
    if not conn:
        logger.info("No active TrainingPeaks connection for athlete %s", athlete_id)
        return None

    access_token = await _get_valid_tp_token(db, conn)
    if not access_token:
        return None

    # Load recommendation
    rec_result = await db.execute(
        select(AIRecommendation).where(AIRecommendation.id == recommendation_id)
    )
    rec = rec_result.scalar_one_or_none()
    if not rec:
        return None

    # Get TP athlete ID
    tp_athlete_id = conn.provider_athlete_id
    if not tp_athlete_id:
        try:
            tp_profile = await _tp.get_athlete(access_token)
            tp_athlete_id = str(tp_profile.get("athleteId") or tp_profile.get("id", ""))
            conn.provider_athlete_id = tp_athlete_id
            db.add(conn)
            await db.commit()
        except Exception as e:
            logger.warning("Could not fetch TP athlete profile: %s", e)
            return None

    # Build TP workout payload
    plan = rec.structured_plan or {}
    tp_workout = _tp.recommendation_to_tp_workout(
        rec_date=rec.recommendation_date,
        workout_type=rec.workout_type or "rest",
        title=rec.title or "AI Recommended Workout",
        structured_plan=plan,
        duration_minutes=plan.get("duration_minutes"),
    )
    tp_workout["athleteId"] = tp_athlete_id

    try:
        result = await _tp.create_planned_workout(access_token, tp_athlete_id, tp_workout)
        logger.info("Pushed recommendation %s to TrainingPeaks for athlete %s", recommendation_id, athlete_id)

        # Update last_sync_at
        conn.last_sync_at = datetime.now(timezone.utc)
        db.add(conn)
        await db.commit()

        return result
    except Exception as e:
        logger.exception("Failed to push recommendation to TP: %s", e)
        return None


async def sync_completed_workouts_from_tp(
    db: AsyncSession,
    athlete_id: str,
    days_back: int = 3,
) -> list[str]:
    """
    Poll TrainingPeaks for completed workouts and import them.
    Returns list of new workout IDs created.
    """
    conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete_id,
            PlatformConnection.provider == "trainingpeaks",
            PlatformConnection.is_active == True,
        )
    )
    conn = conn_result.scalar_one_or_none()
    if not conn:
        return []

    access_token = await _get_valid_tp_token(db, conn)
    if not access_token:
        return []

    tp_athlete_id = conn.provider_athlete_id
    if not tp_athlete_id:
        return []

    athlete_result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = athlete_result.scalar_one_or_none()

    from_date = date.today() - timedelta(days=days_back)

    try:
        workouts = await _tp.get_completed_workouts(access_token, tp_athlete_id, from_date)
    except Exception as e:
        logger.exception("Failed to fetch TP workouts: %s", e)
        return []

    imported: list[str] = []
    for tp_wkt in workouts:
        if not tp_wkt.get("completedAt") and not tp_wkt.get("completed"):
            continue  # skip planned-only

        ext_id = f"tp_{tp_wkt.get('id', '')}"
        exists = await db.execute(
            select(Workout).where(
                Workout.athlete_id == athlete_id,
                Workout.external_id == ext_id,
            )
        )
        if exists.scalar_one_or_none():
            continue

        wkt_data = _tp.parse_tp_workout(
            tp_wkt, athlete_id,
            ftp=athlete.ftp_watts if athlete else None,
            max_hr=athlete.max_hr if athlete else None,
            resting_hr=athlete.resting_hr if athlete else None,
        )
        workout = Workout(**wkt_data)
        db.add(workout)
        await db.flush()
        imported.append(str(workout.id))

    if imported:
        await db.commit()
        await recalculate_athlete_load(db, athlete_id, 90)
        conn.last_sync_at = datetime.now(timezone.utc)
        db.add(conn)
        await db.commit()
        logger.info("TP sync: %d new workouts for athlete %s", len(imported), athlete_id)

    return imported
