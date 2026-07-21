"""
Recommendation endpoints.

GET  /api/recommendations/today         — returns today's rec, generates if absent
POST /api/recommendations/generate      — force regenerate today's rec
GET  /api/recommendations               — history (paginated)
GET  /api/recommendations/{id}          — single rec
POST /api/recommendations/{id}/feedback — rate + notes
GET  /api/recommendations/fatigue       — fatigue analysis summary
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_lgpd_consent
from app.models.athlete import Athlete
from app.models.recommendation import AIRecommendation
from app.services.ai_service import AIService, build_athlete_context

router = APIRouter()
logger = logging.getLogger(__name__)

_ai_service = AIService()


# ── Serialiser ────────────────────────────────────────────────────────────────

def _rec_dict(r: AIRecommendation) -> dict:
    return {
        "id": str(r.id),
        "athlete_id": str(r.athlete_id),
        "recommendation_date": r.recommendation_date.isoformat() if r.recommendation_date else None,
        "ai_provider": r.ai_provider,
        "ai_model": r.ai_model,
        "workout_type": r.workout_type,
        "title": r.title,
        "recommendation_text": r.recommendation_text,
        "structured_plan": r.structured_plan,
        "nutrition_plan": r.nutrition_plan,
        "rationale": r.rationale,
        "tokens_used": r.tokens_used,
        "generation_time_ms": r.generation_time_ms,
        "feedback_rating": r.feedback_rating,
        "feedback_notes": r.feedback_notes,
        "was_followed": r.was_followed,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


async def _generate_and_save(db: AsyncSession, athlete: Athlete) -> AIRecommendation:
    """Build context → call AI → persist recommendation."""
    ctx = await build_athlete_context(db, str(athlete.id))
    if not ctx:
        raise HTTPException(status_code=404, detail="Contexto do atleta não encontrado")

    rec = await _ai_service.generate_recommendation(ctx)

    today = date.today()
    stmt = pg_insert(AIRecommendation.__table__).values(
        athlete_id=athlete.id,
        recommendation_date=today,
        ai_provider=rec.ai_provider,
        ai_model=rec.ai_model,
        workout_type=rec.workout_type,
        title=rec.title,
        recommendation_text=rec.recommendation_text,
        structured_plan=rec.structured_plan,
        nutrition_plan=rec.nutrition_plan,
        rationale=rec.rationale,
        tokens_used=rec.tokens_used,
        generation_time_ms=rec.generation_time_ms,
        input_context={"tsb": ctx.tsb, "ctl": ctx.ctl, "atl": ctx.atl, "metrics_missing": ctx.metrics_missing},
    ).on_conflict_do_update(
        index_elements=["athlete_id", "recommendation_date"],
        set_={
            "ai_provider": rec.ai_provider,
            "ai_model": rec.ai_model,
            "workout_type": rec.workout_type,
            "title": rec.title,
            "recommendation_text": rec.recommendation_text,
            "structured_plan": rec.structured_plan,
            "nutrition_plan": rec.nutrition_plan,
            "rationale": rec.rationale,
            "tokens_used": rec.tokens_used,
            "generation_time_ms": rec.generation_time_ms,
        },
    ).returning(AIRecommendation.__table__)

    result = await db.execute(stmt)
    await db.commit()
    row = result.fetchone()

    # Re-fetch ORM object
    obj_result = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.athlete_id == athlete.id,
            AIRecommendation.recommendation_date == today,
        )
    )
    return obj_result.scalar_one()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/today", summary="Recomendação de hoje (gera se não existir)")
async def get_today(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    result = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.athlete_id == athlete.id,
            AIRecommendation.recommendation_date == today,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return _rec_dict(existing)

    # Generate on-demand
    saved = await _generate_and_save(db, athlete)
    return _rec_dict(saved)


@router.post("/generate", status_code=201, summary="Forçar nova geração da recomendação de hoje")
async def force_generate(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    saved = await _generate_and_save(db, athlete)
    return _rec_dict(saved)


@router.get("/fatigue", summary="Análise de fadiga atual")
async def get_fatigue(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    ctx = await build_athlete_context(db, str(athlete.id))
    if not ctx:
        raise HTTPException(status_code=404, detail="Contexto não encontrado")
    return await _ai_service.analyze_fatigue(ctx)


@router.get("", summary="Histórico de recomendações")
async def list_recommendations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count(AIRecommendation.id))
        .where(AIRecommendation.athlete_id == athlete.id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(AIRecommendation)
        .where(AIRecommendation.athlete_id == athlete.id)
        .order_by(desc(AIRecommendation.recommendation_date))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    recs = result.scalars().all()

    return {
        "items": [_rec_dict(r) for r in recs],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{rec_id}", summary="Detalhes de uma recomendação")
async def get_recommendation(
    rec_id: str,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.id == rec_id,
            AIRecommendation.athlete_id == athlete.id,
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recomendação não encontrada")
    return _rec_dict(rec)


@router.post("/{rec_id}/push-to-strava", summary="Enviar treino planejado ao Strava")
async def push_to_strava(
    rec_id: str,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select as _sel
    from app.models.athlete import PlatformConnection
    from app.services.strava_service import StravaService, get_valid_access_token

    rec_result = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.id == rec_id,
            AIRecommendation.athlete_id == athlete.id,
        )
    )
    rec = rec_result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recomendação não encontrada")

    conn_result = await db.execute(
        _sel(PlatformConnection).where(
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
        raise HTTPException(status_code=401, detail="Token Strava inválido")

    # Map workout_type → Strava sport_type
    sport_map = {
        "cycling_endurance": "Ride", "cycling_threshold": "Ride",
        "cycling_vo2max": "Ride", "cycling_long": "Ride",
        "running_easy": "Run", "running_tempo": "Run", "running_intervals": "Run",
        "swimming_base": "Swim", "swimming_intervals": "Swim",
        "strength_upper": "WeightTraining", "strength_lower": "WeightTraining",
        "strength_full": "WeightTraining", "strength_push": "WeightTraining",
        "strength_pull": "WeightTraining", "triathlon_brick": "Workout",
        "mobility": "Yoga", "rest": "Workout",
    }
    strava_sport = sport_map.get(rec.workout_type or "", "Workout")
    plan = rec.structured_plan or {}
    duration_s = (plan.get("duration_minutes") or 60) * 60

    svc = StravaService()
    try:
        result = await svc.create_planned_workout(
            access_token=access_token,
            name=rec.title or "AI Recommended Workout",
            sport_type=strava_sport,
            planned_date=str(rec.recommendation_date),
            description=rec.rationale or "",
            duration_seconds=duration_s,
        )
        return {"detail": "Treino enviado ao Strava", "strava_workout_id": result.get("id")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao enviar para o Strava: {e}")


@router.post("/{rec_id}/push-to-trainingpeaks", summary="Enviar treino planejado ao TrainingPeaks")
async def push_to_trainingpeaks(
    rec_id: str,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    from app.services.tp_sync import push_recommendation_to_trainingpeaks
    result = await push_recommendation_to_trainingpeaks(db, str(athlete.id), rec_id)
    if result is None:
        raise HTTPException(status_code=400, detail="TrainingPeaks não conectado ou erro no envio")
    return {"detail": "Treino enviado ao TrainingPeaks", "tp_workout_id": result.get("id")}


class FeedbackRequest(BaseModel):
    rating: int  # 1–5
    notes: str | None = None
    was_followed: bool | None = None


@router.post("/{rec_id}/feedback", summary="Registrar feedback da recomendação")
async def submit_feedback(
    rec_id: str,
    body: FeedbackRequest,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    if not (1 <= body.rating <= 5):
        raise HTTPException(status_code=400, detail="Rating deve ser entre 1 e 5")

    result = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.id == rec_id,
            AIRecommendation.athlete_id == athlete.id,
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recomendação não encontrada")

    rec.feedback_rating = body.rating
    rec.feedback_notes = body.notes
    if body.was_followed is not None:
        rec.was_followed = body.was_followed

    db.add(rec)
    await db.commit()
    return {"detail": "Feedback registrado", "rating": body.rating}
