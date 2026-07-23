"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import api from "@/lib/api";
import CTLATLTSBChart from "@/components/charts/CTLATLTSBChart";
import type { TrainingLoad, Workout } from "@/lib/types";

type Tab = "profile" | "plan" | "history" | "adherence";

interface AthleteDetail {
  id: string; name: string; email: string; phone: string | null;
  birth_date: string | null; gender: string | null;
  height_cm: number | null; weight_kg: number | null;
  primary_modality: string | null; sport_modalities: string[];
  fitness_level: string | null; goal: string | null;
  weekly_availability: Record<string, string[]> | null;
  ftp_watts: number | null; max_hr: number | null; resting_hr: number | null;
  onboarding_complete: boolean; auto_report_enabled: boolean;
  training_load: { ctl: number | null; atl: number | null; tsb: number | null;
    tsb_status: string; daily_tss: number | null; load_date: string | null };
  days_since_last_workout: number | null; no_workout_alert: boolean;
}

interface AdherenceSummary {
  period_days: number; total_recommendations: number;
  with_feedback: number; followed: number; adherence_pct: number | null;
  avg_rating: number | null; rest_days: number;
}

const TSB_COLOR: Record<string, string> = {
  good: "text-green-600", moderate: "text-yellow-600",
  alert: "text-orange-600", critical: "text-red-600", unknown: "text-gray-400",
};

const SPORT_ICON: Record<string, string> = {
  cycling: "🚴", running: "🏃", swimming: "🏊",
  strength: "💪", triathlon: "🏅", other: "⚡", mobility: "🧘", rest: "😴",
};

