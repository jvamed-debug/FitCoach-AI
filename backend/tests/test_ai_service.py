"""
T05.2 — AI service tests.
All Anthropic / OpenAI API calls are mocked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

import pytest

from app.services.ai_service import (
    AIService,
    AIProvider,
    AthleteContext,
    _extract_json,
    _rest_day_plan,
    safety_check,
    _downgrade_plan,
    generate_default_nutrition,
    format_athlete_context,
    build_athlete_context,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_context(**overrides) -> AthleteContext:
    base = AthleteContext(
        name="Test Athlete",
        age=30,
        weight_kg=70.0,
        height_cm=175.0,
        gender="male",
        ftp_watts=280,
        max_hr=185,
        resting_hr=55,
        sport_modalities=["cycling", "strength"],
        primary_modality="cycling",
        fitness_level="intermediate",
        goal="Complete Iron Man 2027",
        weekly_availability={"cycling": ["tue", "thu", "sat"], "strength": ["mon", "fri"]},
        ctl=65.0,
        atl=70.0,
        tsb=-5.0,
        daily_tss=80.0,
        weekly_tss=420.0,
        recent_workouts=[],
        recent_strength=[],
        latest_metrics=None,
    )
    for k, v in overrides.items():
        object.__setattr__(base, k, v)
    return base


def _valid_plan(workout_type: str = "cycling_endurance") -> dict:
    return {
        "workout_type": workout_type,
        "title": "Test Ride",
        "duration_minutes": 90,
        "intensity": "moderate",
        "sections": [
            {"name": "Warm-up", "duration_minutes": 15, "description": "Easy spin",
             "targets": {"power_pct_ftp": 55, "hr_zone": 2, "rpe": 3}},
        ],
        "exercises": [],
        "key_metrics_considered": ["CTL: 65", "TSB: -5"],
        "cautions": [],
        "rationale": "Good moderate session.",
        "nutrition_plan": {
            "calories_target": 2800, "carbs_g": 380, "protein_g": 160,
            "fat_g": 80, "hydration_ml": 3000,
            "pre_workout": "oats + banana", "during_workout": "gel every 40min",
            "post_workout": "whey + rice", "notes": "",
        },
    }


# ── JSON extraction ───────────────────────────────────────────────────────────

class TestExtractJSON:
    def test_direct_json(self):
        data = {"workout_type": "cycling_endurance", "title": "Test"}
        result = _extract_json(json.dumps(data))
        assert result == data

    def test_markdown_fenced_json(self):
        raw = '```json\n{"workout_type": "rest"}\n```'
        result = _extract_json(raw)
        assert result["workout_type"] == "rest"

    def test_json_embedded_in_text(self):
        raw = 'Here is the plan:\n{"workout_type": "mobility", "title": "Yoga"}\nDone.'
        result = _extract_json(raw)
        assert result["workout_type"] == "mobility"

    def test_malformed_returns_rest_fallback(self):
        result = _extract_json("This is not valid JSON at all.")
        assert result["workout_type"] == "rest"

    def test_empty_string_returns_fallback(self):
        result = _extract_json("")
        assert result["workout_type"] == "rest"

    def test_nested_json_extracted(self):
        raw = '{"workout_type": "strength_upper", "nutrition_plan": {"carbs_g": 300}}'
        result = _extract_json(raw)
        assert result["nutrition_plan"]["carbs_g"] == 300


# ── Safety check ──────────────────────────────────────────────────────────────

class TestSafetyCheck:
    def test_critical_tsb_must_rest(self):
        ctx = _make_context(tsb=-28.0)
        plan = _valid_plan("cycling_threshold")
        warnings = safety_check(plan, ctx)
        assert any("TSB" in w for w in warnings)

    def test_critical_tsb_rest_ok(self):
        ctx = _make_context(tsb=-28.0)
        plan = _valid_plan("rest")
        warnings = safety_check(plan, ctx)
        assert not any("TSB" in w for w in warnings)

    def test_high_fatigue_triggers_warning(self):
        ctx = _make_context(
            tsb=5.0,
            latest_metrics={"fatigue_score": 9, "muscle_soreness": 3,
                            "sleep_quality": 7, "motivation_score": 7}
        )
        plan = _valid_plan("cycling_threshold")
        plan["intensity"] = "hard"
        warnings = safety_check(plan, ctx)
        assert any("fatigue" in w for w in warnings)

    def test_high_soreness_blocks_strength(self):
        ctx = _make_context(
            tsb=10.0,
            latest_metrics={"fatigue_score": 5, "muscle_soreness": 9,
                            "sleep_quality": 7, "motivation_score": 7}
        )
        plan = _valid_plan("strength_upper")
        warnings = safety_check(plan, ctx)
        assert any("soreness" in w for w in warnings)

    def test_absurd_duration_triggers_warning(self):
        ctx = _make_context(tsb=5.0)
        plan = _valid_plan()
        plan["duration_minutes"] = 400
        warnings = safety_check(plan, ctx)
        assert any("6 hours" in w for w in warnings)

    def test_normal_session_no_warnings(self):
        ctx = _make_context(tsb=-5.0, latest_metrics=None)
        plan = _valid_plan("cycling_endurance")
        warnings = safety_check(plan, ctx)
        assert len(warnings) == 0

    def test_excessive_ftp_percentage_warning(self):
        ctx = _make_context(tsb=5.0, ftp_watts=280)
        plan = _valid_plan("cycling_threshold")
        plan["sections"][0]["targets"]["power_pct_ftp"] = 170
        warnings = safety_check(plan, ctx)
        assert any("FTP" in w or "%" in w for w in warnings)


# ── Downgrade plan ────────────────────────────────────────────────────────────

class TestDowngradePlan:
    def test_very_hard_becomes_hard(self):
        plan = {"intensity": "very_hard", "rationale": "Test"}
        result = _downgrade_plan(plan, ["warning"])
        assert result["intensity"] == "hard"

    def test_easy_becomes_rest(self):
        plan = {"intensity": "easy", "rationale": "Test"}
        result = _downgrade_plan(plan, ["warning"])
        assert result["intensity"] == "rest"

    def test_warnings_added_to_cautions(self):
        plan = {"intensity": "hard", "rationale": "Test", "cautions": []}
        result = _downgrade_plan(plan, ["warning A", "warning B"])
        assert "warning A" in result["cautions"]
        assert "SAFETY OVERRIDE" in result["rationale"]


# ── Default nutrition ─────────────────────────────────────────────────────────

class TestDefaultNutrition:
    def test_hard_session_high_carbs(self):
        nutrition = generate_default_nutrition(70.0, "cycling_threshold")
        assert nutrition["carbs_g"] >= 70 * 6

    def test_rest_day_high_protein(self):
        nutrition = generate_default_nutrition(70.0, "rest")
        assert nutrition["protein_g"] >= 70 * 2

    def test_no_weight_uses_default_70kg(self):
        nutrition = generate_default_nutrition(None, "cycling_endurance")
        assert nutrition["calories_target"] is not None
        assert nutrition["calories_target"] > 0

    def test_post_workout_always_present(self):
        nutrition = generate_default_nutrition(75.0, "cycling_endurance")
        assert nutrition["post_workout"] is not None


# ── Context formatter ─────────────────────────────────────────────────────────

class TestFormatContext:
    def test_includes_tsb(self):
        ctx = _make_context(tsb=-5.0)
        text = format_athlete_context(ctx)
        assert "TSB" in text
        assert "-5" in text

    def test_includes_athlete_name(self):
        ctx = _make_context(name="Maria Silva")
        text = format_athlete_context(ctx)
        assert "Maria Silva" in text

    def test_critical_tsb_shows_mandatory_rest(self):
        ctx = _make_context(tsb=-30.0)
        text = format_athlete_context(ctx)
        assert "CRITICAL" in text or "mandatory" in text

    def test_missing_metrics_noted(self):
        ctx = _make_context(latest_metrics=None, metrics_missing=True)
        text = format_athlete_context(ctx)
        assert "NOT RECORDED" in text or "missing" in text.lower()


# ── AI service with mocks ─────────────────────────────────────────────────────

class TestAIServiceGeneration:
    @pytest.mark.asyncio
    async def test_anthropic_primary_success(self):
        svc = AIService(provider=AIProvider.ANTHROPIC)
        ctx = _make_context()
        valid_response = json.dumps(_valid_plan())

        with patch.object(svc, "_call_anthropic", new=AsyncMock(return_value=(valid_response, 1000))):
            rec = await svc.generate_recommendation(ctx)

        assert rec.workout_type == "cycling_endurance"
        assert rec.ai_provider == "anthropic"
        assert rec.tokens_used == 1000

    @pytest.mark.asyncio
    async def test_fallback_to_openai_when_anthropic_fails(self):
        svc = AIService(provider=AIProvider.ANTHROPIC)
        ctx = _make_context()
        valid_response = json.dumps(_valid_plan())

        with patch.object(svc, "_call_anthropic", new=AsyncMock(side_effect=Exception("API error"))):
            with patch.object(svc, "_call_openai", new=AsyncMock(return_value=(valid_response, 800))):
                rec = await svc.generate_recommendation(ctx)

        assert rec.ai_provider == "openai"

    @pytest.mark.asyncio
    async def test_rest_day_when_all_providers_fail(self):
        svc = AIService(provider=AIProvider.ANTHROPIC)
        ctx = _make_context()

        with patch.object(svc, "_call_anthropic", new=AsyncMock(side_effect=Exception("fail"))):
            with patch.object(svc, "_call_openai", new=AsyncMock(side_effect=Exception("fail"))):
                rec = await svc.generate_recommendation(ctx)

        assert rec.workout_type == "rest"
        assert rec.ai_provider == "fallback"

    @pytest.mark.asyncio
    async def test_critical_tsb_overridden_to_rest(self):
        svc = AIService(provider=AIProvider.ANTHROPIC)
        ctx = _make_context(tsb=-30.0)
        # AI returns threshold plan despite critical TSB
        dangerous_plan = _valid_plan("cycling_threshold")
        dangerous_plan["intensity"] = "hard"

        with patch.object(svc, "_call_anthropic", new=AsyncMock(return_value=(json.dumps(dangerous_plan), 500))):
            rec = await svc.generate_recommendation(ctx)

        # Safety check should override to rest
        assert rec.workout_type in ("rest", "mobility")

    @pytest.mark.asyncio
    async def test_nutrition_plan_always_present(self):
        svc = AIService(provider=AIProvider.ANTHROPIC)
        ctx = _make_context()
        # AI returns plan WITHOUT nutrition
        plan_no_nutrition = _valid_plan()
        del plan_no_nutrition["nutrition_plan"]

        with patch.object(svc, "_call_anthropic", new=AsyncMock(return_value=(json.dumps(plan_no_nutrition), 400))):
            rec = await svc.generate_recommendation(ctx)

        assert rec.nutrition_plan is not None
        assert "calories_target" in rec.nutrition_plan or "hydration_ml" in rec.nutrition_plan

    @pytest.mark.asyncio
    async def test_malformed_json_returns_valid_recommendation(self):
        svc = AIService(provider=AIProvider.ANTHROPIC)
        ctx = _make_context()

        with patch.object(svc, "_call_anthropic", new=AsyncMock(return_value=("This is not JSON at all!", 200))):
            with patch.object(svc, "_call_openai", new=AsyncMock(side_effect=Exception("fail"))):
                rec = await svc.generate_recommendation(ctx)

        assert rec.workout_type == "rest"  # fallback
        assert rec.recommendation_text is not None


# ── Fatigue analysis ──────────────────────────────────────────────────────────

class TestFatigueAnalysis:
    @pytest.mark.asyncio
    async def test_critical_tsb_returns_critical(self):
        svc = AIService()
        ctx = _make_context(tsb=-28.0)
        result = await svc.analyze_fatigue(ctx)
        assert result["level"] == "critical"
        assert len(result["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_fresh_returns_low(self):
        svc = AIService()
        ctx = _make_context(tsb=12.0, ctl=80.0, atl=68.0)
        result = await svc.analyze_fatigue(ctx)
        assert result["level"] == "low"
