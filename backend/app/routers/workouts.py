"""
Workout endpoints (endurance: cycling, running, etc.)

GET    /api/workouts                 — list with filters
GET    /api/workouts/{id}            — detail
POST   /api/workouts                 — manual entry
DELETE /api/workouts/{id}
GET    /api/workouts/load            — current CTL/ATL/TSB + 90-day history
GET    /api/workouts/load/current    — current CTL/ATL/TSB only
GET    /api/workouts/stats/weekly    — TSS + distance + time for last 7 days vs prev 7
POST   /api/workouts/recalculate     — force recalculate training load
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta, date

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_athlete, require_lgpd_consent
from app.models.athlete import Athlete
from app.models.workout import Workout
from app.services.training_load import (
    get_current_load,
    get_load_history,
    recalculate_athlete_load,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateWorkoutRequest(BaseModel):
    sport_type: str
    title: str | None = None
    description: str | None = None
    start_time: str
    duration_seconds: int | None = None
    distance_meters: float | None = None
    elevation_gain_meters: float | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    avg_power_watts: int | None = None
    normalized_power_watts: int | None = None
    max_power_watts: int | None = None
    avg_cadence: int | None = None
    calories: int | None = None
    tss: float | None = None


def _workout_to_dict(w: Workout) -> dict:
    return {
        "id": str(w.id),
        "athlete_id": str(w.athlete_id),
        "external_id": w.external_id,
        "source": w.source,
        "sport_type": w.sport_type,
        "title": w.title,
        "description": w.description,
        "start_time": w.start_time.isoformat() if w.start_time else None,
        "duration_seconds": w.duration_seconds,
        "distance_meters": float(w.distance_meters) if w.distance_meters else None,
        "elevation_gain_meters": float(w.elevation_gain_meters) if w.elevation_gain_meters else None,
        "avg_heart_rate": w.avg_heart_rate,
        "max_heart_rate": w.max_heart_rate,
        "avg_power_watts": w.avg_power_watts,
        "normalized_power_watts": w.normalized_power_watts,
        "max_power_watts": w.max_power_watts,
        "avg_cadence": w.avg_cadence,
        "calories": w.calories,
        "tss": float(w.tss) if w.tss else None,
        "if_score": float(w.if_score) if w.if_score else None,
        "hr_zones": w.hr_zones,
        "power_zones": w.power_zones,
        "is_completed": w.is_completed,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


@router.get("/load", summary="CTL/ATL/TSB atual + histórico de 90 dias")
async def get_load(
    days: int = Query(90, ge=7, le=365),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    current = await get_current_load(db, str(athlete.id))
    history = await get_load_history(db, str(athlete.id), days)
    return {"current": current, "history": history}


@router.get("/load/current", summary="CTL/ATL/TSB atual")
async def get_current_load_endpoint(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    current = await get_current_load(db, str(athlete.id))
    return current or {"ctl": 0, "atl": 0, "tsb": 0, "daily_tss": 0, "weekly_tss": 0}


@router.post("/recalculate", summary="Recalcular carga de treino")
async def recalculate_load(
    background_tasks: BackgroundTasks,
    days_back: int = Query(90, ge=30, le=365),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    background_tasks.add_task(recalculate_athlete_load, db, str(athlete.id), days_back)
    return {"detail": f"Recalculando carga dos últimos {days_back} dias em background"}


@router.get("/stats/weekly", summary="Estatísticas TSS, distância e tempo semanal")
async def weekly_stats(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    week_start = today - timedelta(days=6)
    prev_start = today - timedelta(days=13)
    prev_end = today - timedelta(days=7)

    async def _stats(start: date, end: date) -> dict:
        result = await db.execute(
            select(
                func.count(Workout.id).label("count"),
                func.sum(Workout.duration_seconds).label("total_seconds"),
                func.sum(Workout.distance_meters).label("total_meters"),
                func.sum(Workout.tss).label("total_tss"),
            ).where(
                Workout.athlete_id == athlete.id,
                Workout.is_completed == True,
                func.date(Workout.start_time) >= start,
                func.date(Workout.start_time) <= end,
            )
        )
        row = result.one()
        return {
            "workout_count": row.count or 0,
            "total_seconds": row.total_seconds or 0,
            "total_meters": float(row.total_meters or 0),
            "total_tss": float(row.total_tss or 0),
        }

    this_week = await _stats(week_start, today)
    last_week = await _stats(prev_start, prev_end)

    return {"this_week": this_week, "last_week": last_week}


@router.get("", summary="Listar treinos")
async def list_workouts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sport_type: str | None = Query(None),
    source: str | None = Query(None),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    query = select(Workout).where(
        Workout.athlete_id == athlete.id,
        Workout.is_completed == True,
    )
    if sport_type:
        query = query.where(Workout.sport_type == sport_type)
    if source:
        query = query.where(Workout.source == source)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.order_by(desc(Workout.start_time)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    workouts = result.scalars().all()

    return {
        "items": [_workout_to_dict(w) for w in workouts],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{workout_id}", summary="Detalhes de um treino")
async def get_workout(
    workout_id: str,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workout).where(Workout.id == workout_id, Workout.athlete_id == athlete.id)
    )
    workout = result.scalar_one_or_none()
    if not workout:
        raise HTTPException(status_code=404, detail="Treino não encontrado")
    return _workout_to_dict(workout)


@router.post("", status_code=201, summary="Registrar treino manualmente")
async def create_workout(
    body: CreateWorkoutRequest,
    background_tasks: BackgroundTasks,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    workout = Workout(
        athlete_id=athlete.id,
        source="manual",
        sport_type=body.sport_type,
        title=body.title,
        description=body.description,
        start_time=datetime.fromisoformat(body.start_time),
        duration_seconds=body.duration_seconds,
        distance_meters=body.distance_meters,
        elevation_gain_meters=body.elevation_gain_meters,
        avg_heart_rate=body.avg_heart_rate,
        max_heart_rate=body.max_heart_rate,
        avg_power_watts=body.avg_power_watts,
        normalized_power_watts=body.normalized_power_watts,
        max_power_watts=body.max_power_watts,
        avg_cadence=body.avg_cadence,
        calories=body.calories,
        tss=body.tss,
        is_completed=True,
    )
    db.add(workout)
    await db.commit()
    await db.refresh(workout)

    # Trigger background recalculation of training load
    background_tasks.add_task(recalculate_athlete_load, db, str(athlete.id), 90)

    return _workout_to_dict(workout)


@router.post("/sync/strava", summary="Importar atividades recentes do Strava")
async def sync_strava(
    background_tasks: BackgroundTasks,
    days_back: int = Query(7, ge=1, le=60),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select as _select
    from app.models.athlete import PlatformConnection
    from app.services.strava_service import StravaService, get_valid_access_token

    conn_result = await db.execute(
        _select(PlatformConnection).where(
            PlatformConnection.athlete_id == athlete.id,
            PlatformConnection.provider == "strava",
            PlatformConnection.is_active == True,
        )
    )
    conn = conn_result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=400, detail="Strava não conectado")

    access_token = await get_valid_access_token(db, conn)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token Strava inválido ou expirado")

    svc = StravaService()
    imported_ids = await svc.sync_recent_activities(
        db, str(athlete.id), access_token,
        days_back=days_back,
        ftp=athlete.ftp_watts, max_hr=athlete.max_hr, resting_hr=athlete.resting_hr,
    )

    if imported_ids:
        background_tasks.add_task(recalculate_athlete_load, db, str(athlete.id), 90)

    return {
        "imported": len(imported_ids),
        "workout_ids": imported_ids,
        "detail": f"{len(imported_ids)} atividade(s) importada(s) dos últimos {days_back} dias",
    }


@router.get("/{workout_id}/adherence", summary="Análise de aderência: planejado vs executado")
async def get_adherence(
    workout_id: str,
    rec_date: str | None = Query(None, description="ISO date of the recommendation to compare against"),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as _date
    from sqlalchemy import select as _select
    from app.models.recommendation import AIRecommendation
    from app.utils.adherence import analyze_workout_adherence

    wkt_result = await db.execute(
        select(Workout).where(Workout.id == workout_id, Workout.athlete_id == athlete.id)
    )
    workout = wkt_result.scalar_one_or_none()
    if not workout:
        raise HTTPException(status_code=404, detail="Treino não encontrado")

    # Find matching recommendation (by date or explicit rec_date)
    target_date = _date.fromisoformat(rec_date) if rec_date else (
        workout.start_time.date() if workout.start_time else None
    )
    if not target_date:
        raise HTTPException(status_code=400, detail="Não foi possível determinar a data para comparação")

    rec_result = await db.execute(
        _select(AIRecommendation).where(
            AIRecommendation.athlete_id == athlete.id,
            AIRecommendation.recommendation_date == target_date,
        )
    )
    rec = rec_result.scalar_one_or_none()
    if not rec or not rec.structured_plan:
        return {"detail": "Nenhuma recomendação encontrada para esta data", "followed": None}

    wkt_dict = {
        "duration_seconds": workout.duration_seconds,
        "tss": float(workout.tss) if workout.tss else None,
        "normalized_power_watts": workout.normalized_power_watts,
        "avg_heart_rate": workout.avg_heart_rate,
    }
    report = analyze_workout_adherence(rec.structured_plan, wkt_dict)

    return {
        "workout_id": str(workout.id),
        "recommendation_date": str(target_date),
        "followed": report.followed,
        "tss_planned": report.tss_planned,
        "tss_actual": report.tss_actual,
        "tss_deviation_pct": report.tss_deviation_pct,
        "duration_planned_min": report.duration_planned_min,
        "duration_actual_min": report.duration_actual_min,
        "duration_deviation_pct": report.duration_deviation_pct,
        "rpe_planned": report.rpe_planned,
        "rpe_actual": report.rpe_actual,
        "rpe_deviation": report.rpe_deviation,
        "summary": report.summary,
        "adjustment_hint": report.adjustment_hint,
    }


@router.delete("/{workout_id}", summary="Remover treino")
async def delete_workout(
    workout_id: str,
    background_tasks: BackgroundTasks,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workout).where(Workout.id == workout_id, Workout.athlete_id == athlete.id)
    )
    workout = result.scalar_one_or_none()
    if not workout:
        raise HTTPException(status_code=404, detail="Treino não encontrado")
    await db.delete(workout)
    await db.commit()
    background_tasks.add_task(recalculate_athlete_load, db, str(athlete.id), 90)
    return {"detail": "Treino removido"}
