"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import { AdminDashboardAthlete, AlertSummary } from "@/lib/types";
import AlertsList from "@/components/admin/AlertsList";

// ── TSB display helpers ───────────────────────────────────────────────────────

const TSB_CONFIG = {
  good:     { label: "Ótimo",    className: "bg-green-100 text-green-700 border border-green-200" },
  moderate: { label: "Neutro",   className: "bg-yellow-100 text-yellow-700 border border-yellow-200" },
  alert:    { label: "Fatigado", className: "bg-orange-100 text-orange-700 border border-orange-200" },
  critical: { label: "Crítico",  className: "bg-red-100 text-red-700 border border-red-200" },
  unknown:  { label: "Sem dados",className: "bg-gray-100 text-gray-500 border border-gray-200" },
};

const MODALITY_ICON: Record<string, string> = {
  cycling: "🚴",
  running: "🏃",
  swimming: "🏊",
  triathlon: "🏅",
  strength: "🏋️",
};

function SeverityBadge({ count, severity }: { count: number; severity: string }) {
  if (count === 0) return null;
  const cls =
    severity === "critical" ? "bg-red-500 text-white" :
    severity === "warning"  ? "bg-yellow-500 text-white" :
                              "bg-blue-400 text-white";
  return (
    <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${cls}`}>
      {count > 9 ? "9+" : count}
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AdminDashboardPage() {
  const router = useRouter();
  const { role } = useAuthStore();

  const [athletes, setAthletes] = useState<AdminDashboardAthlete[]>([]);
  const [summary, setSummary] = useState<AlertSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"athletes" | "alerts">("athletes");

  useEffect(() => {
    if (role !== "admin") router.replace("/auth/login");
  }, [role, router]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [athletesRes, summaryRes] = await Promise.all([
        api.get<{ items: AdminDashboardAthlete[]; total: number }>("/api/admin/athletes?per_page=100"),
        api.get<AlertSummary>("/api/admin/alerts/summary"),
      ]);
      // Sort: critical → alert → moderate → good → unknown
      const order = { critical: 0, alert: 1, moderate: 2, good: 3, unknown: 4 };
      const sorted = [...athletesRes.data.items].sort(
        (a, b) =>
          (order[a.training_load.tsb_status] ?? 4) -
          (order[b.training_load.tsb_status] ?? 4)
      );
      setAthletes(sorted);
      setSummary(summaryRes.data);
    } catch {
      // keep existing state on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filtered = athletes.filter(
    (a) =>
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.email.toLowerCase().includes(search.toLowerCase())
  );

  const criticalCount = athletes.filter((a) => a.training_load.tsb_status === "critical").length;
  const noWorkoutCount = athletes.filter((a) => a.no_workout_alert).length;
  const onboardingCount = athletes.filter((a) => !a.onboarding_complete).length;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Painel do Coach</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {athletes.length} atleta{athletes.length !== 1 ? "s" : ""} ativos
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/admin/athletes/new"
              className="bg-sky-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-sky-700"
            >
              + Novo atleta
            </Link>
            <Link
              href="/admin/athletes"
              className="text-sm text-sky-600 hover:text-sky-800"
            >
              Lista completa →
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            label="Total de atletas"
            value={athletes.length}
            sub="ativos na plataforma"
            color="sky"
          />
          <KpiCard
            label="Estado crítico"
            value={criticalCount}
            sub="TSB < −25 (overtraining)"
            color={criticalCount > 0 ? "red" : "green"}
            href="/admin/dashboard?tab=alerts"
          />
          <KpiCard
            label="Sem treino (3d+)"
            value={noWorkoutCount}
            sub="atletas sem registro"
            color={noWorkoutCount > 0 ? "orange" : "green"}
          />
          <KpiCard
            label="Alertas não lidos"
            value={summary?.total_unread ?? 0}
            sub={`${summary?.critical ?? 0} críticos · ${summary?.warning ?? 0} avisos`}
            color={(summary?.total_unread ?? 0) > 0 ? "yellow" : "green"}
            onClick={() => setActiveTab("alerts")}
          />
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 border-b border-gray-200">
          {(["athletes", "alerts"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-sky-600 text-sky-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab === "athletes" ? "Atletas" : (
                <span className="flex items-center gap-1.5">
                  Alertas
                  {(summary?.total_unread ?? 0) > 0 && (
                    <SeverityBadge count={summary!.total_unread} severity={summary!.critical > 0 ? "critical" : "warning"} />
                  )}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Athletes tab */}
        {activeTab === "athletes" && (
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Buscar atleta..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full max-w-sm border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />

            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="h-36 rounded-xl bg-gray-100 animate-pulse" />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <p className="text-sm text-gray-400 py-8 text-center">Nenhum atleta encontrado.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filtered.map((athlete) => (
                  <AthleteCard key={athlete.id} athlete={athlete} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Alerts tab */}
        {activeTab === "alerts" && (
          <div className="max-w-2xl">
            <AlertsList
              limit={100}
              unreadOnly={false}
              onRead={fetchData}
            />
          </div>
        )}
      </div>
    </div>
  );
}


// ── Sub-components ────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  color,
  href,
  onClick,
}: {
  label: string;
  value: number;
  sub: string;
  color: "sky" | "red" | "orange" | "yellow" | "green";
  href?: string;
  onClick?: () => void;
}) {
  const colors = {
    sky:    "text-sky-700 bg-sky-50 border-sky-200",
    red:    "text-red-700 bg-red-50 border-red-200",
    orange: "text-orange-700 bg-orange-50 border-orange-200",
    yellow: "text-yellow-700 bg-yellow-50 border-yellow-200",
    green:  "text-green-700 bg-green-50 border-green-200",
  };

  const inner = (
    <div className={`rounded-xl border px-5 py-4 cursor-pointer ${colors[color]} ${href || onClick ? "hover:opacity-80" : ""}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      <p className="text-xs opacity-60 mt-0.5">{sub}</p>
    </div>
  );

  if (href) return <Link href={href}>{inner}</Link>;
  if (onClick) return <button onClick={onClick} className="text-left w-full">{inner}</button>;
  return inner;
}

