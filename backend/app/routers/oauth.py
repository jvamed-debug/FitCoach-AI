"""
OAuth endpoints for platform connections.

GET    /api/auth/oauth/strava/authorize   — redirect to Strava
GET    /api/auth/oauth/strava/callback    — exchange code, save tokens
DELETE /api/auth/oauth/strava             — disconnect
GET    /api/auth/oauth/connections        — list active platform connections
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_athlete, require_lgpd_consent
from app.models.athlete import Athlete, PlatformConnection
from app.models.lgpd import AuditLog
from app.services.strava_service import StravaService, encrypt_token

router = APIRouter()
logger = logging.getLogger(__name__)
_strava = StravaService()


async def _audit(db: AsyncSession, athlete: Athlete, action: str, resource_id=None, ip: str | None = None):
    db.add(AuditLog(
        actor_id=athlete.id, actor_type="athlete",
        action=action, resource_type="platform_connections",
        resource_id=resource_id, ip_address=ip,
    ))
    await db.commit()


# ── Strava OAuth ──────────────────────────────────────────────────────────────

@router.get("/strava/authorize", summary="Iniciar OAuth Strava")
async def strava_authorize(
    request: Request,
    athlete: Athlete = Depends(require_lgpd_consent),
):
    state = secrets.token_urlsafe(16)
    # In production, persist state in Redis with TTL=10min for CSRF check.
    # For now, embed athlete_id in state (signed token would be better in prod).
    full_state = f"{state}:{athlete.id}"
    url = _strava.get_authorization_url(full_state)
    return RedirectResponse(url)


@router.get("/strava/callback", summary="Callback OAuth Strava")
async def strava_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if error:
        return RedirectResponse(f"{settings.frontend_url}/settings?strava=denied")

    # Extract athlete_id from state
    try:
        _, athlete_id = state.rsplit(":", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido")

    athlete_result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.is_active == True)
    )
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    # Exchange code for tokens
    try:
        token_data = await _strava.exchange_code_for_tokens(code)
    except Exception as e:
        logger.exception("Strava token exchange failed: %s", e)
        return RedirectResponse(f"{settings.frontend_url}/settings?strava=error")

    strava_athlete = token_data.get("athlete", {})
    provider_athlete_id = str(strava_athlete.get("id", ""))
    expires_at = datetime.fromtimestamp(token_data["expires_at"], tz=timezone.utc)

    # Upsert platform_connection
    conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete.id,
            PlatformConnection.provider == "strava",
        )
    )
    conn = conn_result.scalar_one_or_none()

    if conn:
        conn.access_token_enc  = encrypt_token(token_data["access_token"])
        conn.refresh_token_enc = encrypt_token(token_data["refresh_token"])
        conn.token_expires_at  = expires_at
        conn.provider_athlete_id = provider_athlete_id
        conn.scope = token_data.get("scope", "")
        conn.is_active = True
        conn.consecutive_failures = 0
        conn.sync_error = None
    else:
        conn = PlatformConnection(
            athlete_id=athlete.id,
            provider="strava",
            provider_athlete_id=provider_athlete_id,
            access_token_enc=encrypt_token(token_data["access_token"]),
            refresh_token_enc=encrypt_token(token_data["refresh_token"]),
            token_expires_at=expires_at,
            scope=token_data.get("scope", ""),
            is_active=True,
        )

    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    await _audit(db, athlete, "strava_connected", resource_id=conn.id, ip=request.client.host)
    logger.info("Strava connected for athlete %s (Strava ID: %s)", athlete.id, provider_athlete_id)

    return RedirectResponse(f"{settings.frontend_url}/settings?strava=connected")


# ── TrainingPeaks OAuth ───────────────────────────────────────────────────────

from app.services.tp_service import TrainingPeaksService
_tp = TrainingPeaksService()


@router.get("/trainingpeaks/authorize", summary="Iniciar OAuth TrainingPeaks")
async def tp_authorize(
    request: Request,
    athlete: Athlete = Depends(require_lgpd_consent),
):
    import secrets as _secrets
    state = f"{_secrets.token_urlsafe(12)}:{athlete.id}"
    url = _tp.get_authorization_url(state)
    return RedirectResponse(url)


@router.get("/trainingpeaks/callback", summary="Callback OAuth TrainingPeaks")
async def tp_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if error:
        return RedirectResponse(f"{settings.frontend_url}/settings?tp=denied")

    try:
        _, athlete_id = state.rsplit(":", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido")

    athlete_result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.is_active == True)
    )
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    try:
        token_data = await _tp.exchange_code_for_tokens(code)
    except Exception as e:
        logger.exception("TrainingPeaks token exchange failed: %s", e)
        return RedirectResponse(f"{settings.frontend_url}/settings?tp=error")

    # TP tokens use expires_in (seconds) not expires_at (timestamp)
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete.id,
            PlatformConnection.provider == "trainingpeaks",
        )
    )
    conn = conn_result.scalar_one_or_none()

    if conn:
        conn.access_token_enc   = encrypt_token(token_data["access_token"])
        conn.refresh_token_enc  = encrypt_token(token_data["refresh_token"])
        conn.token_expires_at   = expires_at
        conn.is_active          = True
        conn.consecutive_failures = 0
        conn.sync_error         = None
    else:
        conn = PlatformConnection(
            athlete_id=athlete.id,
            provider="trainingpeaks",
            access_token_enc=encrypt_token(token_data["access_token"]),
            refresh_token_enc=encrypt_token(token_data["refresh_token"]),
            token_expires_at=expires_at,
            scope=token_data.get("scope", ""),
            is_active=True,
        )

    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    await _audit(db, athlete, "trainingpeaks_connected", resource_id=conn.id, ip=request.client.host)
    logger.info("TrainingPeaks connected for athlete %s", athlete.id)

    return RedirectResponse(f"{settings.frontend_url}/settings?tp=connected")


@router.delete("/trainingpeaks", summary="Desconectar TrainingPeaks")
async def tp_disconnect(
    request: Request,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete.id,
            PlatformConnection.provider == "trainingpeaks",
        )
    )
    conn = conn_result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="TrainingPeaks não conectado")

    conn.is_active = False
    conn.access_token_enc = None
    conn.refresh_token_enc = None
    db.add(conn)
    await db.commit()

    await _audit(db, athlete, "trainingpeaks_disconnected", resource_id=conn.id, ip=request.client.host)
    return {"detail": "TrainingPeaks desconectado"}


@router.delete("/strava", summary="Desconectar Strava")
async def strava_disconnect(
    request: Request,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    conn_result = await db.execute(
        select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete.id,
            PlatformConnection.provider == "strava",
        )
    )
    conn = conn_result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Strava não conectado")

    conn.is_active = False
    conn.access_token_enc = None
    conn.refresh_token_enc = None
    db.add(conn)
    await db.commit()

    await _audit(db, athlete, "strava_disconnected", resource_id=conn.id, ip=request.client.host)
    return {"detail": "Strava desconectado"}


@router.get("/connections", summary="Conexões de plataformas ativas")
async def list_connections(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformConnection).where(PlatformConnection.athlete_id == athlete.id)
    )
    conns = result.scalars().all()
    return [
        {
            "provider": c.provider,
            "is_active": c.is_active,
            "provider_athlete_id": c.provider_athlete_id,
            "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
            "sync_error": c.sync_error,
            "consecutive_failures": c.consecutive_failures,
        }
        for c in conns
    ]
