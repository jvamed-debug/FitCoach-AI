"""
Billing service — Stripe integration.

Plans:
  trial    — 3 athletes,   free (14-day automatic trial on signup)
  starter  — 5 athletes,   R$149/mo  (Stripe price ID: STARTER_PRICE_ID)
  pro      — 20 athletes,  R$299/mo  (Stripe price ID: PRO_PRICE_ID)
  elite    — unlimited,    R$499/mo  (Stripe price ID: ELITE_PRICE_ID)

Flows:
  1. Admin signs up → trial subscription created (no Stripe customer yet)
  2. Admin clicks upgrade → create_checkout_session() → Stripe Checkout
  3. Checkout completes → webhook `checkout.session.completed` → upsert subscription
  4. Invoice paid monthly → webhook `invoice.paid` → extend current_period_end
  5. Subscription canceled → webhook `customer.subscription.deleted` → status=canceled
  6. Admin clicks "Manage billing" → create_portal_session() → Stripe Customer Portal
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.admin import AdminUser
from app.models.athlete import Athlete
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key

# ── Plan catalogue ────────────────────────────────────────────────────────────

PLANS: dict[str, dict] = {
    "trial": {
        "label": "Trial",
        "athlete_limit": 3,
        "price_brl": 0,
        "description": "Teste grátis por 14 dias",
        "stripe_price_id": None,
    },
    "starter": {
        "label": "Starter",
        "athlete_limit": 5,
        "price_brl": 149,
        "description": "Até 5 atletas ativos",
        "stripe_price_id": settings.stripe_price_starter,
    },
    "pro": {
        "label": "Pro",
        "athlete_limit": 20,
        "price_brl": 299,
        "description": "Até 20 atletas ativos",
        "stripe_price_id": settings.stripe_price_pro,
    },
    "elite": {
        "label": "Elite",
        "athlete_limit": 999_999,
        "price_brl": 499,
        "description": "Atletas ilimitados",
        "stripe_price_id": settings.stripe_price_elite,
    },
}


# ── Subscription helpers ──────────────────────────────────────────────────────

async def get_or_create_subscription(db: AsyncSession, admin_id: str) -> Subscription:
    """Return the admin's subscription, creating a trial one if it doesn't exist."""
    result = await db.execute(
        select(Subscription).where(Subscription.admin_id == admin_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        return sub

    sub = Subscription(
        admin_id=admin_id,
        plan="trial",
        status="trialing",
        athlete_limit=PLANS["trial"]["athlete_limit"],
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def get_active_athlete_count(db: AsyncSession, admin_id: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(Athlete).where(
            Athlete.admin_id == admin_id,
            Athlete.is_active == True,
        )
    )
    return result.scalar() or 0


async def check_athlete_limit(db: AsyncSession, admin_id: str) -> tuple[bool, int, int]:
    """
    Returns (can_add, current_count, limit).
    Raises nothing — callers decide how to handle.
    """
    sub = await get_or_create_subscription(db, admin_id)
    current = await get_active_athlete_count(db, admin_id)
    limit = sub.athlete_limit
    return current < limit, current, limit


# ── Stripe Checkout ───────────────────────────────────────────────────────────

async def create_checkout_session(
    db: AsyncSession,
    admin: AdminUser,
    plan: str,
) -> str:
    """
    Creates a Stripe Checkout Session for the given plan.
    Returns the session URL to redirect the admin to.
    """
    plan_info = PLANS.get(plan)
    if not plan_info or not plan_info["stripe_price_id"]:
        raise ValueError(f"Plan '{plan}' is not purchasable")

    sub = await get_or_create_subscription(db, str(admin.id))

    # Retrieve or create Stripe customer
    if sub.stripe_customer_id:
        customer_id = sub.stripe_customer_id
    else:
        customer = stripe.Customer.create(
            email=admin.email,
            name=admin.name,
            metadata={"admin_id": str(admin.id)},
        )
        customer_id = customer.id
        sub.stripe_customer_id = customer_id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": plan_info["stripe_price_id"], "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.frontend_url}/billing?success=1&plan={plan}",
        cancel_url=f"{settings.frontend_url}/billing?canceled=1",
        metadata={"admin_id": str(admin.id), "plan": plan},
        subscription_data={
            "metadata": {"admin_id": str(admin.id), "plan": plan},
        },
    )
    return session.url


# ── Stripe Customer Portal ────────────────────────────────────────────────────

async def create_portal_session(db: AsyncSession, admin_id: str) -> str:
    """Returns the URL to Stripe's billing portal for managing the subscription."""
    sub = await get_or_create_subscription(db, admin_id)
    if not sub.stripe_customer_id:
        raise ValueError("No Stripe customer associated with this admin")

    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
    return session.url


