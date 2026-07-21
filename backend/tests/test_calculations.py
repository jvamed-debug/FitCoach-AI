"""
T03.1 — Unit tests for training load calculations.
All expected values are derived from published formulas / known references.
"""

import math
from datetime import date
import pytest

from app.utils.calculations import (
    calculate_tss_cycling,
    calculate_tss_from_hr,
    calculate_strength_tss,
    calculate_ctl,
    calculate_atl,
    calculate_tsb,
    calculate_training_load_series,
    calculate_intensity_zones_cycling,
    calculate_hr_zones,
    tsb_label,
    LoadPoint,
)


# ── TSS cycling ───────────────────────────────────────────────────────────────

class TestTSSCycling:
    def test_one_hour_at_threshold(self):
        # 3600s at NP=250=FTP → IF=1.0 → TSS=100
        tss = calculate_tss_cycling(3600, 250, 250)
        assert abs(tss - 100.0) < 0.01

    def test_one_hour_at_70_pct_ftp(self):
        # 3600s, NP=175, FTP=250 → IF=0.7 → TSS = 3600×175×0.7 / (250×3600) × 100 = 49
        tss = calculate_tss_cycling(3600, 175, 250)
        assert abs(tss - 49.0) < 0.01

    def test_two_hours_endurance(self):
        # 7200s at NP=200 with FTP=280 → IF=200/280≈0.714
        tss = calculate_tss_cycling(7200, 200, 280)
        if_val = 200 / 280
        expected = (7200 * 200 * if_val) / (280 * 3600) * 100
        assert abs(tss - expected) < 0.01

    def test_explicit_intensity_factor(self):
        tss = calculate_tss_cycling(3600, 260, 250, intensity_factor=1.0)
        # IF overridden to 1.0 → TSS = 3600×260×1.0 / (250×3600) × 100 = 104
        assert abs(tss - 104.0) < 0.01

    def test_zero_ftp_raises(self):
        with pytest.raises(ValueError):
            calculate_tss_cycling(3600, 200, 0)

    def test_short_interval_session(self):
        # 30min (1800s) at NP=320, FTP=280 → IF=1.143
        tss = calculate_tss_cycling(1800, 320, 280)
        if_val = 320 / 280
        expected = (1800 * 320 * if_val) / (280 * 3600) * 100
        assert abs(tss - expected) < 0.01


# ── TSS from HR ───────────────────────────────────────────────────────────────

class TestTSSFromHR:
    def test_easy_ride(self):
        # 90min easy ride, avg_hr=130, max_hr=185, resting=55
        tss = calculate_tss_from_hr(5400, 130, 185, 55)
        assert 30 < tss < 70  # plausible range for easy endurance

    def test_hard_session(self):
        # 60min hard, avg_hr=165, max_hr=185, resting=55
        tss = calculate_tss_from_hr(3600, 165, 185, 55)
        assert tss > 70  # hard session should score higher

    def test_hr_ratio_clamp(self):
        # avg_hr above max_hr should not raise, hr_ratio clamped to 1.0
        tss = calculate_tss_from_hr(3600, 200, 185, 55)
        assert tss > 0

    def test_invalid_hr_range_raises(self):
        with pytest.raises(ValueError):
            calculate_tss_from_hr(3600, 150, 55, 55)  # max_hr == resting_hr

    def test_formula_values(self):
        # Manual calculation: avg=150, max=185, rest=55 → hrr=130, hr_ratio=95/130≈0.731
        avg_hr, max_hr, resting_hr = 150, 185, 55
        hr_ratio = (avg_hr - resting_hr) / (max_hr - resting_hr)
        duration_min = 60
        trimp = duration_min * hr_ratio * 0.64 * math.exp(1.92 * hr_ratio)
        expected = round(trimp * 0.8, 2)
        tss = calculate_tss_from_hr(3600, avg_hr, max_hr, resting_hr)
        assert abs(tss - expected) < 0.01


# ── Strength TSS ──────────────────────────────────────────────────────────────

class TestStrengthTSS:
    def test_moderate_session(self):
        # 60min at RPE 7 → (60 × 49) / 600 × 100 = 490 → capped at 150
        tss = calculate_strength_tss(60, 7)
        assert tss == 150.0

    def test_light_session(self):
        # 30min at RPE 4 → (30 × 16) / 600 × 100 = 80
        tss = calculate_strength_tss(30, 4)
        assert abs(tss - 80.0) < 0.01

    def test_very_light_session(self):
        # 20min at RPE 2 → (20 × 4) / 600 × 100 = 13.33
        tss = calculate_strength_tss(20, 2)
        assert abs(tss - 13.33) < 0.01

    def test_cap_at_150(self):
        tss = calculate_strength_tss(120, 10)
        assert tss == 150.0

    def test_invalid_rpe_raises(self):
        with pytest.raises(ValueError):
            calculate_strength_tss(60, 0)
        with pytest.raises(ValueError):
            calculate_strength_tss(60, 11)


# ── CTL / ATL ─────────────────────────────────────────────────────────────────

