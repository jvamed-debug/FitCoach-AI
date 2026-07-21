"use client";

import Link from "next/link";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import type { Workout } from "@/lib/types";

const SPORT_ICON: Record<string, string> = {
  cycling: "🚴", running: "🏃", swimming: "🏊",
  strength: "💪", triathlon: "🏅", rest: "😴",
  mobility: "🧘", other: "⚡",
};

function fmt(seconds: number | null) {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h${m.toString().padStart(2,"0")}` : `${m}min`;
}

interface Props { workouts: Workout[] }

export default function RecentWorkoutsList({ workouts }: Props) {
  if (!workouts.length) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-medium text-gray-900 mb-3">Treinos recentes</h3>
        <p className="text-sm text-gray-400">Nenhum treino ainda.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-900">Treinos recentes</h3>
        <Link href="/workouts" className="text-xs text-brand-600 hover:underline">Ver todos →</Link>
      </div>
      <div className="space-y-2">
        {workouts.slice(0, 5).map((w) => (
          <div key={w.id} className="flex items-center gap-3 py-1.5">
            <span className="text-lg w-7 text-center flex-shrink-0">
              {SPORT_ICON[w.sport_type] ?? "⚡"}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {w.title ?? w.sport_type}
              </p>
              <p className="text-xs text-gray-400">
                {w.start_time
                  ? format(parseISO(w.start_time), "EEE dd/MM", { locale: ptBR })
                  : "—"}
              </p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-sm font-medium text-gray-700">{fmt(w.duration_seconds)}</p>
              {w.tss != null && (
                <p className="text-xs text-gray-400">{w.tss.toFixed(0)} TSS</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
