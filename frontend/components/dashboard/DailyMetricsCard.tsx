"use client";

import Link from "next/link";
import type { DailyMetrics } from "@/lib/types";

function ScaleDot({ value, max = 10 }: { value: number | null; max?: number }) {
  if (value === null || value === undefined) return <span className="text-gray-300">—</span>;
  const pct = (value / max) * 100;
  const color =
    pct >= 80 ? "text-red-600"    :
    pct >= 60 ? "text-orange-500" :
    pct >= 40 ? "text-yellow-500" :
                "text-green-600";
  return <span className={`font-bold ${color}`}>{value}</span>;
}

interface Props {
  metrics: DailyMetrics | null;
  loading?: boolean;
}

export default function DailyMetricsCard({ metrics, loading }: Props) {
  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="grid grid-cols-3 gap-3">
          {[1,2,3,4,5,6].map((i) => (
            <div key={i} className="h-12 bg-gray-100 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-medium text-gray-900">Métricas de hoje</h3>
          <Link href="/metrics" className="text-xs text-brand-600 hover:underline">Registrar →</Link>
        </div>
        <p className="text-sm text-gray-400">Ainda não registradas hoje.</p>
        <p className="text-xs text-gray-300 mt-1">
          Registre suas métricas para que a IA possa personalizar melhor seu treino.
        </p>
      </div>
    );
  }

  const items = [
    { label: "Fadiga",     value: metrics.fatigue_score,    icon: "😴" },
    { label: "Dor muscular",value: metrics.muscle_soreness, icon: "💢" },
    { label: "Motivação",  value: metrics.motivation_score, icon: "🔥", invert: true },
    { label: "Sono",       value: metrics.sleep_quality,    icon: "🌙", invert: true },
    { label: "HRV",        value: metrics.hrv_ms ? `${metrics.hrv_ms}ms` : null, icon: "💓", raw: true },
    { label: "FC repouso", value: metrics.resting_hr ? `${metrics.resting_hr}bpm` : null, icon: "❤️", raw: true },
  ];

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-900">Métricas de hoje</h3>
        <Link href="/metrics" className="text-xs text-brand-600 hover:underline">Editar →</Link>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {items.map(({ label, value, icon, raw }) => (
          <div key={label} className="bg-gray-50 rounded-lg p-2.5 text-center">
            <p className="text-base mb-0.5">{icon}</p>
            <p className="text-xs text-gray-500 leading-tight">{label}</p>
            <div className="text-sm mt-0.5">
              {raw ? (
                <span className="font-medium text-gray-700">{value ?? "—"}</span>
              ) : (
                <ScaleDot value={value as number | null} />
              )}
            </div>
          </div>
        ))}
      </div>
      {metrics.notes && (
        <p className="text-xs text-gray-400 mt-3 italic line-clamp-1">"{metrics.notes}"</p>
      )}
    </div>
  );
}
