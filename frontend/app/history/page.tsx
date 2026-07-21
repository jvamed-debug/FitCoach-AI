"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { format, parseISO, subDays } from "date-fns";
import { ptBR } from "date-fns/locale";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import { SkeletonList } from "@/components/ui/Skeleton";
import type { Workout } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

interface StrengthItem {
  id: string;
  session_date: string;
  session_type: string | null;
  duration_minutes: number | null;
  rpe_overall: number | null;
  tss: number | null;
}

type HistoryItem =
  | ({ kind: "workout" } & Workout)
  | ({ kind: "strength" } & StrengthItem);

// ── Helpers ───────────────────────────────────────────────────────────────────

const SPORT_ICON: Record<string, string> = {
  cycling: "🚴", running: "🏃", swimming: "🏊",
  triathlon: "🏅", strength: "💪", rest: "😴",
  mobility: "🧘", other: "⚡",
};

const SPORT_LABEL: Record<string, string> = {
  cycling: "Ciclismo", running: "Corrida", swimming: "Natação",
  triathlon: "Triathlon", strength: "Musculação", rest: "Descanso",
  mobility: "Mobilidade", other: "Outro",
};

const SESSION_TYPE_LABEL: Record<string, string> = {
  upper: "Superior", lower: "Inferior", full_body: "Corpo todo",
  push: "Empurrar", pull: "Puxar",
};

