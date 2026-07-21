"""
AI Coach Service — provider-agnostic training recommendation engine.

Provider routing:  Anthropic Claude (primary)  →  OpenAI GPT-4o (fallback)  →  rest day
Parse strategy:    progressive JSON extraction — handles markdown fences, partial JSON, text fallback
Safety check:      post-parse guard against dangerous prescriptions
Nutrition:         generated in the same API call; never a separate round-trip
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from enum import Enum
from typing import Any

import anthropic
import openai
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.athlete import Athlete
from app.models.metric import DailyMetric
from app.models.workout import Workout
from app.models.strength import StrengthSession
from app.services.training_load import get_current_load

logger = logging.getLogger(__name__)


# ── Enums & data classes ──────────────────────────────────────────────────────

class AIProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI    = "openai"


@dataclass
class AthleteContext:
    # Profile
    name: str
    age: int | None
    weight_kg: float | None
    height_cm: float | None
    gender: str | None
    ftp_watts: int | None
    max_hr: int | None
    resting_hr: int | None
    sport_modalities: list[str]
    primary_modality: str | None
    fitness_level: str | None
    goal: str | None
    weekly_availability: dict | None

    # Training load
    ctl: float
    atl: float
    tsb: float
    daily_tss: float
    weekly_tss: float

    # History
    recent_workouts: list[dict]       # last 14 sessions (cycling/running/etc.)
    recent_strength: list[dict]       # last 7 strength sessions
    latest_metrics: dict | None       # today's subjective metrics (may be None)

    # Flags
    is_new_athlete: bool = False
    detraining_detected: bool = False
    metrics_missing: bool = False
    target_event: str | None = None
    weeks_to_event: int | None = None


@dataclass
class NutritionPlan:
    calories_target: int | None = None
    carbs_g: int | None = None
    protein_g: int | None = None
    fat_g: int | None = None
    hydration_ml: int | None = None
    pre_workout: str | None = None
    during_workout: str | None = None
    post_workout: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class TrainingRecommendation:
    workout_type: str
    title: str
    recommendation_text: str
    structured_plan: dict
    nutrition_plan: dict
    rationale: str
    ai_provider: str
    ai_model: str
    tokens_used: int = 0
    generation_time_ms: int = 0


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are Dr. Performance — an elite endurance coach, certified strength & conditioning specialist (CSCS), and sports nutritionist. You work with athletes who combine cycling, running, swimming, triathlon, and strength training.

## YOUR MISSION
Generate ONE specific training session for TOMORROW, plus a nutrition plan for that day. Be precise, evidence-based, and individualized.

## TSB DECISION RULES (mandatory)
- TSB < -25 → prescribe REST or MOBILITY ONLY. No exceptions.
- TSB -25 to -15 → recovery ride Z1/Z2, yoga, or very light strength
- TSB -15 to -5  → normal base training, moderate intensity
- TSB -5 to +5   → quality training, threshold or tempo work appropriate
- TSB +5 to +15  → high quality session, VO2max or race-pace intervals
- TSB > +15 → athlete is very fresh, high-intensity or race simulation

## SUBJECTIVE METRICS (override TSB if severe)
- fatigue_score ≥ 8 → downgrade 2 zones even if TSB is positive
- muscle_soreness ≥ 8 → avoid strength or high-impact work
- motivation_score ≤ 3 → prescribe shorter, enjoyable session
- sleep_quality ≤ 4 → full rest or active recovery only

## SPORT-SPECIFIC FORMAT
- **Cycling**: sections with duration_minutes, power_pct_ftp, hr_zone, cadence_rpm, rpe
- **Running**: sections with duration_minutes, pace_min_per_km OR rpe, hr_zone
- **Swimming**: sections with distance_m, stroke, rest_seconds, description
- **Strength**: exercises list with sets, reps (or duration), load_pct_1rm OR load_kg, rpe, rest_seconds
- **Triathlon**: ordered sections mixing cycling/running/swimming blocks
- **Mobility/Recovery**: exercises with duration_seconds and technique notes

## NUTRITION RULES
- High-intensity day (TSS > 80): carbs_g ≥ 6g/kg body weight, hydration_ml ≥ 600ml during
- Rest/recovery day: protein_g ≥ 2g/kg, reduce carbs 20-30%
- Always include pre_workout, during_workout, post_workout guidance
- Calibrate calories to weight and session intensity

## OUTPUT FORMAT (strict JSON — no markdown, no extra text)
{
  "workout_type": "cycling_endurance|cycling_threshold|cycling_vo2max|cycling_long|running_easy|running_tempo|running_intervals|swimming_base|swimming_intervals|strength_upper|strength_lower|strength_full|strength_push|strength_pull|triathlon_brick|mobility|rest",
  "title": "Short descriptive title",
  "duration_minutes": 60,
  "intensity": "easy|moderate|hard|very_hard|rest",
  "sections": [
    {
      "name": "Warm-up",
      "duration_minutes": 15,
      "description": "Detailed instructions",
      "targets": {
        "power_pct_ftp": 55,
        "hr_zone": 2,
        "rpe": 3,
        "cadence_rpm": 90
      }
    }
  ],
  "exercises": [],
  "key_metrics_considered": ["CTL: X", "ATL: Y", "TSB: Z", "fatigue: N"],
  "cautions": [],
  "rationale": "2-3 sentence evidence-based explanation",
  "nutrition_plan": {
    "calories_target": 2800,
    "carbs_g": 380,
    "protein_g": 160,
    "fat_g": 80,
    "hydration_ml": 3000,
    "pre_workout": "2h before: 60g carbs + 20g protein",
    "during_workout": "30-45g carbs/hour if > 60min",
    "post_workout": "Within 30min: 1g/kg carbs + 0.3g/kg protein",
    "notes": "Extra electrolytes if sweating heavily"
  }
}
""".strip()


