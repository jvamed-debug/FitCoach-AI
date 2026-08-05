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
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.availability import DIA_PT, describe_for_prompt, weekday_key
from app.models.athlete import Athlete
from app.models.metric import DailyMetric
from app.models.workout import Workout
from app.models.strength import StrengthSession
from app.models.training_load import TrainingLoad
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
    # Convergência da série de CTL (§8.9 da spec): CTL só é confiável com
    # histórico longo; abaixo disso está subestimado por construção.
    ctl_converged: bool = True
    history_days: int = 0
    target_event: str | None = None
    weeks_to_event: int | None = None
    # §7: notas do gate de qualidade de dados, injetadas no prompt para que o
    # agente se auto-restrinja quando a base é fraca (preenchido em _generate_and_save).
    data_quality_notes: list[str] = field(default_factory=list)
    # Ciclo de feedback: o que o atleta achou das recomendações anteriores e
    # quais ele de fato executou. É INFORMAÇÃO DECLARADA (§5, nível 4) — revela
    # preferência e aderência, nunca resposta fisiológica.
    recent_feedback: list[dict] = field(default_factory=list)
    feedback_patterns: list[dict] = field(default_factory=list)
    # Dia da sessão. Sem isto o agente vê "cycling: tue, thu, sat" e não tem
    # como cruzar com a agenda — não sabe que dia é hoje.
    target_date: date | None = None
    # Override do dia, informado na hora ("hoje só tenho 40 min", "quero nadar").
    # Vence a disponibilidade declarada, que é a regra geral; a situação real do
    # dia é mais específica que o padrão semanal.
    available_minutes: int | None = None
    preferred_modality: str | None = None


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


# ── §7: Gate de qualidade de dados ────────────────────────────────────────────

@dataclass
class DataQualityCheck:
    code: str
    severity: str   # "info" | "warning" | "blocking"
    message: str


@dataclass
class DataQualityReport:
    """
    Laudo formal de qualidade dos dados que sustentam a recomendação (§7).
    Não impede a geração — degrada com honestidade: expõe as limitações ao
    agente (via prompt) e ao atleta (via API), para que ninguém trate uma base
    fraca como se fosse forte.
    """
    level: str                       # "ok" | "degraded" | "insufficient"
    checks: list[DataQualityCheck] = field(default_factory=list)

    @property
    def notes(self) -> list[str]:
        return [c.message for c in self.checks]

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "checks": [
                {"code": c.code, "severity": c.severity, "message": c.message}
                for c in self.checks
            ],
        }


def _parse_dt(valor):
    """ISO 8601 tolerante a 'Z' e a valores ausentes."""
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def detect_duplicates(workouts: list[dict]) -> list[tuple[dict, dict]]:
    """
    §7: sessões duplicadas entre fontes.

    O caso real: o atleta registra o treino manualmente e depois sincroniza o
    Strava — a mesma sessão entra duas vezes, com fontes diferentes. O TSS do
    dia dobra, e como CTL/ATL/TSB derivam dele, TODO número a jusante fica
    inflado sem nenhum sinal de erro. É a falha de qualidade mais cara desta
    lista, porque é silenciosa e permanente.

    Heurística: início a menos de 15 min de distância, fontes distintas e
    durações dentro de 15%. Deliberadamente conservadora — duas sessões
    genuinamente distintas no mesmo horário são raras, mas um falso positivo
    aqui só gera um aviso, nunca descarta dado.
    """
    pares: list[tuple[dict, dict]] = []
    comdata = [(w, _parse_dt(w.get("start_time"))) for w in workouts]
    comdata = [(w, d) for w, d in comdata if d is not None]

    for i, (a, da) in enumerate(comdata):
        for b, db in comdata[i + 1:]:
            if a.get("source") == b.get("source"):
                continue
            if abs((da - db).total_seconds()) > 15 * 60:
                continue
            dur_a = a.get("duration_seconds") or 0
            dur_b = b.get("duration_seconds") or 0
            if dur_a and dur_b:
                maior = max(dur_a, dur_b)
                if abs(dur_a - dur_b) / maior > 0.15:
                    continue
            pares.append((a, b))
    return pares


