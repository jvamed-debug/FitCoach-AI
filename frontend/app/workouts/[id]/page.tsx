"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import { SkeletonCard } from "@/components/ui/Skeleton";
import type { Workout } from "@/lib/types";

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

const SOURCE_LABEL: Record<string, string> = {
  strava: "Strava", trainingpeaks: "TrainingPeaks",
  garmin: "Garmin", manual: "Manual", planned: "Planejado",
};

function formatDuration(seconds: number | null): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}min` : `${m}min`;
}

function formatDistance(meters: number | null): string {
  if (!meters) return "—";
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

function StatBox({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3 text-center">
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className="text-lg font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function ZoneBar({ zones, type }: { zones: Record<string, number>; type: "hr" | "power" }) {
  const total = Object.values(zones).reduce((a, b) => a + b, 0);
  if (!total) return null;

  const colors =
    type === "hr"
      ? ["bg-blue-300", "bg-green-400", "bg-yellow-400", "bg-orange-400", "bg-red-500"]
      : ["bg-gray-300", "bg-blue-300", "bg-green-400", "bg-yellow-400", "bg-orange-400", "bg-red-500", "bg-purple-500"];

  return (
    <div>
      <p className="text-sm font-medium text-gray-700 mb-2">
        {type === "hr" ? "Zonas de Frequência Cardíaca" : "Zonas de Potência (Coggan)"}
      </p>
      <div className="flex rounded-full overflow-hidden h-5 gap-0.5">
        {Object.entries(zones).map(([zone, seconds], i) => {
          const pct = (seconds / total) * 100;
          if (pct < 1) return null;
          return (
            <div
              key={zone}
              className={`${colors[i] || "bg-gray-400"} flex items-center justify-center text-white text-xs font-medium`}
              style={{ width: `${pct}%` }}
              title={`${zone}: ${Math.round(pct)}% (${Math.round(seconds / 60)}min)`}
            >
              {pct > 8 ? `Z${i + 1}` : ""}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
        {Object.entries(zones).map(([zone, seconds], i) => {
          const mins = Math.round(seconds / 60);
          if (mins === 0) return null;
          return (
            <span key={zone} className="text-xs text-gray-500">
              <span className={`inline-block w-2 h-2 rounded-full mr-1 ${colors[i] || "bg-gray-400"}`} />
              {zone}: {mins}min
            </span>
          );
        })}
      </div>
    </div>
  );
}

export default function WorkoutDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const { role } = useAuthStore();
  const [workout, setWorkout] = useState<Workout | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!role) router.replace("/auth/login");
  }, [role, router]);

  useEffect(() => {
    if (!params.id) return;
    setLoading(true);
    api
      .get<Workout>(`/api/workouts/${params.id}`)
      .then((res) => setWorkout(res.data))
      .catch(() => setError("Treino não encontrado."))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-4 space-y-4 max-w-2xl mx-auto">
        <SkeletonCard className="h-24" />
        <div className="grid grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => <SkeletonCard key={i} className="h-20" />)}
        </div>
        <SkeletonCard className="h-40" />
      </div>
    );
  }

  if (error || !workout) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
        <p className="text-gray-500">{error || "Treino não encontrado."}</p>
        <Link href="/workouts" className="text-sky-600 text-sm hover:underline">← Voltar para treinos</Link>
      </div>
    );
  }

  const date = workout.start_time ? parseISO(workout.start_time) : null;
  const icon = SPORT_ICON[workout.sport_type] ?? "⚡";
  const sportLabel = SPORT_LABEL[workout.sport_type] ?? workout.sport_type;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-4 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <Link href="/workouts" className="text-gray-400 hover:text-gray-600 text-xl">←</Link>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xl">{icon}</span>
              <h1 className="font-semibold text-gray-900 truncate">
                {workout.title || sportLabel}
              </h1>
            </div>
            {date && (
              <p className="text-xs text-gray-400 ml-8">
                {format(date, "EEEE, d 'de' MMMM 'de' yyyy · HH:mm", { locale: ptBR })}
              </p>
            )}
          </div>
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-1 rounded-full flex-shrink-0">
            {SOURCE_LABEL[workout.source] ?? workout.source}
          </span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-5 space-y-5">

        {/* Primary stats */}
        <div className="grid grid-cols-3 gap-3">
          <StatBox label="Duração" value={formatDuration(workout.duration_seconds)} />
          <StatBox label="Distância" value={formatDistance(workout.distance_meters)} />
          <StatBox
            label="TSS"
            value={workout.tss != null ? workout.tss.toFixed(0) : "—"}
            sub={workout.if_score != null ? `IF ${workout.if_score.toFixed(2)}` : undefined}
          />
        </div>

        {/* Power stats (cycling) */}
        {(workout.avg_power_watts || workout.normalized_power_watts) && (
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <p className="text-sm font-medium text-gray-700 mb-3">Potência</p>
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Média" value={workout.avg_power_watts ? `${workout.avg_power_watts}W` : "—"} />
              <StatBox label="Normalizada" value={workout.normalized_power_watts ? `${workout.normalized_power_watts}W` : "—"} />
              <StatBox label="Máxima" value={workout.max_power_watts ? `${workout.max_power_watts}W` : "—"} />
            </div>
          </div>
        )}

        {/* HR stats */}
        {(workout.avg_heart_rate || workout.max_heart_rate) && (
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <p className="text-sm font-medium text-gray-700 mb-3">Frequência Cardíaca</p>
            <div className="grid grid-cols-2 gap-3">
              <StatBox label="Média" value={workout.avg_heart_rate ? `${workout.avg_heart_rate} bpm` : "—"} />
              <StatBox label="Máxima" value={workout.max_heart_rate ? `${workout.max_heart_rate} bpm` : "—"} />
            </div>
          </div>
        )}

        {/* Other stats */}
        <div className="grid grid-cols-3 gap-3">
          {workout.avg_cadence != null && (
            <StatBox label="Cadência" value={`${workout.avg_cadence} rpm`} />
          )}
          {workout.elevation_gain_meters != null && (
            <StatBox label="Elevação" value={`${Math.round(workout.elevation_gain_meters)} m`} />
          )}
          {workout.calories != null && (
            <StatBox label="Calorias" value={`${workout.calories} kcal`} />
          )}
        </div>

        {/* Zone distribution */}
        {(workout.power_zones || workout.hr_zones) && (
          <div className="bg-white rounded-xl border border-gray-100 p-4 space-y-5">
            {workout.power_zones && Object.keys(workout.power_zones).length > 0 && (
              <ZoneBar zones={workout.power_zones} type="power" />
            )}
            {workout.hr_zones && Object.keys(workout.hr_zones).length > 0 && (
              <ZoneBar zones={workout.hr_zones} type="hr" />
            )}
          </div>
        )}

        {/* Description */}
        {workout.description && (
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <p className="text-sm font-medium text-gray-700 mb-2">Descrição</p>
            <p className="text-sm text-gray-600 whitespace-pre-line">{workout.description}</p>
          </div>
        )}
      </div>
    </div>
  );
}
