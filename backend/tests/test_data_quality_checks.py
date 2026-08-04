"""
Verificações de qualidade de dados do §7 que faltavam.

A mais importante é a duplicidade entre fontes. O caso real: o atleta registra
o treino à mão e depois sincroniza o Strava — a mesma sessão entra duas vezes,
o TSS do dia dobra, e como CTL/ATL/TSB derivam dele, todo número a jusante fica
inflado sem nenhum sinal de erro. Silenciosa e permanente.
"""

from __future__ import annotations

import pytest

from app.services.ai_service import (
    detect_device_change,
    detect_duplicates,
    detect_gaps,
)


def _w(source, hora, dur=3600, sport="cycling", np_watts=None):
    return {
        "source": source,
        "start_time": f"2026-01-20T{hora}:00+00:00",
        "duration_seconds": dur,
        "sport_type": sport,
        "normalized_power_watts": np_watts,
    }


# ── Duplicidade entre fontes ──────────────────────────────────────────────────

def test_mesma_sessao_de_fontes_diferentes_e_duplicata():
    pares = detect_duplicates([_w("manual", "07:00", 3600), _w("strava", "07:05", 3660)])
    assert len(pares) == 1


def test_mesma_fonte_nunca_e_duplicata():
    """Duas sessões da mesma fonte são dois treinos — a dedup é do conector."""
    assert detect_duplicates([_w("strava", "07:00"), _w("strava", "07:05")]) == []


def test_horarios_distantes_nao_sao_duplicata():
    """Duas pedaladas no mesmo dia, de manhã e à tarde, são legítimas."""
    assert detect_duplicates([_w("manual", "07:00"), _w("strava", "09:00")]) == []


def test_duracoes_muito_diferentes_nao_sao_duplicata():
    """1h e 15min no mesmo horário são sessões distintas, não a mesma."""
    assert detect_duplicates([_w("manual", "07:00", 3600), _w("strava", "07:05", 900)]) == []


def test_duracao_ausente_nao_impede_deteccao():
    """Sem duração comparável, horário + fonte distinta já bastam para o aviso."""
    a, b = _w("manual", "07:00"), _w("strava", "07:05")
    a["duration_seconds"] = None
    assert len(detect_duplicates([a, b])) == 1


def test_start_time_invalido_e_ignorado_sem_quebrar():
    a = _w("manual", "07:00")
    a["start_time"] = "não é uma data"
    assert detect_duplicates([a, _w("strava", "07:05")]) == []


# ── Lacunas na série ──────────────────────────────────────────────────────────

def test_lacuna_longa_e_detectada():
    g = detect_gaps([
        {"start_time": "2026-01-01T07:00:00+00:00"},
        {"start_time": "2026-01-25T07:00:00+00:00"},
    ])
    assert len(g) == 1 and g[0][2] == 24


def test_intervalo_normal_nao_e_lacuna():
    assert detect_gaps([
        {"start_time": "2026-01-01T07:00:00+00:00"},
        {"start_time": "2026-01-04T07:00:00+00:00"},
    ]) == []


def test_lacunas_independem_da_ordem_de_entrada():
    """A consulta vem em ordem decrescente; o detector ordena antes de medir."""
    desordenado = [
        {"start_time": "2026-01-25T07:00:00+00:00"},
        {"start_time": "2026-01-01T07:00:00+00:00"},
    ]
    assert len(detect_gaps(desordenado)) == 1


# ── Mudança de dispositivo ────────────────────────────────────────────────────

def test_potencia_intermitente_indica_troca():
    assert detect_device_change([
        _w("strava", "07:00", np_watts=200),
        _w("strava", "08:00", np_watts=None),
        _w("strava", "09:00", np_watts=210),
    ]) is True


@pytest.mark.parametrize("watts", [200, None])
def test_consistencia_nao_indica_troca(watts):
    assert detect_device_change([_w("strava", "07:00", np_watts=watts)] * 3) is False


def test_amostra_pequena_nao_conclui():
    """Duas sessões não bastam para chamar de troca de dispositivo."""
    assert detect_device_change([
        _w("strava", "07:00", np_watts=200),
        _w("strava", "08:00", np_watts=None),
    ]) is False


# ── §12: documento de entrada normalizado ─────────────────────────────────────

def test_spec_input_tem_a_forma_do_contrato():
    """
    O §12 define a forma do documento de entrada. Este serializador não cria um
    segundo modelo — traduz o AthleteContext existente para o vocabulário da
    spec, para que se possa auditar o que o agente recebeu.
    """
    from app.utils.spec_io import to_spec_input
    from evals.scenarios import by_name

    ctx = by_name("ctl_nao_convergido").contexto
    doc = to_spec_input(ctx, athlete_id="atl_1", timezone="America/Sao_Paulo")

    for campo in ("athlete", "analysis_period", "data_quality", "activities",
                  "daily_load", "official_pmc", "subjective_metrics",
                  "environmental_context", "request"):
        assert campo in doc, f"campo do §12 ausente: {campo}"

    assert doc["athlete"]["timezone"] == "America/Sao_Paulo"
    assert doc["data_quality"]["ctl_converged"] is False
    assert doc["data_quality"]["history_days"] == 21


def test_spec_input_nao_inventa_valor_ausente():
    """
    §4: não inventar valores. O app não guarda pace limiar nem a data de
    vigência dos limiares — declarar null é o comportamento correto, e
    preencher com 'hoje' seria fabricar dado.
    """
    from app.utils.spec_io import to_spec_input
    from evals.scenarios import by_name

    doc = to_spec_input(by_name("tsb_critico").contexto,
                        athlete_id="atl_1", timezone="America/Sao_Paulo")
    thr = doc["athlete"]["thresholds"]
    assert thr["threshold_pace_sec_per_km"] is None
    assert thr["effective_from"] is None
    # §11: sem contrato autorizado do TrainingPeaks não existe PMC oficial.
    assert doc["official_pmc"] == []