def detect_gaps(workouts: list[dict], *, min_dias: int = 14) -> list[tuple[str, str, int]]:
    """
    §7: lacunas na série.

    Uma lacuna longa entre sessões registradas pode significar duas coisas
    opostas — o atleta parou, ou treinou sem registrar. As duas produzem o
    mesmo decaimento de CTL/ATL, e a diferença importa. O agente precisa
    perguntar em vez de assumir.
    """
    datas = sorted(d for d in (_parse_dt(w.get("start_time")) for w in workouts) if d)
    lacunas: list[tuple[str, str, int]] = []
    for anterior, seguinte in zip(datas, datas[1:]):
        dias = (seguinte - anterior).days
        if dias >= min_dias:
            lacunas.append((anterior.date().isoformat(), seguinte.date().isoformat(), dias))
    return lacunas


def detect_device_change(workouts: list[dict]) -> bool:
    """
    §7: mudança abrupta de dispositivo.

    Aproximada pela presença intermitente de potência dentro do ciclismo: se
    parte das sessões tem potenciômetro e parte não, o TSS da série mistura
    medida e estimativa, e uma comparação temporal ingênua leria a troca de
    dispositivo como mudança de condicionamento.
    """
    ciclismo = [w for w in workouts if w.get("sport_type") == "cycling"]
    if len(ciclismo) < 3:
        return False
    com_potencia = sum(1 for w in ciclismo if w.get("normalized_power_watts"))
    return 0 < com_potencia < len(ciclismo)


def assess_data_quality(ctx: "AthleteContext") -> DataQualityReport:
    """
    Executa as verificações de qualidade antes de qualquer chamada de IA.

    Regras (todas convenções de treinamento, não fatos clínicos):
      - histórico curto → CTL subestimado, não ancorar progressão nele;
      - sem métricas subjetivas hoje → decisão só por carga objetiva;
      - sem sessões recentes → base insuficiente para individualizar;
      - TSS só por FC → estimativa, não medida;
      - FTP/FC ausentes → alvos por %FTP ou zonas de FC indisponíveis.
    """
    checks: list[DataQualityCheck] = []

    if not ctx.ctl_converged:
        checks.append(DataQualityCheck(
            "ctl_not_converged", "warning",
            f"Histórico de carga curto ({ctx.history_days} dias): CTL está "
            "subestimado por construção — não ancorar decisões de progressão nele.",
        ))

    if ctx.metrics_missing:
        checks.append(DataQualityCheck(
            "metrics_missing", "warning",
            "Métricas subjetivas de hoje ausentes: a decisão se apoia apenas na "
            "carga objetiva, sem sono, fadiga percebida ou dor muscular.",
        ))

    n_sessions = len(ctx.recent_workouts) + len(ctx.recent_strength)
    if n_sessions == 0:
        checks.append(DataQualityCheck(
            "no_recent_sessions", "blocking",
            "Nenhuma sessão recente registrada: sem base para individualizar a "
            "recomendação — sugestão será conservadora e genérica.",
        ))

    # Proveniência agregada: só há TSS estimado por FC, nenhum medido por potência.
    methods = {w.get("tss_method") for w in ctx.recent_workouts if w.get("tss")}
    if methods and "power" not in methods and "stored" not in methods and methods <= {"hr", "strength"}:
        checks.append(DataQualityCheck(
            "tss_hr_only", "info",
            "TSS recente derivado de FC/RPE (estimativa), não de potência (medida): "
            "trate os valores de carga como aproximados.",
        ))

    modalities = ctx.sport_modalities or []
    if ctx.ftp_watts is None and ("cycling" in modalities or ctx.primary_modality == "cycling"):
        checks.append(DataQualityCheck(
            "no_ftp", "info",
            "FTP não definido: alvos em %FTP indisponíveis — usar RPE e zonas de FC.",
        ))
    if not ctx.max_hr or not ctx.resting_hr:
        checks.append(DataQualityCheck(
            "no_hr_anchors", "info",
            "FC máxima/repouso incompletas: zonas de FC e estimativa de TSS por FC "
            "ficam imprecisas.",
        ))

    # §7: duplicidade entre fontes. Bloqueante porque corrompe o TSS do dia e,
    # por consequência, toda a série de CTL/ATL/TSB — interpretar carga sobre
    # uma base duplicada é pior que não interpretar.
    duplicatas = detect_duplicates(ctx.recent_workouts)
    if duplicatas:
        exemplos = "; ".join(
            f"{(a.get('start_time') or '')[:16]} ({a.get('source')} × {b.get('source')})"
            for a, b in duplicatas[:3]
        )
        checks.append(DataQualityCheck(
            "duplicate_sessions", "blocking",
            f"{len(duplicatas)} par(es) de sessões possivelmente duplicadas entre "
            f"fontes — {exemplos}. Isso dobra o TSS do dia e infla CTL/ATL/TSB. "
            f"Confirme e remova a duplicata antes de interpretar a carga.",
        ))

    # §7: lacunas na série.
    lacunas = detect_gaps(ctx.recent_workouts)
    if lacunas:
        ini, fim, dias = max(lacunas, key=lambda x: x[2])
        checks.append(DataQualityCheck(
            "series_gap", "warning",
            f"Lacuna de {dias} dias entre {ini} e {fim} sem sessão registrada. "
            f"Não é possível distinguir pausa real de treino não registrado — "
            f"as duas produzem o mesmo decaimento de CTL/ATL.",
        ))

    # §7: mudança abrupta de dispositivo.
    if detect_device_change(ctx.recent_workouts):
        checks.append(DataQualityCheck(
            "device_change", "info",
            "Parte das sessões de ciclismo tem potência e parte não: a série "
            "mistura TSS medido e estimado. Uma comparação temporal ingênua "
            "leria a troca de dispositivo como mudança de condicionamento.",
        ))

    if any(c.severity == "blocking" for c in checks):
        level = "insufficient"
    elif any(c.severity == "warning" for c in checks):
        level = "degraded"
    else:
        level = "ok"

    return DataQualityReport(level=level, checks=checks)


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are Dr. Performance — an elite endurance coach, certified strength & conditioning specialist (CSCS), and sports nutritionist. You work with athletes who combine cycling, running, swimming, triathlon, and strength training.