# ── Context formatter ─────────────────────────────────────────────────────────

def format_athlete_context(ctx: AthleteContext) -> str:
    lines: list[str] = [
        "=== ATHLETE PROFILE ===",
        f"Name: {ctx.name}",
        f"Age: {ctx.age or 'unknown'}  |  Gender: {ctx.gender or 'unknown'}",
        f"Weight: {ctx.weight_kg or '?'} kg  |  Height: {ctx.height_cm or '?'} cm",
        f"FTP: {ctx.ftp_watts or '?'} W  |  Max HR: {ctx.max_hr or '?'} bpm  |  Resting HR: {ctx.resting_hr or '?'} bpm",
        f"Fitness level: {ctx.fitness_level or 'unknown'}",
        f"Primary modality: {ctx.primary_modality or 'general'}",
        f"Sport modalities: {', '.join(ctx.sport_modalities) or 'not specified'}",
        f"Goal: {ctx.goal or 'not specified'}",
        "",
    ]

    if ctx.weekly_availability:
        lines.append("Weekly availability:")
        for sport, days in ctx.weekly_availability.items():
            lines.append(f"  {sport}: {', '.join(days)}")
        lines.append("")

    if ctx.target_event:
        lines.append(f"Target event: {ctx.target_event}  ({ctx.weeks_to_event} weeks away)")
        lines.append("")

    lines += [
        "=== TRAINING LOAD (TODAY) ===",
        f"CTL (Fitness, 42d): {ctx.ctl:.1f}",
        f"ATL (Fatigue,  7d): {ctx.atl:.1f}",
        f"TSB (Form):         {ctx.tsb:+.1f}  → state: {_tsb_state(ctx.tsb)}",
        f"Daily TSS:          {ctx.daily_tss:.1f}",
        f"Weekly TSS:         {ctx.weekly_tss:.1f}",
        f"Is new athlete:     {ctx.is_new_athlete}",
        f"Detraining detected:{ctx.detraining_detected}",
        "",
    ]

    if ctx.latest_metrics:
        m = ctx.latest_metrics
        lines += [
            "=== TODAY'S SUBJECTIVE METRICS ===",
            f"Fatigue score:     {m.get('fatigue_score', '?')} / 10",
            f"Muscle soreness:   {m.get('muscle_soreness', '?')} / 10",
            f"Motivation:        {m.get('motivation_score', '?')} / 10",
            f"Stress:            {m.get('stress_score', '?')} / 10",
            f"Sleep hours:       {m.get('sleep_hours', '?')}",
            f"Sleep quality:     {m.get('sleep_quality', '?')} / 10",
            f"HRV:               {m.get('hrv_ms', '?')} ms",
            f"Resting HR:        {m.get('resting_hr', '?')} bpm",
            f"Notes: {m.get('notes') or 'none'}",
            "",
        ]
    else:
        lines += ["=== SUBJECTIVE METRICS: NOT RECORDED TODAY ===", ""]

    if ctx.recent_workouts:
        lines.append("=== RECENT WORKOUTS (last 14 sessions) ===")
        for w in ctx.recent_workouts[:14]:
            tss = f"  TSS={w.get('tss', '?'):.0f}" if w.get('tss') else ""
            np  = f"  NP={w.get('normalized_power_watts')}W" if w.get('normalized_power_watts') else ""
            hr  = f"  avgHR={w.get('avg_heart_rate')}bpm" if w.get('avg_heart_rate') else ""
            adherence = f"  [ADHERENCE: {w.get('adherence_hint')}]" if w.get('adherence_hint') else ""
            lines.append(
                f"  {w.get('start_time', '')[:10]}  {w.get('sport_type','?'):12s}"
                f"  {_fmt_dur(w.get('duration_seconds'))}{tss}{np}{hr}{adherence}"
            )
        lines.append("")

    if ctx.recent_strength:
        lines.append("=== RECENT STRENGTH SESSIONS (last 7) ===")
        for s in ctx.recent_strength[:7]:
            tss = f"  TSS={float(s.get('tss') or 0):.0f}" if s.get('tss') else ""
            lines.append(
                f"  {str(s.get('session_date',''))[:10]}  {s.get('session_type','?'):12s}"
                f"  {s.get('duration_minutes','?')}min  RPE={s.get('rpe_overall','?')}{tss}"
            )
        lines.append("")

    lines += [
        "=== INSTRUCTION ===",
        "Generate tomorrow's training session JSON. Follow all TSB decision rules.",
        "Return ONLY valid JSON — no markdown, no preamble, no explanation outside the JSON.",
    ]

    return "\n".join(lines)


