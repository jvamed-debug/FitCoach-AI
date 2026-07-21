"""
LGPD compliance endpoints for athletes.
POST /api/lgpd/consent        — record consent (called during onboarding)
DELETE /api/lgpd/consent      — revoke consent (triggers deletion pipeline)
GET  /api/lgpd/consent        — get current consent status
POST /api/lgpd/export         — request personal data export
GET  /api/lgpd/deletion-status — check deletion request status
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import logging

from app.database import get_db
from app.dependencies import get_current_athlete
from app.models.athlete import Athlete
from app.models.lgpd import LGPDConsent, AuditLog, LGPDDeletionRequest

router = APIRouter()
logger = logging.getLogger(__name__)

CURRENT_CONSENT_VERSION = "1.0"
DELETION_DEADLINE_HOURS = 72


class ConsentRequest(BaseModel):
    consent_version: str = CURRENT_CONSENT_VERSION


class RevokeRequest(BaseModel):
    reason: str | None = None


async def _log_action(db: AsyncSession, actor_id, actor_type: str, action: str,
                      resource_type: str, resource_id=None, ip: str | None = None):
    log = AuditLog(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip,
    )
    db.add(log)
    await db.commit()


@router.post("/consent", status_code=status.HTTP_201_CREATED, summary="Registrar consentimento LGPD")
async def record_consent(
    body: ConsentRequest,
    request: Request,
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    # Check if already has active consent for this version
    result = await db.execute(
        select(LGPDConsent).where(
            LGPDConsent.athlete_id == athlete.id,
            LGPDConsent.consent_version == body.consent_version,
            LGPDConsent.revoked_at == None,
        )
    )
    if result.scalar_one_or_none():
        return {"detail": "Consentimento já registrado", "version": body.consent_version}

    consent = LGPDConsent(
        athlete_id=athlete.id,
        consent_version=body.consent_version,
        consented_at=datetime.now(timezone.utc),
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(consent)

    # Mark onboarding step complete if this was missing
    if not athlete.onboarding_complete:
        athlete.onboarding_complete = True
        db.add(athlete)

    await db.commit()

    await _log_action(db, athlete.id, "athlete", "lgpd_consent_given",
                      "lgpd_consents", resource_id=consent.id, ip=request.client.host)

    return {
        "detail": "Consentimento registrado com sucesso",
        "version": body.consent_version,
        "consented_at": consent.consented_at.isoformat(),
    }


@router.get("/consent", summary="Status do consentimento LGPD")
async def get_consent_status(
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LGPDConsent)
        .where(LGPDConsent.athlete_id == athlete.id)
        .order_by(LGPDConsent.consented_at.desc())
        .limit(1)
    )
    consent = result.scalar_one_or_none()
    if not consent:
        return {"has_consent": False, "version": None}

    return {
        "has_consent": consent.revoked_at is None,
        "version": consent.consent_version,
        "consented_at": consent.consented_at.isoformat() if consent.consented_at else None,
        "revoked_at": consent.revoked_at.isoformat() if consent.revoked_at else None,
    }


@router.delete("/consent", summary="Revogar consentimento LGPD (inicia exclusão de dados)")
async def revoke_consent(
    body: RevokeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    # Revoke all active consents
    result = await db.execute(
        select(LGPDConsent).where(
            LGPDConsent.athlete_id == athlete.id,
            LGPDConsent.revoked_at == None,
        )
    )
    consents = result.scalars().all()
    if not consents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Nenhum consentimento ativo encontrado")

    now = datetime.now(timezone.utc)
    for c in consents:
        c.revoked_at = now
        c.revoke_reason = body.reason
        db.add(c)

    # Create deletion request with 72h deadline
    deletion = LGPDDeletionRequest(
        athlete_id=athlete.id,
        requested_at=now,
        deadline=now + timedelta(hours=DELETION_DEADLINE_HOURS),
        status="pending",
    )
    db.add(deletion)
    await db.commit()

    await _log_action(db, athlete.id, "athlete", "lgpd_consent_revoked",
                      "lgpd_consents", ip=request.client.host)

    logger.info("LGPD deletion requested for athlete %s — deadline %s", athlete.id, deletion.deadline)

    return {
        "detail": "Consentimento revogado. Dados serão excluídos em até 72 horas.",
        "deletion_deadline": deletion.deadline.isoformat(),
        "deletion_request_id": str(deletion.id),
    }


@router.get("/deletion-status", summary="Status da solicitação de exclusão de dados")
async def get_deletion_status(
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LGPDDeletionRequest)
        .where(LGPDDeletionRequest.athlete_id == athlete.id)
        .order_by(LGPDDeletionRequest.requested_at.desc())
        .limit(1)
    )
    req = result.scalar_one_or_none()
    if not req:
        return {"has_pending_deletion": False}

    return {
        "has_pending_deletion": req.status == "pending",
        "status": req.status,
        "requested_at": req.requested_at.isoformat(),
        "deadline": req.deadline.isoformat(),
        "executed_at": req.executed_at.isoformat() if req.executed_at else None,
    }


@router.post("/export", summary="Solicitar exportação de dados pessoais (PDF via e-mail)")
async def request_data_export(
    request: Request,
    background_tasks: BackgroundTasks,
    athlete: Athlete = Depends(get_current_athlete),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a LGPD data export PDF and sends it to the athlete's email.
    The PDF is generated in background to avoid blocking the response.
    """
    await _log_action(db, athlete.id, "athlete", "lgpd_export_requested",
                      "athletes", resource_id=athlete.id, ip=request.client.host)

    athlete_id = str(athlete.id)
    athlete_email = athlete.email
    athlete_name = athlete.name

    async def _generate_and_send():
        from app.database import AsyncSessionLocal
        from app.services.pdf_service import generate_lgpd_export_pdf
        from app.services.email_service import send_lgpd_export_email
        try:
            async with AsyncSessionLocal() as new_db:
                pdf = await generate_lgpd_export_pdf(new_db, athlete_id)
            await send_lgpd_export_email(athlete_email, athlete_name, pdf)
            logger.info("LGPD export PDF sent to athlete %s", athlete_id)
        except Exception as exc:
            logger.exception("LGPD export PDF failed for athlete %s: %s", athlete_id, exc)

    background_tasks.add_task(_generate_and_send)
    logger.info("Data export requested by athlete %s", athlete_id)

    return {
        "detail": "Exportação iniciada. Você receberá o PDF por e-mail em alguns minutos.",
        "email": athlete_email,
    }