## YOUR MISSION
Generate ONE specific training session for THE DAY NAMED IN THE CONTEXT (see "SESSION DAY, SCHEDULE AND TIME BUDGET"), plus a nutrition plan for that day. Be precise, evidence-based, and individualized.

## GUARDRAILS (mandatory — epistemic and safety discipline)
- DESCRIBE load state; NEVER predict injury and NEVER diagnose. The association between acute/chronic imbalance and injury risk is contested in the literature — do not assert it, even softened. Issue no clinical judgment.
- Keep three registers separate and use distinct wording for each:
  * MEASURED — values from the athlete's own series ("CTL rose from 62 to 71").
  * INFERRED — a pattern in the series ("TSB stayed below -20 for 11 consecutive days").
  * CONVENTION — coaching heuristics and reference ranges (including the TSB bands below). Name them explicitly as conventions without established scientific validation; never present a convention as a hard fact.
- TSS captures only duration and intensity relative to threshold. It ignores terrain, heat, humidity, altitude, sleep, nutrition, occupational stress and injury history. State this limitation before any interpretation when relevant — two TSS-120 sessions cost differently at 32°C vs 14°C.
- Never attribute causality to data you do not have. Sleep, nutrition and stress are not captured by TSS unless explicitly provided.
- Persistent fatigue, performance decline or somatic symptoms may have causes outside training. Surface the pattern to the coach and stop — medical referral is a human decision, never yours.
- Prefer the athlete's actual series values over generic ranges; when you must use a generic range, label it as a convention.
- SOURCE PROVENANCE: state where a metric comes from. TSS derived from POWER (NP/FTP) is reliable; TSS ESTIMATED FROM HEART RATE (TRIMP) is an estimate/convention, not an official value — say so and do not treat it as authoritative. Never invent missing values.
- CTL CONVERGENCE: if the athlete's history is short (context marks CTL as NOT converged, i.e. under ~90 days, and especially under 42), CTL is underestimated by construction. Do NOT anchor progression or high-load decisions on CTL in that case — say the fitness baseline is not yet reliable and prefer subjective metrics and recent sessions.

## TSB DECISION RULES (operational convention — used to choose the session, not a scientific claim)
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

## MODALITY AND TIME (personalise the session to the actual day)
The context names the session's day, what the athlete scheduled for that
weekday, and how long they have. Use all three — a technically perfect session
the athlete has no time to do is a failed recommendation.
- **Time is a hard ceiling.** `duration_minutes` must be the TOTAL of every
  section (warm-up + main set + cool-down) and must never exceed the stated
  budget. When the budget is tight, cut volume before cutting the warm-up, and
  compress the session honestly rather than pretending the same stimulus fits.
