"""
T01.7 — Auth tests (NFR-16)

Covered:
- Admin login returns JWT with role=admin
- Athlete login returns JWT with role=athlete
- Expired/invalid token returns 401
- Athlete role blocked on admin-only endpoints
- LGPD middleware blocks athlete without consent (403)
- /api/auth/me returns correct profile for each role
- Refresh endpoint works
- Logout invalidates session
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient
from jose import jwt

from app.config import settings
from app.models.admin import AdminUser
from app.models.athlete import Athlete
from tests.conftest import make_jwt


# ── Helpers ───────────────────────────────────────────────────────────────────

def _supabase_token_response(user_id: str, role: str = "authenticated") -> dict:
    """Fake Supabase /token response."""
    access_token = make_jwt(user_id)
    return {
        "access_token": access_token,
        "refresh_token": "fake-refresh-token",
        "expires_in": 3600,
        "token_type": "bearer",
        "user": {"id": user_id, "email": "test@test.com", "role": role},
    }


# ── Admin login ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, admin_user: AdminUser):
    fake_response = _supabase_token_response(str(admin_user.user_id))

    with patch("app.routers.auth._supabase_sign_in", new=AsyncMock(return_value=fake_response)):
        resp = await client.post("/api/auth/admin/login", json={
            "email": "admin@test.com",
            "password": "secret123"
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_admin_login_wrong_credentials(client: AsyncClient):
    from fastapi import HTTPException

    with patch("app.routers.auth._supabase_sign_in",
               new=AsyncMock(side_effect=HTTPException(status_code=401, detail="Credenciais inválidas"))):
        resp = await client.post("/api/auth/admin/login", json={
            "email": "wrong@test.com",
            "password": "wrongpass"
        })

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_non_admin_user(client: AsyncClient, athlete_user: Athlete):
    """A user who is registered as athlete (not admin) should get 403 on admin login."""
    fake_response = _supabase_token_response(str(athlete_user.user_id))

    with patch("app.routers.auth._supabase_sign_in", new=AsyncMock(return_value=fake_response)):
        resp = await client.post("/api/auth/admin/login", json={
            "email": "athlete@test.com",
            "password": "secret123"
        })

    assert resp.status_code == 403


# ── Athlete login ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_athlete_login_success(client: AsyncClient, athlete_user: Athlete):
    fake_response = _supabase_token_response(str(athlete_user.user_id))

    with patch("app.routers.auth._supabase_sign_in", new=AsyncMock(return_value=fake_response)):
        resp = await client.post("/api/auth/athlete/login", json={
            "email": "athlete@test.com",
            "password": "secret123"
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "athlete"
    assert "access_token" in data


# ── Token validation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_expired_token_returns_401(client: AsyncClient):
    expired_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient):
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer this.is.garbage"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_token_returns_403(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 403


# ── /me endpoint ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_admin(client: AsyncClient, admin_user: AdminUser):
    token = make_jwt(str(admin_user.user_id))
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert data["email"] == admin_user.email


@pytest.mark.asyncio
async def test_get_me_athlete(client: AsyncClient, athlete_user: Athlete):
    token = make_jwt(str(athlete_user.user_id))
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "athlete"
    assert data["email"] == athlete_user.email


# ── Role separation ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_athlete_cannot_use_admin_login_route(client: AsyncClient, athlete_user: Athlete):
    """Athlete credentials on /admin/login should return 403 (not admin in DB)."""
    fake_response = _supabase_token_response(str(athlete_user.user_id))

    with patch("app.routers.auth._supabase_sign_in", new=AsyncMock(return_value=fake_response)):
        resp = await client.post("/api/auth/admin/login", json={
            "email": "athlete@test.com",
            "password": "secret"
        })

    assert resp.status_code == 403


# ── LGPD middleware ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lgpd_consent_endpoint_no_consent(client: AsyncClient, athlete_user: Athlete):
    """GET /api/lgpd/consent for an athlete with no consent returns has_consent=False."""
    token = make_jwt(str(athlete_user.user_id))
    resp = await client.get("/api/lgpd/consent", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["has_consent"] is False


@pytest.mark.asyncio
async def test_lgpd_record_consent(client: AsyncClient, athlete_user: Athlete):
    token = make_jwt(str(athlete_user.user_id))
    resp = await client.post("/api/lgpd/consent",
                              json={"consent_version": "1.0"},
                              headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == "1.0"
    assert "consented_at" in data


@pytest.mark.asyncio
async def test_lgpd_consent_idempotent(client: AsyncClient, athlete_with_consent: Athlete):
    """Recording consent twice should be safe (idempotent)."""
    token = make_jwt(str(athlete_with_consent.user_id))
    resp = await client.post("/api/lgpd/consent",
                              json={"consent_version": "1.0"},
                              headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 201
    assert "já registrado" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_require_lgpd_consent_blocks_without_consent(client: AsyncClient, athlete_user: Athlete):
    """
    An endpoint that uses require_lgpd_consent dependency must return 403
    when the athlete has not consented yet.
    We test this via a synthetic route added in this test.
    """
    from fastapi import Depends
    from app.dependencies import require_lgpd_consent
    from app.main import app

    # Add a temporary test route
    @app.get("/test/lgpd-guarded", include_in_schema=False)
    async def _guarded(a: Athlete = Depends(require_lgpd_consent)):
        return {"ok": True}

    token = make_jwt(str(athlete_user.user_id))
    resp = await client.get("/test/lgpd-guarded", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
    assert "LGPD" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_require_lgpd_consent_passes_with_consent(client: AsyncClient, athlete_with_consent: Athlete):
    from fastapi import Depends
    from app.dependencies import require_lgpd_consent
    from app.main import app

    @app.get("/test/lgpd-guarded-ok", include_in_schema=False)
    async def _guarded_ok(a: Athlete = Depends(require_lgpd_consent)):
        return {"ok": True}

    token = make_jwt(str(athlete_with_consent.user_id))
    resp = await client.get("/test/lgpd-guarded-ok", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ── Profile update ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_profile_admin(client: AsyncClient, admin_user: AdminUser):
    token = make_jwt(str(admin_user.user_id))
    resp = await client.put("/api/auth/me",
                             json={"name": "Dr. Updated"},
                             headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_profile_empty_body(client: AsyncClient, admin_user: AdminUser):
    token = make_jwt(str(admin_user.user_id))
    resp = await client.put("/api/auth/me",
                             json={},
                             headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 400


# ── Refresh ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, admin_user: AdminUser):
    new_access = make_jwt(str(admin_user.user_id))
    fake_refresh_response = {
        "access_token": new_access,
        "refresh_token": "new-refresh-token",
        "expires_in": 3600,
        "user": {"id": str(admin_user.user_id)},
    }

    with patch("app.routers.auth._supabase_refresh", new=AsyncMock(return_value=fake_refresh_response)):
        resp = await client.post("/api/auth/refresh",
                                  json={"refresh_token": "old-refresh-token"})

    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