export default function AdminAthleteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [athlete, setAthlete]         = useState<AthleteDetail | null>(null);
  const [activeTab, setActiveTab]     = useState<Tab>("profile");
  const [loading, setLoading]         = useState(true);

  // Tab data
  const [loadHistory, setLoadHistory] = useState<TrainingLoad[]>([]);
  const [workouts, setWorkouts]       = useState<Workout[]>([]);
  const [adherence, setAdherence]     = useState<AdherenceSummary | null>(null);
  const [todayRec, setTodayRec]       = useState<Record<string, unknown> | null>(null);
  const [anamnese, setAnamnese]       = useState<string | null>(null);
  const [anamneseText, setAnamneseText] = useState("");
  const [anamneseLoading, setAnamneseLoading] = useState(false);
  const [anamneseSaved, setAnamneseSaved] = useState(false);
  const [resending, setResending]     = useState(false);

  useEffect(() => {
    api.get(`/api/admin/athletes/${id}`)
      .then((r) => setAthlete(r.data))
      .catch(() => router.push("/admin/athletes"))
      .finally(() => setLoading(false));
  }, [id, router]);

  useEffect(() => {
    if (!athlete) return;
    // Pre-load load history and today's rec for Plan tab
    api.get(`/api/admin/athletes/${id}/load-history?days=90`).then((r) => {
      setLoadHistory(r.data.history ?? []);
    }).catch(() => {});
  }, [athlete, id]);

  const loadTabData = useCallback(async (tab: Tab) => {
    try {
      if (tab === "history" && workouts.length === 0) {
        const r = await api.get(`/api/admin/athletes/${id}/workouts?per_page=30`);
        setWorkouts(r.data.items ?? []);
      }
      if (tab === "adherence" && !adherence) {
        const r = await api.get(`/api/admin/athletes/${id}/adherence-summary?days=30`);
        setAdherence(r.data);
      }
      if (tab === "plan" && !todayRec) {
        const r = await api.get(`/api/admin/athletes/${id}/recommendations?per_page=5`);
        setTodayRec(r.data.items?.[0] ?? null);
      }
    } catch {}
  }, [id, workouts.length, adherence, todayRec]);

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    loadTabData(tab);
  };

  const loadAnamnese = async () => {
    setAnamneseLoading(true);
    try {
      const r = await api.get(`/api/admin/athletes/${id}/anamnese`);
      setAnamnese(r.data.content ?? "");
      setAnamneseText(r.data.content ?? "");
    } finally {
      setAnamneseLoading(false);
    }
  };

  const saveAnamnese = async () => {
    await api.put(`/api/admin/athletes/${id}/anamnese`, { content: anamneseText });
    setAnamneseSaved(true);
    setTimeout(() => setAnamneseSaved(false), 2000);
  };

  const resendInvite = async () => {
    setResending(true);
    try {
      await api.post(`/api/admin/athletes/${id}/resend-invite`);
      alert("Convite reenviado!");
    } finally {
      setResending(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Carregando…</div>
  );
  if (!athlete) return null;

  const load = athlete.training_load;
  const tsbColor = TSB_COLOR[load.tsb_status] ?? "text-gray-400";

  const KPI = [
    { label: "CTL",   value: load.ctl?.toFixed(1) ?? "—",   color: "text-blue-600" },
    { label: "ATL",   value: load.atl?.toFixed(1) ?? "—",   color: "text-orange-500" },
    { label: "TSB",   value: load.tsb !== null ? `${load.tsb > 0 ? "+" : ""}${load.tsb.toFixed(1)}` : "—", color: tsbColor },
    { label: "Último treino", value: athlete.days_since_last_workout !== null
        ? (athlete.days_since_last_workout === 0 ? "hoje" : `${athlete.days_since_last_workout}d atrás`)
        : "—", color: athlete.no_workout_alert ? "text-orange-600" : "text-gray-800" },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-3 mb-2">
            <Link href="/admin/athletes" className="text-sm text-gray-400 hover:text-gray-600">← Atletas</Link>
          </div>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                {athlete.name}
                {load.tsb !== null && load.tsb < -25 && (
                  <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">
                    ⚠️ TSB crítico
                  </span>
                )}
                {!athlete.onboarding_complete && (
                  <span className="text-xs bg-yellow-100 text-yellow-600 px-2 py-0.5 rounded-full font-medium">
                    Onboarding pendente
                  </span>
                )}
              </h1>
              <p className="text-sm text-gray-500">{athlete.email}</p>
            </div>
            <div className="flex gap-2">
              {!athlete.onboarding_complete && (
                <button onClick={resendInvite} disabled={resending}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-40">
                  {resending ? "Reenviando…" : "Reenviar convite"}
                </button>
              )}
              <Link href={`/admin/athletes/${id}/edit`}
                className="px-3 py-1.5 text-sm rounded-lg bg-brand-600 text-white hover:bg-brand-700">
                Editar
              </Link>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-5 space-y-5">
        {/* KPI row */}
        <div className="grid grid-cols-4 gap-4">
          {KPI.map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500 mb-1">{label}</p>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          {(["profile", "plan", "history", "adherence"] as Tab[]).map((tab) => (
            <button key={tab} onClick={() => handleTabChange(tab)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors capitalize ${
                activeTab === tab
                  ? "border-b-2 border-brand-600 text-brand-700"
                  : "text-gray-500 hover:text-gray-700"
              }`}>
              {{
                profile: "Perfil",
                plan: "Plano IA",
                history: "Histórico",
                adherence: "Aderência",
              }[tab]}
            </button>
          ))}
        </div>

        {/* ── Profile tab ── */}
        {activeTab === "profile" && (
          <div className="grid grid-cols-2 gap-5">
            <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
              <h3 className="font-medium text-gray-900">Dados pessoais</h3>
              {[
                ["Nascimento", athlete.birth_date ?? "—"],
                ["Sexo",       athlete.gender ?? "—"],
                ["Altura",     athlete.height_cm ? `${athlete.height_cm}cm` : "—"],
                ["Peso",       athlete.weight_kg ? `${athlete.weight_kg}kg` : "—"],
                ["Telefone",   athlete.phone ?? "—"],
                ["Nível",      athlete.fitness_level ?? "—"],
              ].map(([l, v]) => (
                <div key={String(l)} className="flex justify-between text-sm">
                  <span className="text-gray-500">{l}</span>
                  <span className="font-medium capitalize">{v}</span>
                </div>
              ))}
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
              <h3 className="font-medium text-gray-900">Fisiologia & Modalidades</h3>
              {[
                ["FTP",          athlete.ftp_watts ? `${athlete.ftp_watts}W` : "—"],
                ["FC máxima",    athlete.max_hr ? `${athlete.max_hr}bpm` : "—"],
                ["FC repouso",   athlete.resting_hr ? `${athlete.resting_hr}bpm` : "—"],
                ["Mod. principal", athlete.primary_modality ?? "—"],
              ].map(([l, v]) => (
                <div key={String(l)} className="flex justify-between text-sm">
                  <span className="text-gray-500">{l}</span>
                  <span className="font-medium capitalize">{v}</span>
                </div>
              ))}
              <div className="flex gap-1.5 flex-wrap mt-2">
                {athlete.sport_modalities.map((m) => (
                  <span key={m} className="bg-brand-50 text-brand-700 text-xs px-2 py-0.5 rounded-md capitalize">{m}</span>
                ))}
              </div>
            </div>

            <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">Anamnese</h3>
                {anamneseSaved && <span className="text-xs text-green-600">✓ Salvo</span>}
                {anamnese === null && (
                  <button onClick={loadAnamnese}
                    className="text-xs text-brand-600 hover:underline">
                    {anamneseLoading ? "Descriptografando…" : "Carregar anamnese"}
                  </button>
                )}
              </div>
              {anamnese !== null && (
                <>
                  <textarea value={anamneseText} onChange={(e) => setAnamneseText(e.target.value)}
                    rows={10} className="w-full text-sm font-mono rounded-lg border border-gray-200 px-3 py-2 outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                    placeholder="Histórico médico, lesões, medicações…" />
                  <button onClick={saveAnamnese}
                    className="mt-2 px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700">
                    Salvar anamnese
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Plan tab ── */}
        {activeTab === "plan" && (
          <div className="space-y-5">
            {loadHistory.length > 1 && <CTLATLTSBChart data={loadHistory} />}

            {/* Monthly report download */}
            <AdminAthleteReportCard athleteId={id} />

            {todayRec ? (
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="font-medium text-gray-900 mb-3">Última recomendação</h3>
                <div className="flex items-center gap-3">
                  <span className="text-2xl">
                    {SPORT_ICON[(todayRec.workout_type as string) ?? ""] ?? "🏋️"}
                  </span>
                  <div>
                    <p className="font-medium">{todayRec.title as string}</p>
                    <p className="text-xs text-gray-400">
                      {todayRec.recommendation_date as string} · {todayRec.ai_provider as string}
                    </p>
                  </div>
                  {Boolean(todayRec.feedback_rating) && (
                    <span className="ml-auto text-sm text-yellow-500">
                      {"⭐".repeat(todayRec.feedback_rating as number)}
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400">Nenhuma recomendação disponível.</p>
            )}
          </div>
        )}

        {/* ── History tab ── */}
        {activeTab === "history" && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Data</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Treino</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-gray-500">Duração</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-gray-500">TSS</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-gray-500">Fonte</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {workouts.length === 0 ? (
                  <tr><td colSpan={5} className="py-8 text-center text-gray-400">Nenhum treino ainda</td></tr>
                ) : workouts.map((w) => {
                  const dur = w.duration_seconds
                    ? `${Math.floor(w.duration_seconds / 3600)}h${Math.floor((w.duration_seconds % 3600)/60).toString().padStart(2,"0")}`
                    : "—";
                  return (
                    <tr key={w.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        {w.start_time
                          ? format(parseISO(w.start_time), "dd/MM/yy", { locale: ptBR })
                          : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span className="mr-2">{SPORT_ICON[w.sport_type] ?? "⚡"}</span>
                        {w.title ?? w.sport_type}
                      </td>
                      <td className="px-4 py-3 text-center text-gray-600">{dur}</td>
                      <td className="px-4 py-3 text-center font-medium">
                        {w.tss ? w.tss.toFixed(0) : "—"}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full capitalize">
                          {w.source}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Adherence tab ── */}
        {activeTab === "adherence" && adherence && (
          <div className="grid grid-cols-3 gap-4">
            {[
              {
                label: "Aderência",
                value: adherence.adherence_pct !== null ? `${adherence.adherence_pct}%` : "—",
                sub: `${adherence.followed} de ${adherence.total_recommendations} seguidos`,
                color: (adherence.adherence_pct ?? 0) >= 70 ? "text-green-600" : "text-orange-600",
              },
              {
                label: "Avaliação média",
                value: adherence.avg_rating ? `${adherence.avg_rating}/5 ⭐` : "—",
                sub: `${adherence.with_feedback} feedbacks`,
                color: "text-yellow-600",
              },
              {
                label: "Dias de descanso",
                value: adherence.rest_days,
                sub: `nos últimos ${adherence.period_days} dias`,
                color: "text-blue-600",
              },
            ].map(({ label, value, sub, color }) => (
              <div key={label} className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <p className={`text-3xl font-bold ${color}`}>{value}</p>
                <p className="text-xs text-gray-400 mt-1">{sub}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AdminAthleteReportCard({ athleteId }: { athleteId: string }) {
  const [loading, setLoading] = useState(false);

  const today = new Date();
  const targetMonth = today.getDate() <= 5
    ? today.getMonth() === 0 ? 12 : today.getMonth()
    : today.getMonth() + 1;
  const targetYear = today.getDate() <= 5 && today.getMonth() === 0
    ? today.getFullYear() - 1
    : today.getFullYear();
  const monthNames = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  const label = `${monthNames[targetMonth - 1]}/${targetYear}`;

  const download = async () => {
    setLoading(true);
    try {
      const res = await api.get(
        `/api/admin/athletes/${athleteId}/report/monthly?year=${targetYear}&month=${targetMonth}`,
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `fitcoach-relatorio-atleta-${targetMonth.toString().padStart(2,"0")}-${targetYear}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between gap-4">
      <div>
        <p className="font-medium text-gray-900 text-sm">Relatório mensal — {label}</p>
        <p className="text-xs text-gray-400 mt-0.5">PDF com treinos, CTL/ATL/TSB e aderência</p>
      </div>
      <button
        onClick={download}
        disabled={loading}
        className="flex-shrink-0 px-3 py-1.5 text-xs font-medium bg-sky-600 text-white rounded-lg hover:bg-sky-700 disabled:opacity-50"
      >
        {loading ? "Gerando…" : "⬇ Baixar PDF"}
      </button>
    </div>
  );
}