function AthleteCard({ athlete }: { athlete: AdminDashboardAthlete }) {
  const tsb = athlete.training_load;
  const tsbCfg = TSB_CONFIG[tsb.tsb_status];
  const icon = MODALITY_ICON[athlete.primary_modality ?? ""] ?? "🏅";

  return (
    <Link href={`/admin/athletes/${athlete.id}`}>
      <div className="bg-white rounded-xl border border-gray-200 p-4 hover:border-sky-300 hover:shadow-sm transition-all">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xl">{icon}</span>
            <div className="min-w-0">
              <p className="font-medium text-gray-900 truncate text-sm">{athlete.name}</p>
              <p className="text-xs text-gray-400 truncate">{athlete.email}</p>
            </div>
          </div>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${tsbCfg.className}`}>
            {tsbCfg.label}
          </span>
        </div>

        {/* Metrics row */}
        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          <Metric label="CTL" value={tsb.ctl?.toFixed(0) ?? "—"} />
          <Metric label="ATL" value={tsb.atl?.toFixed(0) ?? "—"} />
          <Metric label="TSB" value={tsb.tsb != null ? (tsb.tsb > 0 ? "+" : "") + tsb.tsb.toFixed(1) : "—"} highlight={
            tsb.tsb != null ? (tsb.tsb < -15 ? "red" : tsb.tsb > 10 ? "green" : undefined) : undefined
          } />
        </div>

        {/* Footer row */}
        <div className="mt-3 flex items-center justify-between text-xs text-gray-400">
          <span>
            {athlete.days_since_last_workout != null
              ? athlete.days_since_last_workout === 0
                ? "Treinou hoje"
                : `Último treino há ${athlete.days_since_last_workout}d`
              : "Sem treinos"}
          </span>
          {athlete.no_workout_alert && (
            <span className="text-orange-500 font-medium">⚠ sem treino 3d+</span>
          )}
          {!athlete.onboarding_complete && (
            <span className="text-gray-400">onboarding pendente</span>
          )}
        </div>
      </div>
    </Link>
  );
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: "red" | "green" }) {
  const cls =
    highlight === "red"   ? "text-red-600 font-bold" :
    highlight === "green" ? "text-green-600 font-semibold" :
                            "text-gray-800";
  return (
    <div className="bg-gray-50 rounded-lg py-1.5">
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`text-sm font-semibold ${cls}`}>{value}</p>
    </div>
  );
}
