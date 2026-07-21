"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import api from "@/lib/api";

const MODALITIES = ["cycling", "running", "swimming", "triathlon", "strength", "mobility"] as const;
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const DAY_LABELS: Record<string, string> = {
  mon: "Seg", tue: "Ter", wed: "Qua", thu: "Qui",
  fri: "Sex", sat: "Sáb", sun: "Dom",
};

const schema = z.object({
  name: z.string().min(2, "Nome muito curto"),
  email: z.string().email("E-mail inválido"),
  phone: z.string().optional(),
  birth_date: z.string().optional(),
  gender: z.string().optional(),
  height_cm: z.coerce.number().positive().optional().or(z.literal("")),
  weight_kg: z.coerce.number().positive().optional().or(z.literal("")),
  sport_modalities: z.array(z.string()).min(1, "Selecione ao menos uma modalidade"),
  primary_modality: z.string().optional(),
  fitness_level: z.string().optional(),
  goal: z.string().optional(),
  ftp_watts: z.coerce.number().positive().optional().or(z.literal("")),
  max_hr: z.coerce.number().positive().optional().or(z.literal("")),
  resting_hr: z.coerce.number().positive().optional().or(z.literal("")),
  cycling_days: z.array(z.string()).optional(),
  strength_days: z.array(z.string()).optional(),
});

type FormData = z.infer<typeof schema>;

function DayPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const toggle = (d: string) =>
    onChange(value.includes(d) ? value.filter((x) => x !== d) : [...value, d]);

  return (
    <div>
      <p className="text-xs font-medium text-gray-600 mb-1.5">{label}</p>
      <div className="flex gap-1.5 flex-wrap">
        {DAYS.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => toggle(d)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              value.includes(d)
                ? "bg-brand-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {DAY_LABELS[d]}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function NewAthletePage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      sport_modalities: [],
      cycling_days: [],
      strength_days: [],
    },
  });

  const watchedModalities = watch("sport_modalities") ?? [];

  const onSubmit = async (data: FormData) => {
    setServerError(null);
    setLoading(true);
    try {
      const weekly_availability: Record<string, string[]> = {};
      if (data.cycling_days?.length) weekly_availability.cycling = data.cycling_days;
      if (data.strength_days?.length) weekly_availability.strength = data.strength_days;

      const payload: Record<string, unknown> = {
        name: data.name,
        email: data.email,
        sport_modalities: data.sport_modalities,
      };
      if (data.phone) payload.phone = data.phone;
      if (data.birth_date) payload.birth_date = data.birth_date;
      if (data.gender) payload.gender = data.gender;
      if (data.height_cm) payload.height_cm = Number(data.height_cm);
      if (data.weight_kg) payload.weight_kg = Number(data.weight_kg);
      if (data.primary_modality) payload.primary_modality = data.primary_modality;
      if (data.fitness_level) payload.fitness_level = data.fitness_level;
      if (data.goal) payload.goal = data.goal;
      if (data.ftp_watts) payload.ftp_watts = Number(data.ftp_watts);
      if (data.max_hr) payload.max_hr = Number(data.max_hr);
      if (data.resting_hr) payload.resting_hr = Number(data.resting_hr);
      if (Object.keys(weekly_availability).length) payload.weekly_availability = weekly_availability;

      const resp = await api.post("/api/admin/athletes", payload);
      setSuccess(`Atleta cadastrado! E-mail de convite enviado para ${data.email}.`);
      setTimeout(() => router.push("/admin/athletes"), 2000);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao cadastrar atleta.";
      setServerError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <button onClick={() => router.back()} className="text-gray-400 hover:text-gray-600 text-sm">
            ← Voltar
          </button>
          <h1 className="text-xl font-semibold text-gray-900">Novo atleta</h1>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-8">
        {success ? (
          <div className="rounded-xl bg-green-50 border border-green-200 p-6 text-center">
            <p className="text-green-700 font-medium">{success}</p>
            <p className="text-sm text-green-600 mt-1">Redirecionando…</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* ── Dados básicos ── */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="font-medium text-gray-900 mb-4">Dados básicos</h2>
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nome completo *</label>
                  <input {...register("name")} className="input-field" placeholder="João da Silva" />
                  {errors.name && <p className="field-error">{errors.name.message}</p>}
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">E-mail *</label>
                  <input {...register("email")} type="email" className="input-field" placeholder="atleta@email.com" />
                  {errors.email && <p className="field-error">{errors.email.message}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Telefone</label>
                  <input {...register("phone")} type="tel" className="input-field" placeholder="+55 11 99999-9999" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Data de nascimento</label>
                  <input {...register("birth_date")} type="date" className="input-field" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Sexo</label>
                  <select {...register("gender")} className="input-field">
                    <option value="">Selecione</option>
                    <option value="male">Masculino</option>
                    <option value="female">Feminino</option>
                    <option value="other">Outro</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nível de condicionamento</label>
                  <select {...register("fitness_level")} className="input-field">
                    <option value="">Selecione</option>
                    <option value="beginner">Iniciante</option>
                    <option value="intermediate">Intermediário</option>
                    <option value="advanced">Avançado</option>
                    <option value="elite">Elite</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Altura (cm)</label>
                  <input {...register("height_cm")} type="number" className="input-field" placeholder="175" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Peso (kg)</label>
                  <input {...register("weight_kg")} type="number" step="0.1" className="input-field" placeholder="70.0" />
                </div>
              </div>
            </div>

            {/* ── Modalidades ── */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="font-medium text-gray-900 mb-4">Modalidades esportivas *</h2>
              <div className="flex gap-2 flex-wrap mb-4">
                <Controller
                  name="sport_modalities"
                  control={control}
                  render={({ field }) => (
                    <>
                      {MODALITIES.map((m) => (
                        <label key={m} className="cursor-pointer">
                          <input
                            type="checkbox"
                            className="sr-only"
                            checked={field.value?.includes(m) ?? false}
                            onChange={(e) => {
                              if (e.target.checked) field.onChange([...(field.value ?? []), m]);
                              else field.onChange((field.value ?? []).filter((x: string) => x !== m));
                            }}
                          />
                          <span className={`inline-block px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${
                            field.value?.includes(m)
                              ? "bg-brand-600 text-white"
                              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                          }`}>
                            {m}
                          </span>
                        </label>
                      ))}
                    </>
                  )}
                />
              </div>
              {errors.sport_modalities && (
                <p className="field-error">{errors.sport_modalities.message}</p>
              )}
              {watchedModalities.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Modalidade principal</label>
                  <select {...register("primary_modality")} className="input-field w-auto">
                    <option value="">Selecione</option>
                    {watchedModalities.map((m) => (
                      <option key={m} value={m} className="capitalize">{m}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* ── Disponibilidade ── */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="font-medium text-gray-900 mb-4">Disponibilidade semanal</h2>
              <div className="space-y-4">
                <Controller
                  name="cycling_days"
                  control={control}
                  render={({ field }) => (
                    <DayPicker label="Ciclismo / Endurance" value={field.value ?? []} onChange={field.onChange} />
                  )}
                />
                <Controller
                  name="strength_days"
                  control={control}
                  render={({ field }) => (
                    <DayPicker label="Musculação / Força" value={field.value ?? []} onChange={field.onChange} />
                  )}
                />
              </div>
            </div>

            {/* ── Dados fisiológicos ── */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="font-medium text-gray-900 mb-1">Dados fisiológicos</h2>
              <p className="text-xs text-gray-500 mb-4">Usados pela IA para cálculo de TSS e zonas de treino.</p>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">FTP (watts)</label>
                  <input {...register("ftp_watts")} type="number" className="input-field" placeholder="250" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">FC máxima (bpm)</label>
                  <input {...register("max_hr")} type="number" className="input-field" placeholder="185" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">FC repouso (bpm)</label>
                  <input {...register("resting_hr")} type="number" className="input-field" placeholder="55" />
                </div>
              </div>
            </div>

            {/* ── Objetivo ── */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="font-medium text-gray-900 mb-4">Objetivo do atleta</h2>
              <textarea
                {...register("goal")}
                rows={3}
                className="input-field resize-none"
                placeholder="Ex: Completar o Iron Man Floripa 2027, melhorar FTP em 15%, perder 5kg..."
              />
            </div>

            {serverError && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {serverError}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-brand-600 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Cadastrando e enviando convite…" : "Cadastrar atleta e enviar convite"}
            </button>
          </form>
        )}
      </div>

      <style jsx global>{`
        .input-field {
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid #d1d5db;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          outline: none;
        }
        .input-field:focus {
          ring: 2px;
          border-color: transparent;
          box-shadow: 0 0 0 2px #0ea5e9;
        }
        .field-error {
          margin-top: 0.25rem;
          font-size: 0.75rem;
          color: #dc2626;
        }
      `}</style>
    </div>
  );
}
