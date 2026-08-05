"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import DataQualityNotice from "@/components/recommendations/DataQualityNotice";
import type { AIRecommendation, StructuredPlan, NutritionPlan } from "@/lib/types";

const WORKOUT_ICON: Record<string, string> = {
  cycling_endurance:  "🚴", cycling_threshold:  "⚡", cycling_vo2max:   "🔥",
  cycling_long:       "🗺️", running_easy:       "🏃", running_tempo:    "💨",
  running_intervals:  "🏁", swimming_base:      "🏊", swimming_intervals:"🌊",
  strength_upper:     "💪", strength_lower:     "🦵", strength_full:    "🏋️",
  strength_push:      "↑",  strength_pull:      "↓",  triathlon_brick:  "🏅",
  mobility:           "🧘", rest:               "😴",
};

const INTENSITY_COLOR: Record<string, string> = {
  easy:      "bg-green-100 text-green-700",
  moderate:  "bg-blue-100 text-blue-700",
  hard:      "bg-orange-100 text-orange-700",
  very_hard: "bg-red-100 text-red-700",
  rest:      "bg-surface-2 text-muted-foreground",
};

function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hovered, setHovered] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHovered(star)}
          onMouseLeave={() => setHovered(0)}
          className="text-2xl transition-transform hover:scale-110"
        >
          {star <= (hovered || value) ? "⭐" : "☆"}
        </button>
      ))}
    </div>
  );
}

function SectionCard({ section }: { section: StructuredPlan["sections"][0] }) {
  const [open, setOpen] = useState(true);
  const t = section.targets ?? {};
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-background hover:bg-surface-2 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm text-foreground">{section.name}</span>
          <span className="text-xs text-muted-foreground">{section.duration_minutes}min</span>
        </div>
        <div className="flex items-center gap-2">
          {t.power_pct_ftp && (
            <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
              {t.power_pct_ftp}% FTP
            </span>
          )}
          {t.hr_zone && (
            <span className="text-xs bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full">
              Z{t.hr_zone}
            </span>
          )}
          {t.rpe && (
            <span className="text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full">
              RPE {t.rpe}
            </span>
          )}
          <span className="text-muted-foreground text-sm">{open ? "▲" : "▼"}</span>
        </div>
      </button>
      {open && (
        <div className="px-4 py-3 text-sm text-muted-foreground">
          {section.description}
        </div>
      )}
    </div>
  );
}

