"""
Ida e volta da disponibilidade: o que a tela salva é o que o agente lê.

Até agora FTP e disponibilidade só existiam nas telas de admin — um atleta
autônomo não tinha onde informá-los, o que tornava inalcançável toda a cadeia
de carga (TSS → CTL/ATL/TSB → recomendação personalizada por tempo e
modalidade). Estes testes prendem o contrato entre as duas pontas.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.routers.auth import ProfileUpdateRequest
from app.utils.availability import describe_for_prompt, normalize, scheduled_for

TERCA = date(2026, 1, 20)


# Exatamente o corpo que o editor da tela de Configurações envia.
PAYLOAD_DO_EDITOR = {
    "ftp_watts": 250,
    "max_hr": 185,
    "resting_hr": 52,
    "goal": "Gran fondo de 120 km em outubro",
    "weekly_availability": {
        "cycling": {"days": ["tue", "thu", "sat"], "minutes": 90},
        "strength": {"days": ["mon", "fri"], "minutes": 45},
    },
}


def test_endpoint_de_perfil_aceita_o_payload_do_editor():
    req = ProfileUpdateRequest(**PAYLOAD_DO_EDITOR)
    assert req.ftp_watts == 250
    assert req.max_hr == 185 and req.resting_hr == 52
    assert set(req.weekly_availability) == {"cycling", "strength"}


def test_o_que_a_tela_salva_chega_ao_prompt_com_duracao():
    req = ProfileUpdateRequest(**PAYLOAD_DO_EDITOR)
    linhas = "\n".join(describe_for_prompt(req.weekly_availability, TERCA))
    assert "cycling: tue, thu, sat — up to 90 min" in linhas
    assert "Scheduled for this day: cycling (90 min)" in linhas


def test_modalidade_sem_dia_nao_deveria_chegar():
    """
    O editor descarta modalidades sem dia antes de enviar; se alguma passar,
    a normalização também a ignora. Ausência = "não pratico", que é diferente
    de "pratico zero minutos".
    """
    n = normalize({"swimming": {"days": [], "minutes": 60}})
    assert "swimming" not in n


def test_limpar_um_campo_envia_null_e_nao_zero():
    """
    Campo em branco vira null: "não informado" e "zero" são estados
    diferentes, e o agente trata cada um de um jeito.
    """
    req = ProfileUpdateRequest(ftp_watts=None, max_hr=None, goal=None)
    assert req.ftp_watts is None and req.max_hr is None and req.goal is None


def test_perfil_legado_continua_legivel_pela_tela_e_pelo_agente():
    """Perfis gravados antes do editor têm só a lista de dias."""
    req = ProfileUpdateRequest(weekly_availability={"cycling": ["tue", "thu"]})
    n = normalize(req.weekly_availability)
    assert n["cycling"]["days"] == ["tue", "thu"]
    assert n["cycling"]["minutes"] is None
    assert "duration not declared" in "\n".join(
        describe_for_prompt(req.weekly_availability, TERCA)
    )


@pytest.mark.parametrize("dia,esperado", [
    (date(2026, 1, 20), {"cycling"}),          # terça
    (date(2026, 1, 19), {"strength"}),         # segunda
    (date(2026, 1, 21), set()),                # quarta — dia livre
])
def test_agenda_do_dia_bate_com_o_que_foi_salvo(dia, esperado):
    req = ProfileUpdateRequest(**PAYLOAD_DO_EDITOR)
    assert {a["modality"] for a in scheduled_for(req.weekly_availability, dia)} == esperado