class TestCTLATL:
    def test_ctl_converges_to_tss(self):
        # After many days of constant TSS, CTL should approach that TSS value
        ctl = 0.0
        for _ in range(300):
            ctl = calculate_ctl(ctl, 100.0)
        assert abs(ctl - 100.0) < 1.0

    def test_atl_converges_faster(self):
        # ATL (7-day) should reach 90% of steady-state faster than CTL (42-day)
        ctl = atl = 0.0
        for _ in range(20):
            ctl = calculate_ctl(ctl, 100.0)
            atl = calculate_atl(atl, 100.0)
        # ATL should be higher than CTL after only 20 days of ramping up
        assert atl > ctl

    def test_rest_day_decreases_atl_faster(self):
        # After a rest day (TSS=0), ATL decays faster than CTL
        ctl = atl = 80.0
        ctl_after = calculate_ctl(ctl, 0)
        atl_after = calculate_atl(atl, 0)
        assert atl_after < ctl_after  # ATL drops more per day

    def test_ctl_custom_time_constant(self):
        alpha = 1 - math.exp(-1 / 42)
        prev = 50.0
        tss = 80.0
        expected = round(prev + (tss - prev) * alpha, 4)
        assert calculate_ctl(prev, tss) == expected

    def test_atl_custom_time_constant(self):
        alpha = 1 - math.exp(-1 / 7)
        prev = 50.0
        tss = 80.0
        expected = round(prev + (tss - prev) * alpha, 4)
        assert calculate_atl(prev, tss) == expected

    def test_tsb_positive_when_rested(self):
        ctl = 80.0
        atl = 60.0
        assert calculate_tsb(ctl, atl) == 20.0

    def test_tsb_negative_when_fatigued(self):
        ctl = 60.0
        atl = 80.0
        assert calculate_tsb(ctl, atl) == -20.0


# ── Series calculation ────────────────────────────────────────────────────────

class TestTrainingLoadSeries:
    def _make_series(self, entries: list[tuple[str, float]]) -> list[dict]:
        return [{"date": date.fromisoformat(d), "tss": t} for d, t in entries]

    def test_single_day(self):
        series = self._make_series([("2024-01-01", 100.0)])
        result = calculate_training_load_series(series)
        assert len(result) == 1
        assert result[0].daily_tss == 100.0
        assert result[0].ctl > 0
        assert result[0].atl > 0

    def test_gap_fills_with_rest(self):
        series = self._make_series([("2024-01-01", 100.0), ("2024-01-05", 80.0)])
        result = calculate_training_load_series(series)
        assert len(result) == 5  # Jan 1–5 inclusive
        # Days 2-4 should have daily_tss = 0
        assert result[1].daily_tss == 0.0
        assert result[2].daily_tss == 0.0
        assert result[3].daily_tss == 0.0

    def test_ctl_increases_with_training(self):
        series = self._make_series([(f"2024-01-{i:02d}", 100.0) for i in range(1, 15)])
        result = calculate_training_load_series(series)
        # CTL should be monotonically increasing
        for i in range(1, len(result)):
            assert result[i].ctl >= result[i - 1].ctl

    def test_atl_increases_faster_than_ctl(self):
        series = self._make_series([(f"2024-01-{i:02d}", 100.0) for i in range(1, 10)])
        result = calculate_training_load_series(series, initial_ctl=0, initial_atl=0)
        # After a hard week, ATL should exceed CTL
        assert result[-1].atl > result[-1].ctl

    def test_tsb_negative_during_training_block(self):
        series = self._make_series([(f"2024-01-{i:02d}", 120.0) for i in range(1, 15)])
        result = calculate_training_load_series(series, initial_ctl=60, initial_atl=60)
        # TSB should go negative during a training block
        assert result[-1].tsb < 0

    def test_initial_values_respected(self):
        series = self._make_series([("2024-01-01", 0.0)])
        result = calculate_training_load_series(series, initial_ctl=80.0, initial_atl=90.0)
        # With rest day (TSS=0), CTL should drop from 80, ATL should drop from 90
        assert result[0].ctl < 80.0
        assert result[0].atl < 90.0

    def test_empty_returns_empty(self):
        assert calculate_training_load_series([]) == []

    def test_same_day_tss_aggregated(self):
        # Two workouts on the same day should sum TSS
        series = [
            {"date": date(2024, 1, 1), "tss": 60.0},
            {"date": date(2024, 1, 1), "tss": 40.0},
        ]
        result = calculate_training_load_series(series)
        assert len(result) == 1
        assert result[0].daily_tss == 100.0


# ── Zones ─────────────────────────────────────────────────────────────────────

class TestZones:
    def test_cycling_zones_count(self):
        zones = calculate_intensity_zones_cycling(250)
        assert len(zones) == 7

    def test_cycling_z4_is_threshold(self):
        zones = calculate_intensity_zones_cycling(250)
        z4 = zones["Z4"]
        assert z4["min_watts"] == round(250 * 0.90)
        assert z4["max_watts"] == round(250 * 1.05)

    def test_cycling_z7_has_no_max(self):
        zones = calculate_intensity_zones_cycling(250)
        assert zones["Z7"]["max_watts"] is None

    def test_cycling_zones_scale_with_ftp(self):
        z1_300 = calculate_intensity_zones_cycling(300)
        z1_250 = calculate_intensity_zones_cycling(250)
        assert z1_300["Z4"]["min_watts"] > z1_250["Z4"]["min_watts"]

    def test_hr_zones_count(self):
        zones = calculate_hr_zones(185, 55)
        assert len(zones) == 5

    def test_hr_z5_approaches_max_hr(self):
        zones = calculate_hr_zones(185, 55)
        assert zones["Z5"]["max_hr"] == 185

    def test_hr_zones_ordered(self):
        zones = calculate_hr_zones(185, 55)
        zone_list = list(zones.values())
        for i in range(1, len(zone_list)):
            assert zone_list[i]["min_hr"] >= zone_list[i - 1]["min_hr"]


# ── TSB label ─────────────────────────────────────────────────────────────────

class TestTSBLabel:
    @pytest.mark.parametrize("tsb,expected", [
        (-35, "overreaching"),
        (-15, "fatigued"),
        (0,   "neutral"),
        (10,  "fresh"),
        (25,  "very_fresh"),
    ])
    def test_labels(self, tsb, expected):
        assert tsb_label(tsb) == expected
