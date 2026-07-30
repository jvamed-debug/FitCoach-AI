"""
Protocolo de validação contra dados oficiais do TrainingPeaks (§17).

Compara a série CTL/ATL/TSB calculada localmente com o PMC oficial, ponto a
ponto, e — quando diverge — percorre a escada de causas do §17.6 NA ORDEM
prescrita, testando cada hipótese computacionalmente em vez de deixá-la para
inspeção manual.

Uso:
    python -m scripts.validate_against_tp dados.json
    python -m scripts.validate_against_tp dados.csv --tz America/Sao_Paulo

Formato de entrada (JSON):
    [{"date": "2025-01-01", "tss": 87.0, "ctl": 62.14, "atl": 71.03, "tsb": -8.89}, ...]

Formato de entrada (CSV): cabeçalho date,tss,ctl,atl,tsb

O dataset deve vir de conta autorizada com mais de 180 dias contínuos (§17.1) e
ser anonimizado antes de qualquer registro (§17.7). Este script NÃO acessa a API
do TrainingPeaks: ele consome um export já obtido por quem tem autorização.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# Permite rodar como script solto (python scripts/validate_against_tp.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.calculations import calculate_training_load_series  # noqa: E402

# §17.5 — critério de aceite.
CTL_TOLERANCE = 0.5

ALGORITHM_VERSION = "fitcoach-pmc/1.0 (CTL τ=42, ATL τ=7, TSB=prev-day, densificado)"


# ── Entrada ───────────────────────────────────────────────────────────────────

@dataclass
class OfficialPoint:
    day: date
    tss: float
    ctl: float
    atl: float
    tsb: float


def load_dataset(path: Path) -> list[OfficialPoint]:
    raw: list[dict]
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8") as fh:
            raw = list(csv.DictReader(fh))
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))

    points = [
        OfficialPoint(
            day=date.fromisoformat(str(r["date"])[:10]),
            tss=float(r.get("tss") or 0),
            ctl=float(r["ctl"]),
            atl=float(r["atl"]),
            tsb=float(r["tsb"]),
        )
        for r in raw
    ]
    points.sort(key=lambda p: p.day)
    return points


# ── Cálculo local ─────────────────────────────────────────────────────────────

def local_series(
    points: list[OfficialPoint],
    *,
    date_shift_days: int = 0,
    densify: bool = True,
    seed_ctl: float = 0.0,
    seed_atl: float = 0.0,
) -> dict[date, tuple[float, float, float]]:
    """Roda o algoritmo local e devolve {dia: (ctl, atl, tsb)}."""
    entries = [
        {"date": p.day + timedelta(days=date_shift_days), "tss": p.tss}
        for p in points
        if densify or p.tss > 0
    ]
    series = calculate_training_load_series(entries, seed_ctl, seed_atl)
    return {pt.load_date: (pt.ctl, pt.atl, pt.tsb) for pt in series}


def compare(
    points: list[OfficialPoint],
    computed: dict[date, tuple[float, float, float]],
) -> dict:
    """Erro ponto a ponto (§17.4)."""
    d_ctl, d_atl, d_tsb, worst = [], [], [], None
    for p in points:
        got = computed.get(p.day)
        if not got:
            continue
        e_ctl, e_atl, e_tsb = got[0] - p.ctl, got[1] - p.atl, got[2] - p.tsb
        d_ctl.append(e_ctl)
        d_atl.append(e_atl)
        d_tsb.append(e_tsb)
        if worst is None or abs(e_ctl) > abs(worst[1]):
            worst = (p.day, e_ctl)

    if not d_ctl:
        return {"matched": 0, "max_abs_ctl": math.inf}

    return {
        "matched": len(d_ctl),
        "max_abs_ctl": max(abs(x) for x in d_ctl),
        "mean_ctl": statistics.fmean(d_ctl),
        "max_abs_atl": max(abs(x) for x in d_atl),
        "max_abs_tsb": max(abs(x) for x in d_tsb),
        "worst_day": worst[0] if worst else None,
        "worst_error": worst[1] if worst else None,
        "errors_ctl": d_ctl,
    }


# ── §17.6 — escada de diagnóstico, na ordem prescrita ─────────────────────────

def diagnose(
    points: list[OfficialPoint],
    baseline: dict,
    *,
    seed_ctl: float = 0.0,
    seed_atl: float = 0.0,
) -> list[str]:
    """
    Testa cada causa candidata computacionalmente e devolve as que explicam a
    divergência. A ordem é a do §17.6 e não deve ser reordenada: uma causa
    anterior mascara as seguintes.

    As semeaduras devem ser as MESMAS usadas para produzir `baseline` — caso
    contrário as contra-hipóteses comparam séries diferentes e qualquer uma
    delas parece explicar a divergência.
    """
    findings: list[str] = []
    base_err = baseline["max_abs_ctl"]
    seeds = {"seed_ctl": seed_ctl, "seed_atl": seed_atl}

    # 1. Fuso horário — um deslocamento de ±1 dia melhora o encaixe?
    for shift in (-1, 1):
        r = compare(points, local_series(points, date_shift_days=shift, **seeds))
        if r["max_abs_ctl"] < base_err * 0.5:
            findings.append(
                f"FUSO HORÁRIO: deslocar a série em {shift:+d} dia reduz o erro máximo "
                f"de CTL de {base_err:.3f} para {r['max_abs_ctl']:.3f}. O agrupamento "
                f"diário provavelmente usa um fuso diferente do assumido."
            )
            return findings  # causa dominante: investigar as demais só depois de corrigir

    # 2. Ausência de dias com TSS zero (densificação).
    r = compare(points, local_series(points, densify=False, **seeds))
    if abs(r["max_abs_ctl"] - base_err) > 0.01:
        findings.append(
            f"DENSIFICAÇÃO: remover os dias de TSS=0 muda o erro de {base_err:.3f} para "
            f"{r['max_abs_ctl']:.3f}. Confirme que a fonte oficial também inclui dias de "
            f"descanso como zero na média exponencial."
        )

    # 3. Coeficiente de suavização — qual τ minimizaria o erro?
    best_tau, best_err = _fit_tau(points)
    if best_tau is not None and abs(best_tau - 42) > 0.5:
        findings.append(
            f"COEFICIENTE DE SUAVIZAÇÃO: τ={best_tau:.1f} dias ajusta melhor "
            f"(erro {best_err:.3f}) que o τ=42 assumido. O TrainingPeaks pode usar "
            f"outra constante — pendência §18, não fechar por suposição."
        )

    # 4. Convenção temporal do TSB (mesmo dia vs. dia anterior).
    computed = local_series(points, **seeds)
    same_day_err = max(
        (abs((got[0] - got[1]) - p.tsb) for p in points if (got := computed.get(p.day))),
        default=math.inf,
    )
    if same_day_err + 0.01 < baseline.get("max_abs_tsb", math.inf):
        findings.append(
            f"CONVENÇÃO TEMPORAL DO TSB: o TSB oficial encaixa melhor em CTL−ATL do "
            f"MESMO dia (erro {same_day_err:.3f}) que na convenção do dia anterior "
            f"usada localmente (erro {baseline['max_abs_tsb']:.3f})."
        )

    # 5. Semeadura insuficiente — o erro está concentrado no início da série?
    errs = [abs(e) for e in baseline["errors_ctl"]]
    head, tail = errs[: len(errs) // 4], errs[len(errs) // 4 :]
    if head and tail and statistics.fmean(head) > 3 * max(statistics.fmean(tail), 1e-9):
        findings.append(
            f"SEMEADURA: o erro médio no primeiro quarto da série "
            f"({statistics.fmean(head):.3f}) é muito maior que no restante "
            f"({statistics.fmean(tail):.3f}). Os valores iniciais de CTL/ATL não "
            f"correspondem ao estado real do atleta no início da janela."
        )

    # 6. Alteração de limiar — há um salto de erro em um dia específico?
    jumps = [
        (points[i].day, abs(errs[i] - errs[i - 1]))
        for i in range(1, min(len(errs), len(points)))
        if abs(errs[i] - errs[i - 1]) > 0.5
    ]
    if jumps:
        d, mag = max(jumps, key=lambda x: x[1])
        findings.append(
            f"ALTERAÇÃO DE LIMIAR: salto de erro de {mag:.3f} em {d}. Verifique se o "
            f"FTP/limiar foi alterado nessa data — o TSS histórico pode ter sido "
            f"recalculado retroativamente na origem."
        )

    # 7. Arredondamento — resíduo pequeno e uniforme.
    if base_err < 0.05 and not findings:
        findings.append(
            f"ARREDONDAMENTO: erro máximo de {base_err:.4f} é compatível com diferença "
            f"de precisão decimal, não com divergência de algoritmo."
        )

    return findings


def _fit_tau(points: list[OfficialPoint]) -> tuple[float | None, float]:
    """Varre τ e devolve o que minimiza o erro máximo de CTL."""
    best, best_err = None, math.inf
    for tau_10x in range(300, 550, 5):          # τ de 30,0 a 54,5 dias
        tau = tau_10x / 10
        alpha = 1 - math.exp(-1 / tau)
        ctl, err = 0.0, 0.0
        for p in points:
            ctl += (p.tss - ctl) * alpha
            err = max(err, abs(ctl - p.ctl))
        if err < best_err:
            best, best_err = tau, err
    return best, best_err


# ── Relatório ─────────────────────────────────────────────────────────────────

def main() -> int:
    # O relatório usa τ, § e ✓; consoles Windows em cp1252 quebrariam nesses
    # caracteres. Reconfigura a saída para UTF-8 quando possível.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    ap = argparse.ArgumentParser(description="Valida o PMC local contra dados oficiais do TrainingPeaks (§17).")
    ap.add_argument("dataset", type=Path, help="JSON ou CSV com date,tss,ctl,atl,tsb")
    ap.add_argument("--tz", default="America/Sao_Paulo", help="Fuso IANA usado no agrupamento local")
    args = ap.parse_args()

    points = load_dataset(args.dataset)
    span = (points[-1].day - points[0].day).days + 1 if points else 0

    print("=" * 72)
    print("VALIDAÇÃO DO PMC CONTRA DADOS OFICIAIS (§17)")
    print("=" * 72)
    print(f"Algoritmo   : {ALGORITHM_VERSION}")
    print(f"Fuso        : {args.tz}")
    print(f"Dataset     : {args.dataset.name} — {len(points)} pontos, {span} dias corridos")

    # §17.1 — exige mais de 180 dias contínuos.
    if span <= 180:
        print(f"\n⚠ AVISO: o protocolo exige série contínua > 180 dias; esta tem {span}.")
        print("  O resultado não é conclusivo para liberar produção.")

    computed = local_series(points)
    result = compare(points, computed)

    print(f"Pontos comparados: {result['matched']}")
    print()
    print(f"  CTL — erro máx. absoluto : {result['max_abs_ctl']:.4f}  (tolerância {CTL_TOLERANCE})")
    print(f"  CTL — erro médio (viés)  : {result['mean_ctl']:+.4f}")
    print(f"  ATL — erro máx. absoluto : {result['max_abs_atl']:.4f}")
    print(f"  TSB — erro máx. absoluto : {result['max_abs_tsb']:.4f}")
    if result.get("worst_day"):
        print(f"  Pior dia                 : {result['worst_day']} ({result['worst_error']:+.4f})")

    passed = result["max_abs_ctl"] < CTL_TOLERANCE
    print()
    print("RESULTADO:", "✓ APROVADO" if passed else "✗ REPROVADO")

    if not passed:
        print()
        print("-" * 72)
        print("DIAGNÓSTICO (§17.6 — causas na ordem prescrita)")
        print("-" * 72)
        findings = diagnose(points, result)
        if findings:
            for i, f in enumerate(findings, 1):
                print(f"\n{i}. {f}")
        else:
            print("\nNenhuma causa candidata explicou a divergência automaticamente.")
            print("Investigue manualmente e considere as pendências do §18 —")
            print("o coeficiente exato do TrainingPeaks não é público.")

    print()
    print("-" * 72)
    print("REGISTRO (§17.7): anonimize o dataset antes de arquivar; guarde este")
    print(f"relatório junto da versão do algoritmo ({ALGORITHM_VERSION}).")
    print("-" * 72)

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