- **Duration not declared** means unknown, not unlimited. Infer a plausible
  duration from the athlete's recent sessions of that modality and say that is
  what you did.
- **Prescribe the modality scheduled for that weekday.** If the day has more
  than one, pick the one the load state favours and explain the choice. If the
  athlete requested a modality for today, that request wins over the weekly
  schedule — it is more specific.
- **A day with nothing scheduled is information, not a blank to fill.** Prefer
  rest, mobility, or a short optional session, and say the day was free.
- **Load rules still outrank both.** Having two hours free never justifies
  intensity the TSB rules forbid; a requested modality never overrides a
  critical TSB. When you must refuse a request, say plainly why and offer the
  closest thing you can within that modality (an easy spin instead of
  intervals) rather than silently substituting something else.

## ATHLETE FEEDBACK (declared information — shapes HOW, never WHETHER)
Past ratings, adherence and free-text notes tell you what this athlete
tolerates, enjoys and actually does. They are declared preference, not
physiological measurement, and they rank BELOW load data in the source
hierarchy. Concretely:
- Feedback NEVER overrides the TSB rules or the subjective-metric overrides
  above. A 5/5 rating on hard intervals is not a reason to prescribe intensity
  at TSB < -25. Load decides WHAT the session is; feedback decides how it is
  built and phrased.
- Low adherence to a session type means your approach is not landing — adapt it
  (shorter, different time of day, different exercise selection, clearer
  rationale). It does not mean repeat it harder, and it does not mean drop the
  training quality the athlete needs.
- The free-text notes are the richest signal because they say WHY. Address the
  actual complaint: "too long" is a duration problem, "boring" is a variety
  problem, "knee hurt" is a red flag to surface — never something to design
  around silently.
- Do not infer physiological adaptation from ratings. An athlete rating easy
  sessions highly tells you about preference, not about their aerobic response.
- Small samples are not patterns. If the context says no aggregate pattern has
  formed yet, treat each entry as an anecdote and say so rather than
  generalising from two data points.

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

## WORKED EXAMPLE — the hard case

Context: TSB -28 (critical), athlete rated the last three interval sessions 5/5
and asked for more intensity, fatigue_score 6/10.

The rule is not negotiable here: TSB < -25 means rest or mobility, and a high
rating is preference, not physiology. The skill is delivering that without
sounding punitive or dismissive of what the athlete wants.

{
  "workout_type": "rest",
  "title": "Descanso — a carga acumulada pede",
  "duration_minutes": 0,
  "intensity": "rest",
  "sections": [],
  "exercises": [],
  "rationale": "Seu TSB está em -28, o ponto mais negativo das últimas seis semanas: a fadiga acumulada (ATL 98) está bem acima da base de condicionamento (CTL 70). Isso é uma medida da sua própria série, não uma estimativa. Você avaliou os últimos intervalados em 5/5 e pediu mais intensidade — isso me diz que a sessão está bem construída para você, e ela volta assim que o TSB permitir. O que a nota não mede é a carga acumulada, e é ela que decide hoje. Descanso agora protege exatamente as sessões de qualidade que você quer fazer: treinar forte com TSB nesse nível costuma render menos e atrasar a recuperação.",
  "key_metrics_considered": ["TSB: -28", "CTL: 70", "ATL: 98", "fatigue_score: 6/10"],
  "cautions": ["O TSS não captura sono, calor, estresse nem trabalho de força — se algum desses estiver pesado, o custo real foi maior que o registrado."]
}

