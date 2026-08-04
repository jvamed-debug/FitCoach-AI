"""
Endpoints do agente analítico (§13–15 do contrato).

GET /api/ai/analysis — análise auditável do estado de treino do atleta.

Distinto de /api/recommendations, que PRESCREVE uma sessão. Aqui o agente
ANALISA e apresenta opções para validação de um treinador humano; a saída
sempre carrega requires_human_validation=true.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_lgpd_consent
from app.models.athlete import Athlete
from app.services.ai_service import assess_data_quality, build_athlete_context
from app.services.analysis_service import AnalysisService
from app.utils.spec_io import to_spec_input

router = APIRouter()
logger = logging.getLogger(__name__)

_analysis_service = AnalysisService()


@router.get("/analysis", summary="Análise auditável do estado de treino (§13–15)")
async def get_analysis(
    include_input: bool = Query(
        False,
        description="Anexa o documento de entrada do §12 — exatamente o que o "
                    "agente recebeu, no vocabulário do contrato. Para auditoria "
                    "e para o protocolo de validação do §17.",
    ),
    athlete: Athlete = Depends(require_lgpd_consent),
    db: AsyncSession = Depends(get_db),
):
    ctx = await build_athlete_context(db, str(athlete.id))
    if not ctx:
        raise HTTPException(status_code=404, detail="Contexto do atleta não encontrado")

    quality = assess_data_quality(ctx)
    analysis = await _analysis_service.analyze(ctx, quality)

    resposta = analysis.to_dict()
    if include_input:
        resposta["spec_input"] = to_spec_input(
            ctx,
            athlete_id=str(athlete.id),
            timezone=getattr(athlete, "timezone", None) or "America/Sao_Paulo",
            quality=quality,
        )
    return resposta
