"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import CTLATLTSBChart from "@/components/charts/CTLATLTSBChart";
import DailyRecommendationCard from "@/components/dashboard/DailyRecommendationCard";
import WeeklyTSSBar from "@/components/dashboard/WeeklyTSSBar";
import RecentWorkoutsList from "@/components/dashboard/RecentWorkoutsList";
import DailyMetricsCard from "@/components/dashboard/DailyMetricsCard";
import type { TrainingLoad, Workout, DailyMetrics, AIRecommendation, AthleteProfile } from "@/lib/types";

interface CurrentLoad {
  ctl: number; atl: number; tsb: number;
  daily_tss: number; weekly_tss: number; load_date: string;
}

interface WeekStats {
  workout_count: number; total_seconds: number;
  total_meters: number; total_tss: number;
}

const TSB_STATE = (tsb: number) => {
  if (tsb < -25) return { label: "Crítico",     bg: "bg-red-50",    text: "text-red-700",    border: "border-red-200" };
  if (tsb < -10) return { label: "Fatigado",    bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" };
  if (tsb < 5)   return { label: "Neutro",      bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" };
  if (tsb < 15)  return { label: "Fresco",      bg: "bg-green-50",  text: "text-green-700",  border: "border-green-200" };
  return               { label: "Muito fresco", bg: "bg-teal-50",   text: "text-teal-700",   border: "border-teal-200" };
};

function NavBar() {
  const { profile } = useAuthStore();
  const athlete = profile as AthleteProfile | null;
  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <Link href="/dashboard" className="font-bold text-brand-700 text-lg">FitCoach AI</Link>
      <div className="flex gap-5 text-sm">
        {[
          ["/dashboard",      "Dashboard"],
          ["/workouts",       "Treinos"],
          ["/strength",       "Musculação"],
          ["/recommendations","Recomendação"],
          ["/metrics",        "Métricas"],
        ].map(([href, label]) => (
          <Link key={href} href={href}
            className="text-gray-500 hover:text-brand-700 transition-colors">{label}</Link>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-600">{athlete?.name?.split(" ")[0]}</span>
        <Link href="/settings" className="text-gray-400 hover:text-gray-600 text-sm">⚙️</Link>
      </div>
    </nav>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { role, profile } = useAuthStore();

  const [currentLoad, setCurrentLoad] = useState<CurrentLoad | null>(null);
  const [loadHistory, setLoadHistory]  = useState<TrainingLoad[]>([]);
  const [weekStats, setWeekStats]      = useState<{ this_week: WeekStats; last_week: WeekStats } | null>(null);
  const [recentWorkouts, setRecentWorkouts] = useState<Workout[]>([]);
  const [todayRec, setTodayRec]        = useState<AIRecommendation | null>(null);
  const [todayMetrics, setTodayMetrics]= useState<DailyMetrics | null>(null);
  const [loading, setLoading]          = useState(true);

  useEffect(() => {
    if (!role || !profile) { router.replace("/auth/login"); return; }
  }, [role, profile, router]);

  useEffect(() => {
    if (!profile) return;
    Promise.all([
      api.get("/api/workouts/load?days=90").catch(() => null),
      api.get("/api/workouts/stats/weekly").catch(() => null),
      api.get("/api/workouts?per_page=5").catch(() => null),
      api.get("/api/recommendations/today").catch(() => null),
      api.get("/api/metrics/today").catch(() => null),
    ]).then(([loadResp, weekResp, wktResp, recResp, metricsResp]) => {
      if (loadResp) {
        setCurrentLoad(loadResp.data.current);
        setLoadHistory(loadResp.data.history ?? []);
      }
      if (weekResp) setWeekStats(weekResp.data);
      if (wktResp)  setRecentWorkouts(wktResp.data.items ?? []);
      if (recResp)  setTodayRec(recResp.data);
      if (metricsResp) setTodayMetrics(metricsResp.data);
    }).finally(() => setLoading(false));
  }, [profile]);

  if (!profile) return null;

  const athlete = profile as AthleteProfile;
  const tsb = currentLoad?.tsb ?? 0;
  const tsbState = TSB_STATE(tsb);

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar />

      <div className="max-w-6xl mx-auto px-6 py-6 space-y-5">
        {/* Greeting + critical alert */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Olá, {athlete.name.split(" ")[0]}! 👋
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}
            </p>
          </div>
          {tsb < -25 && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-700 flex items-center gap-2">
              <span>⚠️</span>
              <span>TSB crítico ({tsb.toFixed(1)}) — descanso recomendado</span>
            </div>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-4 gap-4">
            {[1,2,3,4].map((i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse h-24" />
            ))}
          </div>
        ) : (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* TSB — colored by state */}
              <div className={`rounded-xl border ${tsbState.border} ${tsbState.bg} p-4`}>
                <p className="text-xs text-gray-500 mb-1">Forma (TSB)</p>
                <p className={`text-3xl font-bold ${tsbState.text}`}>
                  {currentLoad ? `${tsb > 0 ? "+" : ""}${tsb.toFixed(1)}` : "—"}
                </p>
                <p className={`text-xs mt-1 font-medium ${tsbState.text}`}>{tsbState.label}</p>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-500 mb-1">CTL (Fitness)</p>
                <p className="text-3xl font-bold text-blue-600">
                  {currentLoad?.ctl.toFixed(1) ?? "—"}
                </p>
                <p className="text-xs text-gray-400 mt-1">42 dias</p>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-500 mb-1">ATL (Fadiga)</p>
                <p className="text-3xl font-bold text-orange-500">
                  {currentLoad?.atl.toFixed(1) ?? "—"}
                </p>
                <p className="text-xs text-gray-400 mt-1">7 dias</p>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-500 mb-1">TSS semanal</p>
                <p className="text-3xl font-bold text-gray-800">
                  {weekStats?.this_week.total_tss.toFixed(0) ?? "—"}
                </p>
                {weekStats && (
                  <p className="text-xs text-gray-400 mt-1">
                    anterior: {weekStats.last_week.total_tss.toFixed(0)}
                  </p>
                )}
              </div>
            </div>

            {/* CTL/ATL/TSB Chart */}
            {loadHistory.length > 1 ? (
              <CTLATLTSBChart data={loadHistory} />
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
                <p className="text-gray-400 text-sm">Dados insuficientes para o gráfico.</p>
                <p className="text-xs text-gray-300 mt-1">Conecte o Strava ou registre treinos para começar.</p>
              </div>
            )}

            {/* Middle row: Recommendation + Metrics */}
            <div className="grid grid-cols-2 gap-5">
              <DailyRecommendationCard rec={todayRec} loading={false} />
              <DailyMetricsCard metrics={todayMetrics} loading={false} />
            </div>

            {/* Bottom row: Weekly TSS + Recent Workouts */}
            <div className="grid grid-cols-2 gap-5">
              <WeeklyTSSBar thisWeek={weekStats?.this_week ?? null} lastWeek={weekStats?.last_week ?? null} />
              <RecentWorkoutsList workouts={recentWorkouts} />
            </div>

            {/* Quick actions */}
            <MonthlyReportCard />
          </>
        )}
      </div>
    </div>
  );
}

function MonthlyReportCard() {
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const today = new Date();
  // Default to last month if we're in the first 5 days of the month
  const targetMonth = today.getDate() <= 5
    ? today.getMonth() === 0 ? 12 : today.getMonth()
    : today.getMonth() + 1;
  const targetYear = today.getDate() <= 5 && today.getMonth() === 0
    ? today.getFullYear() - 1
    : today.getFullYear();

  const monthNames = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  const label = `${monthNames[targetMonth - 1]}/${targetYear}`;

  const downloadPdf = async () => {
    setLoading(true);
    try {
      const res = await api.get(
        `/api/reports/monthly?year=${targetYear}&month=${targetMonth}`,
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `fitcoach-relatorio-${targetMonth.toString().padStart(2, "0")}-${targetYear}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      // silently fail — user can retry
    } finally {
      setLoading(false);
    }
  };

  const sendByEmail = async () => {
    setLoading(true);
    try {
      await api.post(`/api/reports/monthly/email?year=${targetYear}&month=${targetMonth}`);
      setSent(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-center justify-between gap-4">
      <div>
        <p className="font-medium text-gray-900 text-sm">Relatório mensal — {label}</p>
        <p className="text-xs text-gray-400 mt-0.5">
          PDF com treinos, CTL/ATL/TSB, métricas e aderência
        </p>
      </div>
      <div className="flex gap-2 flex-shrink-0">
        <button
          onClick={downloadPdf}
          disabled={loading}
          className="px-3 py-1.5 text-xs font-medium bg-sky-600 text-white rounded-lg hover:bg-sky-700 disabled:opacity-50"
        >
          {loading ? "..." : "⬇ Baixar PDF"}
        </button>
        <button
          onClick={sendByEmail}
          disabled={loading || sent}
          className="px-3 py-1.5 text-xs font-medium border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          {sent ? "✓ Enviado" : "📧 Enviar por e-mail"}
        </button>
      </div>
    </div>
  );
}
