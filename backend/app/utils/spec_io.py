"""
Serialização do contexto interno para o modelo de entrada do §12.

O AthleteContext já é o "modelo interno normalizado" que o §19 exige — este
módulo não cria um segundo modelo, ele traduz o existente para o vocabulário da
spec. O ganho é auditabilidade: dá para ver exatamente o que o agente recebeu,
nos termos do contrato, sem ler o prompt renderizado.

Serve também ao §17: o protocolo de validação precisa de um documento de
entrada estável para comparar execuções entre versões do algoritmo.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.services.ai_service import AthleteContext, DataQualityReport


def to_spec_input(
    ctx: "AthleteContext",
    *,
    athlete_id: str,
    timezone: str,
    quality: "DataQualityReport | None" = None,
    request: str = "",
) -> dict:
    """Constrói o documento do §12 a partir do contexto montado."""
    hoje = date.today()

    return {
        "athlete": {
            "id": athlete_id,
            "timezone": timezone,
            "sport_profile": list(ctx.sport_modalities or []),
            "goals": [ctx.goal] if ctx.goal else [],
            "thresholds": {
                "ftp_watts": ctx.ftp_watts,
                # O app não guarda pace limiar nem histórico de vigência dos
                # limiares. Declarar null é o comportamento correto: o §4 proíbe
                # inventar valor ausente, e o effective_from é uma pendência
                # honesta do modelo de dados, não um campo a preencher com hoje.
                "threshold_pace_sec_per_km": None,
                "threshold_hr_bpm": ctx.max_hr,
                "effective_from": None,
            },
        },
        "analysis_period": {
            "start": (hoje - timedelta(days=max(ctx.history_days, 1))).isoformat(),
            "end": hoje.isoformat(),
        },
        "data_quality": {
            "daily_series_dense": True,   # a série é densificada no cálculo (§8.7)
            "ctl_converged": ctx.ctl_converged,
            "history_days": ctx.history_days,
            "official_seed_imported": False,   # sem integração TrainingPeaks (§11)
            "grade": (
                {"ok": "high", "degraded": "moderate", "insufficient": "low"}
                .get(quality.level, "low") if quality else None
            ),
            "issues": [c.message for c in quality.checks] if quality else [],
        },
        "activities": [
            {
                "sport": w.get("sport_type"),
                "source": w.get("source"),
                "start_time": w.get("start_time"),
                "duration_seconds": w.get("duration_seconds"),
                "tss": w.get("tss"),
                "tss_source": w.get("tss_method"),
                "normalized_power_watts": w.get("normalized_power_watts"),
                "avg_hr_bpm": w.get("avg_heart_rate"),
            }
            for w in ctx.recent_workouts
        ],
        "daily_load": [{
            "date": hoje.isoformat(),
            "ctl": ctx.ctl, "atl": ctx.atl, "tsb": ctx.tsb,
            "daily_tss": ctx.daily_tss, "weekly_tss": ctx.weekly_tss,
        }],
        # Vazio por construção: sem contrato autorizado do TrainingPeaks não há
        # PMC oficial, e o §11 proíbe presumir endpoints para preenchê-lo.
        "official_pmc": [],
        "subjective_metrics": [
            dict(ctx.latest_metrics, date=hoje.isoformat())
        ] if ctx.latest_metrics else [],
        # O §9 lista o contexto que o TSS não captura; o app não coleta nenhum
        # desses campos hoje. A lista vazia é a declaração honesta disso.
        "environmental_context": [],
        "request": request,
        # Extensão fora do §12: o feedback não existia no contrato original, mas
        # omiti-lo tornaria o documento incompleto como registro de auditoria.
        "athlete_feedback": ctx.recent_feedback,
    }
