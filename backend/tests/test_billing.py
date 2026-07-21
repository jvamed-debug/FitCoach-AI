"""
Tests for billing service: plan limits, subscription creation, athlete enforcement.
"""

import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.models.athlete import Athlete
from app.models.subscription import Subscription
from app.services.billing_service import (
    PLANS,
    check_athlete_limit,
    get_or_create_subscription,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> AdminUser:
    admin = AdminUser(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Coach Test",
        email="coach@test.com",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


async def _add_athletes(db: AsyncSession, admin_id, count: int) -> list[Athlete]:
    athletes = []
    for i in range(count):
        a = Athlete(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            admin_id=admin_id,
            name=f"Athlete {i}",
            email=f"athlete{i}@test.com",
            is_active=True,
        )
        db.add(a)
        athletes.append(a)
    await db.commit()
    return athletes


# ── Tests: plan catalogue ─────────────────────────────────────────────────────

def test_plan_catalogue_completeness():
    """All required plans exist with correct fields."""
    for key in ("trial", "starter", "pro", "elite"):
        assert key in PLANS
        p = PLANS[key]
        assert "athlete_limit" in p
        assert "price_brl" in p
        assert p["athlete_limit"] > 0


def test_trial_plan_is_free():
    assert PLANS["trial"]["price_brl"] == 0


def test_elite_plan_is_unlimited():
    assert PLANS["elite"]["athlete_limit"] >= 999_999


def test_plan_limits_ascending():
    limits = [PLANS[k]["athlete_limit"] for k in ("trial", "starter", "pro")]
    assert limits == sorted(limits), "Plans should have ascending athlete limits"


# ── Tests: subscription creation ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_or_create_subscription_creates_trial(db_session: AsyncSession, admin_user: AdminUser):
    """First call creates a trial subscription."""
    sub = await get_or_create_subscription(db_session, str(admin_user.id))
    assert sub.plan == "trial"
    assert sub.status == "trialing"
    assert sub.athlete_limit == PLANS["trial"]["athlete_limit"]


@pytest.mark.asyncio
async def test_get_or_create_subscription_idempotent(db_session: AsyncSession, admin_user: AdminUser):
    """Calling twice returns the same subscription without duplication."""
    sub1 = await get_or_create_subscription(db_session, str(admin_user.id))
    sub2 = await get_or_create_subscription(db_session, str(admin_user.id))
    assert sub1.id == sub2.id


# ── Tests: athlete limit enforcement ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_athlete_limit_within_trial(db_session: AsyncSession, admin_user: AdminUser):
    """Trial plan: 0 of 3 athletes used → can add."""
    can_add, count, limit = await check_athlete_limit(db_session, str(admin_user.id))
    assert can_add is True
    assert count == 0
    assert limit == PLANS["trial"]["athlete_limit"]


@pytest.mark.asyncio
async def test_check_athlete_limit_at_trial_cap(db_session: AsyncSession, admin_user: AdminUser):
    """Trial plan: fills all 3 slots → cannot add."""
    await _add_athletes(db_session, admin_user.id, PLANS["trial"]["athlete_limit"])
    can_add, count, limit = await check_athlete_limit(db_session, str(admin_user.id))
    assert can_add is False
    assert count == limit


@pytest.mark.asyncio
async def test_check_athlete_limit_after_upgrade(db_session: AsyncSession, admin_user: AdminUser):
    """Upgrading the subscription raises the athlete limit."""
    trial_limit = PLANS["trial"]["athlete_limit"]
    await _add_athletes(db_session, admin_user.id, trial_limit)

    # Simulate upgrade to starter
    sub = await get_or_create_subscription(db_session, str(admin_user.id))
    sub.plan = "starter"
    sub.status = "active"
    sub.athlete_limit = PLANS["starter"]["athlete_limit"]
    await db_session.commit()

    can_add, count, limit = await check_athlete_limit(db_session, str(admin_user.id))
    assert can_add is True
    assert limit == PLANS["starter"]["athlete_limit"]


@pytest.mark.asyncio
async def test_inactive_athletes_not_counted(db_session: AsyncSession, admin_user: AdminUser):
    """Inactive athletes do not count against the limit."""
    trial_limit = PLANS["trial"]["athlete_limit"]
    athletes = await _add_athletes(db_session, admin_user.id, trial_limit)

    # Deactivate all
    for a in athletes:
        a.is_active = False
    await db_session.commit()

    can_add, count, limit = await check_athlete_limit(db_session, str(admin_user.id))
    assert can_add is True
    assert count == 0


# ── Tests: API enforcement (via HTTP client) ──────────────────────────────────

@pytest.mark.asyncio
async def test_create_athlete_blocked_at_limit(client, db_session: AsyncSession, admin_user: AdminUser):
    """POST /api/admin/athletes returns 402 when athlete limit is reached."""
    from tests.conftest import make_jwt
    token = make_jwt(str(admin_user.user_id))

    # Fill trial limit
    await _add_athletes(db_session, admin_user.id, PLANS["trial"]["athlete_limit"])

    resp = await client.post(
        "/api/admin/athletes",
        json={
            "name": "Extra Athlete",
            "email": "extra@test.com",
            "sport_modalities": ["cycling"],
            "primary_modality": "cycling",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 402
    assert "Limite de atletas" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_athlete_allowed_within_limit(client, db_session: AsyncSession, admin_user: AdminUser):
    """POST /api/admin/athletes succeeds when under the athlete limit."""
    from tests.conftest import make_jwt
    from unittest.mock import patch as mock_patch

    token = make_jwt(str(admin_user.user_id))

    with mock_patch("app.services.email_service.send_athlete_invite", return_value=True):
        resp = await client.post(
            "/api/admin/athletes",
            json={
                "name": "First Athlete",
                "email": "first@test.com",
                "sport_modalities": ["cycling"],
                "primary_modality": "cycling",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201
