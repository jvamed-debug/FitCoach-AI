"use client";

import Link from "next/link";
import type { AIRecommendation } from "@/lib/types";

const WORKOUT_ICON: Record<string, string> = {
  cycling_endurance:  "🚴", cycling_threshold: "⚡", cycling_vo2max:  "🔥",
  cycling_long:       "🗺️", running_easy:      "🏃", running_tempo:   "💨",
  running_intervals:  "🏁", swimming_base:     "🏊", strength_upper:  "💪",
  strength_lower:     "🦵", strength_full:     "🏋️", triathlon_brick: "🏅",
  mobility:           "🧘", rest:              "😴",
};

const INTENSITY_PILL: Record<string, string> = {
  easy:      "bg-green-100 text-green-700",
  moderate:  "bg-blue-100 text-blue-700",
  hard:      "bg-orange-100 text-orange-700",
  very_hard: "bg-red-100 text-red-700",
  rest:      "bg-gray-100 text-gray-500",
};

interface Props {
  rec: AIRecommendation | null;
  loading: boolean;
}

export default function DailyRecommendationCard({ rec, loading }: Props) {
  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-3" />
        <div className="h-8 bg-gray-200 rounded w-2/3 mb-2" />
        <div className="h-4 bg-gray-200 rounded w-1/2" />
      </div>
    );
  }

  if (!rec) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-medium text-gray-900 mb-1">Treino de hoje</h3>
        <p className="text-sm text-gray-400 mb-3">Nenhuma recomendação gerada ainda.</p>
        <Link
          href="/recommendations"
          className="text-sm text-brand-600 font-medium hover:underline"
        >
          Gerar recomendação →
        </Link>
      </div>
    );
  }

  const plan = rec.structured_plan as { intensity?: string; duration_minutes?: number } | null;
  const icon = WORKOUT_ICON[rec.workout_type ?? ""] ?? "🏋️";
  const pill = INTENSITY_PILL[plan?.intensity ?? "moderate"] ?? INTENSITY_PILL.moderate;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-900">Treino de hoje</h3>
        <Link href="/recommendations" className="text-xs text-brand-600 hover:underline">
          Ver detalhes →
        </Link>
      </div>

      <div className="flex items-start gap-3">
        <span className="text-3xl">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 truncate">{rec.title}</p>
          <div className="flex gap-2 mt-1 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${pill}`}>
              {plan?.intensity ?? "—"}
            </span>
            {plan?.duration_minutes && (
              <span className="text-xs text-gray-400">{plan.duration_minutes}min</span>
            )}
            <span className="text-xs text-gray-300 capitalize">
              {rec.workout_type?.replace(/_/g, " ")}
            </span>
          </div>
        </div>
      </div>

      {rec.rationale && (
        <p className="text-xs text-gray-500 mt-3 line-clamp-2">{rec.rationale}</p>
      )}

      {rec.feedback_rating === null && (
        <Link
          href="/recommendations"
          className="mt-3 block w-full text-center py-2 rounded-lg bg-brand-50 text-brand-700 text-sm font-medium hover:bg-brand-100 transition-colors"
        >
          Dar feedback →
        </Link>
      )}
    </div>
  );
}
