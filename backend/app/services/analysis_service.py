"""
Agente analítico (§13–15 do contrato).

Modo distinto do prescritor de `ai_service`: em vez de propor UMA sessão para
amanhã, produz uma ANÁLISE AUDITÁVEL para validação de um treinador humano —
separando o que é medida, o que é inferência e o que não pode ser afirmado.

A divisão de trabalho é deliberada:
  - o que é determinístico (métricas, proveniência, status) é montado em Python
    e nunca delegado ao modelo — regra 3 do prompt de sistema proíbe a IA de
    calcular TSS/ATL/CTL/TSB em texto livre;
  - o que é interpretativo (observações, inferências, opções para o treinador)
    vem do modelo, restrito pelo contexto e pelas limitações já apuradas.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from app.config import settings
from app.services.ai_service import (
    AIProvider,
    AIService,
    AthleteContext,
    DataQualityReport,
    _extract_json,
    _first_text,
    format_athlete_context,
)

logger = logging.getLogger(__name__)


# ── §15: prompt de sistema do agente analítico ────────────────────────────────

ANALYST_SYSTEM_PROMPT = """
Você é o fitCoach AI, agente especialista em Educação Física, fisiologia do
exercício e treinamento esportivo de endurance e alta performance.

Sua função é interpretar dados normalizados de Strava, TrainingPeaks e outras
fontes autorizadas, verificar sua qualidade e produzir análises auditáveis para
validação de um treinador humano.

REGRAS INEGOCIÁVEIS

1. Use esta hierarquia: TrainingPeaks oficial; cálculo determinístico local;
   Strava ou arquivo original; informação declarada; referência genérica.
2. Informe a origem das métricas relevantes.
3. Nunca calcule TSS, ATL, CTL ou TSB em texto livre. Use somente resultados
   fornecidos pelas ferramentas determinísticas — os números já vêm no contexto.
4. Classifique afirmações como medida, inferência, convenção ou dado ausente.
5. Não transforme convenção em fato, prescrição obrigatória ou causalidade.
6. Não diagnostique, não prediga lesão e não emita julgamento clínico.
7. Diante de fadiga persistente, perda de desempenho ou sintomas, descreva
   apenas o padrão registrado e informe que a avaliação excede seu domínio.
8. Antes de interpretar, verifique fuso IANA, série densa, origem do TSS,
   limiares vigentes, semeadura, extensão do histórico e convergência.
9. Bloqueie recomendações dependentes de CTL quando ctl_converged não for true.
10. Não reproduza NGP ou hrTSS por fórmula própria.
11. Declare que TSS não captura integralmente ambiente, sono, nutrição,
    estresse, força, doença ou histórico de lesão.
12. Toda alteração em plano ou dado externo exige autorização explícita.
13. Feedback do atleta (notas, aderência, comentários) é INFORMAÇÃO DECLARADA —
    nível 4 da hierarquia. Classifique-o como tal: revela preferência e
    aderência, nunca resposta fisiológica. "O atleta não executou 3 das 4
    sessões de força" é uma medida de aderência e uma observação legítima para
    o treinador; "o atleta responde bem a limiar porque avaliou 5/5" é uma
    inferência fisiológica que o dado não sustenta. Padrões de aderência
    pertencem às opções para o treinador, não às inferências permitidas.

Você NÃO prescreve. Você apresenta OPÇÕES para o treinador humano decidir.

FORMATO DE SAÍDA

Responda SOMENTE com JSON válido, sem markdown e sem texto fora do JSON:

{
  "observed_measures": [
    "Afirmações sobre valores da própria série do atleta, com unidades."
  ],
  "permitted_inferences": [
    "Padrões que a série sustenta, marcados como inferência, sem causalidade."
  ],
  "coach_options": [
    {
      "option": "Descrição objetiva de um caminho possível",
      "rationale": "Por que este caminho é coerente com os dados",
      "tradeoff": "O que se perde ou arrisca ao escolher este caminho"
    }
  ],
  "limitations": [
    "O que os dados não permitem afirmar; dados ausentes relevantes."
  ],
  "safety_flags": [
    "Padrões registrados que merecem atenção humana — sem diagnóstico."
  ]
}

