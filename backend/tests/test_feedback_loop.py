"""
Testes do ciclo de feedback.

O app coletava nota, aderência e notas do atleta e descartava tudo. Agora esse
histórico entra no contexto do agente — mas como INFORMAÇÃO DECLARADA (§5,
nível 4), que revela preferência e aderência, nunca resposta fisiológica.

Estes testes prendem as duas regras que impedem o sinal de virar ruído:
não agregar amostra pequena, e não perder o texto livre (que é o único que
explica o porquê de uma nota).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.ai_service import _MIN_PARA_PADRAO, _summarize_feedback


class Rec:
    """Dublê de AIRecommendation com feedback."""

    def __init__(self, wtype, rating=None, followed=None, notes=None, day=1):
        self.recommendation_date = date(2026, 1, day)
        self.workout_type = wtype
        self.title = f"Sessão {wtype}"
        self.feedback_rating = rating
        self.was_followed = followed
        self.feedback_notes = notes


# ── Limiar de agregação ───────────────────────────────────────────────────────

def test_amostra_pequena_nao_vira_padrao():
    """Duas notas altas não são tendência — só entradas individuais."""
    recs = [Rec("cycling_threshold", rating=5, day=d) for d in (1, 2)]
    entries, patterns = _summarize_feedback(recs)

    assert len(entries) == 2, "as entradas individuais seguem visíveis"
    assert patterns == [], "mas nenhum padrão é declarado"


def test_amostra_suficiente_vira_padrao():
    recs = [Rec("cycling_threshold", rating=r, day=i + 1)
            for i, r in enumerate([5, 4, 5])]
    _, patterns = _summarize_feedback(recs)

    assert len(patterns) == 1
    assert patterns[0]["workout_type"] == "cycling_threshold"
    assert patterns[0]["n"] == _MIN_PARA_PADRAO
    assert patterns[0]["avg_rating"] == pytest.approx(4.7, abs=0.05)


def test_taxa_de_execucao_ignora_nao_informados():
    """was_followed=None é 'não informado', não é 'não executou'."""
    recs = [
        Rec("strength_upper", followed=True, day=1),
        Rec("strength_upper", followed=False, day=2),
        Rec("strength_upper", followed=None, day=3),
    ]
    _, patterns = _summarize_feedback(recs)

    # 1 de 2 informados = 0.5 — o terceiro não entra no denominador.
    assert patterns[0]["followed_rate"] == pytest.approx(0.5)


def test_padroes_ordenados_por_volume():
    recs = (
        [Rec("cycling_endurance", rating=4, day=i + 1) for i in range(5)]
        + [Rec("strength_lower", rating=3, day=i + 10) for i in range(3)]
    )
    _, patterns = _summarize_feedback(recs)

    assert [p["workout_type"] for p in patterns] == ["cycling_endurance", "strength_lower"]


# ── Preservação do texto livre ────────────────────────────────────────────────

def test_notas_do_atleta_sao_preservadas():
    """O texto livre é o único sinal que diz POR QUÊ a nota foi baixa."""
    recs = [Rec("cycling_vo2max", rating=2, notes="Longo demais, não tenho 2h num dia útil")]
    entries, _ = _summarize_feedback(recs)

    assert entries[0]["notes"] == "Longo demais, não tenho 2h num dia útil"


@pytest.mark.parametrize("vazio", ["", "   ", None])
def test_notas_vazias_viram_none(vazio):
    """Evita poluir o prompt com strings em branco."""
    entries, _ = _summarize_feedback([Rec("rest", rating=3, notes=vazio)])
    assert entries[0]["notes"] is None


def test_sem_feedback_devolve_vazio():
    entries, patterns = _summarize_feedback([])
    assert entries == [] and patterns == []


def test_recomendacao_sem_tipo_nao_quebra_agregacao():
    """workout_type nulo entra nas entradas mas não cria um bucket."""
    entries, patterns = _summarize_feedback([Rec(None, rating=4)])
    assert len(entries) == 1
    assert patterns == []
