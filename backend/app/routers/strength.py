"""
Strength training endpoints.

POST   /api/strength                        — create session (auto-calculates TSS)
GET    /api/strength                        — list sessions (paginated)
GET    /api/strength/{id}                   — session detail with exercises
PUT    /api/strength/{id}                   — update session header
DELETE /api/strength/{id}
POST   /api/strength/{id}/exercises         — add exercise to session
PUT    /api/strength/{id}/exercises/{eid}   — update exercise
DELETE /api/strength/{id}/exercises/{eid}   — remove exercise
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, date as _date

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import require_lgpd_consent
from app.models.athlete import Athlete
from app.models.strength import StrengthSession, StrengthExercise
from app.services.training_load import recalculate_athlete_load
from app.utils.calculations import calculate_strength_tss

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_SESSION_TYPES = {"upper", "lower", "full_body", "push", "pull", "legs", "core", "other"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class ExerciseIn(BaseModel):
    exercise_name: str
    sets: int
    reps: int | None = None
    duration_seconds: int | None = None
    load_kg: float | None = None
    rpe: int | None = None
    notes: str | None = None
    exercise_order: int | None = None

    @field_validator("rpe")
    @classmethod
    def validate_rpe(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 10):
            raise ValueError("RPE must be between 1 and 10")
        return v


class CreateStrengthRequest(BaseModel):
    session_date: str  # ISO date: "2024-01-15"
    session_type: str | None = None
    duration_minutes: int | None = None
    rpe_overall: int | None = None
    notes: str | None = None
    exercises: list[ExerciseIn] = []

    @field_validator("session_type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v and v not in VALID_SESSION_TYPES:
            raise ValueError(f"session_type must be one of {VALID_SESSION_TYPES}")
        return v

    @field_validator("rpe_overall")
    @classmethod
    def validate_rpe_overall(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 10):
            raise ValueError("rpe_overall must be between 1 and 10")
        return v


class UpdateStrengthRequest(BaseModel):
    session_date: str | None = None
    session_type: str | None = None
    duration_minutes: int | None = None
    rpe_overall: int | None = None
    notes: str | None = None


# ── Serialisers ───────────────────────────────────────────────────────────────

def _exercise_dict(e: StrengthExercise) -> dict:
    return {
        "id": str(e.id),
        "exercise_name": e.exercise_name,
        "sets": e.sets,
        "reps": e.reps,
        "duration_seconds": e.duration_seconds,
        "load_kg": float(e.load_kg) if e.load_kg else None,
        "rpe": e.rpe,
        "notes": e.notes,
        "exercise_order": e.exercise_order,
    }


def _session_dict(s: StrengthSession, with_exercises: bool = True) -> dict:
    d = {
        "id": str(s.id),
        "athlete_id": str(s.athlete_id),
        "session_date": s.session_date.date().isoformat() if isinstance(s.session_date, datetime) else s.session_date.isoformat() if s.session_date else None,
        "session_type": s.session_type,
        "duration_minutes": s.duration_minutes,
        "rpe_overall": s.rpe_overall,
        "notes": s.notes,
        "tss": float(s.tss) if s.tss else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
    if with_exercises:
        d["exercises"] = [_exercise_dict(e) for e in (s.exercises or [])]
    return d


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Registrar sessão de musculação")
async def create_session(
    body: CreateStrengthRequest,
    background_tasks: BackgroundTasks,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    # Auto-calculate TSS if duration + RPE available
    tss: float | None = None
    if body.duration_minutes and body.rpe_overall:
        try:
            tss = calculate_strength_tss(body.duration_minutes, body.rpe_overall)
        except ValueError:
            pass

    session_dt = datetime.fromisoformat(body.session_date)

    session = StrengthSession(
        athlete_id=athlete.id,
        session_date=session_dt,
        session_type=body.session_type,
        duration_minutes=body.duration_minutes,
        rpe_overall=body.rpe_overall,
        notes=body.notes,
        tss=tss,
    )
    db.add(session)
    await db.flush()  # get session.id before adding exercises

    for order, ex in enumerate(body.exercises, start=1):
        exercise = StrengthExercise(
            session_id=session.id,
            exercise_name=ex.exercise_name,
            sets=ex.sets,
            reps=ex.reps,
            duration_seconds=ex.duration_seconds,
            load_kg=ex.load_kg,
            rpe=ex.rpe,
            notes=ex.notes,
            exercise_order=ex.exercise_order if ex.exercise_order is not None else order,
        )
        db.add(exercise)

    await db.commit()
    await db.refresh(session)

    # Reload with exercises
    result = await db.execute(
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(StrengthSession.id == session.id)
    )
    session = result.scalar_one()

    background_tasks.add_task(recalculate_athlete_load, db, str(athlete.id), 90)

    return _session_dict(session)


@router.get("", summary="Listar sessões de musculação")
async def list_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session_type: str | None = Query(None),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    query = select(StrengthSession).where(StrengthSession.athlete_id == athlete.id)
    if session_type:
        query = query.where(StrengthSession.session_type == session_type)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = (
        query
        .order_by(desc(StrengthSession.session_date))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    return {
        "items": [_session_dict(s, with_exercises=False) for s in sessions],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{session_id}", summary="Detalhes da sessão com exercícios")
async def get_session(
    session_id: str,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StrengthSession)
        .options(selectinload(StrengthSession.exercises))
        .where(StrengthSession.id == session_id, StrengthSession.athlete_id == athlete.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return _session_dict(session)


@router.put("/{session_id}", summary="Atualizar sessão")
async def update_session(
    session_id: str,
    body: UpdateStrengthRequest,
    background_tasks: BackgroundTasks,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StrengthSession)
        .where(StrengthSession.id == session_id, StrengthSession.athlete_id == athlete.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    update_data = body.model_dump(exclude_none=True)
    if "session_date" in update_data:
        update_data["session_date"] = datetime.fromisoformat(update_data["session_date"])

    for field, value in update_data.items():
        setattr(session, field, value)

    # Recalculate TSS if duration/RPE changed
    if session.duration_minutes and session.rpe_overall:
        try:
            session.tss = calculate_strength_tss(session.duration_minutes, session.rpe_overall)
        except ValueError:
            pass

    db.add(session)
    await db.commit()
    background_tasks.add_task(recalculate_athlete_load, db, str(athlete.id), 90)
    return {"detail": "Sessão atualizada"}


@router.delete("/{session_id}", summary="Remover sessão")
async def delete_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StrengthSession)
        .where(StrengthSession.id == session_id, StrengthSession.athlete_id == athlete.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    await db.delete(session)
    await db.commit()
    background_tasks.add_task(recalculate_athlete_load, db, str(athlete.id), 90)
    return {"detail": "Sessão removida"}


@router.post("/{session_id}/exercises", status_code=201, summary="Adicionar exercício à sessão")
async def add_exercise(
    session_id: str,
    body: ExerciseIn,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StrengthSession)
        .where(StrengthSession.id == session_id, StrengthSession.athlete_id == athlete.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # Get current max order
    order_result = await db.execute(
        select(func.max(StrengthExercise.exercise_order))
        .where(StrengthExercise.session_id == session_id)
    )
    max_order = order_result.scalar_one_or_none() or 0

    exercise = StrengthExercise(
        session_id=session_id,
        exercise_name=body.exercise_name,
        sets=body.sets,
        reps=body.reps,
        duration_seconds=body.duration_seconds,
        load_kg=body.load_kg,
        rpe=body.rpe,
        notes=body.notes,
        exercise_order=body.exercise_order if body.exercise_order is not None else max_order + 1,
    )
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    return _exercise_dict(exercise)


@router.put("/{session_id}/exercises/{exercise_id}", summary="Atualizar exercício")
async def update_exercise(
    session_id: str,
    exercise_id: str,
    body: ExerciseIn,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    # Verify session ownership
    sess_result = await db.execute(
        select(StrengthSession)
        .where(StrengthSession.id == session_id, StrengthSession.athlete_id == athlete.id)
    )
    if not sess_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    ex_result = await db.execute(
        select(StrengthExercise)
        .where(StrengthExercise.id == exercise_id, StrengthExercise.session_id == session_id)
    )
    exercise = ex_result.scalar_one_or_none()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercício não encontrado")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(exercise, field, value)

    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    return _exercise_dict(exercise)


@router.delete("/{session_id}/exercises/{exercise_id}", summary="Remover exercício")
async def delete_exercise(
    session_id: str,
    exercise_id: str,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    sess_result = await db.execute(
        select(StrengthSession)
        .where(StrengthSession.id == session_id, StrengthSession.athlete_id == athlete.id)
    )
    if not sess_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    ex_result = await db.execute(
        select(StrengthExercise)
        .where(StrengthExercise.id == exercise_id, StrengthExercise.session_id == session_id)
    )
    exercise = ex_result.scalar_one_or_none()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercício não encontrado")

    await db.delete(exercise)
    await db.commit()
    return {"detail": "Exercício removido"}
