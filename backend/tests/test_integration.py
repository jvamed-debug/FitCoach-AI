"""
Integration tests — end-to-end flows through the full API stack.

Each test uses the in-memory SQLite DB and HTTPX async client (no real Supabase/Stripe/AI calls).
External services (Supabase Auth, Stripe, Anthropic, Resend) are patched.

Flows tested:
  1. Health check
  2. Admin creates athlete → invite email sent
  3. Athlete limit enforcement (402 on over-limit)
  4. Alert service creates overreaching alert when TSB < -25
  5. Training load calculation round-trip
  6. Billing plan auto-creation for new admin
"""

import uuid
from datetime import date, datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.models.athlete import Athlete
from app.models.training_load import TrainingLoad
from app.models.lgpd import LGPDConsent
from app.services.billing_service import PLANS
from tests.conftest import make_jwt


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create_admin(db: AsyncSession) -> AdminUser:
    admin = AdminUser(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Coach Integration",
        email="coach-int@test.com",
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def _create_athlete_with_consent(db: AsyncSession, admin: AdminUser) -> Athlete:
    athlete = Athlete(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        admin_id=admin.id,
        name="Athlete Int",
        email="athlete-int@test.com",
        is_active=True,
        onboarding_complete=True,
        ftp_watts=250,
        max_hr=185,
        resting_hr=50,
    )
    db.add(athlete)
    consent = LGPDConsent(
        athlete_id=athlete.id,
        consent_version="1.0",
        consented_at=datetime.now(timezone.utc),
        ip_address="127.0.0.1",
    )
    db.add(consent)
    await db.commit()
    await db.refresh(athlete)
    return athlete


# ── Test 1: Health check ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ── Test 2: Admin creates athlete (full API flow) ─────────────────────────────

@pytest.mark.asyncio
async def test_admin_creates_athlete_full_flow(client, db_session: AsyncSession):
    admin = await _create_admin(db_session)
    token = make_jwt(str(admin.user_id))

    with patch("app.services.email_service.send_athlete_invite", return_value=True):
        resp = await client.post(
            "/api/admin/athletes",
            json={
                "name": "New Athlete",
                "email": "new-athlete@test.com",
                "sport_modalities": ["cycling"],
                "primary_modality": "cycling",
                "ftp_watts": 220,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "New Athlete"
    assert body["email"] == "new-athlete@test.com"
    assert "id" in body


# ── Test 3: Duplicate email is rejected ───────────────────────────────────────

@pytest.mark.asyncio
async def test_create_athlete_duplicate_email_rejected(client, db_session: AsyncSession):
    admin = await _create_admin(db_session)
    token = make_jwt(str(admin.user_id))

    with patch("app.services.email_service.send_athlete_invite", return_value=True):
        await client.post(
            "/api/admin/athletes",
            json={"name": "A1", "email": "dup@test.com", "sport_modalities": ["cycling"], "primary_modality": "cycling"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await client.post(
            "/api/admin/athletes",
            json={"name": "A2", "email": "dup@test.com", "sport_modalities": ["running"], "primary_modality": "running"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 409


# ── Test 4: Athlete limit enforced by plan ────────────────────────────────────

@pytest.mark.asyncio
async def test_athlete_limit_enforced(client, db_session: AsyncSession):
    admin = await _create_admin(db_session)
    token = make_jwt(str(admin.user_id))
    trial_limit = PLANS["trial"]["athlete_limit"]

    # Fill up trial slots
    with patch("app.services.email_service.send_athlete_invite", return_value=True):
        for i in range(trial_limit):
            resp = await client.post(
                "/api/admin/athletes",
                json={"name": f"Athlete {i}", "email": f"limit{i}@test.com",
                      "sport_modalities": ["cycling"], "primary_modality": "cycling"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201, f"Expected 201 for athlete {i}, got {resp.status_code}"

        # One more should fail
        over_resp = await client.post(
            "/api/admin/athletes",
            json={"name": "Over Limit", "email": "overlimit@test.com",
                  "sport_modalities": ["cycling"], "primary_modality": "cycling"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert over_resp.status_code == 402


# ── Test 5: Alert service — overreaching detection ───────────────────────────

@pytest.mark.asyncio
async def test_overreaching_alert_created(db_session: AsyncSession):
    from app.services.alert_service import check_overreaching
    from app.models.alert import AdminAlert

    admin = await _create_admin(db_session)
    athlete = await _create_athlete_with_consent(db_session, admin)

    # Insert a critical TSB load
    load = TrainingLoad(
        athlete_id=athlete.id,
        load_date=date.today(),
        ctl=80.0,
        atl=110.0,
        tsb=-30.0,  # below -25 threshold
        daily_tss=0.0,
    )
    db_session.add(load)
    await db_session.commit()

    with patch("app.services.email_service.send_alert_email", return_value=True):
        with patch("asyncio.create_task"):
            alert = await check_overreaching(db_session, athlete, date.today())

    assert alert is not None
    assert alert.alert_type == "overreaching"
    assert alert.severity == "critical"
    assert float(load.tsb) < -25


@pytest.mark.asyncio
async def test_no_alert_when_tsb_normal(db_session: AsyncSession):
    from app.services.alert_service import check_overreaching

    admin = await _create_admin(db_session)
    athlete = await _create_athlete_with_consent(db_session, admin)

    load = TrainingLoad(
        athlete_id=athlete.id,
        load_date=date.today(),
        ctl=60.0,
        atl=65.0,
        tsb=-5.0,  # normal range
        daily_tss=50.0,
    )
    db_session.add(load)
    await db_session.commit()

    alert = await check_overreaching(db_session, athlete, date.today())
    assert alert is None


# ── Test 6: Alert deduplication ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alert_not_duplicated_same_day(db_session: AsyncSession):
    from app.services.alert_service import check_overreaching, create_athlete_alerts
    from app.models.alert import AdminAlert
    from sqlalchemy import select, func

    admin = await _create_admin(db_session)
    athlete = await _create_athlete_with_consent(db_session, admin)

    load = TrainingLoad(
        athlete_id=athlete.id,
        load_date=date.today(),
        ctl=80.0, atl=115.0, tsb=-35.0, daily_tss=0.0,
    )
    db_session.add(load)
    await db_session.commit()

    today = date.today()
    with patch("app.services.email_service.send_alert_email", return_value=True):
        with patch("asyncio.create_task"):
            await check_overreaching(db_session, athlete, today)
            await db_session.commit()
            # Second call should NOT create another alert
            second = await check_overreaching(db_session, athlete, today)

    assert second is None

    result = await db_session.execute(
        select(func.count()).select_from(AdminAlert).where(
            AdminAlert.athlete_id == athlete.id,
            AdminAlert.alert_type == "overreaching",
        )
    )
    assert result.scalar() == 1


# ── Test 7: Training load calculations ───────────────────────────────────────

@pytest.mark.asyncio
async def test_training_load_recalculation(client, db_session: AsyncSession):
    admin = await _create_admin(db_session)
    athlete = await _create_athlete_with_consent(db_session, admin)
    token = make_jwt(str(athlete.user_id))

    # Manually insert a workout (bypass Strava)
    from app.models.workout import Workout
    w = Workout(
        athlete_id=athlete.id,
        source="manual",
        sport_type="cycling",
        title="Test Ride",
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        duration_seconds=3600,
        tss=80.0,
        is_completed=True,
    )
    db_session.add(w)
    await db_session.commit()

    resp = await client.post(
        "/api/workouts/recalculate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


# ── Test 8: Billing plan endpoint returns current plan ────────────────────────

@pytest.mark.asyncio
async def test_billing_plan_returns_trial_for_new_admin(client, db_session: AsyncSession):
    admin = await _create_admin(db_session)
    token = make_jwt(str(admin.user_id))

    resp = await client.get(
        "/api/billing/plan",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "trial"
    assert data["status"] == "trialing"
    assert data["athlete_limit"] == PLANS["trial"]["athlete_limit"]


# ── Test 9: Unauthenticated requests are blocked ──────────────────────────────

@pytest.mark.asyncio
async def test_unauthenticated_request_blocked(client):
    for path in ["/api/admin/athletes", "/api/workouts", "/api/recommendations/today"]:
        resp = await client.get(path)
        assert resp.status_code in (401, 403), f"Expected 401/403 for {path}, got {resp.status_code}"


# ── Test 10: LGPD consent required for athlete data ──────────────────────────

@pytest.mark.asyncio
async def test_lgpd_consent_required(client, db_session: AsyncSession):
    admin = await _create_admin(db_session)
    # Athlete WITHOUT consent
    athlete = Athlete(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        admin_id=admin.id,
        name="No Consent",
        email="noconsent@test.com",
        is_active=True,
        onboarding_complete=False,
    )
    db_session.add(athlete)
    await db_session.commit()

    token = make_jwt(str(athlete.user_id))
    resp = await client.get(
        "/api/workouts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
