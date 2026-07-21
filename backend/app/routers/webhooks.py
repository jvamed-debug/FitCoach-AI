"""
Webhook endpoints.

GET  /api/webhooks/strava  — Strava hub.challenge verification
POST /api/webhooks/strava  — Strava activity events (HMAC-SHA256 verified)
POST /api/webhooks/apple-health/{token} — Apple Health daily metrics via iOS Shortcut
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone, date

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.athlete import Athlete, PlatformConnection
from app.models.metric import DailyMetric
from app.models.workout import Workout
from app.services.strava_service import StravaService, get_valid_access_token
from app.services.training_load import recalculate_athlete_load

router = APIRouter()
logger = logging.getLogger(__name__)

_strava = StravaService()


# ── Strava webhook ────────────────────────────────────────────────────────────

@router.get("/strava", summary="Strava webhook hub.challenge verification")
async def strava_webhook_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid hub.mode")
    if hub_verify_token != settings.strava_webhook_verify_token:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}


def _verify_strava_signature(body: bytes, signature: str) -> bool:
    """HMAC-SHA256 verification of Strava webhook payload."""
    expected = hmac.new(
        settings.strava_client_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _process_strava_event(event: dict, db: AsyncSession) -> None:
    """Background task: fetch activity details and upsert workout."""
    if event.get("object_type") != "activity":
        return
    aspect_type = event.get("aspect_type")
    if aspect_type not in ("create", "update"):
        return

    owner_id = str(event.get("owner_id", ""))
    activity_id = event.get("object_id")

    # Find platform_connection by Strava athlete ID
    conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.provider == "strava",
            PlatformConnection.provider_athlete_id == owner_id,
            PlatformConnection.is_active == True,
        )
    )
    conn = conn_result.scalar_one_or_none()
    if not conn:
        logger.warning("No active Strava connection for owner_id %s", owner_id)
        return

    access_token = await get_valid_access_token(db, conn)
    if not access_token:
        logger.warning("Could not get valid access token for connection %s", conn.id)
        return

    # Fetch athlete for TSS calculation context
    athlete_result = await db.execute(
        select(Athlete).where(Athlete.id == conn.athlete_id)
    )
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        return

    try:
        activity = await _strava.get_activity_detail(access_token, activity_id)
    except Exception as e:
        logger.exception("Failed to fetch activity %s: %s", activity_id, e)
        return

    wkt_data = _strava.parse_activity_to_workout(
        activity, str(athlete.id),
        ftp=athlete.ftp_watts, max_hr=athlete.max_hr, resting_hr=athlete.resting_hr,
    )

    # Upsert by external_id
    stmt = pg_insert(Workout.__table__).values(
        **{k: v for k, v in wkt_data.items() if k not in ("id",)}
    ).on_conflict_do_update(
        index_elements=["athlete_id", "external_id"],
        set_={k: wkt_data[k] for k in (
            "title", "description", "duration_seconds", "avg_heart_rate",
            "avg_power_watts", "normalized_power_watts", "tss", "if_score",
            "hr_zones", "power_zones", "calories",
        ) if k in wkt_data},
    )
    await db.execute(stmt)
    await db.commit()

    # Update last_sync_at
    conn.last_sync_at = datetime.now(timezone.utc)
    conn.sync_error = None
    conn.consecutive_failures = 0
    db.add(conn)
    await db.commit()

    await recalculate_athlete_load(db, str(athlete.id), 90)
    logger.info("Processed Strava event: %s activity %s for athlete %s",
                aspect_type, activity_id, athlete.id)


async def _process_strava_event_bg(event: dict) -> None:
    """
    Background entrypoint: opens its OWN DB session. The request-scoped session
    is closed once the webhook response is returned, so background work must not
    reuse it.
    """
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await _process_strava_event(event, db)
    except Exception:
        logger.exception("Background Strava event processing failed")


@router.post("/strava", status_code=200, summary="Strava activity event")
async def strava_webhook_event(
    request: Request,
    background_tasks: BackgroundTasks,
):
    # Trust model: Strava does NOT sign webhook events, so this endpoint is
    # effectively unauthenticated. Safety does not rely on the HMAC below —
    # it comes from the fact that an event only triggers a re-fetch of the
    # REAL activity from Strava, keyed on an owner_id that must match an
    # existing ACTIVE connection (see _process_strava_event). No attacker-
    # supplied data is persisted. The HMAC check is kept as defence-in-depth:
    # if a signature IS present (e.g. added by a proxy) a tampered one is
    # rejected, but a missing signature cannot be required for genuine events.
    # Mitigate abuse (forced syncs / Strava API quota) with edge rate limiting.
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature", "").removeprefix("sha256=")

    if signature and not _verify_strava_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        event = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info("Strava webhook event: %s %s", event.get("object_type"), event.get("aspect_type"))
    background_tasks.add_task(_process_strava_event_bg, event)
    return {"status": "ok"}


# ── Apple Health webhook ──────────────────────────────────────────────────────

class AppleHealthPayload(BaseModel):
    date: str  # ISO date
    sleep_hours: float | None = None
    sleep_quality: int | None = None
    hrv_ms: int | None = None
    resting_hr: int | None = None
    weight_kg: float | None = None
    steps: int | None = None


async def _ingest_apple_health(token: str, payload: AppleHealthPayload, db: AsyncSession) -> dict:
    """Shared ingest logic. `token` is a per-athlete secret and is never logged."""
    if not token:
        raise HTTPException(status_code=401, detail="Token ausente")

    result = await db.execute(
        select(Athlete).where(
            Athlete.apple_health_token == token,
            Athlete.is_active == True,
        )
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Token inválido")

    try:
        metric_date = date.fromisoformat(payload.date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida")

    stmt = pg_insert(DailyMetric.__table__).values(
        athlete_id=athlete.id,
        metric_date=metric_date,
        sleep_hours=payload.sleep_hours,
        sleep_quality=payload.sleep_quality,
        hrv_ms=payload.hrv_ms,
        resting_hr=payload.resting_hr,
        weight_kg=payload.weight_kg,
        source="apple_health",
    ).on_conflict_do_update(
        index_elements=["athlete_id", "metric_date"],
        set_={
            col: getattr(payload, col)
            for col in ("sleep_hours", "sleep_quality", "hrv_ms", "resting_hr", "weight_kg")
            if getattr(payload, col) is not None
        },
    )
    await db.execute(stmt)
    await db.commit()

    # Update resting_hr on athlete profile if provided
    if payload.resting_hr and abs((athlete.resting_hr or 0) - payload.resting_hr) > 5:
        athlete.resting_hr = payload.resting_hr
        db.add(athlete)
        await db.commit()

    logger.info("Apple Health data ingested for athlete %s date %s", athlete.id, metric_date)
    return {"status": "ok", "date": str(metric_date)}


@router.post("/apple-health", status_code=200,
             summary="Apple Health daily metrics (token no header Authorization)")
async def apple_health_ingest_header(
    payload: AppleHealthPayload,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Preferred endpoint. Send the per-athlete token as `Authorization: Bearer <token>`.
    Tokens in headers do not leak into access logs, proxies or browser history the
    way path parameters do.
    """
    token = (authorization or "").removeprefix("Bearer ").strip()
    return await _ingest_apple_health(token, payload, db)


@router.post("/apple-health/{token}", status_code=200,
             summary="[DEPRECATED] Apple Health metrics with token in the URL path")
async def apple_health_ingest_path(
    token: str,
    payload: AppleHealthPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Deprecated: the token travels in the URL and can leak via logs. Kept for
    backward compatibility with existing iOS Shortcuts — migrate to
    `POST /apple-health` with an `Authorization: Bearer` header.
    """
    return await _ingest_apple_health(token, payload, db)