# ── Webhook handlers ──────────────────────────────────────────────────────────

async def handle_checkout_completed(db: AsyncSession, event_data: dict) -> None:
    """checkout.session.completed → activate subscription."""
    session = event_data["object"]
    admin_id = session.get("metadata", {}).get("admin_id")
    plan = session.get("metadata", {}).get("plan", "starter")
    customer_id = session.get("customer")
    stripe_sub_id = session.get("subscription")

    if not admin_id:
        logger.warning("checkout.session.completed missing admin_id metadata")
        return

    # Fetch subscription period from Stripe
    period_end = None
    if stripe_sub_id:
        try:
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
            period_end = datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc)
        except Exception as exc:
            logger.warning("Could not fetch Stripe subscription %s: %s", stripe_sub_id, exc)

    result = await db.execute(select(Subscription).where(Subscription.admin_id == admin_id))
    sub = result.scalar_one_or_none()
    if not sub:
        sub = Subscription(admin_id=admin_id)
        db.add(sub)

    plan_info = PLANS.get(plan, PLANS["starter"])
    sub.plan = plan
    sub.status = "active"
    sub.stripe_customer_id = customer_id
    sub.stripe_subscription_id = stripe_sub_id
    sub.athlete_limit = plan_info["athlete_limit"]
    sub.current_period_start = datetime.now(timezone.utc)
    sub.current_period_end = period_end
    await db.commit()
    logger.info("Subscription activated for admin %s (plan=%s)", admin_id, plan)


async def handle_invoice_paid(db: AsyncSession, event_data: dict) -> None:
    """invoice.paid → renew current_period_end."""
    invoice = event_data["object"]
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    # Fetch updated period from Stripe
    try:
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        sub.current_period_end = datetime.fromtimestamp(
            stripe_sub["current_period_end"], tz=timezone.utc
        )
        sub.status = "active"
        await db.commit()
        logger.info("Subscription renewed for admin %s until %s", sub.admin_id, sub.current_period_end)
    except Exception as exc:
        logger.warning("Could not renew subscription %s: %s", stripe_sub_id, exc)


async def handle_subscription_updated(db: AsyncSession, event_data: dict) -> None:
    """customer.subscription.updated → sync status and plan."""
    stripe_sub = event_data["object"]
    stripe_sub_id = stripe_sub.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    sub.status = stripe_sub.get("status", sub.status)
    plan_key = stripe_sub.get("metadata", {}).get("plan", sub.plan)
    plan_info = PLANS.get(plan_key, PLANS[sub.plan])
    sub.plan = plan_key
    sub.athlete_limit = plan_info["athlete_limit"]
    await db.commit()


async def handle_subscription_deleted(db: AsyncSession, event_data: dict) -> None:
    """customer.subscription.deleted → mark as canceled."""
    stripe_sub = event_data["object"]
    stripe_sub_id = stripe_sub.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    sub.status = "canceled"
    sub.plan = "trial"
    sub.athlete_limit = PLANS["trial"]["athlete_limit"]
    await db.commit()
    logger.info("Subscription canceled for admin %s", sub.admin_id)


async def handle_payment_failed(db: AsyncSession, event_data: dict) -> None:
    """invoice.payment_failed → set status to past_due."""
    invoice = event_data["object"]
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return

    sub.status = "past_due"
    await db.commit()
    logger.warning("Payment failed for subscription %s (admin %s)", stripe_sub_id, sub.admin_id)
