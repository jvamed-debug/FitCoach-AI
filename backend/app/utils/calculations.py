"""
Training load calculations based on the Banister Performance Manager Chart (PMC).

CTL = Chronic Training Load  — 42-day exponential weighted average (Fitness)
ATL = Acute Training Load    —  7-day exponential weighted average (Fatigue)
TSB = Training Stress Balance = CTL − ATL                          (Form)
TSS = Training Stress Score  — per-session load unit

References:
  Coggan, A. (2003). Training and racing using a power meter.
  Bannister, E.W. (1991). Modeling elite athletic performance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import NamedTuple


# ── TSS calculators ───────────────────────────────────────────────────────────

# Converte TRIMP (Banister) em TSS. Ancorado na definição de TSS: 1 hora no
# limiar = 100 TSS. Ver a derivação em calculate_tss_from_hr.
_TRIMP_TO_TSS = 0.60


def calculate_tss_cycling(
    duration_seconds: int,
    normalized_power: int,
    ftp: int,
    intensity_factor: float | None = None,
) -> float:
    """
    TSS = (duration_sec × NP × IF) / (FTP × 3600) × 100
    IF  = NP / FTP
    """
    if ftp <= 0:
        raise ValueError("FTP must be positive")
    if_val = intensity_factor if intensity_factor is not None else normalized_power / ftp
    tss = (duration_seconds * normalized_power * if_val) / (ftp * 3600) * 100
    return round(tss, 2)


def calculate_tss_from_hr(
    duration_seconds: int,
    avg_hr: int,
    max_hr: int,
    resting_hr: int,
) -> float:
    """
    HR-based TSS estimate via TRIMP (Banister).
    hr_ratio = (avg_hr - resting_hr) / (max_hr - resting_hr)
    TRIMP     = duration_min × hr_ratio × 0.64 × e^(1.92 × hr_ratio)
    TSS       = TRIMP × _TRIMP_TO_TSS

    Calibração de _TRIMP_TO_TSS: por definição, 1 hora no limiar vale 100 TSS.
    No limiar, hr_ratio ≈ 0.85 (85% da reserva de FC), logo
        TRIMP(60min, 0.85) = 60 × 0.85 × 0.64 × e^(1.92 × 0.85) ≈ 166.9
        fator = 100 / 166.9 ≈ 0.60
    O fator 0.8 usado antes produzia ~133 TSS por hora de limiar, superestimando
    a carga de todo treino estimado por FC em cerca de 33%.
    """
    if max_hr <= resting_hr:
        raise ValueError("max_hr must be greater than resting_hr")
    hr_ratio = (avg_hr - resting_hr) / (max_hr - resting_hr)
    hr_ratio = max(0.0, min(1.0, hr_ratio))
    duration_min = duration_seconds / 60
    trimp = duration_min * hr_ratio * 0.64 * math.exp(1.92 * hr_ratio)
    tss = trimp * _TRIMP_TO_TSS
    return round(tss, 2)


def calculate_strength_tss(duration_minutes: int, rpe: int) -> float:
    """
    Strength TSS estimate.
    Formula: (duration_min × rpe²) / (10 × 60) × 100
    Capped at 150 TSS/session.
    RPE must be 1–10.
    """
    if not (1 <= rpe <= 10):
        raise ValueError("RPE must be between 1 and 10")
    tss = (duration_minutes * rpe ** 2) / (10 * 60) * 100
    return round(min(tss, 150.0), 2)


# ── CTL / ATL / TSB ───────────────────────────────────────────────────────────

def _ema_factor(time_constant_days: int) -> float:
    """Alpha factor for exponential moving average: 1 − e^(−1/τ)."""
    return 1 - math.exp(-1 / time_constant_days)


def calculate_ctl(
    previous_ctl: float,
    daily_tss: float,
    time_constant_days: int = 42,
) -> float:
    """CTL(t) = CTL(t-1) + (TSS − CTL(t-1)) × (1 − e^(−1/42))"""
    alpha = _ema_factor(time_constant_days)
    return round(previous_ctl + (daily_tss - previous_ctl) * alpha, 4)


def calculate_atl(
    previous_atl: float,
    daily_tss: float,
    time_constant_days: int = 7,
) -> float:
    """ATL(t) = ATL(t-1) + (TSS − ATL(t-1)) × (1 − e^(−1/7))"""
    alpha = _ema_factor(time_constant_days)
    return round(previous_atl + (daily_tss - previous_atl) * alpha, 4)


def calculate_tsb(ctl: float, atl: float) -> float:
    """TSB = CTL − ATL  (positive → fresh, negative → fatigued)"""
    return round(ctl - atl, 4)


# ── Full series ───────────────────────────────────────────────────────────────

@dataclass
class LoadPoint:
    load_date: date
    ctl: float
    atl: float
    tsb: float
    daily_tss: float


def calculate_training_load_series(
    tss_series: list[dict],
    initial_ctl: float = 0.0,
    initial_atl: float = 0.0,
) -> list[LoadPoint]:
    """
    Compute CTL/ATL/TSB for every calendar day in the range covered by tss_series,
    filling gaps (rest days) with TSS = 0.

    Args:
        tss_series: [{"date": date, "tss": float}, ...] — may have gaps, must be sorted.
        initial_ctl: CTL value before the first day in the series.
        initial_atl: ATL value before the first day in the series.

    Returns:
        List of LoadPoint ordered by date (one entry per calendar day).
    """
    if not tss_series:
        return []

    # Build a date→tss map
    tss_map: dict[date, float] = {}
    for entry in tss_series:
        d = entry["date"] if isinstance(entry["date"], date) else date.fromisoformat(str(entry["date"]))
        tss_map[d] = tss_map.get(d, 0.0) + float(entry["tss"])

    start = min(tss_map)
    end = max(tss_map)

    ctl = initial_ctl
    atl = initial_atl
    results: list[LoadPoint] = []

    current = start
    while current <= end:
        daily_tss = tss_map.get(current, 0.0)
        ctl = calculate_ctl(ctl, daily_tss)
        atl = calculate_atl(atl, daily_tss)
        tsb = calculate_tsb(ctl, atl)
        results.append(LoadPoint(load_date=current, ctl=ctl, atl=atl, tsb=tsb, daily_tss=daily_tss))
        current += timedelta(days=1)

    return results


# ── Training zones ────────────────────────────────────────────────────────────

def calculate_intensity_zones_cycling(ftp: int) -> dict[str, dict[str, float]]:
    """
    Coggan 7-zone power model.
    Returns dict of zone → {min_pct, max_pct, min_watts, max_watts, description}.
    """
    zones = {
        "Z1": (0,   55,  "Active Recovery"),
        "Z2": (55,  75,  "Endurance"),
        "Z3": (75,  90,  "Tempo"),
        "Z4": (90,  105, "Threshold"),
        "Z5": (105, 120, "VO2max"),
        "Z6": (120, 150, "Anaerobic Capacity"),
        "Z7": (150, 999, "Neuromuscular Power"),
    }
    result: dict = {}
    for name, (lo_pct, hi_pct, desc) in zones.items():
        result[name] = {
            "min_pct": lo_pct,
            "max_pct": hi_pct if hi_pct != 999 else None,
            "min_watts": round(ftp * lo_pct / 100),
            "max_watts": round(ftp * hi_pct / 100) if hi_pct != 999 else None,
            "description": desc,
        }
    return result


def calculate_hr_zones(max_hr: int, resting_hr: int) -> dict[str, dict[str, int | str]]:
    """
    Karvonen 5-zone HR model (Heart Rate Reserve method).
    hrr = max_hr − resting_hr
    zone_hr = resting_hr + (hrr × pct)
    """
    hrr = max_hr - resting_hr
    zones = {
        "Z1": (50, 60,  "Recovery"),
        "Z2": (60, 70,  "Aerobic Base"),
        "Z3": (70, 80,  "Aerobic Power"),
        "Z4": (80, 90,  "Threshold"),
        "Z5": (90, 100, "Maximal"),
    }
    result: dict = {}
    for name, (lo_pct, hi_pct, desc) in zones.items():
        result[name] = {
            "min_hr": round(resting_hr + hrr * lo_pct / 100),
            "max_hr": round(resting_hr + hrr * hi_pct / 100),
            "description": desc,
        }
    return result


# ── TSB state label ───────────────────────────────────────────────────────────

def tsb_label(tsb: float) -> str:
    """Human-readable training state from TSB value."""
    if tsb < -30:
        return "overreaching"
    if tsb < -10:
        return "fatigued"
    if tsb < 5:
        return "neutral"
    if tsb < 20:
        return "fresh"
    return "very_fresh"