Note what the example does: it names the number and its provenance, it takes
the athlete's preference seriously and says when it will be honoured, it
separates what the rating measures from what it does not, and it gives a
reason to rest that serves the athlete's own goal. It does not moralise, does
not predict injury, and does not soften the decision into an option.
""".strip()


# ── Context formatter ─────────────────────────────────────────────────────────

def format_athlete_context(ctx: AthleteContext) -> str:
    lines: list[str] = []

    # §7: o gate de qualidade vem PRIMEIRO — o agente deve calibrar a confiança
    # de toda a análise por estas limitações antes de ler qualquer número.
    if ctx.data_quality_notes:
        lines.append("=== DATA QUALITY GATE (read first — constrain your confidence) ===")
        for note in ctx.data_quality_notes:
            lines.append(f"  ⚠ {note}")
        lines.append("")

    lines += [
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

    # Dia da sessão + agenda + tempo. Nesta ordem de propósito: o agente precisa
    # saber QUE DIA é antes de a agenda semanal significar alguma coisa.
    alvo = ctx.target_date or date.today()
    lines.append("=== SESSION DAY, SCHEDULE AND TIME BUDGET ===")
    lines.append(
        f"This session is for {alvo.isoformat()} "
        f"({DIA_PT[weekday_key(alvo)]}, '{weekday_key(alvo)}')."
    )
    lines += describe_for_prompt(ctx.weekly_availability, alvo)

    # O override do dia vence a agenda declarada — é mais específico.
    if ctx.available_minutes:
        lines.append(
            f"TIME AVAILABLE TODAY: {ctx.available_minutes} minutes — stated by "
            f"the athlete for this specific day. This is a HARD ceiling and it "
            f"overrides the weekly declaration. Total session duration "
            f"(warm-up + main set + cool-down) must not exceed it."
        )
    if ctx.preferred_modality:
        lines.append(
            f"MODALITY REQUESTED TODAY: {ctx.preferred_modality} — stated by the "
            f"athlete for this specific day. Honour it unless the load state "
            f"forbids training at all; if you cannot, say plainly why and offer "
            f"the closest alternative within that modality."
        )
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
        f"Load history:       {ctx.history_days} days"
        + ("" if ctx.ctl_converged
           else "  → CTL NOT CONVERGED (underestimated; do not anchor decisions on CTL)"),
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
        # §13: cada TSS carrega sua proveniência para o agente ponderar confiança.
        _PROV = {"power": "medida", "hr": "estimativa-FC", "strength": "estimativa-RPE", "stored": "importado"}
        for w in ctx.recent_workouts[:14]:
            if w.get('tss'):
                prov = _PROV.get(w.get('tss_method'))
                tss = f"  TSS={w['tss']:.0f}" + (f"[{prov}]" if prov else "")
            else:
                tss = ""
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

    # Ciclo de feedback. Rotulado como DECLARED INFORMATION (§5, nível 4) para
    # que o agente não o confunda com medida fisiológica: uma nota alta diz que
    # o atleta GOSTOU, não que a sessão foi adequada à carga dele.
    if ctx.recent_feedback:
        lines.append("=== ATHLETE FEEDBACK ON PAST RECOMMENDATIONS ===")
        lines.append(
            "DECLARED INFORMATION (source hierarchy level 4) — preference and "
            "adherence only. Never physiological response, never a reason to "
            "override the TSB rules or the subjective-metric overrides."
        )
        if ctx.feedback_patterns:
            lines.append(f"Patterns (only types with >= {_MIN_PARA_PADRAO} entries):")
            for p in ctx.feedback_patterns:
                bits = [f"n={p['n']}"]
                if p["avg_rating"] is not None:
                    bits.append(f"avg rating {p['avg_rating']}/5")
                if p["followed_rate"] is not None:
                    bits.append(f"followed {p['followed_rate'] * 100:.0f}%")
                lines.append(f"  {p['workout_type']:22s} {' · '.join(bits)}")
        else:
            lines.append(
                f"No aggregate pattern yet (no workout type reached "
                f"{_MIN_PARA_PADRAO} rated sessions). Treat the entries below as "
                f"individual data points, not as a trend."
            )
        lines.append("Most recent entries:")
        for f in ctx.recent_feedback[:10]:
            rating = f"{f['rating']}/5" if f["rating"] is not None else "sem nota"
            followed = (
                "executou" if f["was_followed"] is True
                else "NÃO executou" if f["was_followed"] is False
                else "execução não informada"
            )
            lines.append(
                f"  {f.get('date', '')[:10]}  {f.get('workout_type') or '?':22s}"
                f"  {rating:9s}  {followed}"
            )
            if f["notes"]:
                # O texto livre é o sinal mais rico: é o único que diz POR QUÊ.
                lines.append(f'      nota do atleta: "{f["notes"]}"')
        lines.append("")

    lines += [
        "=== INSTRUCTION ===",
        f"Generate the training session JSON for {alvo.isoformat()} "
        f"({DIA_PT[weekday_key(alvo)]}). Follow all TSB decision rules, the "
        f"time budget and the modality scheduled or requested for this day.",
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

def _is_config_error(exc: Exception) -> bool:
    """
    Distingue erro de código/configuração de indisponibilidade da API.

    TypeError/AttributeError vindos de uma chamada ao SDK quase sempre
    significam parâmetro que a versão fixada não conhece ou campo que mudou de
    forma — um bug que nenhum retry resolve. Tratá-lo como "provedor fora do ar"
    é o que fez a recomendação cair silenciosamente no plano de descanso.
    """
    return isinstance(exc, (TypeError, AttributeError, NameError, ImportError))


def _first_text(blocks) -> str:
    """
    Extrai o texto da resposta da Anthropic.

    Necessário porque `content[0]` NÃO é o texto quando há raciocínio: nos
    modelos atuais o thinking vem ligado por padrão e ocupa os primeiros
    blocos, então indexar em [0] pegava um bloco sem `.text` e levantava
    AttributeError. Percorre os blocos e concatena apenas os de tipo 'text'.
    """
    return "".join(
        b.text for b in (blocks or [])
        if getattr(b, "type", None) == "text" and getattr(b, "text", None)
    )

class AIService:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or AIProvider(settings.default_ai_provider)
        # Async clients: the sync SDK clients do blocking network I/O, which would
        # freeze the whole event loop for the multi-second duration of an AI call.
        self._anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._openai    = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def _call_anthropic(self, user_message: str) -> tuple[str, int]:
        """Returns (raw_response_text, tokens_used)."""
        response = await self._anthropic.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.ai_max_tokens,
            # Sem `temperature`: o parâmetro foi removido no Opus 4.7+ e retorna
            # 400. A determinação vem do prompt e do effort, não da amostragem.
            output_config={"effort": settings.ai_effort},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        # Os classificadores de segurança podem recusar (HTTP 200 + stop_reason).
        if response.stop_reason == "refusal":
            raise RuntimeError("Anthropic recusou a requisição (stop_reason=refusal)")
        text = _first_text(response.content)
        tokens = response.usage.input_tokens + response.usage.output_tokens
        return text, tokens

    async def _call_openai(self, user_message: str) -> tuple[str, int]:
        """Returns (raw_response_text, tokens_used)."""
        response = await self._openai.chat.completions.create(
            model=settings.openai_model,
            temperature=0.3,
            max_tokens=settings.ai_max_tokens,
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
                if _is_config_error(e):
                    # Erro de código/configuração: não é indisponibilidade e não
                    # vai se curar sozinho. Já custou dois diagnósticos errados
                    # (parâmetro inexistente no SDK fixado, chave ausente) porque
                    # ficava indistinguível de uma queda da API.
                    logger.error(
                        "AI provider %s: ERRO DE CONFIGURAÇÃO (%s: %s). "
                        "Isto é um bug, não indisponibilidade — verifique versão do "
                        "SDK, nome do modelo e variáveis de ambiente.",
                        prov.value, type(e).__name__, e,
                    )
                else:
                    logger.warning("AI provider %s failed: %s — trying next", prov.value, e)

        # All providers failed → rest day.
        # O texto distingue as duas causas: um erro de configuração continuaria
        # devolvendo "descanso" todo dia, e sem essa distinção o atleta leria
        # isso como uma prescrição real da IA em vez de um defeito a corrigir.
        is_config = last_error is not None and _is_config_error(last_error)
        logger.error(
            "All AI providers failed (%s). Last error: %s: %s",
            "ERRO DE CONFIGURAÇÃO" if is_config else "indisponibilidade",
            type(last_error).__name__ if last_error else "?", last_error,
        )
        if is_config:
            reason = (
                "Erro de configuração da IA — este texto NÃO é uma recomendação de "
                "treino. Nenhum modelo chegou a ser consultado. Verifique a versão "
                "do SDK, o nome do modelo e as variáveis de ambiente do backend."
            )
        else:
            reason = (
                "Provedores de IA indisponíveis no momento — este texto NÃO é uma "
                "recomendação de treino. Tente gerar novamente em alguns minutos."
            )
        rest = _rest_day_plan(reason)
        rest.pop("nutrition_plan", None)
        return TrainingRecommendation(
            workout_type="rest",
            title="Recomendação indisponível",
            recommendation_text=reason,
            structured_plan=rest,
            nutrition_plan=generate_default_nutrition(context.weight_kg, "rest"),
            rationale=reason,
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


# ── Ciclo de feedback ─────────────────────────────────────────────────────────

# Abaixo disto não é padrão, é anedota. Duas notas altas para "cycling_threshold"
# não significam que o atleta responde bem a limiar — significam que ele avaliou
# duas sessões. O agente vê as entradas individuais de qualquer forma; só a
# AGREGAÇÃO exige massa mínima.
_MIN_PARA_PADRAO = 3


def _summarize_feedback(recs) -> tuple[list[dict], list[dict]]:
    """
    Converte recomendações avaliadas em (entradas individuais, padrões agregados).

    Devolve as duas formas de propósito: as entradas carregam as notas em texto
    livre — o sinal mais rico e o único que explica o PORQUÊ de uma nota baixa —
    enquanto os agregados só aparecem quando há amostra suficiente.
    """
    entries: list[dict] = []
    por_tipo: dict[str, list[dict]] = {}

    for r in recs:
        entry = {
            "date": r.recommendation_date.isoformat() if r.recommendation_date else None,
            "workout_type": r.workout_type,
            "title": r.title,
            "rating": r.feedback_rating,
            "was_followed": r.was_followed,
            "notes": (r.feedback_notes or "").strip() or None,
        }
        entries.append(entry)
        if r.workout_type:
            por_tipo.setdefault(r.workout_type, []).append(entry)

    patterns: list[dict] = []
    for wtype, items in por_tipo.items():
        if len(items) < _MIN_PARA_PADRAO:
            continue
        notas = [i["rating"] for i in items if i["rating"] is not None]
        executados = [i["was_followed"] for i in items if i["was_followed"] is not None]
        patterns.append({
            "workout_type": wtype,
            "n": len(items),
            "avg_rating": round(sum(notas) / len(notas), 1) if notas else None,
            "followed_rate": (
                round(sum(1 for x in executados if x) / len(executados), 2)
                if executados else None
            ),
        })

    patterns.sort(key=lambda p: -p["n"])
    return entries, patterns


# ── Context builder ───────────────────────────────────────────────────────────

async def build_athlete_context(
    db: AsyncSession,
    athlete_id: str,
    *,
    target_date: date | None = None,
    available_minutes: int | None = None,
    preferred_modality: str | None = None,
) -> AthleteContext | None:
    athlete_result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        return None

    # Definido aqui porque o bloco de aderência abaixo já o usa; atribuí-lo só
    # junto das métricas do dia deixava a função inteira em UnboundLocalError.
    today = date.today()

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
            "source": w.source,          # §7: necessário para detectar duplicidade
            "start_time": w.start_time.isoformat() if w.start_time else None,
            "duration_seconds": w.duration_seconds,
            "tss": float(w.tss) if w.tss else None,
            "tss_method": w.tss_method,
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

    # Ciclo de feedback: recomendações passadas que o atleta avaliou ou marcou
    # como (não) executadas. Sem isso o app coletava a nota e a descartava.
    fb_result = await db.execute(
        select(AIRecommendation)
        .where(
            AIRecommendation.athlete_id == athlete_id,
            or_(
                AIRecommendation.feedback_rating.isnot(None),
                AIRecommendation.was_followed.isnot(None),
            ),
        )
        .order_by(desc(AIRecommendation.recommendation_date))
        .limit(20)
    )
    recent_feedback, feedback_patterns = _summarize_feedback(fb_result.scalars().all())

    # Today's metrics
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

    # Convergência do CTL: nº de dias de histórico na série de carga (§8.9).
    hist_result = await db.execute(
        select(func.count()).select_from(TrainingLoad).where(TrainingLoad.athlete_id == athlete_id)
    )
    history_days = int(hist_result.scalar() or 0)
    ctl_converged = history_days >= 90

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
        ctl_converged=ctl_converged,
        history_days=history_days,
        recent_feedback=recent_feedback,
        feedback_patterns=feedback_patterns,
        target_date=target_date or today,
        available_minutes=available_minutes,
        preferred_modality=preferred_modality,
    )
