"""
Report endpoints.

GET  /api/reports/monthly                     — athlete's own monthly PDF (download)
POST /api/reports/monthly/email               — send monthly PDF to athlete via email
GET  /api/admin/athletes/{id}/report/monthly  — admin generates PDF for one of their athletes
"""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_athlete, get_current_admin, require_lgpd_consent
from app.models.admin import AdminUser
from app.models.athlete import Athlete

# Two routers: athlete endpoints (/api/reports/...) and admin endpoints (/api/admin/...)
athlete_router = APIRouter()
admin_router   = APIRouter()
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _validate_period(year: int, month: int) -> None:
    today = date.today()
    if not (2020 <= year <= today.year):
        raise HTTPException(status_code=422, detail="Ano inválido")
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="Mês inválido (1–12)")
    if date(year, month, 1) > today:
        raise HTTPException(status_code=422, detail="Não é possível gerar relatório de mês futuro")


# ── Athlete: download PDF ─────────────────────────────────────────────────────

@athlete_router.get("/monthly", summary="Relatório mensal em PDF")
async def athlete_monthly_report(
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month if date.today().day > 5 else (date.today().month - 1 or 12)),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    _validate_period(year, month)
    from app.services.pdf_service import generate_monthly_report_pdf
    try:
        pdf = await generate_monthly_report_pdf(db, str(athlete.id), year, month)
    except Exception as exc:
        logger.exception("Monthly report PDF failed for athlete %s: %s", athlete.id, exc)
        raise HTTPException(status_code=500, detail="Erro ao gerar PDF. Tente novamente.")

    month_pt = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"][month - 1]
    filename = f"fitcoach-{athlete.name.split()[0].lower()}-{month_pt}{year}.pdf"
    return _pdf_response(pdf, filename)


# ── Athlete: send by email ────────────────────────────────────────────────────

@athlete_router.post("/monthly/email", summary="Enviar relatório mensal por e-mail")
async def email_monthly_report(
    background_tasks: BackgroundTasks,
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month if date.today().day > 5 else (date.today().month - 1 or 12)),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    _validate_period(year, month)

    async def _send():
        from app.services.pdf_service import generate_monthly_report_pdf
        from app.services.email_service import send_monthly_report_email
        try:
            pdf = await generate_monthly_report_pdf(db, str(athlete.id), year, month)
            await send_monthly_report_email(
                to_email=athlete.email,
                athlete_name=athlete.name,
                year=year,
                month=month,
                pdf_bytes=pdf,
            )
        except Exception as exc:
            logger.exception("Email monthly report failed for athlete %s: %s", athlete.id, exc)

    background_tasks.add_task(_send)
    return {"detail": f"Relatório de {month}/{year} será enviado para {athlete.email} em instantes."}


# ── Admin: generate for one of their athletes ─────────────────────────────────

@admin_router.get("/athletes/{athlete_id}/report/monthly", summary="Admin — relatório mensal de atleta em PDF")
async def admin_athlete_monthly_report(
    athlete_id: str,
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month if date.today().day > 5 else (date.today().month - 1 or 12)),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    athlete_result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    _validate_period(year, month)
    from app.services.pdf_service import generate_monthly_report_pdf
    try:
        pdf = await generate_monthly_report_pdf(db, str(athlete.id), year, month)
    except Exception as exc:
        logger.exception("Admin monthly report PDF failed for athlete %s: %s", athlete_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao gerar PDF.")

    month_pt = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"][month - 1]
    filename = f"fitcoach-{athlete.name.split()[0].lower()}-{month_pt}{year}.pdf"
    return _pdf_response(pdf, filename)
