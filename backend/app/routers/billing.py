"""
Billing endpoints.

GET  /api/billing/plan             — current subscription status + plan details
GET  /api/billing/plans            — list all available plans
POST /api/billing/checkout/{plan}  — create Stripe Checkout Session → redirect URL
POST /api/billing/portal           — create Stripe Customer Portal session → redirect URL
POST /api/billing/webhook          — Stripe webhook receiver (HMAC verified)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.models.subscription import Subscription, WebhookEvent
from app.services.billing_service import (
    PLANS,
    check_athlete_limit,
    create_checkout_session,
    create_portal_session,
    get_or_create_subscription,
    handle_checkout_completed,
    handle_invoice_paid,
    handle_payment_failed,
    handle_subscription_deleted,
    handle_subscription_updated,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Current plan ──────────────────────────────────────────────────────────────

@router.get("/plan")
async def get_current_plan(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    sub = await get_or_create_subscription(db, str(admin.id))
    can_add, current_count, limit = await check_athlete_limit(db, str(admin.id))
    plan_info = PLANS.get(sub.plan, PLANS["trial"])

    return {
        "plan": sub.plan,
        "label": plan_info["label"],
        "status": sub.status,
        "athlete_limit": sub.athlete_limit,
        "athlete_count": current_count,
        "can_add_athlete": can_add,
        "price_brl": plan_info["price_brl"],
        "description": plan_info["description"],
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "stripe_customer_id": sub.stripe_customer_id,
    }


# ── Plans catalogue ───────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans():
    return [
        {
            "key": key,
            "label": info["label"],
            "athlete_limit": info["athlete_limit"],
            "price_brl": info["price_brl"],
            "description": info["description"],
            "purchasable": info["stripe_price_id"] is not None,
        }
        for key, info in PLANS.items()
        if key != "trial"
    ]


# ── Checkout ──────────────────────────────────────────────────────────────────

@router.post("/checkout/{plan}")
async def checkout(
    plan: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if plan not in PLANS or PLANS[plan]["stripe_price_id"] is None:
        raise HTTPException(status_code=400, detail=f"Plano '{plan}' inválido ou não disponível para compra")

    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Pagamentos não configurados neste ambiente")

    try:
        url = await create_checkout_session(db, admin, plan)
        return {"checkout_url": url}
    except Exception as exc:
        logger.exception("Checkout session creation failed for admin %s: %s", admin.id, exc)
        raise HTTPException(status_code=500, detail="Erro ao criar sessão de pagamento")


# ── Customer Portal ───────────────────────────────────────────────────────────

@router.post("/portal")
async def billing_portal(
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        url = await create_portal_session(db, str(admin.id))
        return {"portal_url": url}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Portal session failed for admin %s: %s", admin.id, exc)
        raise HTTPException(status_code=500, detail="Erro ao abrir portal de billing")


# ── Stripe Webhook ────────────────────────────────────────────────────────────

@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # Verify HMAC signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook error: {exc}")

    event_id = event["id"]
    event_type = event["type"]

    # Idempotency check — skip if already processed
    existing = await db.execute(
        select(WebhookEvent).where(
            WebhookEvent.provider == "stripe",
            WebhookEvent.event_id == event_id,
            WebhookEvent.processed_at != None,
        )
    )
    if existing.scalar_one_or_none():
        logger.info("Stripe webhook %s already processed — skipping", event_id)
        return

    # Record the event
    webhook_record = WebhookEvent(
        provider="stripe",
        event_id=event_id,
        event_type=event_type,
        payload=event.to_dict(),
    )
    db.add(webhook_record)
    await db.flush()

    try:
        handlers = {
            "checkout.session.completed":       handle_checkout_completed,
            "invoice.paid":                     handle_invoice_paid,
            "customer.subscription.updated":    handle_subscription_updated,
            "customer.subscription.deleted":    handle_subscription_deleted,
            "invoice.payment_failed":           handle_payment_failed,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(db, event["data"])
            logger.info("Handled Stripe event %s (%s)", event_type, event_id)
        else:
            logger.debug("Unhandled Stripe event type: %s", event_type)

        webhook_record.processed_at = datetime.now(timezone.utc)
    except Exception as exc:
        webhook_record.error = str(exc)
        logger.exception("Error processing Stripe event %s: %s", event_id, exc)

    await db.commit()
