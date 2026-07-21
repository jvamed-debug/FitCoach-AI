"""
Admin → Athlete management endpoints.

POST   /api/admin/athletes                             — create athlete + send invite email
GET    /api/admin/athletes                             — paginated list with TSB indicators
GET    /api/admin/athletes/{id}                        — full profile (anamnese decrypted)
PUT    /api/admin/athletes/{id}                        — update profile, availability, goals
DELETE /api/admin/athletes/{id}                        — deactivate (soft-delete)
PUT    /api/admin/athletes/{id}/anamnese               — save/update encrypted anamnese
GET    /api/admin/athletes/{id}/anamnese               — read decrypted anamnese
GET    /api/admin/athletes/{id}/workouts               — workout history (admin view)
GET    /api/admin/athletes/{id}/load-history           — CTL/ATL/TSB history
GET    /api/admin/athletes/{id}/recommendations        — recommendation history
GET    /api/admin/athletes/{id}/adherence-summary      — adherence stats (% followed)
POST   /api/admin/athletes/{id}/resend-invite  — resend onboarding email
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, BackgroundTasks
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func, select, text, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.models.athlete import Athlete
from app.models.lgpd import AuditLog
from app.models.training_load import TrainingLoad
from app.models.workout import Workout
from app.services.email_service import send_athlete_invite
from app.utils.crypto import (
    decrypt_anamnese,
    encrypt_anamnese,
    generate_invite_token,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _audit(db: AsyncSession, admin: AdminUser, action: str,
                  resource_type: str, resource_id=None, ip: str | None = None):
    db.add(AuditLog(
        actor_id=admin.id,
        actor_type="admin",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip,
    ))
    await db.commit()


def _tsb_status(tsb: float | None) -> str:
    if tsb is None:
        return "unknown"
    if tsb < -20:
        return "critical"
    if tsb < -5:
        return "alert"
    if tsb < 5:
        return "moderate"
    return "good"


def _athlete_summary(athlete: Athlete, load: TrainingLoad | None, last_workout_date: date | None) -> dict:
    tsb = float(load.tsb) if load and load.tsb is not None else None
    days_since = None
    if last_workout_date:
        days_since = (date.today() - last_workout_date).days

    return {
        "id": str(athlete.id),
        "name": athlete.name,
        "email": athlete.email,
        "primary_modality": athlete.primary_modality,
        "sport_modalities": athlete.sport_modalities,
        "fitness_level": athlete.fitness_level,
        "onboarding_complete": athlete.onboarding_complete,
        "is_active": athlete.is_active,
        "created_at": athlete.created_at.isoformat() if athlete.created_at else None,
        "training_load": {
            "ctl": float(load.ctl) if load and load.ctl is not None else None,
            "atl": float(load.atl) if load and load.atl is not None else None,
            "tsb": tsb,
            "tsb_status": _tsb_status(tsb),
            "daily_tss": float(load.daily_tss) if load and load.daily_tss is not None else None,
            "load_date": load.load_date.isoformat() if load else None,
        },
        "days_since_last_workout": days_since,
        "no_workout_alert": days_since is not None and days_since >= 3,
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateAthleteRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    birth_date: str | None = None
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    sport_modalities: list[str] = []
    primary_modality: str | None = None
    fitness_level: str | None = None
    goal: str | None = None
    weekly_availability: dict | None = None
    ftp_watts: int | None = None
    max_hr: int | None = None
    resting_hr: int | None = None

    @field_validator("sport_modalities")
    @classmethod
    def validate_modalities(cls, v: list[str]) -> list[str]:
        allowed = {"cycling", "running", "swimming", "triathlon", "strength", "mobility"}
        for m in v:
            if m not in allowed:
                raise ValueError(f"Modalidade inválida: {m}. Permitidas: {allowed}")
        return v


class UpdateAthleteRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    birth_date: str | None = None
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    sport_modalities: list[str] | None = None
    primary_modality: str | None = None
    fitness_level: str | None = None
    goal: str | None = None
    weekly_availability: dict | None = None
    ftp_watts: int | None = None
    max_hr: int | None = None
    resting_hr: int | None = None
    auto_report_enabled: bool | None = None


class AnamneseRequest(BaseModel):
    content: str  # JSON string or free-text medical history


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED, summary="Criar atleta e enviar convite")
async def create_athlete(
    body: CreateAthleteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    # Check subscription athlete limit
    from app.services.billing_service import check_athlete_limit
    can_add, current_count, limit = await check_athlete_limit(db, str(admin.id))
    if not can_add:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Limite de atletas atingido para seu plano ({current_count}/{limit}). "
                "Faça upgrade em /billing para adicionar mais atletas."
            ),
        )

    # Check email uniqueness
    existing = await db.execute(select(Athlete).where(Athlete.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="E-mail já cadastrado")

    # Create a Supabase Auth user with a temporary random password
    # The athlete will set their own password via the invite link.
    # We store a placeholder user_id; Supabase user creation happens when
    # the athlete clicks the invite link (handled in T02.5 / /auth/onboarding).
    placeholder_user_id = _uuid.uuid4()

    athlete = Athlete(
        user_id=placeholder_user_id,
        admin_id=admin.id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        gender=body.gender,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        sport_modalities=body.sport_modalities,
        primary_modality=body.primary_modality,
        fitness_level=body.fitness_level,
        goal=body.goal,
        weekly_availability=body.weekly_availability,
        ftp_watts=body.ftp_watts,
        max_hr=body.max_hr,
        resting_hr=body.resting_hr,
        is_active=True,
        onboarding_complete=False,
    )
    if body.birth_date:
        from datetime import date as _date
        athlete.birth_date = _date.fromisoformat(body.birth_date)

    db.add(athlete)
    await db.commit()
    await db.refresh(athlete)

    # Generate invite token and enqueue email
    token = generate_invite_token(str(athlete.id))
    onboarding_url = f"{settings.frontend_url}/onboarding?token={token}"

    background_tasks.add_task(
        send_athlete_invite,
        to_email=athlete.email,
        athlete_name=athlete.name,
        admin_name=admin.name,
        onboarding_url=onboarding_url,
    )

    await _audit(db, admin, "athlete_created", "athletes",
                 resource_id=athlete.id, ip=request.client.host)

    return {
        "id": str(athlete.id),
        "name": athlete.name,
        "email": athlete.email,
        "onboarding_url": onboarding_url,
        "detail": "Atleta criado. E-mail de convite enviado.",
    }


@router.get("", summary="Listar atletas com indicadores de carga")
async def list_athletes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    active_only: bool = Query(True),
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Athlete).where(Athlete.admin_id == admin.id)
    if active_only:
        query = query.where(Athlete.is_active == True)
    if search:
        like = f"%{search}%"
        query = query.where(
            (Athlete.name.ilike(like)) | (Athlete.email.ilike(like))
        )

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.order_by(Athlete.name).offset((page - 1) * per_page).limit(per_page)
    athletes_result = await db.execute(query)
    athletes = athletes_result.scalars().all()

    # Batch-fetch latest training_load for each athlete
    athlete_ids = [a.id for a in athletes]
    items: list[dict] = []

    for athlete in athletes:
        # Latest load entry
        load_result = await db.execute(
            select(TrainingLoad)
            .where(TrainingLoad.athlete_id == athlete.id)
            .order_by(desc(TrainingLoad.load_date))
            .limit(1)
        )
        load = load_result.scalar_one_or_none()

        # Latest workout date
        wkt_result = await db.execute(
            select(func.max(Workout.start_time))
            .where(Workout.athlete_id == athlete.id, Workout.is_completed == True)
        )
        last_wkt_dt = wkt_result.scalar_one_or_none()
        last_wkt_date = last_wkt_dt.date() if last_wkt_dt else None

        items.append(_athlete_summary(athlete, load, last_wkt_date))

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/{athlete_id}", summary="Perfil completo do atleta")
async def get_athlete(
    athlete_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    load_result = await db.execute(
        select(TrainingLoad)
        .where(TrainingLoad.athlete_id == athlete.id)
        .order_by(desc(TrainingLoad.load_date))
        .limit(1)
    )
    load = load_result.scalar_one_or_none()

    wkt_result = await db.execute(
        select(func.max(Workout.start_time))
        .where(Workout.athlete_id == athlete.id, Workout.is_completed == True)
    )
    last_wkt_dt = wkt_result.scalar_one_or_none()
    last_wkt_date = last_wkt_dt.date() if last_wkt_dt else None

    base = _athlete_summary(athlete, load, last_wkt_date)
    base.update({
        "phone": athlete.phone,
        "birth_date": athlete.birth_date.isoformat() if athlete.birth_date else None,
        "gender": athlete.gender,
        "height_cm": float(athlete.height_cm) if athlete.height_cm else None,
        "weight_kg": float(athlete.weight_kg) if athlete.weight_kg else None,
        "goal": athlete.goal,
        "weekly_availability": athlete.weekly_availability,
        "ftp_watts": athlete.ftp_watts,
        "max_hr": athlete.max_hr,
        "resting_hr": athlete.resting_hr,
        "auto_report_enabled": athlete.auto_report_enabled,
        "apple_health_token": str(athlete.apple_health_token) if athlete.apple_health_token else None,
    })
    return base


@router.put("/{athlete_id}", summary="Atualizar perfil do atleta")
async def update_athlete(
    athlete_id: str,
    body: UpdateAthleteRequest,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    if "birth_date" in update_data:
        from datetime import date as _date
        update_data["birth_date"] = _date.fromisoformat(update_data["birth_date"])

    for field, value in update_data.items():
        if hasattr(athlete, field):
            setattr(athlete, field, value)

    db.add(athlete)
    await db.commit()

    await _audit(db, admin, "athlete_updated", "athletes",
                 resource_id=athlete.id, ip=request.client.host)

    return {"detail": "Atleta atualizado com sucesso"}


@router.delete("/{athlete_id}", summary="Desativar atleta (soft-delete)")
async def deactivate_athlete(
    athlete_id: str,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    athlete.is_active = False
    db.add(athlete)
    await db.commit()

    await _audit(db, admin, "athlete_deactivated", "athletes",
                 resource_id=athlete.id, ip=request.client.host)

    return {"detail": "Atleta desativado"}


@router.put("/{athlete_id}/anamnese", summary="Salvar anamnese criptografada")
async def save_anamnese(
    athlete_id: str,
    body: AnamneseRequest,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    encrypted = await encrypt_anamnese(db, body.content)
    athlete.anamnese_encrypted = encrypted
    db.add(athlete)
    await db.commit()

    await _audit(db, admin, "anamnese_updated", "athletes",
                 resource_id=athlete.id, ip=request.client.host)

    return {"detail": "Anamnese salva com criptografia AES-256"}


@router.get("/{athlete_id}/anamnese", summary="Ler anamnese descriptografada")
async def get_anamnese(
    athlete_id: str,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    if not athlete.anamnese_encrypted:
        return {"content": None, "detail": "Anamnese não preenchida"}

    plaintext = await decrypt_anamnese(db, athlete.anamnese_encrypted)

    await _audit(db, admin, "anamnese_accessed", "athletes",
                 resource_id=athlete.id, ip=request.client.host)

    return {"content": plaintext}


@router.get("/{athlete_id}/workouts", summary="Histórico de treinos do atleta (admin)")
async def admin_get_workouts(
    athlete_id: str,
    page: int = 1,
    per_page: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    # Verify admin owns this athlete
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    from app.models.workout import Workout
    from sqlalchemy import desc

    total_q = await db.execute(
        select(func.count(Workout.id)).where(
            Workout.athlete_id == athlete_id, Workout.is_completed == True
        )
    )
    total = total_q.scalar_one()

    wkt_q = await db.execute(
        select(Workout)
        .where(Workout.athlete_id == athlete_id, Workout.is_completed == True)
        .order_by(desc(Workout.start_time))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    workouts = wkt_q.scalars().all()

    return {
        "items": [
            {
                "id": str(w.id),
                "sport_type": w.sport_type,
                "title": w.title,
                "start_time": w.start_time.isoformat() if w.start_time else None,
                "duration_seconds": w.duration_seconds,
                "tss": float(w.tss) if w.tss else None,
                "normalized_power_watts": w.normalized_power_watts,
                "avg_heart_rate": w.avg_heart_rate,
                "source": w.source,
            }
            for w in workouts
        ],
        "total": total, "page": page, "per_page": per_page,
    }


@router.get("/{athlete_id}/load-history", summary="Histórico CTL/ATL/TSB do atleta (admin)")
async def admin_get_load_history(
    athlete_id: str,
    days: int = 90,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    from app.services.training_load import get_current_load, get_load_history
    current = await get_current_load(db, athlete_id)
    history = await get_load_history(db, athlete_id, days)
    return {"current": current, "history": history}


@router.get("/{athlete_id}/recommendations", summary="Recomendações do atleta (admin)")
async def admin_get_recommendations(
    athlete_id: str,
    page: int = 1,
    per_page: int = 10,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    from app.models.recommendation import AIRecommendation
    from sqlalchemy import desc

    total_q = await db.execute(
        select(func.count(AIRecommendation.id)).where(AIRecommendation.athlete_id == athlete_id)
    )
    total = total_q.scalar_one()

    recs_q = await db.execute(
        select(AIRecommendation)
        .where(AIRecommendation.athlete_id == athlete_id)
        .order_by(desc(AIRecommendation.recommendation_date))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    recs = recs_q.scalars().all()

    return {
        "items": [
            {
                "id": str(r.id),
                "recommendation_date": r.recommendation_date.isoformat() if r.recommendation_date else None,
                "workout_type": r.workout_type,
                "title": r.title,
                "ai_provider": r.ai_provider,
                "feedback_rating": r.feedback_rating,
                "was_followed": r.was_followed,
            }
            for r in recs
        ],
        "total": total, "page": page, "per_page": per_page,
    }


@router.get("/{athlete_id}/adherence-summary", summary="Resumo de aderência do atleta")
async def admin_get_adherence_summary(
    athlete_id: str,
    days: int = 30,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Atleta não encontrado")

    from app.models.recommendation import AIRecommendation
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days)

    recs_q = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.athlete_id == athlete_id,
            AIRecommendation.recommendation_date >= cutoff,
        )
    )
    recs = recs_q.scalars().all()

    total_recs = len(recs)
    with_feedback = [r for r in recs if r.feedback_rating is not None]
    followed = [r for r in recs if r.was_followed is True]
    avg_rating = (
        round(sum(r.feedback_rating for r in with_feedback) / len(with_feedback), 1)
        if with_feedback else None
    )

    return {
        "period_days": days,
        "total_recommendations": total_recs,
        "with_feedback": len(with_feedback),
        "followed": len(followed),
        "adherence_pct": round(len(followed) / total_recs * 100) if total_recs else None,
        "avg_rating": avg_rating,
        "rest_days": sum(1 for r in recs if r.workout_type == "rest"),
    }


@router.post("/{athlete_id}/resend-invite", summary="Reenviar e-mail de convite")
async def resend_invite(
    athlete_id: str,
    background_tasks: BackgroundTasks,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Athlete).where(Athlete.id == athlete_id, Athlete.admin_id == admin.id)
    )
    athlete = result.scalar_one_or_none()
    if not athlete:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")
    if athlete.onboarding_complete:
        raise HTTPException(status_code=400, detail="Atleta já completou o onboarding")

    token = generate_invite_token(str(athlete.id))
    onboarding_url = f"{settings.frontend_url}/onboarding?token={token}"

    background_tasks.add_task(
        send_athlete_invite,
        to_email=athlete.email,
        athlete_name=athlete.name,
        admin_name=admin.name,
        onboarding_url=onboarding_url,
    )

    return {"detail": "Convite reenviado", "onboarding_url": onboarding_url}
