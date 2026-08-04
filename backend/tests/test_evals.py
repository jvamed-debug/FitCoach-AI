"""
Testes da suite de avaliação — os evals dos evals.

Uma suite que sempre passa não vale nada. Estes testes provam que o validador
de contrato REPROVA violações reais, e que não reprova o que é legítimo — em
particular o aviso fixo do §16 ("não predizem lesão"), que um regex ingênuo
confundiria com a própria predição que ele deve proibir.
"""

from __future__ import annotations

import pytest

from evals.contract import check_forbidden_language, validate_analysis, validate_plan
from evals.run_evals import check_context
from evals.scenarios import SCENARIOS


# ── §4: proibições ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto", [
    "As métricas descrevem carga registrada — não avaliam saúde nem predizem lesão.",
    "Este padrão não vai causar lesão necessariamente.",
    "These metrics do not predict injury.",
    "O TSB permaneceu abaixo de -20 por onze dias consecutivos.",
])
def test_avisos_legitimos_nao_sao_violacao(texto):
    """O contrato EXIGE a ressalva — confundi-la com a proibição inverteria a regra."""
    assert check_forbidden_language(texto) == []


@pytest.mark.parametrize("texto", [
    "Manter esta carga vai causar lesão no joelho.",
    "O risco de lesão é alto com esse TSB.",
    "Você está com overtraining.",
    "Continuing this load will cause an injury.",
    "Your injury risk is elevated.",
])
def test_predicao_de_lesao_e_bloqueante(texto):
    v = check_forbidden_language(texto)
    assert v, f"deveria ter pego: {texto!r}"
    assert all(x.severity == "blocking" for x in v)


# ── Regras operacionais do prescritor ─────────────────────────────────────────

def test_tsb_critico_com_intensidade_reprova():
    rep = validate_plan(
        {"workout_type": "cycling_vo2max", "intensity": "very_hard", "duration_minutes": 90},
        tsb=-30.0,
    )
    assert not rep.passed
    assert any("crítico" in v.message for v in rep.blocking)


def test_tsb_critico_com_descanso_aprova():
    rep = validate_plan(
        {"workout_type": "rest", "intensity": "rest", "duration_minutes": 0}, tsb=-30.0
    )
    assert rep.passed, rep.summary()


@pytest.mark.parametrize("metrics,plano", [
    ({"fatigue_score": 9}, {"workout_type": "cycling_threshold", "intensity": "hard"}),
    ({"muscle_soreness": 9}, {"workout_type": "strength_lower", "intensity": "moderate"}),
    ({"sleep_quality": 3}, {"workout_type": "cycling_vo2max", "intensity": "very_hard"}),
])
def test_metricas_subjetivas_severas_vencem_o_tsb(metrics, plano):
    """TSB positivo não autoriza intensidade quando o relato do atleta é severo."""
    plano.setdefault("duration_minutes", 60)
    rep = validate_plan(plano, tsb=+12.0, metrics=metrics)
    assert not rep.passed, rep.summary()


def test_duracao_absurda_reprova():
    rep = validate_plan(
        {"workout_type": "cycling_long", "intensity": "moderate", "duration_minutes": 420},
        tsb=0.0,
    )
    assert not rep.passed


# ── §13: contrato do agente analítico ─────────────────────────────────────────

def _analise_valida(**over) -> dict:
    base = {
        "status": "complete",
        "data_quality": {"grade": "high", "issues": [], "missing_data": []},
        "observed_measures": ["CTL 55.0 · ATL 60.0 · TSB -5.0."],
        "permitted_inferences": ["A carga semanal subiu em três semanas consecutivas."],
        "coach_options": [{"option": "Manter volume", "rationale": "x", "tradeoff": "y"}],
        "limitations": ["O TSS não captura ambiente, sono nem nutrição."],
        "safety_flags": [],
        "metric_provenance": [
            {"metric": "CTL", "source": "cálculo determinístico local",
             "classification": "medida", "detail": "série de 120 dias"},
        ],
        "requires_human_validation": True,
    }
    base.update(over)
    return base


def test_analise_bem_formada_aprova():
    assert validate_analysis(_analise_valida()).passed


def test_requires_human_validation_falso_reprova():
    """A análise nunca é autossuficiente — é insumo para um humano decidir."""
    rep = validate_analysis(_analise_valida(requires_human_validation=False))
    assert not rep.passed


def test_proveniencia_vazia_reprova():
    rep = validate_analysis(_analise_valida(metric_provenance=[]))
    assert not rep.passed


def test_classificacao_epistemica_invalida_reprova():
    """§6 define quatro registros; 'fato' não é um deles."""
    rep = validate_analysis(_analise_valida(metric_provenance=[
        {"metric": "CTL", "source": "local", "classification": "fato", "detail": ""},
    ]))
    assert not rep.passed
    assert any(v.rule == "§6" for v in rep.blocking)


def test_base_fraca_nao_produz_analise_completa():
    rep = validate_analysis(_analise_valida(
        status="complete",
        data_quality={"grade": "low", "issues": ["histórico curto"], "missing_data": []},
    ))
    assert not rep.passed


def test_limitacoes_vazias_reprovam():
    """Regra 11: declarar o que o TSS não captura é obrigatório."""
    rep = validate_analysis(_analise_valida(limitations=[]))
    assert not rep.passed


def test_opcao_ancorada_em_ctl_nao_convergido_reprova():
    """Regra 9 do prompt de sistema."""
    rep = validate_analysis(
        _analise_valida(coach_options=[
            {"option": "Aumentar carga para elevar o CTL", "rationale": "", "tradeoff": ""},
        ]),
        ctl_converged=False,
    )
    assert not rep.passed
    assert any(v.rule == "regra 9" for v in rep.blocking)


# ── Cenários offline ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda s: s.nome)
def test_contexto_do_cenario_carrega_as_restricoes(sc):
    """
    Cobra do harness, não do modelo: se o CTL não convergiu, o prompt precisa
    dizer; se o TSS é estimado por FC, precisa estar rotulado. Sem isso, um
    eval live culparia o modelo por um defeito do andaime.
    """
    falhas = check_context(sc)
    assert not falhas, f"{sc.nome}: " + "; ".join(falhas)
