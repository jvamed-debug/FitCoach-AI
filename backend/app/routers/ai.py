"""
Endpoints do agente analítico (§13–15 do contrato).

GET /api/ai/analysis — análise auditável do estado de treino do atleta.

Distinto de /api/recommendations, que PRESCREVE uma sessão. Aqui o agente
ANALISA e apresenta opções para validação de um treinador humano; a saída
sempre carrega requires_human_validation=true.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_lgpd_consent
from app.models.athlete import Athlete
from app.services.ai_service import assess_data_quality, build_athlete_context
from app.services.analysis_service import AnalysisService

router = APIRouter()
logger = logging.getLogger(__name__)

_analysis_service = AnalysisService()


@router.get("/analysis", summary="Análise auditável do estado de treino (§13–15)")
async def get_analysis(
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    ctx = await build_athlete_context(db, str(athlete.id))
    if not ctx:
        raise HTTPException(status_code=404, detail="Contexto do atleta não encontrado")

    quality = assess_data_quality(ctx)
    analysis = await _analysis_service.analyze(ctx, quality)
    return analysis.to_dict()
