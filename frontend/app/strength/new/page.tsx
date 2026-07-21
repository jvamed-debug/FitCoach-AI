"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import api from "@/lib/api";

const SESSION_TYPES = [
  { value: "upper",     label: "Superior" },
  { value: "lower",     label: "Inferior" },
  { value: "full_body", label: "Full Body" },
  { value: "push",      label: "Push" },
  { value: "pull",      label: "Pull" },
  { value: "legs",      label: "Legs" },
  { value: "core",      label: "Core" },
  { value: "other",     label: "Outro" },
];

const exerciseSchema = z.object({
  exercise_name: z.string().min(1, "Nome obrigatório"),
  sets: z.coerce.number().int().min(1, "Min 1 série"),
  reps: z.coerce.number().int().positive().optional().or(z.literal("")),
  load_kg: z.coerce.number().nonnegative().optional().or(z.literal("")),
  rpe: z.coerce.number().int().min(1).max(10).optional().or(z.literal("")),
  notes: z.string().optional(),
});

const formSchema = z.object({
  session_date: z.string().min(1, "Data obrigatória"),
  session_type: z.string().optional(),
  duration_minutes: z.coerce.number().int().positive().optional().or(z.literal("")),
  rpe_overall: z.coerce.number().int().min(1).max(10).optional().or(z.literal("")),
  notes: z.string().optional(),
  exercises: z.array(exerciseSchema),
});

type FormData = z.infer<typeof formSchema>;

const COMMON_EXERCISES = [
  "Agachamento", "Leg Press", "Cadeira Extensora", "Mesa Flexora",
  "Supino Reto", "Supino Inclinado", "Desenvolvimento", "Remada Curvada",
  "Puxada Frontal", "Rosca Direta", "Tríceps Pulley", "Stiff",
  "Agachamento Búlgaro", "Hip Thrust", "Panturrilha", "Prancha",
  "Deadlift", "Power Clean", "Barra Fixa", "Mergulho",
];