Use português do Brasil, terminologia técnica, linguagem objetiva e números com
unidades. Diferencie claramente fato, inferência e incerteza.
""".strip()


# ── §13: contrato de saída ────────────────────────────────────────────────────

@dataclass
class CoachOption:
    option: str
    rationale: str = ""
    tradeoff: str = ""

    def to_dict(self) -> dict:
        return {"option": self.option, "rationale": self.rationale, "tradeoff": self.tradeoff}


@dataclass
class TrainingAnalysis:
    """Saída do agente analítico, no formato do §13."""
    status: str                                  # complete | limited | blocked
    data_quality: dict
    observed_measures: list[str] = field(default_factory=list)
    permitted_inferences: list[str] = field(default_factory=list)
    coach_options: list[CoachOption] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)
    metric_provenance: list[dict] = field(default_factory=list)
    requires_human_validation: bool = True
    ai_provider: str = ""
    ai_model: str = ""
    generation_time_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "data_quality": self.data_quality,
            "observed_measures": self.observed_measures,
            "permitted_inferences": self.permitted_inferences,
            "coach_options": [o.to_dict() for o in self.coach_options],
            "limitations": self.limitations,
            "safety_flags": self.safety_flags,
            "metric_provenance": self.metric_provenance,
            "requires_human_validation": self.requires_human_validation,
            "ai_provider": self.ai_provider,
            "ai_model": self.ai_model,
            "generation_time_ms": self.generation_time_ms,
        }


# ── Blocos determinísticos (nunca delegados ao modelo) ────────────────────────

_GRADE_BY_LEVEL = {"ok": "high", "degraded": "moderate", "insufficient": "low"}
_STATUS_BY_LEVEL = {"ok": "complete", "degraded": "limited", "insufficient": "blocked"}

_SOURCE_LABEL = {
    "power":    ("cálculo determinístico local", "medida"),
    "hr":       ("cálculo determinístico local", "estimativa"),
    "strength": ("cálculo determinístico local", "estimativa"),
    "stored":   ("plataforma de origem", "importado"),
}


def build_metric_provenance(ctx: AthleteContext) -> list[dict]:
    """
    Monta a proveniência das métricas (§13) a partir dos dados reais — nunca
    pedindo ao modelo, que não tem como saber a origem de cada número.
    """
    prov: list[dict] = []

    # Origem agregada do TSS das sessões recentes.
    methods = [w.get("tss_method") for w in ctx.recent_workouts if w.get("tss")]
    if methods:
        counts: dict[str, int] = {}
        for m in methods:
            counts[m or "desconhecido"] = counts.get(m or "desconhecido", 0) + 1
        for method, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            source, kind = _SOURCE_LABEL.get(method, ("origem não identificada", "dado ausente"))
            prov.append({
                "metric": "TSS",
                "source": source,
                "classification": kind,
                "detail": f"{n} sessão(ões) com TSS via '{method}'",
            })

    # CTL/ATL/TSB são sempre derivados da série local.
    for metric in ("CTL", "ATL", "TSB"):
        entry = {
            "metric": metric,
            "source": "cálculo determinístico local",
            "classification": "medida" if ctx.ctl_converged else "estimativa",
            "detail": f"série de {ctx.history_days} dia(s)"
                      + ("" if ctx.ctl_converged else " — abaixo da convergência (~90 dias)"),
        }
        prov.append(entry)

    # Limiares declarados pelo atleta (não medidos pelo sistema).
    if ctx.ftp_watts:
        prov.append({
            "metric": "FTP", "source": "informação declarada", "classification": "convenção",
            "detail": f"{ctx.ftp_watts} W declarado no perfil — não verificado por teste",
        })
    if ctx.max_hr:
        prov.append({
            "metric": "FC máxima", "source": "informação declarada", "classification": "convenção",
            "detail": f"{ctx.max_hr} bpm declarado no perfil",
        })

    return prov


def _deterministic_limitations(ctx: AthleteContext, quality: DataQualityReport) -> list[str]:
    """Limitações que decorrem dos dados, não da leitura do modelo (regra 11)."""
    lims = [
        "O TSS resume apenas duração e intensidade relativa ao limiar. Não captura "
        "ambiente (calor, umidade, altitude, terreno), sono, nutrição, estresse "
        "ocupacional, trabalho de força, doença nem histórico de lesão.",
    ]
    lims += [c.message for c in quality.checks]
    if not ctx.ctl_converged:
        lims.append(
            f"Com {ctx.history_days} dia(s) de histórico, o CTL está subestimado por "
            "construção: qualquer leitura de progressão ancorada nele fica bloqueada "
            "até a série convergir (~90 dias)."
        )
    return lims


def _fallback_analysis(ctx: AthleteContext, quality: DataQualityReport, reason: str) -> TrainingAnalysis:
    """
    Análise mínima quando a IA não responde. Mantém o contrato e a honestidade:
    entrega só o que é determinístico e declara a ausência do resto.
    """
    return TrainingAnalysis(
        status="blocked",
        data_quality={
            "grade": _GRADE_BY_LEVEL.get(quality.level, "low"),
            "issues": [c.message for c in quality.checks if c.severity != "info"],
            "missing_data": [c.message for c in quality.checks if c.severity == "info"],
        },
        observed_measures=[
            f"CTL {ctx.ctl:.1f} · ATL {ctx.atl:.1f} · TSB {ctx.tsb:+.1f} "
            f"(série local de {ctx.history_days} dia(s)).",
            f"TSS da semana: {ctx.weekly_tss:.0f}.",
        ],
        permitted_inferences=[],
        coach_options=[],
        limitations=_deterministic_limitations(ctx, quality) + [
            f"Camada interpretativa indisponível nesta execução ({reason}): apenas as "
            "medidas determinísticas foram apresentadas.",
        ],
        safety_flags=[],
        metric_provenance=build_metric_provenance(ctx),
        requires_human_validation=True,
    )


# ── Serviço ───────────────────────────────────────────────────────────────────

class AnalysisService:
    """Agente analítico. Reaproveita os clientes do AIService."""

    def __init__(self, ai: AIService | None = None):
        self._ai = ai or AIService()

    async def _call(self, prov: AIProvider, user_message: str) -> tuple[str, str]:
        """Retorna (texto_bruto, modelo)."""
        if prov == AIProvider.ANTHROPIC:
            response = await self._ai._anthropic.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.ai_max_tokens,
                # `temperature` foi removido no Opus 4.7+ (retorna 400).
                output_config={"effort": settings.ai_effort},
                system=ANALYST_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            if response.stop_reason == "refusal":
                raise RuntimeError("Anthropic recusou a requisição (stop_reason=refusal)")
            return _first_text(response.content), settings.anthropic_model

        response = await self._ai._openai.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            max_tokens=settings.ai_max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        return (response.choices[0].message.content or ""), settings.openai_model

    async def analyze(
        self,
        ctx: AthleteContext,
        quality: DataQualityReport,
    ) -> TrainingAnalysis:
        """Executa a análise. Nunca levanta exceção — degrada para o fallback."""
        ctx.data_quality_notes = quality.notes
        user_message = (
            format_athlete_context(ctx)
            .replace(
                "=== INSTRUCTION ===",
                "=== INSTRUÇÃO ===",
            )
            + "\n\nProduza a análise auditável no formato JSON especificado. "
              "Não prescreva: apresente opções para o treinador humano decidir."
        )

        providers = [self._ai.provider]
        providers.append(
            AIProvider.OPENAI if providers[0] == AIProvider.ANTHROPIC else AIProvider.ANTHROPIC
        )

        last_error: Exception | None = None
        for prov in providers:
            t0 = time.monotonic()
            try:
                raw, model = await self._call(prov, user_message)
                ms = int((time.monotonic() - t0) * 1000)
                return self._parse(raw, ctx, quality, prov.value, model, ms)
            except Exception as e:
                last_error = e
                logger.warning("Analysis provider %s failed: %s — trying next", prov.value, e)

        logger.error("All analysis providers failed. Last error: %s", last_error)
        return _fallback_analysis(ctx, quality, "todos os provedores indisponíveis")

    def _parse(
        self,
        raw: str,
        ctx: AthleteContext,
        quality: DataQualityReport,
        provider: str,
        model: str,
        ms: int,
    ) -> TrainingAnalysis:
        try:
            parsed = _extract_json(raw)
        except Exception:
            logger.warning("Analysis JSON parse failed; raw: %s", raw[:200])
            return _fallback_analysis(ctx, quality, "resposta ilegível do provedor")

        # O status vem da qualidade dos dados apurada em Python, não do modelo:
        # o agente não pode se autodeclarar "completo" sobre base fraca (regra 9).
        status = _STATUS_BY_LEVEL.get(quality.level, "limited")

        options = []
        for o in parsed.get("coach_options") or []:
            if isinstance(o, dict):
                options.append(CoachOption(
                    option=str(o.get("option", "")).strip(),
                    rationale=str(o.get("rationale", "")).strip(),
                    tradeoff=str(o.get("tradeoff", "")).strip(),
                ))
            elif isinstance(o, str):
                options.append(CoachOption(option=o.strip()))
        options = [o for o in options if o.option]

        # Regra 9: sem CTL convergido, opções não podem se ancorar em progressão
        # de CTL. Não silencio o modelo — anexo a ressalva a cada opção.
        if not ctx.ctl_converged and options:
            for o in options:
                o.tradeoff = (
                    (o.tradeoff + " " if o.tradeoff else "")
                    + "[CTL não convergido: não use esta opção para justificar progressão de carga.]"
                ).strip()

        def _strs(key: str) -> list[str]:
            return [str(x).strip() for x in (parsed.get(key) or []) if str(x).strip()]

        # Limitações determinísticas SEMPRE presentes, mesmo que o modelo as omita.
        limitations = _deterministic_limitations(ctx, quality)
        for extra in _strs("limitations"):
            if extra not in limitations:
                limitations.append(extra)

        return TrainingAnalysis(
            status=status,
            data_quality={
                "grade": _GRADE_BY_LEVEL.get(quality.level, "low"),
                "issues": [c.message for c in quality.checks if c.severity != "info"],
                "missing_data": [c.message for c in quality.checks if c.severity == "info"],
            },
            observed_measures=_strs("observed_measures"),
            permitted_inferences=_strs("permitted_inferences"),
            coach_options=options,
            limitations=limitations,
            safety_flags=_strs("safety_flags"),
            metric_provenance=build_metric_provenance(ctx),
            requires_human_validation=True,
            ai_provider=provider,
            ai_model=model,
            generation_time_ms=ms,
        )
