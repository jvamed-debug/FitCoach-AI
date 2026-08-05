"""
Disponibilidade: modalidade e tempo do dia da sessão.

Prescrever sem saber o tempo disponível produz o erro mais irritante possível —
um treino de 90 min num dia em que o atleta tem 40. E prescrever sem saber QUE
DIA é torna a agenda semanal inútil: "cycling: tue, thu, sat" não diz nada se o
agente não sabe que hoje é terça.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.utils.availability import (
    describe_for_prompt,
    normalize,
    scheduled_for,
    weekday_key,
)

TERCA = date(2026, 1, 20)     # terça-feira
QUARTA = date(2026, 1, 21)    # quarta-feira


def test_weekday_key_casa_com_a_convencao_do_campo():
    assert weekday_key(TERCA) == "tue"
    assert weekday_key(QUARTA) == "wed"
    assert weekday_key(date(2026, 1, 25)) == "sun"


# ── Compatibilidade com o formato legado ──────────────────────────────────────

def test_formato_legado_continua_valido():
    """Há dados em produção como lista de dias; migração é por leitura."""
    n = normalize({"cycling": ["tue", "thu"]})
    assert n == {"cycling": {"days": ["tue", "thu"], "minutes": None}}


def test_formato_novo_carrega_minutos():
    n = normalize({"cycling": {"days": ["tue"], "minutes": 90}})
    assert n["cycling"]["minutes"] == 90


def test_as_duas_formas_convivem():
    n = normalize({
        "cycling": {"days": ["tue"], "minutes": 90},
        "strength": ["mon", "fri"],
    })
    assert n["cycling"]["minutes"] == 90
    assert n["strength"]["minutes"] is None


@pytest.mark.parametrize("ruim", [None, {}, {"cycling": "terça"}, {"cycling": []}])
def test_entradas_invalidas_nao_quebram(ruim):
    assert normalize(ruim) == {}


def test_minutos_invalidos_viram_none():
    """Zero ou negativo é dado ruim, não 'sem tempo' — melhor tratar como ausente."""
    for m in (0, -30, "noventa", None):
        assert normalize({"cycling": {"days": ["tue"], "minutes": m}})["cycling"]["minutes"] is None


def test_dias_desconhecidos_sao_descartados():
    n = normalize({"cycling": ["tue", "terça", "xyz"]})
    assert n["cycling"]["days"] == ["tue"]


# ── O que está agendado para o dia ────────────────────────────────────────────

def test_agenda_do_dia():
    weekly = {"cycling": {"days": ["tue", "thu"], "minutes": 90},
              "strength": ["mon", "tue"]}
    agendado = scheduled_for(weekly, TERCA)
    assert {a["modality"] for a in agendado} == {"cycling", "strength"}
    assert next(a for a in agendado if a["modality"] == "cycling")["minutes"] == 90


def test_dia_livre_devolve_vazio():
    assert scheduled_for({"cycling": ["tue"]}, QUARTA) == []


# ── Renderização para o prompt ────────────────────────────────────────────────

def test_prompt_declara_o_que_esta_agendado():
    linhas = "\n".join(describe_for_prompt({"cycling": {"days": ["tue"], "minutes": 90}}, TERCA))
    assert "Scheduled for this day: cycling (90 min)" in linhas


def test_prompt_diz_quando_a_duracao_nao_foi_declarada():
    """'Não declarado' é diferente de 'sem limite' — o agente trata os dois diferente."""
    linhas = "\n".join(describe_for_prompt({"cycling": ["tue"]}, TERCA))
    assert "duration not declared" in linhas


def test_dia_livre_e_informacao_e_nao_lacuna_a_preencher():
    linhas = "\n".join(describe_for_prompt({"cycling": ["tue"]}, QUARTA))
    assert "NOTHING" in linhas
    assert "rest, mobility" in linhas


def test_sem_disponibilidade_declarada_nao_gera_ruido():
    assert describe_for_prompt(None, TERCA) == []


# ── Integração com o prompt do agente ─────────────────────────────────────────

def test_prompt_informa_o_dia_da_sessao():
    """
    Sem isto o agente não consegue cruzar a agenda semanal com nada — era o
    caso antes: ele via os dias disponíveis e não sabia qual era hoje.
    """
    from app.services.ai_service import format_athlete_context
    from evals.scenarios import by_name

    ctx = by_name("tsb_critico").contexto
    ctx.target_date = TERCA
    ctx.weekly_availability = {"cycling": {"days": ["tue"], "minutes": 60}}

    prompt = format_athlete_context(ctx)
    assert "2026-01-20" in prompt
    assert "terça-feira" in prompt
    assert "cycling (60 min)" in prompt


def test_override_do_dia_aparece_como_teto_rigido():
    from app.services.ai_service import format_athlete_context
    from evals.scenarios import by_name

    ctx = by_name("tsb_critico").contexto
    ctx.target_date = TERCA
    ctx.available_minutes = 40
    ctx.preferred_modality = "swimming"

    prompt = format_athlete_context(ctx)
    assert "TIME AVAILABLE TODAY: 40 minutes" in prompt
    assert "HARD ceiling" in prompt
    assert "MODALITY REQUESTED TODAY: swimming" in prompt


def test_prompt_nao_pede_mais_a_sessao_de_amanha():
    """
    O prompt pedia "TOMORROW" enquanto a recomendação era gravada e exibida
    como a de hoje — o agente planejava um dia e o atleta lia outro.
    """
    from app.services.ai_service import SYSTEM_PROMPT

    assert "session for TOMORROW" not in SYSTEM_PROMPT
    assert "THE DAY NAMED IN THE CONTEXT" in SYSTEM_PROMPT
