"""
Cenários de avaliação do agente.

Cada cenário é uma situação onde uma regra específica do contrato deve morder.
Foram escolhidos pelo mesmo critério: são os casos em que um modelo sem as
restrições certas produz uma saída plausível e errada — TSB crítico onde ele
quer prescrever qualidade, CTL não convergido onde ele quer falar de
progressão, base fraca onde ele quer soar confiante.

Os cenários não dependem do banco: constroem um AthleteContext direto, então
rodam na CI sem Postgres e sem chave de API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from app.services.ai_service import AthleteContext


@dataclass
class Scenario:
    nome: str
    descricao: str
    contexto: AthleteContext
    # O que a saída precisa respeitar. Recebe (plano, contexto) e devolve
    # mensagens de falha — vazio significa aprovado.
    expectativas: list[Callable[[dict, AthleteContext], list[str]]] = field(default_factory=list)


def _ctx(**over) -> AthleteContext:
    """Atleta-base razoável; cada cenário sobrescreve só o que interessa."""
    base = dict(
        name="Atleta Teste", age=38, weight_kg=78.0, height_cm=178.0, gender="M",
        ftp_watts=250, max_hr=185, resting_hr=52,
        sport_modalities=["cycling"], primary_modality="cycling",
        fitness_level="intermediate", goal="Melhorar resistência", weekly_availability=None,
        ctl=55.0, atl=60.0, tsb=-5.0, daily_tss=70.0, weekly_tss=420.0,
        recent_workouts=[
            {"sport_type": "cycling", "start_time": "2026-01-19T07:00:00+00:00",
             "duration_seconds": 3600, "tss": 75.0, "tss_method": "power",
             "normalized_power_watts": 210, "avg_heart_rate": 145, "title": "Endurance"},
        ] * 5,
        recent_strength=[], latest_metrics={
            "fatigue_score": 4, "muscle_soreness": 3, "motivation_score": 7,
            "sleep_quality": 7, "sleep_hours": 7.5, "hrv_ms": 60, "resting_hr": 52,
            "stress_score": 4, "notes": None,
        },
        history_days=120, ctl_converged=True,
    )
    base.update(over)
    return AthleteContext(**base)


# ── Expectativas reutilizáveis ────────────────────────────────────────────────

def espera_descanso(plano: dict, ctx: AthleteContext) -> list[str]:
    if plano.get("workout_type") not in ("rest", "mobility"):
        return [f"TSB={ctx.tsb:.1f} exige rest/mobility, veio {plano.get('workout_type')!r}"]
    return []


def espera_sem_intensidade(plano: dict, ctx: AthleteContext) -> list[str]:
    if plano.get("intensity") in ("hard", "very_hard"):
        return [f"intensidade {plano.get('intensity')!r} indevida neste cenário"]
    return []


def espera_dentro_do_tempo(plano: dict, ctx: AthleteContext) -> list[str]:
    """O teto de tempo é rígido: um treino que não cabe no dia é inútil."""
    if not ctx.available_minutes:
        return []
    total = plano.get("duration_minutes") or 0
    if total > ctx.available_minutes:
        return [f"sessão de {total}min excede os {ctx.available_minutes}min disponíveis"]
    # A soma das seções tem de bater com o total declarado.
    soma = sum(s.get("duration_minutes") or 0 for s in plano.get("sections") or [])
    if soma and soma > ctx.available_minutes:
        return [f"seções somam {soma}min, acima dos {ctx.available_minutes}min disponíveis"]
    return []


def espera_mencao(*termos: str):
    """A justificativa precisa reconhecer explicitamente a limitação do cenário."""
    def _check(plano: dict, ctx: AthleteContext) -> list[str]:
        texto = (plano.get("rationale", "") + " " +
                 " ".join(plano.get("cautions") or [])).lower()
        faltando = [t for t in termos if t.lower() not in texto]
        return [f"justificativa não menciona: {', '.join(faltando)}"] if faltando else []
    return _check


# ── Os cenários ───────────────────────────────────────────────────────────────

SCENARIOS: list[Scenario] = [
    Scenario(
        nome="tsb_critico",
        descricao=(
            "TSB muito negativo. A regra do prompt é dura e sem exceção: só rest "
            "ou mobility. É o cenário onde um modelo tende a negociar."
        ),
        contexto=_ctx(ctl=70.0, atl=100.0, tsb=-30.0, weekly_tss=800.0),
        expectativas=[espera_descanso],
    ),
    Scenario(
        nome="fadiga_extrema_com_tsb_positivo",
        descricao=(
            "TSB positivo convida à qualidade, mas a fadiga reportada é 9/10. "
            "Métrica subjetiva severa vence o TSB — o caso onde o número "
            "objetivo e o relato do atleta discordam."
        ),
        contexto=_ctx(
            ctl=60.0, atl=45.0, tsb=+12.0,
            latest_metrics={"fatigue_score": 9, "muscle_soreness": 5,
                            "motivation_score": 5, "sleep_quality": 6,
                            "sleep_hours": 6.0, "hrv_ms": 45, "resting_hr": 58,
                            "stress_score": 7, "notes": "Acordei quebrado"},
        ),
        expectativas=[espera_sem_intensidade],
    ),
    Scenario(
        nome="ctl_nao_convergido",
        descricao=(
            "Apenas 21 dias de histórico: o CTL está subestimado por construção. "
            "Regra 9 — nada pode se ancorar em progressão de CTL."
        ),
        contexto=_ctx(history_days=21, ctl_converged=False, ctl=18.0, atl=22.0, tsb=-4.0),
        expectativas=[espera_mencao("histórico")],
    ),
    Scenario(
        nome="sem_metricas_subjetivas",
        descricao=(
            "Nenhuma métrica do dia. A decisão se apoia só na carga objetiva e "
            "o agente precisa declarar essa lacuna em vez de preencher."
        ),
        contexto=_ctx(latest_metrics=None, metrics_missing=True),
        expectativas=[],
    ),
    Scenario(
        nome="tss_apenas_por_fc",
        descricao=(
            "Sem potenciômetro: todo TSS é estimativa por FC. O agente deve "
            "tratar a carga como aproximada, não como medida."
        ),
        contexto=_ctx(
            ftp_watts=None,
            recent_workouts=[
                {"sport_type": "cycling", "start_time": "2026-01-19T07:00:00+00:00",
                 "duration_seconds": 3600, "tss": 68.0, "tss_method": "hr",
                 "normalized_power_watts": None, "avg_heart_rate": 148,
                 "title": "Pedal"},
            ] * 5,
        ),
        expectativas=[],
    ),
    Scenario(
        nome="atleta_novo",
        descricao=(
            "Um único treino registrado. Base insuficiente para individualizar; "
            "a sugestão deve ser conservadora e assumidamente genérica."
        ),
        contexto=_ctx(
            history_days=3, ctl_converged=False, ctl=5.0, atl=8.0, tsb=-2.0,
            weekly_tss=70.0, is_new_athlete=True,
            recent_workouts=[
                {"sport_type": "cycling", "start_time": "2026-01-19T07:00:00+00:00",
                 "duration_seconds": 2400, "tss": 45.0, "tss_method": "hr",
                 "normalized_power_watts": None, "avg_heart_rate": 140, "title": "Primeiro"},
            ],
        ),
        expectativas=[espera_sem_intensidade],
    ),
    Scenario(
        nome="tempo_curto_no_dia",
        descricao=(
            "O atleta tem 40 min hoje e pediu natação, mas a agenda semanal "
            "marca ciclismo de 90 min nesta terça. O pedido do dia é mais "
            "específico e vence — e a duração é teto rígido, não sugestão."
        ),
        contexto=_ctx(
            target_date=date(2026, 1, 20),   # terça-feira
            weekly_availability={"cycling": {"days": ["tue", "thu"], "minutes": 90}},
            available_minutes=40,
            preferred_modality="swimming",
            sport_modalities=["cycling", "swimming"],
        ),
        expectativas=[espera_dentro_do_tempo],
    ),
    Scenario(
        nome="dia_sem_nada_agendado",
        descricao=(
            "Quarta-feira, e o atleta não marcou nenhuma modalidade para este "
            "dia. Dia livre é informação, não uma lacuna a preencher com uma "
            "sessão inventada."
        ),
        contexto=_ctx(
            target_date=date(2026, 1, 21),   # quarta-feira
            weekly_availability={"cycling": {"days": ["tue", "thu"], "minutes": 90}},
        ),
        expectativas=[],
    ),
    Scenario(
        nome="sessoes_duplicadas",
        descricao=(
            "O mesmo treino entrou pelo registro manual e pelo Strava. O TSS do "
            "dia está dobrado e a série inteira de CTL/ATL/TSB, inflada. O gate "
            "tem de bloquear antes de qualquer interpretação de carga."
        ),
        contexto=_ctx(
            recent_workouts=[
                {"sport_type": "cycling", "source": "manual",
                 "start_time": "2026-01-19T07:00:00+00:00", "duration_seconds": 3600,
                 "tss": 75.0, "tss_method": "hr", "normalized_power_watts": None,
                 "avg_heart_rate": 145, "title": "Pedal registrado à mão"},
                {"sport_type": "cycling", "source": "strava",
                 "start_time": "2026-01-19T07:06:00+00:00", "duration_seconds": 3650,
                 "tss": 76.0, "tss_method": "hr", "normalized_power_watts": None,
                 "avg_heart_rate": 146, "title": "Morning Ride"},
            ],
        ),
        expectativas=[],
    ),
    Scenario(
        nome="feedback_baixa_aderencia_forca",
        descricao=(
            "O atleta ignorou as três últimas sessões de força e disse por quê. "
            "O agente deve adaptar a abordagem — não repetir mais forte, nem "
            "abandonar o estímulo."
        ),
        contexto=_ctx(
            recent_feedback=[
                {"date": "2026-01-18", "workout_type": "strength_lower", "title": "Força",
                 "rating": 2, "was_followed": False,
                 "notes": "Não consigo ir à academia em dia de semana"},
                {"date": "2026-01-15", "workout_type": "strength_lower", "title": "Força",
                 "rating": 2, "was_followed": False, "notes": None},
                {"date": "2026-01-11", "workout_type": "strength_lower", "title": "Força",
                 "rating": None, "was_followed": False, "notes": None},
            ],
            feedback_patterns=[{"workout_type": "strength_lower", "n": 3,
                                "avg_rating": 2.0, "followed_rate": 0.0}],
        ),
        expectativas=[],
    ),
]


def by_name(nome: str) -> Scenario:
    for s in SCENARIOS:
        if s.nome == nome:
            return s
    raise KeyError(f"cenário desconhecido: {nome!r} (disponíveis: "
                   f"{', '.join(s.nome for s in SCENARIOS)})")
