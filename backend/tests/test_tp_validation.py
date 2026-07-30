"""
Testes do protocolo de validação contra o TrainingPeaks (§17).

Não dependem da API do TrainingPeaks: exercitam o harness com séries sintéticas
onde a causa da divergência é conhecida, verificando que a escada de diagnóstico
do §17.6 identifica a causa certa. Isso é o critério de aceite do §19,
"testes comparativos preparados para dados oficiais".
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

from scripts.validate_against_tp import (
    CTL_TOLERANCE,
    OfficialPoint,
    compare,
    diagnose,
    local_series,
)

A_CTL = 1 - math.exp(-1 / 42)
A_ATL = 1 - math.exp(-1 / 7)
START = date(2025, 1, 1)


def _make_tss(n: int, seed: int = 11) -> list[float]:
    """Série de TSS com segundas-feiras de descanso. O dia 0 é zero de propósito:
    elimina o efeito de borda ao testar realinhamento de datas."""
    rng = random.Random(seed)
    return [0.0] + [
        0.0 if (START + timedelta(days=i)).weekday() == 0 else round(rng.uniform(40, 140), 1)
        for i in range(1, n)
    ]


def _official(
    tss: list[float],
    *,
    report_shifted: bool = False,
    start_ctl: float = 0.0,
    start_atl: float = 0.0,
) -> list[OfficialPoint]:
    """Constrói a série 'oficial' a partir do TSS verdadeiro.

    Com report_shifted, o TSS reportado sai um dia depois do que gerou o PMC —
    é assim que um erro de fuso se manifesta num export.

    Com start_ctl/start_atl, o atleta já chega com condicionamento acumulado
    antes da janela exportada — o caso de semeadura insuficiente do §17.6.
    """
    ctl, atl = start_ctl, start_atl
    prev = (start_ctl, start_atl)
    points: list[OfficialPoint] = []
    for i, t in enumerate(tss):
        ctl += (t - ctl) * A_CTL
        atl += (t - atl) * A_ATL
        points.append(OfficialPoint(
            day=START + timedelta(days=i),
            tss=(tss[i - 1] if i > 0 else 0.0) if report_shifted else t,
            ctl=round(ctl, 4),
            atl=round(atl, 4),
            tsb=round(prev[0] - prev[1], 4),   # convenção do dia anterior
        ))
        prev = (ctl, atl)
    return points


def test_serie_coerente_passa_no_criterio():
    """Série gerada pelo mesmo algoritmo deve bater dentro da tolerância (§17.5)."""
    points = _official(_make_tss(200))
    result = compare(points, local_series(points))

    assert result["matched"] == 200
    assert result["max_abs_ctl"] < CTL_TOLERANCE
    # O acordo deve ser muito melhor que a tolerância — só resíduo de arredondamento.
    assert result["max_abs_ctl"] < 0.01


def test_desvio_de_fuso_e_diagnosticado_primeiro():
    """§17.6: fuso horário é a primeira causa da escada e deve ser identificada."""
    points = _official(_make_tss(210), report_shifted=True)
    result = compare(points, local_series(points))

    assert result["max_abs_ctl"] > CTL_TOLERANCE, "o desvio deveria reprovar"

    findings = diagnose(points, result)
    assert findings, "a escada de diagnóstico não apontou causa alguma"
    assert "FUSO HORÁRIO" in findings[0]
    # Uma causa dominante interrompe a escada: corrigi-la primeiro é o protocolo.
    assert len(findings) == 1


def test_realinhamento_de_um_dia_zera_o_erro():
    """Confirma que o deslocamento é de fato a causa, não uma coincidência."""
    points = _official(_make_tss(210), report_shifted=True)
    realigned = compare(points, local_series(points, date_shift_days=-1))

    assert realigned["max_abs_ctl"] < 0.01


def test_semeadura_insuficiente_e_detectada():
    """§17.6: erro concentrado no início indica semeadura incorreta.

    Cenário real: o atleta já vinha treinando (CTL 45) quando a janela exportada
    começa, mas o cálculo local parte do zero.
    """
    points = _official(_make_tss(200), start_ctl=45.0, start_atl=45.0)
    result = compare(points, local_series(points))   # local semeia em zero

    assert result["max_abs_ctl"] > CTL_TOLERANCE
    findings = diagnose(points, result)
    assert any("SEMEADURA" in f for f in findings), findings


def test_diagnostico_usa_a_mesma_semeadura_do_baseline():
    """
    Contra-hipóteses semeadas de forma diferente do baseline comparam séries
    distintas e apontam causas falsas — a semeadura precisa ser propagada.
    """
    points = _official(_make_tss(200))
    seeded = compare(points, local_series(points, seed_ctl=45.0, seed_atl=45.0))

    # Sem propagar a semeadura, o teste de fuso enxerga uma melhora enorme que
    # vem só da diferença de semeadura, e acusa fuso horário falsamente.
    assert "FUSO HORÁRIO" in diagnose(points, seeded)[0]

    # Propagando, a causa espúria desaparece.
    coherent = diagnose(points, seeded, seed_ctl=45.0, seed_atl=45.0)
    assert not any("FUSO HORÁRIO" in f for f in coherent), coherent