function ExerciseTable({ exercises }: { exercises: StructuredPlan["exercises"] }) {
  if (!exercises?.length) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-background text-left">
            <th className="px-3 py-2 text-xs font-medium text-muted-foreground">Exercício</th>
            <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-center">Séries</th>
            <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-center">Reps</th>
            <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-center">Carga</th>
            <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-center">Descanso</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {exercises.map((ex, i) => (
            <tr key={i} className="hover:bg-background">
              <td className="px-3 py-2 font-medium text-foreground">{ex.name}</td>
              <td className="px-3 py-2 text-center">{ex.sets}</td>
              <td className="px-3 py-2 text-center">{ex.reps || "—"}</td>
              <td className="px-3 py-2 text-center">{ex.load || "—"}</td>
              <td className="px-3 py-2 text-center">{ex.rest_seconds ? `${ex.rest_seconds}s` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NutritionCard({ nutrition }: { nutrition: NutritionPlan | null }) {
  const [open, setOpen] = useState(false);
  if (!nutrition) return null;

  return (
    <div className="bg-surface rounded-xl border border-border">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">🥗</span>
          <span className="font-medium text-foreground">Plano Nutricional</span>
          {nutrition.calories_target && (
            <span className="text-xs text-muted-foreground">{nutrition.calories_target} kcal</span>
          )}
        </div>
        <span className="text-muted-foreground">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-border pt-4">
          {/* Macros */}
          {(nutrition.carbs_g || nutrition.protein_g || nutrition.fat_g) && (
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Carboidratos", value: nutrition.carbs_g, unit: "g", color: "bg-yellow-50 text-yellow-700" },
                { label: "Proteínas",    value: nutrition.protein_g, unit: "g", color: "bg-blue-50 text-blue-700" },
                { label: "Gorduras",     value: nutrition.fat_g,     unit: "g", color: "bg-orange-50 text-orange-700" },
              ].map(({ label, value, unit, color }) =>
                value ? (
                  <div key={label} className={`rounded-lg p-3 text-center ${color}`}>
                    <p className="text-xl font-bold">{value}{unit}</p>
                    <p className="text-xs mt-0.5">{label}</p>
                  </div>
                ) : null
              )}
            </div>
          )}

          {/* Timing */}
          <div className="space-y-2 text-sm">
            {[
              { icon: "🕐", label: "Pré-treino",   value: nutrition.pre_workout },
              { icon: "⚡", label: "Durante",       value: nutrition.during_workout },
              { icon: "🏁", label: "Pós-treino",    value: nutrition.post_workout },
              { icon: "💧", label: "Hidratação",    value: nutrition.hydration_ml ? `${nutrition.hydration_ml}ml total` : null },
              { icon: "📝", label: "Observações",   value: nutrition.notes },
            ].filter((row) => row.value).map(({ icon, label, value }) => (
              <div key={label} className="flex gap-2">
                <span>{icon}</span>
                <div>
                  <span className="font-medium text-foreground">{label}: </span>
                  <span className="text-muted-foreground">{value}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function RecommendationsPage() {
  const router = useRouter();
  const { role } = useAuthStore();
  const [rec, setRec] = useState<AIRecommendation | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rating, setRating] = useState(0);
  const [feedbackNotes, setFeedbackNotes] = useState("");
  const [minutosHoje, setMinutosHoje] = useState("");
  const [modalidadeHoje, setModalidadeHoje] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [rationaleOpen, setRationaleOpen] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!role) { router.replace("/auth/login"); return; }
    loadToday();
  }, [role, router]);

  const loadToday = async () => {
    setGenerating(true);
    setError(null);
    try {
      const resp = await api.get("/api/recommendations/today");
      setRec(resp.data);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? "Erro ao carregar recomendação");
    } finally {
      setGenerating(false);
    }
  };

  const forceGenerate = async () => {
    // Ajustes do dia. Enviados só quando preenchidos: sem eles vale a
    // disponibilidade semanal do perfil.
    const ajustes: Record<string, unknown> = {};
    if (minutosHoje) ajustes.available_minutes = Number(minutosHoje);
    if (modalidadeHoje) ajustes.preferred_modality = modalidadeHoje;

    setGenerating(true);
    setError(null);
    setRec(null);
    setFeedbackSubmitted(false);
    setRating(0);
    setFeedbackNotes("");

    // Poll every 5s up to 60s
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      if (attempts > 12) {
        clearInterval(poll);
        setGenerating(false);
        setError("Tempo limite atingido. Tente novamente.");
        return;
      }
      try {
        const resp = await api.post("/api/recommendations/generate", ajustes);
        if (resp.data?.workout_type) {
          clearInterval(poll);
          setRec(resp.data);
          setGenerating(false);
        }
      } catch {
        // Keep polling
      }
    }, 5000);
    pollRef.current = poll;

    // First attempt immediately
    try {
      const resp = await api.post("/api/recommendations/generate", ajustes);
      if (resp.data?.workout_type) {
        clearInterval(poll);
        setRec(resp.data);
        setGenerating(false);
      }
    } catch {
      // Wait for polling
    }
  };

  const submitFeedback = async () => {
    if (!rec || !rating) return;
    setSubmittingFeedback(true);
    try {
      await api.post(`/api/recommendations/${rec.id}/feedback`, {
        rating,
        notes: feedbackNotes || undefined,
      });
      setFeedbackSubmitted(true);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const plan = rec?.structured_plan as StructuredPlan | null;
  const nutrition = rec?.nutrition_plan as NutritionPlan | null;
  const icon = rec ? (WORKOUT_ICON[rec.workout_type ?? ""] ?? "🏋️") : "";
  const intensityBadge = plan ? (INTENSITY_COLOR[plan.intensity] ?? "bg-surface-2 text-muted-foreground") : "";

  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <div className="bg-surface border-b border-border px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Recomendação de hoje</h1>
            <p className="text-sm text-muted-foreground">
              {new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}
            </p>
          </div>
          <button
            onClick={forceGenerate}
            disabled={generating}
            className="rounded-lg border border-brand-300 text-brand-700 px-3 py-1.5 text-sm font-medium hover:bg-brand-50 disabled:opacity-40 transition-colors"
          >
            {generating ? "Gerando…" : "↻ Nova recomendação"}
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-6 space-y-5">

        {/* Ajustes do dia. Opcionais: em branco, vale a disponibilidade
            semanal do perfil. Preenchidos, vencem — a situação real de hoje
            é mais específica que o padrão da semana. */}
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-sm font-medium text-foreground">Ajustar para hoje</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Opcional. Em branco, uso a disponibilidade do seu perfil.
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Tempo disponível</span>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min={5}
                  max={480}
                  step={5}
                  inputMode="numeric"
                  placeholder="90"
                  value={minutosHoje}
                  onChange={(e) => setMinutosHoje(e.target.value)}
                  className="w-24 rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm text-foreground"
                />
                <span className="text-xs text-muted-foreground">min</span>
              </div>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Modalidade</span>
              <select
                value={modalidadeHoje}
                onChange={(e) => setModalidadeHoje(e.target.value)}
                className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm text-foreground"
              >
                <option value="">Deixar a IA escolher</option>
                <option value="cycling">Ciclismo</option>
                <option value="running">Corrida</option>
                <option value="swimming">Natação</option>
                <option value="strength">Musculação</option>
                <option value="mobility">Mobilidade</option>
              </select>
            </label>
            <button
              onClick={forceGenerate}
              disabled={generating}
              className="rounded-lg bg-accent px-3.5 py-2 text-sm font-semibold text-accent-foreground transition hover:brightness-110 disabled:opacity-40"
            >
              {generating ? "Gerando…" : "Gerar com estes ajustes"}
            </button>
          </div>
          {(minutosHoje || modalidadeHoje) && (
            <p className="mt-2.5 text-xs text-muted-foreground">
              O tempo é um teto — a sessão não passa dele. A carga acumulada ainda
              manda: se o descanso for indicado, ele vem mesmo assim.
            </p>
          )}
        </div>

        {/* Generating state */}
        {generating && !rec && (
          <div className="bg-surface rounded-2xl border border-border p-12 text-center">
            <div className="text-5xl mb-4 animate-pulse">🤖</div>
            <p className="font-medium text-foreground mb-1">Gerando seu treino…</p>
            <p className="text-sm text-muted-foreground">
              A IA está analisando seu histórico, CTL/ATL/TSB e métricas do dia.
            </p>
            <div className="mt-4 h-1 bg-surface-2 rounded-full overflow-hidden">
              <div className="h-full bg-brand-500 animate-pulse w-3/4 rounded-full" />
            </div>
          </div>
        )}

        {/* Error state */}
        {error && !generating && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-center">
            <p className="text-red-700 text-sm mb-3">{error}</p>
            <button onClick={loadToday} className="text-sm text-brand-600 font-medium hover:underline">
              Tentar novamente
            </button>
          </div>
        )}

        {/* Recommendation card */}
        {rec && !generating && (
          <>
            {/* Gate de qualidade (§7) — vem antes da prescrição de propósito:
                o atleta deve saber sobre qual base a sugestão foi construída. */}
            <DataQualityNotice report={rec.data_quality} />

            {/* Header */}
            <div className="bg-surface rounded-2xl border border-border p-6">
              <div className="flex items-start gap-4">
                <div className="text-5xl">{icon}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-xl font-bold text-foreground">{rec.title}</h2>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${intensityBadge}`}>
                      {plan?.intensity}
                    </span>
                  </div>
                  <div className="flex gap-3 mt-1 text-sm text-muted-foreground flex-wrap">
                    {plan?.duration_minutes ? (
                      <span>⏱ {plan.duration_minutes}min</span>
                    ) : null}
                    <span className="capitalize">📊 {rec.workout_type?.replace(/_/g, " ")}</span>
                    <span className="text-xs text-gray-300">via {rec.ai_provider}</span>
                  </div>
                </div>
              </div>

              {/* Cautions */}
              {plan?.cautions && plan.cautions.length > 0 && (
                <div className="mt-4 bg-orange-50 border border-orange-200 rounded-lg px-4 py-2 text-sm text-orange-700">
                  ⚠️ {plan.cautions.join(" · ")}
                </div>
              )}

              {/* Key metrics */}
              {plan?.key_metrics_considered && plan.key_metrics_considered.length > 0 && (
                <div className="mt-3 flex gap-2 flex-wrap">
                  {plan.key_metrics_considered.map((m, i) => (
                    <span key={i} className="text-xs bg-surface-2 text-muted-foreground px-2 py-0.5 rounded-full">{m}</span>
                  ))}
                </div>
              )}
            </div>

            {/* Sections */}
            {plan?.sections && plan.sections.length > 0 && (
              <div className="bg-surface rounded-2xl border border-border p-5">
                <h3 className="font-medium text-foreground mb-3">Estrutura do treino</h3>
                <div className="space-y-2">
                  {plan.sections.map((s, i) => (
                    <SectionCard key={i} section={s} />
                  ))}
                </div>
              </div>
            )}

            {/* Exercises (strength) */}
            {plan?.exercises && plan.exercises.length > 0 && (
              <div className="bg-surface rounded-2xl border border-border p-5">
                <h3 className="font-medium text-foreground mb-3">Exercícios</h3>
                <ExerciseTable exercises={plan.exercises} />
              </div>
            )}

            {/* Nutrition */}
            <NutritionCard nutrition={nutrition} />

            {/* Rationale (collapsible) */}
            {rec.rationale && (
              <div className="bg-surface rounded-2xl border border-border">
                <button
                  onClick={() => setRationaleOpen((o) => !o)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left"
                >
                  <span className="font-medium text-foreground">🧠 Por que este treino?</span>
                  <span className="text-muted-foreground">{rationaleOpen ? "▲" : "▼"}</span>
                </button>
                {rationaleOpen && (
                  <div className="px-5 pb-5 border-t border-border pt-4">
                    <p className="text-sm text-muted-foreground leading-relaxed">{rec.rationale}</p>
                  </div>
                )}
              </div>
            )}

            {/* Feedback */}
            <div className="bg-surface rounded-2xl border border-border p-5">
              <h3 className="font-medium text-foreground mb-1">Feedback</h3>
              {feedbackSubmitted ? (
                <div className="flex items-center gap-2 text-green-600 text-sm">
                  <span>✓</span>
                  <span>Obrigado pelo feedback!</span>
                </div>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground mb-3">Como foi a recomendação de hoje?</p>
                  <StarRating value={rating} onChange={setRating} />
                  {rating > 0 && (
                    <div className="mt-3 space-y-3">
                      <textarea
                        value={feedbackNotes}
                        onChange={(e) => setFeedbackNotes(e.target.value)}
                        rows={2}
                        placeholder="Comentários opcionais…"
                        className="w-full text-sm rounded-lg border border-gray-300 px-3 py-2 outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                      />
                      <button
                        onClick={submitFeedback}
                        disabled={submittingFeedback}
                        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40 transition-colors"
                      >
                        {submittingFeedback ? "Enviando…" : "Enviar feedback"}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
