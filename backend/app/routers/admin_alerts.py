"""
Admin alerts endpoints.

GET  /api/admin/alerts               — list alerts (filterable)
GET  /api/admin/alerts/summary       — unread counts by severity
PUT  /api/admin/alerts/{id}/read     — mark one alert as read
PUT  /api/admin/alerts/read-all      — mark all unread as read
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.models.alert import AdminAlert

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: str
    athlete_id: str | None
    athlete_name: str | None = None
    alert_type: str
    severity: str
    title: str
    body: str | None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertSummaryOut(BaseModel):
    total_unread: int
    critical: int
    warning: int
    info: int


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AlertOut])
async def list_alerts(
    severity: str | None = Query(None, description="Filter by severity: critical|warning|info"),
    athlete_id: str | None = Query(None),
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    from app.models.athlete import Athlete

    q = (
        select(AdminAlert, Athlete.name.label("athlete_name"))
        .outerjoin(Athlete, AdminAlert.athlete_id == Athlete.id)
        .where(AdminAlert.admin_id == admin.id)
        .order_by(desc(AdminAlert.created_at))
    )

    if severity:
        q = q.where(AdminAlert.severity == severity)
    if athlete_id:
        try:
            aid = _uuid.UUID(athlete_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="athlete_id inválido")
        q = q.where(AdminAlert.athlete_id == aid)
    if unread_only:
        q = q.where(AdminAlert.is_read == False)

    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    rows = result.all()

    return [
        AlertOut(
            id=str(row.AdminAlert.id),
            athlete_id=str(row.AdminAlert.athlete_id) if row.AdminAlert.athlete_id else None,
            athlete_name=row.athlete_name,
            alert_type=row.AdminAlert.alert_type,
            severity=row.AdminAlert.severity,
            title=row.AdminAlert.title,
            body=row.AdminAlert.body,
            is_read=row.AdminAlert.is_read,
            created_at=row.AdminAlert.created_at,
        )
        for row in rows
    ]


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=AlertSummaryOut)
async def alerts_summary(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(
        select(AdminAlert.severity, func.count().label("cnt"))
        .where(AdminAlert.admin_id == admin.id, AdminAlert.is_read == False)
        .group_by(AdminAlert.severity)
    )
    counts = {row.severity: row.cnt for row in result.all()}
    total = sum(counts.values())
    return AlertSummaryOut(
        total_unread=total,
        critical=counts.get("critical", 0),
        warning=counts.get("warning", 0),
        info=counts.get("info", 0),
    )


# ── Mark read ─────────────────────────────────────────────────────────────────

@router.put("/{alert_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        aid = _uuid.UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="alert_id inválido")

    result = await db.execute(
        select(AdminAlert).where(AdminAlert.id == aid, AdminAlert.admin_id == admin.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    alert.is_read = True
    await db.commit()


@router.put("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    await db.execute(
        update(AdminAlert)
        .where(AdminAlert.admin_id == admin.id, AdminAlert.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
