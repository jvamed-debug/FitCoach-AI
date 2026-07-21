"""
Daily health metrics endpoints.

POST /api/metrics          — upsert today's or any day's metrics
GET  /api/metrics/today    — metrics for today (or None)
GET  /api/metrics          — history with date range
GET  /api/metrics/trends   — 7d and 30d averages
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_lgpd_consent
from app.models.athlete import Athlete
from app.models.metric import DailyMetric

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class MetricInput(BaseModel):
    metric_date: str | None = None          # ISO date; defaults to today
    weight_kg: float | None = None
    sleep_hours: float | None = None
    sleep_quality: int | None = None
    hrv_ms: int | None = None
    resting_hr: int | None = None
    fatigue_score: int | None = None
    muscle_soreness: int | None = None
    stress_score: int | None = None
    motivation_score: int | None = None
    notes: str | None = None

    @field_validator("sleep_quality", "fatigue_score", "muscle_soreness",
                     "stress_score", "motivation_score", mode="before")
    @classmethod
    def validate_scale(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 10):
            raise ValueError("Scale values must be between 1 and 10")
        return v


def _metric_dict(m: DailyMetric) -> dict:
    return {
        "id": str(m.id),
        "athlete_id": str(m.athlete_id),
        "metric_date": m.metric_date.isoformat() if m.metric_date else None,
        "weight_kg": float(m.weight_kg) if m.weight_kg else None,
        "sleep_hours": float(m.sleep_hours) if m.sleep_hours else None,
        "sleep_quality": m.sleep_quality,
        "hrv_ms": m.hrv_ms,
        "resting_hr": m.resting_hr,
        "fatigue_score": m.fatigue_score,
        "muscle_soreness": m.muscle_soreness,
        "stress_score": m.stress_score,
        "motivation_score": m.motivation_score,
        "notes": m.notes,
        "source": m.source,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=200, summary="Registrar ou atualizar métricas do dia (upsert)")
async def upsert_metrics(
    body: MetricInput,
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    target_date = date.fromisoformat(body.metric_date) if body.metric_date else date.today()

    values = {"athlete_id": athlete.id, "metric_date": target_date, "source": "manual"}
    update_set = {}

    for field in (
        "weight_kg", "sleep_hours", "sleep_quality", "hrv_ms", "resting_hr",
        "fatigue_score", "muscle_soreness", "stress_score", "motivation_score", "notes",
    ):
        val = getattr(body, field)
        if val is not None:
            values[field] = val
            update_set[field] = val

    if len(values) == 3:  # only id fields, nothing useful
        raise HTTPException(status_code=400, detail="Nenhuma métrica fornecida")

    stmt = pg_insert(DailyMetric.__table__).values(**values)
    if update_set:
        stmt = stmt.on_conflict_do_update(
            index_elements=["athlete_id", "metric_date"],
            set_=update_set,
        )
    else:
        stmt = stmt.on_conflict_do_nothing()

    await db.execute(stmt)
    await db.commit()

    # Re-fetch to return full object
    result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.athlete_id == athlete.id,
            DailyMetric.metric_date == target_date,
        )
    )
    saved = result.scalar_one()
    return _metric_dict(saved)


@router.get("/today", summary="Métricas de hoje")
async def get_today_metrics(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.athlete_id == athlete.id,
            DailyMetric.metric_date == date.today(),
        )
    )
    m = result.scalar_one_or_none()
    return _metric_dict(m) if m else None


@router.get("/trends", summary="Tendências de 7d e 30d")
async def get_trends(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()

    async def _avg(days: int) -> dict:
        since = today - timedelta(days=days)
        result = await db.execute(
            select(DailyMetric).where(
                DailyMetric.athlete_id == athlete.id,
                DailyMetric.metric_date >= since,
                DailyMetric.metric_date <= today,
            )
        )
        rows = result.scalars().all()
        if not rows:
            return {}

        def _mean(attr: str) -> float | None:
            vals = [getattr(r, attr) for r in rows if getattr(r, attr) is not None]
            return round(mean(vals), 2) if vals else None

        return {
            "n": len(rows),
            "weight_kg":       _mean("weight_kg"),
            "sleep_hours":     _mean("sleep_hours"),
            "sleep_quality":   _mean("sleep_quality"),
            "hrv_ms":          _mean("hrv_ms"),
            "resting_hr":      _mean("resting_hr"),
            "fatigue_score":   _mean("fatigue_score"),
            "muscle_soreness": _mean("muscle_soreness"),
            "stress_score":    _mean("stress_score"),
            "motivation_score":_mean("motivation_score"),
        }

    return {
        "7d":  await _avg(7),
        "30d": await _avg(30),
    }


@router.get("", summary="Histórico de métricas")
async def list_metrics(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=90),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    query = select(DailyMetric).where(DailyMetric.athlete_id == athlete.id)
    if start_date:
        query = query.where(DailyMetric.metric_date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(DailyMetric.metric_date <= date.fromisoformat(end_date))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = (
        query
        .order_by(DailyMetric.metric_date.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    rows = result.scalars().all()

    return {
        "items": [_metric_dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