export default function NewStrengthPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [autocomplete, setAutocomplete] = useState<{ index: number; query: string } | null>(null);

  const today = new Date().toISOString().split("T")[0];

  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      session_date: today,
      exercises: [],
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "exercises" });

  const duration = watch("duration_minutes");
  const rpeOverall = watch("rpe_overall");
  const estimatedTSS =
    duration && rpeOverall
      ? Math.min(150, (Number(duration) * Number(rpeOverall) ** 2) / 600)
      : null;

  const onSubmit = async (data: FormData) => {
    setServerError(null);
    setLoading(true);
    try {
      const payload = {
        session_date: data.session_date,
        session_type: data.session_type || undefined,
        duration_minutes: data.duration_minutes ? Number(data.duration_minutes) : undefined,
        rpe_overall: data.rpe_overall ? Number(data.rpe_overall) : undefined,
        notes: data.notes || undefined,
        exercises: data.exercises.map((e) => ({
          exercise_name: e.exercise_name,
          sets: Number(e.sets),
          reps: e.reps ? Number(e.reps) : undefined,
          load_kg: e.load_kg ? Number(e.load_kg) : undefined,
          rpe: e.rpe ? Number(e.rpe) : undefined,
          notes: e.notes || undefined,
        })),
      };
      await api.post("/api/strength", payload);
      router.push("/strength");
    } catch (err: unknown) {
      setServerError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao salvar sessão."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">
            ← Voltar
          </button>
          <h1 className="text-xl font-semibold text-gray-900">Nova sessão de musculação</h1>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-8">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

          {/* ── Session header ── */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Data *</label>
                <input type="date" {...register("session_date")}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500" />
                {errors.session_date && <p className="text-xs text-red-600 mt-1">{errors.session_date.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de sessão</label>
                <select {...register("session_type")}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="">Selecione</option>
                  {SESSION_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Duração (min)</label>
                <input type="number" {...register("duration_minutes")} min="1"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="60" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  RPE geral
                  <span className="ml-1 text-xs text-gray-400">(1–10)</span>
                </label>
                <input type="number" {...register("rpe_overall")} min="1" max="10"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="7" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Notas da sessão</label>
                <textarea {...register("notes")} rows={2} placeholder="Observações gerais…"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
              </div>
            </div>

            {/* TSS preview */}
            {estimatedTSS !== null && (
              <div className="mt-4 flex items-center gap-2 text-sm">
                <span className="text-gray-500">TSS estimado:</span>
                <span className="font-bold text-brand-700">{estimatedTSS.toFixed(0)}</span>
                {estimatedTSS === 150 && <span className="text-xs text-orange-500">(máximo)</span>}
              </div>
            )}
          </div>

          {/* ── Exercises ── */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-medium text-gray-900">Exercícios</h2>
              <button
                type="button"
                onClick={() => append({ exercise_name: "", sets: 3, reps: undefined, load_kg: undefined, rpe: undefined, notes: "" })}
                className="text-sm text-brand-600 font-medium hover:underline"
              >
                + Adicionar exercício
              </button>
            </div>

            {fields.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">
                Nenhum exercício adicionado. Clique em "+ Adicionar exercício" para começar.
              </p>
            ) : (
              <div className="space-y-4">
                {fields.map((field, index) => (
                  <div key={field.id} className="border border-gray-100 rounded-lg p-4 relative">
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div className="flex-1 relative">
                        <label className="block text-xs font-medium text-gray-600 mb-1">Nome do exercício *</label>
                        <input
                          {...register(`exercises.${index}.exercise_name`)}
                          className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-brand-500"
                          placeholder="Ex: Agachamento"
                          autoComplete="off"
                          onChange={(e) => {
                            register(`exercises.${index}.exercise_name`).onChange(e);
                            if (e.target.value.length >= 2) {
                              setAutocomplete({ index, query: e.target.value.toLowerCase() });
                            } else {
                              setAutocomplete(null);
                            }
                          }}
                          onBlur={() => setTimeout(() => setAutocomplete(null), 150)}
                        />
                        {autocomplete?.index === index && (
                          <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
                            {COMMON_EXERCISES
                              .filter((ex) => ex.toLowerCase().includes(autocomplete.query))
                              .slice(0, 6)
                              .map((ex) => (
                                <button
                                  key={ex}
                                  type="button"
                                  onMouseDown={() => {
                                    const el = document.querySelector<HTMLInputElement>(
                                      `input[name="exercises.${index}.exercise_name"]`
                                    );
                                    if (el) { el.value = ex; el.dispatchEvent(new Event("input", { bubbles: true })); }
                                    setAutocomplete(null);
                                  }}
                                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                                >
                                  {ex}
                                </button>
                              ))
                            }
                          </div>
                        )}
                        {errors.exercises?.[index]?.exercise_name && (
                          <p className="text-xs text-red-600 mt-1">{errors.exercises[index]?.exercise_name?.message}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => remove(index)}
                        className="mt-5 text-gray-300 hover:text-red-400 transition-colors text-lg leading-none"
                        aria-label="Remover"
                      >
                        ×
                      </button>
                    </div>

                    <div className="grid grid-cols-4 gap-3">
                      {[
                        { name: `exercises.${index}.sets`, label: "Séries *", type: "number", placeholder: "3" },
                        { name: `exercises.${index}.reps`, label: "Reps", type: "number", placeholder: "10" },
                        { name: `exercises.${index}.load_kg`, label: "Carga (kg)", type: "number", placeholder: "60" },
                        { name: `exercises.${index}.rpe`, label: "RPE", type: "number", placeholder: "8" },
                      ].map(({ name, label, type, placeholder }) => (
                        <div key={name}>
                          <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                          <input
                            {...register(name as Parameters<typeof register>[0])}
                            type={type}
                            placeholder={placeholder}
                            min={name.endsWith("rpe") ? "1" : "0"}
                            max={name.endsWith("rpe") ? "10" : undefined}
                            step={name.includes("load") ? "0.5" : "1"}
                            className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-brand-500"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {serverError && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {serverError}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-brand-600 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40 transition-colors"
          >
            {loading ? "Salvando…" : `Salvar sessão${fields.length > 0 ? ` (${fields.length} exercício${fields.length > 1 ? "s" : ""})` : ""}`}
          </button>
        </form>
      </div>
    </div>
  );
}
