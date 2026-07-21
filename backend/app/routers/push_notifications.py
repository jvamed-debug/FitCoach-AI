"""
Push Notification endpoints (Web Push / VAPID).

GET  /api/push/vapid-key         — return public VAPID key to browser
POST /api/push/subscribe         — save push subscription for authenticated athlete
POST /api/push/unsubscribe       — remove push subscription
POST /api/push/test              — send a test push to authenticated athlete

Subscriptions are stored in the athlete's row as JSONB (push_subscriptions).
The scheduler calls send_push_to_athlete() for daily metric reminders.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_athlete
from app.models.athlete import Athlete

router = APIRouter()
logger = logging.getLogger(__name__)

_PUSH_AVAILABLE = bool(settings.vapid_private_key and settings.vapid_public_key)


def _webpush(subscription_info: dict, data: dict) -> None:
    """Send a Web Push notification. Raises on failure."""
    if not _PUSH_AVAILABLE:
        raise RuntimeError("VAPID keys not configured")
    from pywebpush import webpush, WebPushException
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(data),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={
                "sub": settings.vapid_subject,
            },
        )
    except WebPushException as exc:
        raise RuntimeError(f"WebPush failed: {exc}") from exc


# ── Schemas ───────────────────────────────────────────────────────────────────

class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: PushKeys
    expirationTime: Any = None


class UnsubscribeIn(BaseModel):
    endpoint: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/vapid-key")
async def vapid_key():
    if not _PUSH_AVAILABLE:
        raise HTTPException(status_code=503, detail="Push notifications not configured")
    return {"vapid_public_key": settings.vapid_public_key}


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    body: PushSubscriptionIn,
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    """Store push subscription endpoint for this athlete (upsert by endpoint)."""
    # Subscriptions stored as JSON array in athletes.push_subscriptions (added via migration)
    # Fallback: store in a simple text column or skip if column doesn't exist
    try:
        new_sub = {
            "endpoint": body.endpoint,
            "keys": {"p256dh": body.keys.p256dh, "auth": body.keys.auth},
        }
        # Use raw SQL to upsert into a JSONB column (push_subscriptions) that may not exist yet
        await db.execute(
            text("""
                UPDATE athletes
                SET push_subscriptions = COALESCE(
                    (
                        SELECT jsonb_agg(s)
                        FROM jsonb_array_elements(
                            COALESCE(push_subscriptions, '[]'::jsonb)
                        ) s
                        WHERE s->>'endpoint' != :endpoint
                    ), '[]'::jsonb
                ) || :sub::jsonb
                WHERE id = :athlete_id
            """),
            {
                "endpoint": body.endpoint,
                "sub": json.dumps(new_sub),
                "athlete_id": str(athlete.id),
            },
        )
        await db.commit()
        logger.info("Push subscription saved for athlete %s", athlete.id)
    except Exception as exc:
        logger.warning("Could not save push subscription (column may not exist yet): %s", exc)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    body: UnsubscribeIn,
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    try:
        await db.execute(
            text("""
                UPDATE athletes
                SET push_subscriptions = COALESCE(
                    (
                        SELECT jsonb_agg(s)
                        FROM jsonb_array_elements(
                            COALESCE(push_subscriptions, '[]'::jsonb)
                        ) s
                        WHERE s->>'endpoint' != :endpoint
                    ), '[]'::jsonb
                )
                WHERE id = :athlete_id
            """),
            {"endpoint": body.endpoint, "athlete_id": str(athlete.id)},
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Could not remove push subscription: %s", exc)


@router.post("/test", status_code=status.HTTP_204_NO_CONTENT)
async def send_test_push(
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    if not _PUSH_AVAILABLE:
        raise HTTPException(status_code=503, detail="Push notifications not configured")
    sent = await send_push_to_athlete(
        db,
        str(athlete.id),
        title="FitCoach AI",
        body="Notificação de teste! Push funcionando corretamente. 🎉",
        url="/dashboard",
        tag="test",
    )
    if not sent:
        raise HTTPException(status_code=422, detail="Nenhuma subscription ativa encontrada.")


# ── Shared sender (used by scheduler) ────────────────────────────────────────

async def send_push_to_athlete(
    db: AsyncSession,
    athlete_id: str,
    title: str,
    body: str,
    url: str = "/dashboard",
    tag: str = "fitcoach",
) -> int:
    """
    Send push notification to all active subscriptions of an athlete.
    Returns the number of successful sends.
    """
    if not _PUSH_AVAILABLE:
        return 0

    try:
        result = await db.execute(
            text("SELECT push_subscriptions FROM athletes WHERE id = :id"),
            {"id": athlete_id},
        )
        row = result.fetchone()
        if not row or not row[0]:
            return 0

        subscriptions = row[0] if isinstance(row[0], list) else json.loads(row[0])
    except Exception as exc:
        logger.warning("Could not fetch push subscriptions for athlete %s: %s", athlete_id, exc)
        return 0

    payload = {"title": title, "body": body, "url": url, "tag": tag}
    sent = 0
    stale_endpoints = []

    for sub in subscriptions:
        try:
            _webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": sub["keys"],
                },
                data=payload,
            )
            sent += 1
        except RuntimeError as exc:
            err_str = str(exc)
            if "410" in err_str or "404" in err_str:
                stale_endpoints.append(sub["endpoint"])
            else:
                logger.warning("Push send failed for athlete %s: %s", athlete_id, exc)

    # Clean up expired subscriptions
    if stale_endpoints:
        for endpoint in stale_endpoints:
            try:
                await db.execute(
                    text("""
                        UPDATE athletes
                        SET push_subscriptions = COALESCE(
                            (SELECT jsonb_agg(s) FROM jsonb_array_elements(
                                COALESCE(push_subscriptions, '[]'::jsonb)) s
                             WHERE s->>'endpoint' != :endpoint), '[]'::jsonb)
                        WHERE id = :id
                    """),
                    {"endpoint": endpoint, "id": athlete_id},
                )
            except Exception:
                pass
        await db.commit()

    return sent
