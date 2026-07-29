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
import InfoTip from "@/components/ui/InfoTip";
import type { TrainingLoad, Workout, DailyMetrics, AIRecommendation, AthleteProfile } from "@/lib/types";

// Tooltips educativos por métrica (§16 do contrato do agente). Descrevem o que
// a métrica É, sem prometer avaliação de saúde nem predição.
const TIP = {
  tsb: "Forma (TSB) = diferença entre Fitness e Fadiga, pela convenção temporal configurada. Na configuração inicial usa os valores do dia anterior. Positivo tende a frescor; negativo, a cansaço acumulado.",
  ctl: "Fitness (CTL) = componente de carga de resposta lenta, média exponencial de ~42 dias do seu TSS. Sobe devagar e cai devagar; representa a base de condicionamento.",
  atl: "Fadiga (ATL) = componente de carga de resposta rápida, média exponencial de ~7 dias do seu TSS. Reage rápido às sessões recentes.",
  tss: "TSS resume uma sessão pela combinação de duração e intensidade relativa ao limiar. Uma hora exatamente no limiar equivale a 100. Com potência é uma medida; sem potência, uma estimativa por FC.",
  pmc: "PMC (Performance Management Chart) reúne TSS, Fitness, Fadiga e Forma ao longo do tempo. Interprete a tendência das curvas, não um número isolado.",
} as const;

interface CurrentLoad {
  ctl: number; atl: number; tsb: number;
  daily_tss: number; weekly_tss: number; load_date: string;
}

interface WeekStats {
  workout_count: number; total_seconds: number;
  total_meters: number; total_tss: number;
}

// Estado do TSB → cor semântica (via CSS var) + rótulo. A cor É a informação.
const TSB_STATE = (tsb: number) => {
  if (tsb < -25) return { label: "Crítico · descanso",  color: "hsl(var(--critical))" };
  if (tsb < -10) return { label: "Fatigado",            color: "hsl(var(--fatigued))" };
  if (tsb < 5)   return { label: "Neutro",              color: "hsl(var(--muted-foreground))" };
  if (tsb < 15)  return { label: "Pronto p/ qualidade", color: "hsl(var(--tsb))" };
  return               { label: "Muito fresco",         color: "hsl(var(--tsb))" };
};

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
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-5">
        {/* Saudação */}
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground first-letter:uppercase">
            {new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 className="mt-1 text-[26px] font-extrabold tracking-tight text-foreground">
            Bom treino, {athlete.name.split(" ")[0]}.
          </h1>
        </div>

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-28 animate-pulse rounded-2xl border border-border bg-surface" />
            ))}
          </div>
        ) : (
          <>
            {/* Faixa de métricas de carga */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div
                className="rounded-2xl border bg-surface p-5"
                style={{ borderColor: currentLoad && tsb < -25 ? "hsl(var(--critical))" : "hsl(var(--border))" }}
              >
                <div className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  Forma · TSB <InfoTip text={TIP.tsb} />
                </div>
                <div className="tnum mt-1.5 text-4xl font-bold leading-none" style={{ color: tsbState.color }}>
                  {currentLoad ? `${tsb > 0 ? "+" : ""}${tsb.toFixed(1)}` : "—"}
                </div>
                <div
                  className="mt-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
                  style={{ color: tsbState.color, background: `color-mix(in srgb, ${tsbState.color} 14%, transparent)` }}
                >
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: tsbState.color }} />
                  {tsbState.label}
                </div>
              </div>

              <MetricCard k="Fitness · CTL" value={currentLoad?.ctl} sub="média 42 dias" color="hsl(var(--ctl))" tip={TIP.ctl} />
              <MetricCard k="Fadiga · ATL" value={currentLoad?.atl} sub="média 7 dias" color="hsl(var(--atl))" tip={TIP.atl} />

              <div className="rounded-2xl border border-border bg-surface p-5">
                <div className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  TSS semanal <InfoTip text={TIP.tss} />
                </div>
                <div className="tnum mt-1.5 text-4xl font-bold leading-none text-foreground">
                  {weekStats?.this_week.total_tss.toFixed(0) ?? "—"}
                </div>
                {weekStats && (
                  <div className="mt-3 text-xs text-muted-foreground">
                    anterior: <span className="tnum">{weekStats.last_week.total_tss.toFixed(0)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Gráfico de carga (PMC) */}
            {loadHistory.length > 1 ? (
              <div className="rounded-2xl border border-border bg-surface p-5">
                <div className="mb-3 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  Carga de treino · 90 dias <InfoTip text={TIP.pmc} />
                </div>
                <CTLATLTSBChart data={loadHistory} />
              </div>
            ) : (
              <div className="rounded-2xl border border-border bg-surface p-10 text-center">
                <p className="text-sm text-muted-foreground">Dados insuficientes para o gráfico de carga (PMC).</p>
                <p className="mt-1 text-xs text-muted-foreground/70">
                  Conecte o Strava ou registre um treino para começar a construir seu histórico.
                </p>
              </div>
            )}

            {/* Recomendação + Métricas */}
            <div className="grid gap-5 lg:grid-cols-2">
              <DailyRecommendationCard rec={todayRec} loading={false} />
              <DailyMetricsCard metrics={todayMetrics} loading={false} />
            </div>

            {/* TSS semanal + Treinos recentes */}
            <div className="grid gap-5 lg:grid-cols-2">
              <WeeklyTSSBar thisWeek={weekStats?.this_week ?? null} lastWeek={weekStats?.last_week ?? null} />
              <RecentWorkoutsList workouts={recentWorkouts} />
            </div>

            {/* Quick actions */}
            <MonthlyReportCard />

            {/* Aviso fixo (§16 do contrato do agente) */}
            <p className="px-2 pt-2 text-center text-[11px] leading-relaxed text-muted-foreground/70">
              Valores de referência por nível de atleta são convenções de treinamento sem validação
              científica universal. As métricas descrevem carga registrada — não avaliam saúde nem predizem lesão.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function MetricCard({ k, value, sub, color, tip }: { k: string; value?: number; sub: string; color: string; tip?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
        {k} {tip && <InfoTip text={tip} />}
      </div>
      <div className="tnum mt-1.5 text-4xl font-bold leading-none" style={{ color }}>
        {value != null ? value.toFixed(0) : "—"}
      </div>
      <div className="mt-3 text-xs text-muted-foreground">{sub}</div>
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
    <div className="flex flex-col items-start justify-between gap-4 rounded-2xl border border-border bg-surface p-5 sm:flex-row sm:items-center">
      <div>
        <p className="text-sm font-semibold text-foreground">Relatório mensal — {label}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">PDF com treinos, CTL/ATL/TSB, métricas e aderência</p>
      </div>
      <div className="flex flex-shrink-0 gap-2">
        <button
          onClick={downloadPdf}
          disabled={loading}
          className="rounded-lg bg-accent px-3.5 py-2 text-xs font-semibold text-accent-foreground transition hover:brightness-110 disabled:opacity-50"
        >
          {loading ? "…" : "Baixar PDF"}
        </button>
        <button
          onClick={sendByEmail}
          disabled={loading || sent}
          className="rounded-lg border border-border px-3.5 py-2 text-xs font-semibold text-foreground transition hover:bg-surface-2 disabled:opacity-50"
        >
          {sent ? "✓ Enviado" : "Enviar por e-mail"}
        </button>
      </div>
    </div>
  );
}