function formatDuration(seconds: number | null, minutes?: number | null): string {
  if (seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${m}min` : `${m}min`;
  }
  if (minutes) return `${minutes}min`;
  return "—";
}

function formatDistance(meters: number | null): string {
  if (!meters) return "";
  return meters >= 1000 ? `· ${(meters / 1000).toFixed(1)} km` : `· ${Math.round(meters)} m`;
}

// ── Period presets ────────────────────────────────────────────────────────────

const PERIODS = [
  { label: "7 dias",  days: 7 },
  { label: "30 dias", days: 30 },
  { label: "90 dias", days: 90 },
  { label: "1 ano",   days: 365 },
];

const SPORT_FILTERS = [
  { value: "",         label: "Todos" },
  { value: "cycling",  label: "🚴 Ciclismo" },
  { value: "running",  label: "🏃 Corrida" },
  { value: "swimming", label: "🏊 Natação" },
  { value: "strength", label: "💪 Musculação" },
  { value: "mobility", label: "🧘 Mobilidade" },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const router = useRouter();
  const { role } = useAuthStore();

  const [days, setDays] = useState(30);
  const [sportFilter, setSportFilter] = useState("");
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalTss, setTotalTss] = useState(0);

  useEffect(() => {
    if (!role) router.replace("/auth/login");
  }, [role, router]);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const since = format(subDays(new Date(), days), "yyyy-MM-dd");

      const [workoutsRes, strengthRes] = await Promise.all([
        api.get<{ items: Workout[] }>(`/api/workouts?per_page=200&since=${since}${sportFilter && sportFilter !== "strength" ? `&sport_type=${sportFilter}` : ""}`),
        sportFilter === "" || sportFilter === "strength"
          ? api.get<{ items: StrengthItem[] }>(`/api/strength?per_page=200&since=${since}`)
          : Promise.resolve({ data: { items: [] } }),
      ]);

      const workoutItems: HistoryItem[] = (workoutsRes.data.items ?? []).map((w) => ({
        kind: "workout",
        ...w,
      }));

      const strengthItems: HistoryItem[] =
        sportFilter !== "strength"
          ? []
          : (strengthRes.data.items ?? []).map((s) => ({
              kind: "strength",
              ...s,
            }));

      // For "Todos" or "Musculação" filter, merge strength too
      const allStrength: HistoryItem[] =
        (sportFilter === "" || sportFilter === "strength")
          ? (strengthRes.data.items ?? []).map((s) => ({ kind: "strength" as const, ...s }))
          : [];

      const combined = [
        ...workoutItems,
        ...allStrength,
      ].sort((a, b) => {
        const dateA = a.kind === "workout" ? a.start_time : a.session_date + "T12:00:00";
        const dateB = b.kind === "workout" ? b.start_time : b.session_date + "T12:00:00";
        return new Date(dateB).getTime() - new Date(dateA).getTime();
      });

      setItems(combined);
      setTotalTss(
        combined.reduce((sum, item) => {
          const tss = item.kind === "workout" ? (item.tss ?? 0) : (item.tss ?? 0);
          return sum + tss;
        }, 0)
      );
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [days, sportFilter]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Group by date label
  const grouped = items.reduce<Record<string, HistoryItem[]>>((acc, item) => {
    const rawDate =
      item.kind === "workout" ? item.start_time : item.session_date + "T12:00:00";
    const label = format(parseISO(rawDate), "EEEE, d 'de' MMMM", { locale: ptBR });
    if (!acc[label]) acc[label] = [];
    acc[label].push(item);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-4 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-lg font-semibold text-gray-900">Histórico</h1>
            <div className="text-sm text-gray-500">
              {items.length} sessões · TSS {totalTss.toFixed(0)}
            </div>
          </div>

          {/* Period selector */}
          <div className="flex gap-2 mb-3 overflow-x-auto pb-1 hide-scrollbar">
            {PERIODS.map(({ label, days: d }) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  days === d
                    ? "bg-sky-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Sport filter */}
          <div className="flex gap-2 overflow-x-auto pb-1 hide-scrollbar">
            {SPORT_FILTERS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setSportFilter(value)}
                className={`flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  sportFilter === value
                    ? "bg-gray-800 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-2xl mx-auto px-4 py-4">
        {loading ? (
          <SkeletonList rows={8} />
        ) : items.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-4xl mb-3">🏖️</p>
            <p className="text-gray-500">Nenhuma atividade encontrada neste período.</p>
            <Link href="/workouts" className="text-sky-600 text-sm hover:underline mt-2 inline-block">
              Ver todos os treinos →
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            {Object.entries(grouped).map(([dateLabel, dayItems]) => (
              <div key={dateLabel}>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2 capitalize">
                  {dateLabel}
                </p>
                <div className="space-y-2">
                  {dayItems.map((item) =>
                    item.kind === "workout" ? (
                      <WorkoutRow key={`w-${item.id}`} item={item} />
                    ) : (
                      <StrengthRow key={`s-${item.id}`} item={item} />
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Row sub-components ────────────────────────────────────────────────────────

function WorkoutRow({ item }: { item: Workout & { kind: "workout" } }) {
  const icon = SPORT_ICON[item.sport_type] ?? "⚡";
  const label = SPORT_LABEL[item.sport_type] ?? item.sport_type;

  return (
    <Link href={`/workouts/${item.id}`}>
      <div className="bg-white rounded-xl border border-gray-100 px-4 py-3 flex items-center gap-3 hover:border-sky-200 hover:shadow-sm transition-all">
        <span className="text-2xl w-8 text-center">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 text-sm truncate">
            {item.title || label}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            {formatDuration(item.duration_seconds)}
            {formatDistance(item.distance_meters)}
            {item.avg_power_watts ? ` · ${item.avg_power_watts}W` : ""}
            {item.avg_heart_rate ? ` · ${item.avg_heart_rate}bpm` : ""}
          </p>
        </div>
        <div className="text-right flex-shrink-0">
          {item.tss != null && (
            <p className="text-sm font-semibold text-gray-700">{item.tss.toFixed(0)}</p>
          )}
          <p className="text-xs text-gray-400">TSS</p>
        </div>
      </div>
    </Link>
  );
}

function StrengthRow({ item }: { item: StrengthItem & { kind: "strength" } }) {
  const typeLabel = item.session_type ? (SESSION_TYPE_LABEL[item.session_type] ?? item.session_type) : "Musculação";
  return (
    <Link href={`/strength/${item.id}`}>
      <div className="bg-white rounded-xl border border-gray-100 px-4 py-3 flex items-center gap-3 hover:border-sky-200 hover:shadow-sm transition-all">
        <span className="text-2xl w-8 text-center">💪</span>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 text-sm truncate">{typeLabel}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {item.duration_minutes ? `${item.duration_minutes}min` : "—"}
            {item.rpe_overall ? ` · RPE ${item.rpe_overall}` : ""}
          </p>
        </div>
        <div className="text-right flex-shrink-0">
          {item.tss != null && (
            <p className="text-sm font-semibold text-gray-700">{item.tss.toFixed(0)}</p>
          )}
          <p className="text-xs text-gray-400">TSS</p>
        </div>
      </div>
    </Link>
  );
}