def _tsb_state(tsb: float) -> str:
    if tsb < -25: return "CRITICAL — rest mandatory"
    if tsb < -15: return "very fatigued"
    if tsb < -5:  return "fatigued"
    if tsb < 5:   return "neutral"
    if tsb < 15:  return "fresh"
    return "very fresh"


def _fmt_dur(seconds: int | None) -> str:
    if not seconds: return "?min"
    h, m = divmod(seconds // 60, 60)
    return f"{h}h{m:02d}min" if h else f"{m}min"


# ── JSON parse (progressive) ──────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """
    Progressive JSON extraction:
    1. Direct parse
    2. Extract from ```json ... ``` fences
    3. Find outermost { } braces
    4. Return minimal rest-day fallback
    """
    raw = raw.strip()

    # Attempt 1 — direct
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Attempt 2 — strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 3 — find first complete JSON object
    start = raw.find("{")
    if start != -1:
        depth, end = 0, -1
        for i, ch in enumerate(raw[start:], start):
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end != -1:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass

    logger.warning("JSON parse failed; using rest-day fallback. Raw: %s", raw[:200])
    return _rest_day_plan("JSON parse failure")


def _rest_day_plan(reason: str = "") -> dict:
    return {
        "workout_type": "rest",
        "title": "Dia de descanso",
        "duration_minutes": 0,
        "intensity": "rest",
        "sections": [],
        "exercises": [],
        "key_metrics_considered": [],
        "cautions": [f"Rest day prescribed as fallback. Reason: {reason}"] if reason else [],
        "rationale": "Active recovery prescribed due to technical limitations or safety override.",
        "nutrition_plan": {
            "calories_target": None,
            "carbs_g": None,
            "protein_g": None,
            "hydration_ml": 2500,
            "pre_workout": None,
            "during_workout": None,
            "post_workout": None,
            "notes": "Focus on hydration and adequate protein for recovery.",
        },
    }


# ── Safety check ──────────────────────────────────────────────────────────────

def safety_check(plan: dict, ctx: AthleteContext) -> list[str]:
    """
    Returns list of safety warnings. If non-empty, caller should re-prompt or downgrade.
    """
    warnings: list[str] = []
    workout_type = plan.get("workout_type", "")
    intensity = plan.get("intensity", "")
    duration = plan.get("duration_minutes", 0) or 0

    # Hard override: critical TSB must = rest
    if ctx.tsb < -25 and workout_type not in ("rest", "mobility"):
        warnings.append(f"TSB={ctx.tsb:.1f} is critical but plan prescribes '{workout_type}'. Override to rest.")

    # Extreme fatigue
    if ctx.latest_metrics:
        fatigue = ctx.latest_metrics.get("fatigue_score") or 0
        soreness = ctx.latest_metrics.get("muscle_soreness") or 0
        sleep_q  = ctx.latest_metrics.get("sleep_quality") or 10

        if fatigue >= 9 and intensity in ("hard", "very_hard"):
            warnings.append(f"fatigue_score={fatigue}/10 but intensity='{intensity}'. Downgrade needed.")
        if soreness >= 9 and "strength" in workout_type:
            warnings.append(f"muscle_soreness={soreness}/10 but strength session prescribed.")
        if sleep_q <= 3 and intensity in ("hard", "very_hard"):
            warnings.append(f"sleep_quality={sleep_q}/10 but high-intensity session prescribed.")

    # Absurd duration
    if duration > 360:
        warnings.append(f"duration={duration}min exceeds 6 hours — likely an error.")
    if duration > 180 and intensity == "very_hard":
        warnings.append(f"Very hard session lasting {duration}min is physiologically dangerous.")

    # FTP-based power sanity
    if ctx.ftp_watts:
        for section in plan.get("sections", []):
            pct = section.get("targets", {}).get("power_pct_ftp")
            if pct and pct > 160:
                warnings.append(f"Section '{section.get('name')}' targets {pct}% FTP — unrealistic for a training session.")

    return warnings


def _downgrade_plan(plan: dict, warnings: list[str]) -> dict:
    """Downgrade intensity level by one step after safety warnings."""
    downgrade_map = {"very_hard": "hard", "hard": "moderate", "moderate": "easy", "easy": "rest"}
    new_intensity = downgrade_map.get(plan.get("intensity", "moderate"), "easy")
    plan = dict(plan)
    plan["intensity"] = new_intensity
    plan.setdefault("cautions", []).extend(warnings)
    plan["rationale"] = (
        f"[SAFETY OVERRIDE] {plan.get('rationale', '')} "
        f"Intensity downgraded due to: {'; '.join(warnings)}"
    )
    return plan


# ── Default nutrition fallback ────────────────────────────────────────────────

def generate_default_nutrition(weight_kg: float | None, workout_type: str) -> dict:
    w = weight_kg or 70.0
    is_hard = any(k in workout_type for k in ("threshold", "vo2", "interval", "long", "brick"))
    is_rest  = workout_type in ("rest", "mobility")

    if is_rest:
        carbs_g   = round(w * 3)
        protein_g = round(w * 2.2)
        fat_g     = round(w * 1.0)
    elif is_hard:
        carbs_g   = round(w * 6)
        protein_g = round(w * 1.8)
        fat_g     = round(w * 1.0)
    else:
        carbs_g   = round(w * 4.5)
        protein_g = round(w * 1.8)
        fat_g     = round(w * 1.0)

    calories = carbs_g * 4 + protein_g * 4 + fat_g * 9

    return {
        "calories_target": calories,
        "carbs_g": carbs_g,
        "protein_g": protein_g,
        "fat_g": fat_g,
        "hydration_ml": 3000 if is_hard else 2500,
        "pre_workout": "1-2h before: carbs + light protein" if not is_rest else None,
        "during_workout": "30-60g carbs/hour if session > 60min" if is_hard else None,
        "post_workout": f"Within 30min: {round(w)}g carbs + {round(w * 0.3)}g protein",
        "notes": "Generated by default formula — AI nutritional guidance unavailable.",
    }


# ── Main AI service ───────────────────────────────────────────────────────────

class AIService:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or AIProvider(settings.default_ai_provider)
        self._anthropic = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._openai    = openai.OpenAI(api_key=settings.openai_api_key)

    async def _call_anthropic(self, user_message: str) -> tuple[str, int]:
        """Returns (raw_response_text, tokens_used)."""
        response = self._anthropic.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            temperature=0.3,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text if response.content else ""
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return text, tokens

    async def _call_openai(self, user_message: str) -> tuple[str, int]:
        """Returns (raw_response_text, tokens_used)."""
        response = self._openai.chat.completions.create(
            model=settings.openai_model,
            temperature=0.3,
            max_tokens=2048,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
        )
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return text, tokens

    def _parse_recommendation(
        self,
        raw: str,
        provider: str,
        model: str,
        ctx: AthleteContext,
        generation_time_ms: int,
        tokens_used: int,
    ) -> TrainingRecommendation:
        plan = _extract_json(raw)

        # Ensure nutrition_plan is present (fallback if AI omitted it)
        if not plan.get("nutrition_plan") or not isinstance(plan.get("nutrition_plan"), dict):
            plan["nutrition_plan"] = generate_default_nutrition(ctx.weight_kg, plan.get("workout_type", "rest"))

        # Safety check
        warnings = safety_check(plan, ctx)
        if warnings:
            logger.warning("Safety warnings for %s: %s", ctx.name, warnings)
            if any("TSB" in w for w in warnings) and ctx.tsb < -25:
                # Hard override to rest
                plan = _rest_day_plan("TSB critical override")
            else:
                plan = _downgrade_plan(plan, warnings)

        # Validate required fields per workout_type
        _validate_plan_fields(plan)

        nutrition = plan.pop("nutrition_plan", {})

        return TrainingRecommendation(
            workout_type=plan.get("workout_type", "rest"),
            title=plan.get("title", "Treino do dia"),
            recommendation_text=_plan_to_text(plan),
            structured_plan=plan,
            nutrition_plan=nutrition,
            rationale=plan.get("rationale", ""),
            ai_provider=provider,
            ai_model=model,
            tokens_used=tokens_used,
            generation_time_ms=generation_time_ms,
        )

    async def generate_recommendation(
        self,
        context: AthleteContext,
        provider: AIProvider | None = None,
    ) -> TrainingRecommendation:
        """Primary provider → fallback → rest-day. Never raises."""
        user_message = format_athlete_context(context)
        providers_to_try = [provider or self.provider]
        # Add fallback
        other = AIProvider.OPENAI if providers_to_try[0] == AIProvider.ANTHROPIC else AIProvider.ANTHROPIC
        providers_to_try.append(other)

        last_error: Exception | None = None
        for prov in providers_to_try:
            t0 = time.monotonic()
            try:
                if prov == AIProvider.ANTHROPIC:
                    raw, tokens = await self._call_anthropic(user_message)
                    model = settings.anthropic_model
                else:
                    raw, tokens = await self._call_openai(user_message)
                    model = settings.openai_model

                ms = int((time.monotonic() - t0) * 1000)
                logger.info("AI call (%s) completed in %dms, %d tokens", prov.value, ms, tokens)
                return self._parse_recommendation(raw, prov.value, model, context, ms, tokens)

            except Exception as e:
                last_error = e
                logger.warning("AI provider %s failed: %s — trying next", prov.value, e)

        # All providers failed → rest day
        logger.error("All AI providers failed. Last error: %s", last_error)
        rest = _rest_day_plan("All AI providers unavailable")
        nutrition = rest.pop("nutrition_plan", {})
        return TrainingRecommendation(
            workout_type="rest",
            title="Dia de descanso",
            recommendation_text="Todos os provedores de IA indisponíveis. Descanse hoje.",
            structured_plan=rest,
            nutrition_plan=generate_default_nutrition(context.weight_kg, "rest"),
            rationale="Fallback: IA indisponível.",
            ai_provider="fallback",
            ai_model="none",
        )

    async def analyze_fatigue(self, context: AthleteContext) -> dict:
        if context.tsb < -25:
            level = "critical"
        elif context.tsb < -10:
            level = "high"
        elif context.tsb < 0:
            level = "moderate"
        else:
            level = "low"

        return {
            "level": level,
            "tsb": context.tsb,
            "ctl": context.ctl,
            "atl": context.atl,
            "summary": f"TSB de {context.tsb:+.1f} indica nível de fadiga {level}.",
            "recommendations": _fatigue_recommendations(level),
        }


def _fatigue_recommendations(level: str) -> list[str]:
    return {
        "critical": ["Descanso completo obrigatório", "Priorizar sono ≥ 8h", "Reavalie treino em 48h"],
        "high":     ["Sessões leves apenas (Z1/Z2)", "Alongamento e mobilidade", "Sono e nutrição em foco"],
        "moderate": ["Treino moderado permitido", "Evitar esforços máximos", "Monitore métricas diárias"],
        "low":      ["Corpo recuperado", "Sessões de qualidade indicadas", "Boa janela para treino intenso"],
    }.get(level, [])


def _validate_plan_fields(plan: dict) -> None:
    """Fill missing required fields with sensible defaults to prevent frontend errors."""
    plan.setdefault("workout_type", "rest")
    plan.setdefault("title", "Treino do dia")
    plan.setdefault("duration_minutes", 0)
    plan.setdefault("intensity", "easy")
    plan.setdefault("sections", [])
    plan.setdefault("exercises", [])
    plan.setdefault("key_metrics_considered", [])
    plan.setdefault("cautions", [])
    plan.setdefault("rationale", "")


def _plan_to_text(plan: dict) -> str:
    """Convert structured plan to a human-readable summary string."""
    lines = [f"**{plan.get('title')}**"]
    lines.append(f"Tipo: {plan.get('workout_type')} | Duração: {plan.get('duration_minutes')}min | Intensidade: {plan.get('intensity')}")
    for s in plan.get("sections", []):
        lines.append(f"\n**{s.get('name')}** ({s.get('duration_minutes')}min)")
        lines.append(s.get("description", ""))
    for e in plan.get("exercises", []):
        lines.append(f"• {e.get('name')}: {e.get('sets')}x{e.get('reps')} @ {e.get('load', '—')}")
    if plan.get("cautions"):
        lines.append(f"\n⚠️ {'; '.join(plan['cautions'])}")
    return "\n".join(lines)


# ── Context builder ───────────────────────────────────────────────────────────

async def build_athlete_context(db: AsyncSession, athlete_id: str) -> AthleteContext | None:
    athlete_result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        return None

    # Training load
    load = await get_current_load(db, athlete_id) or {"ctl": 0, "atl": 0, "tsb": 0, "daily_tss": 0, "weekly_tss": 0}

    # Recent workouts (last 14 endurance sessions)
    wkt_result = await db.execute(
        select(Workout)
        .where(Workout.athlete_id == athlete_id, Workout.is_completed == True)
        .order_by(desc(Workout.start_time))
        .limit(14)
    )
    recent_workouts = [
        {
            "sport_type": w.sport_type,
            "start_time": w.start_time.isoformat() if w.start_time else None,
            "duration_seconds": w.duration_seconds,
            "tss": float(w.tss) if w.tss else None,
            "normalized_power_watts": w.normalized_power_watts,
            "avg_heart_rate": w.avg_heart_rate,
            "title": w.title,
        }
        for w in wkt_result.scalars().all()
    ]

    # Last workout adherence (compare yesterday's recommendation vs executed)
    from app.models.recommendation import AIRecommendation
    from app.utils.adherence import analyze_workout_adherence
    yesterday = today - timedelta(days=1)
    yesterday_rec_result = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.athlete_id == athlete_id,
            AIRecommendation.recommendation_date == yesterday,
        )
    )
    yesterday_rec = yesterday_rec_result.scalar_one_or_none()
    if yesterday_rec and yesterday_rec.structured_plan and recent_workouts:
        last_wkt = recent_workouts[0]
        last_wkt_date = (last_wkt.get("start_time") or "")[:10]
        if last_wkt_date == str(yesterday):
            adherence = analyze_workout_adherence(yesterday_rec.structured_plan, last_wkt)
            # Inject adherence hint into first workout entry
            recent_workouts[0]["adherence_hint"] = adherence.adjustment_hint
            recent_workouts[0]["tss_deviation_pct"] = adherence.tss_deviation_pct

    # Recent strength (last 7)
    str_result = await db.execute(
        select(StrengthSession)
        .where(StrengthSession.athlete_id == athlete_id)
        .order_by(desc(StrengthSession.session_date))
        .limit(7)
    )
    recent_strength = [
        {
            "session_date": s.session_date.isoformat() if s.session_date else None,
            "session_type": s.session_type,
            "duration_minutes": s.duration_minutes,
            "rpe_overall": s.rpe_overall,
            "tss": float(s.tss) if s.tss else None,
        }
        for s in str_result.scalars().all()
    ]

    # Today's metrics
    today = date.today()
    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.athlete_id == athlete_id,
            DailyMetric.metric_date == today,
        )
    )
    m = metrics_result.scalar_one_or_none()
    latest_metrics = None
    if m:
        latest_metrics = {
            "fatigue_score": m.fatigue_score,
            "muscle_soreness": m.muscle_soreness,
            "motivation_score": m.motivation_score,
            "stress_score": m.stress_score,
            "sleep_hours": float(m.sleep_hours) if m.sleep_hours else None,
            "sleep_quality": m.sleep_quality,
            "hrv_ms": m.hrv_ms,
            "resting_hr": m.resting_hr,
            "notes": m.notes,
        }

    # Age
    age = None
    if athlete.birth_date:
        today_date = date.today()
        bd = athlete.birth_date
        age = today_date.year - bd.year - ((today_date.month, today_date.day) < (bd.month, bd.day))

    # Flags
    is_new = len(recent_workouts) < 3
    detraining = False
    if len(recent_workouts) >= 2:
        last_date = recent_workouts[0].get("start_time", "")[:10]
        if last_date:
            days_gap = (today - date.fromisoformat(last_date)).days
            detraining = days_gap > 10

    return AthleteContext(
        name=athlete.name,
        age=age,
        weight_kg=float(athlete.weight_kg) if athlete.weight_kg else None,
        height_cm=float(athlete.height_cm) if athlete.height_cm else None,
        gender=athlete.gender,
        ftp_watts=athlete.ftp_watts,
        max_hr=athlete.max_hr,
        resting_hr=athlete.resting_hr,
        sport_modalities=athlete.sport_modalities or [],
        primary_modality=athlete.primary_modality,
        fitness_level=athlete.fitness_level,
        goal=athlete.goal,
        weekly_availability=athlete.weekly_availability,
        ctl=load["ctl"],
        atl=load["atl"],
        tsb=load["tsb"],
        daily_tss=load["daily_tss"],
        weekly_tss=load["weekly_tss"],
        recent_workouts=recent_workouts,
        recent_strength=recent_strength,
        latest_metrics=latest_metrics,
        is_new_athlete=is_new,
        detraining_detected=detraining,
        metrics_missing=(latest_metrics is None),
    )
