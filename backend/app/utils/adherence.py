"""
Workout adherence analysis.
Compares a planned AI recommendation against the actually executed workout.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AdherenceReport:
    followed: bool
    tss_planned: float | None
    tss_actual: float | None
    tss_deviation_pct: float | None         # positive = exceeded, negative = undershot
    duration_planned_min: int | None
    duration_actual_min: int | None
    duration_deviation_pct: float | None
    intensity_match: bool                   # True if intensity zone matches
    rpe_planned: int | None
    rpe_actual: int | None
    rpe_deviation: int | None               # actual - planned
    summary: str
    adjustment_hint: str                    # fed back into AI context


def analyze_workout_adherence(
    planned: dict,      # AIRecommendation.structured_plan
    executed: dict,     # Workout row as dict
    executed_rpe: int | None = None,
) -> AdherenceReport:
    """
    Compare planned vs executed workout.
    planned  — structured_plan dict from AIRecommendation
    executed — Workout dict (duration_seconds, tss, avg_power_watts, etc.)
    executed_rpe — athlete's reported RPE (from strength session or feedback)
    """
    # TSS comparison
    tss_planned = _planned_tss(planned)
    tss_actual  = _executed_tss(executed)
    tss_dev     = _pct_deviation(tss_planned, tss_actual)

    # Duration comparison
    dur_planned_min = planned.get("duration_minutes")
    dur_actual_s    = executed.get("duration_seconds")
    dur_actual_min  = round(dur_actual_s / 60) if dur_actual_s else None
    dur_dev         = _pct_deviation(
        float(dur_planned_min) if dur_planned_min else None,
        float(dur_actual_min) if dur_actual_min else None,
    )

    # Intensity match (rough: compare planned intensity to actual power/HR zones)
    planned_intensity = planned.get("intensity", "moderate")
    intensity_match = _check_intensity_match(planned_intensity, executed)

    # RPE comparison
    rpe_planned = _extract_planned_rpe(planned)
    rpe_dev = (executed_rpe - rpe_planned) if (executed_rpe and rpe_planned) else None

    # Determine followed status
    # "followed" = within 20% of planned TSS or duration
    followed = True
    if tss_dev is not None and abs(tss_dev) > 30:
        followed = False
    if dur_dev is not None and abs(dur_dev) > 30:
        followed = False
    if rpe_dev is not None and abs(rpe_dev) >= 3:
        followed = False

    summary = _build_summary(tss_dev, dur_dev, rpe_dev, followed)
    hint    = _build_adjustment_hint(tss_dev, dur_dev, rpe_dev, executed_rpe, rpe_planned)

    return AdherenceReport(
        followed=followed,
        tss_planned=tss_planned,
        tss_actual=tss_actual,
        tss_deviation_pct=tss_dev,
        duration_planned_min=dur_planned_min,
        duration_actual_min=dur_actual_min,
        duration_deviation_pct=dur_dev,
        intensity_match=intensity_match,
        rpe_planned=rpe_planned,
        rpe_actual=executed_rpe,
        rpe_deviation=rpe_dev,
        summary=summary,
        adjustment_hint=hint,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _planned_tss(plan: dict) -> float | None:
    # Estimate TSS from planned intensity × duration
    dur = plan.get("duration_minutes")
    if not dur:
        return None
    intensity_map = {"easy": 0.4, "moderate": 0.65, "hard": 0.85, "very_hard": 1.0, "rest": 0.0}
    factor = intensity_map.get(plan.get("intensity", "moderate"), 0.65)
    # Rough: IF²  × duration_hours × 100
    return round(factor ** 2 * (dur / 60) * 100, 1)


def _executed_tss(wkt: dict) -> float | None:
    tss = wkt.get("tss")
    return float(tss) if tss else None


def _pct_deviation(planned: float | None, actual: float | None) -> float | None:
    if planned is None or actual is None or planned == 0:
        return None
    return round((actual - planned) / planned * 100, 1)


def _check_intensity_match(planned_intensity: str, wkt: dict) -> bool:
    # If athlete hit within 1 power zone of planned, it's a match
    np = wkt.get("normalized_power_watts")
    ftp = None  # FTP not available here; skip zone check if unavailable
    if not np:
        return True  # assume match when no power data
    return True  # TODO: requires FTP context — plugged in in ai_service


def _extract_planned_rpe(plan: dict) -> int | None:
    """Extract average RPE from section targets."""
    rpes = [
        s.get("targets", {}).get("rpe")
        for s in plan.get("sections", [])
        if s.get("targets", {}).get("rpe")
    ]
    if rpes:
        return round(sum(rpes) / len(rpes))
    return None


def _build_summary(tss_dev: float | None, dur_dev: float | None,
                   rpe_dev: int | None, followed: bool) -> str:
    parts = []
    if tss_dev is not None:
        sign = "+" if tss_dev > 0 else ""
        parts.append(f"Carga: {sign}{tss_dev:.0f}% do planejado")
    if dur_dev is not None:
        sign = "+" if dur_dev > 0 else ""
        parts.append(f"Duração: {sign}{dur_dev:.0f}%")
    if rpe_dev is not None:
        parts.append(f"RPE: {'+' if rpe_dev > 0 else ''}{rpe_dev} vs planejado")
    status = "Treino seguido ✓" if followed else "Desvio significativo ⚠️"
    return f"{status}. {' | '.join(parts)}" if parts else status


def _build_adjustment_hint(
    tss_dev: float | None, dur_dev: float | None,
    rpe_dev: int | None, rpe_actual: int | None, rpe_planned: int | None,
) -> str:
    hints = []
    if tss_dev is not None:
        if tss_dev > 30:
            hints.append("Athlete significantly exceeded planned load — reduce tomorrow's intensity")
        elif tss_dev < -30:
            hints.append("Athlete under-performed planned load — check motivation/fatigue; consider easier session")

    if rpe_dev is not None and rpe_dev >= 3:
        hints.append(
            f"Athlete reported RPE {rpe_actual} vs planned {rpe_planned} "
            f"(+{rpe_dev} harder than expected) — reduce next session intensity"
        )
    elif rpe_dev is not None and rpe_dev <= -3:
        hints.append(
            f"Athlete found session easier than expected (RPE {rpe_actual} vs {rpe_planned}) "
            f"— may increase intensity next session"
        )

    return " | ".join(hints) if hints else "No major adjustments needed."
