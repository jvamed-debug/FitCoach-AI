"""
Runner da suite de avaliação do agente.

Dois modos, com propósitos distintos:

  offline (padrão) — não chama a API. Verifica que o CONTEXTO montado para cada
    cenário carrega as restrições certas: se o CTL não convergiu, o prompt tem
    de dizer isso; se não há métricas, o gate de qualidade tem de acusar. Roda
    na CI, de graça, e pega regressões no harness — que é onde os bugs desta
    base moraram até agora.

  live (--live) — chama o modelo de verdade e valida a saída contra o contrato.
    Custa tokens e exige ANTHROPIC_API_KEY, então é opt-in. É o único modo que
    mede o COMPORTAMENTO do modelo; o offline mede o andaime em volta dele.

Uso:
    python -m evals.run_evals
    python -m evals.run_evals --live
    python -m evals.run_evals --live --scenario tsb_critico --repeat 3
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ai_service import (  # noqa: E402
    assess_data_quality,
    format_athlete_context,
)
from evals.contract import validate_plan  # noqa: E402
from evals.scenarios import SCENARIOS, Scenario, by_name  # noqa: E402


# ── Modo offline: o contexto carrega as restrições? ───────────────────────────

def check_context(sc: Scenario) -> list[str]:
    """
    Verifica que o prompt montado expõe as limitações do cenário.

    Se o agente nunca é informado de que o CTL não convergiu, cobrar dele a
    regra 9 é injusto — e o eval live acusaria o modelo por um defeito do
    harness. Este modo separa as duas coisas.
    """
    falhas: list[str] = []
    ctx = sc.contexto

    quality = assess_data_quality(ctx)
    ctx.data_quality_notes = quality.notes
    prompt = format_athlete_context(ctx)

    if not ctx.ctl_converged:
        if "NOT CONVERGED" not in prompt and "não convergido" not in prompt.lower():
            falhas.append("CTL não convergido, mas o prompt não avisa")
        if not any(c.code == "ctl_not_converged" for c in quality.checks):
            falhas.append("gate de qualidade não acusou ctl_not_converged")

    if ctx.metrics_missing and not any(c.code == "metrics_missing" for c in quality.checks):
        falhas.append("métricas ausentes, mas o gate não acusou")

    metodos = {w.get("tss_method") for w in ctx.recent_workouts if w.get("tss")}
    if metodos and metodos <= {"hr", "strength"}:
        if not any(c.code == "tss_hr_only" for c in quality.checks):
            falhas.append("TSS só por FC, mas o gate não acusou")
        if "estimativa-FC" not in prompt:
            falhas.append("TSS estimado por FC não está rotulado no prompt")

    # §7: duplicidade é bloqueante — corrompe todo número derivado do TSS.
    from app.services.ai_service import detect_duplicates
    if detect_duplicates(ctx.recent_workouts):
        if not any(c.code == "duplicate_sessions" for c in quality.checks):
            falhas.append("há sessões duplicadas, mas o gate não acusou")
        elif quality.level != "insufficient":
            falhas.append("duplicidade detectada mas o gate não bloqueou")

    if ctx.recent_feedback and "ATHLETE FEEDBACK" not in prompt:
        falhas.append("há feedback registrado, mas ele não chega ao prompt")

    if ctx.recent_feedback and "DECLARED INFORMATION" not in prompt:
        falhas.append("feedback presente sem o rótulo epistêmico")

    # Os números da carga precisam chegar — o agente não pode recalculá-los.
    if f"{ctx.tsb:+.1f}" not in prompt and f"{ctx.tsb:.1f}" not in prompt:
        falhas.append(f"TSB ({ctx.tsb}) não aparece no prompt")

    return falhas


# ── Modo live: o modelo obedece? ──────────────────────────────────────────────

async def check_live(sc: Scenario, repeat: int) -> list[str]:
    from app.services.ai_service import AIService

    falhas: list[str] = []
    service = AIService()
    ctx = sc.contexto
    ctx.data_quality_notes = assess_data_quality(ctx).notes

    for tentativa in range(1, repeat + 1):
        rec = await service.generate_recommendation(ctx)
        if rec.ai_provider == "fallback":
            falhas.append(f"tentativa {tentativa}: caiu no fallback — {rec.rationale}")
            continue

        plano = dict(rec.structured_plan or {})
        plano.setdefault("workout_type", rec.workout_type)
        plano.setdefault("rationale", rec.rationale)

        rep = validate_plan(plano, tsb=ctx.tsb, metrics=ctx.latest_metrics)
        falhas += [f"tentativa {tentativa}: {v}" for v in rep.blocking]
        for expect in sc.expectativas:
            falhas += [f"tentativa {tentativa}: {m}" for m in expect(plano, ctx)]

    return falhas


# ── Execução ──────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    ap = argparse.ArgumentParser(description="Suite de avaliação do agente fitCoach AI.")
    ap.add_argument("--live", action="store_true",
                    help="chama o modelo de verdade (consome tokens; exige ANTHROPIC_API_KEY)")
    ap.add_argument("--scenario", help="rodar só um cenário, pelo nome")
    ap.add_argument("--repeat", type=int, default=1,
                    help="repetições por cenário no modo live (a saída varia)")
    args = ap.parse_args()

    alvos = [by_name(args.scenario)] if args.scenario else SCENARIOS

    print("=" * 74)
    print(f"AVALIAÇÃO DO AGENTE — modo {'LIVE' if args.live else 'OFFLINE'}")
    print("=" * 74)
    if not args.live:
        print("Offline valida o harness (o contexto carrega as restrições?).")
        print("Para medir o comportamento do modelo, rode com --live.\n")

    reprovados = 0
    for sc in alvos:
        falhas = (
            asyncio.run(check_live(sc, args.repeat)) if args.live
            else check_context(sc)
        )
        marca = "✓" if not falhas else "✗"
        print(f"{marca} {sc.nome}")
        if falhas:
            reprovados += 1
            for f in falhas:
                print(f"    {f}")

    print()
    print("-" * 74)
    total = len(alvos)
    print(f"{total - reprovados}/{total} cenários aprovados")
    return 1 if reprovados else 0


if __name__ == "__main__":
    raise SystemExit(main())
