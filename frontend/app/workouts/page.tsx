"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { formatDistanceToNow, format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
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

function formatDuration(seconds: number | null): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}min` : `${m}min`;
}

export default function WorkoutsPage() {
  const router = useRouter();
  const { role } = useAuthStore();
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [sportFilter, setSportFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const perPage = 20;

  useEffect(() => {
    if (!role) router.replace("/auth/login");
  }, [role, router]);

  const fetchWorkouts = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, per_page: perPage };
      if (sportFilter) params.sport_type = sportFilter;
      const resp = await api.get("/api/workouts", { params });
      setWorkouts(resp.data.items);
      setTotal(resp.data.total);
    } finally {
      setLoading(false);
    }
  }, [page, sportFilter]);

  useEffect(() => { fetchWorkouts(); }, [fetchWorkouts]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const resp = await api.post("/api/workouts/sync/strava?days_back=14");
      setSyncMsg(`✓ ${resp.data.imported} atividade(s) importada(s)`);
      fetchWorkouts();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSyncMsg(msg ?? "Erro ao sincronizar com Strava");
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMsg(null), 4000);
    }
  };

  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Treinos</h1>
            <p className="text-sm text-gray-500">{total} treino{total !== 1 ? "s" : ""} registrado{total !== 1 ? "s" : ""}</p>
          </div>
          <div className="flex items-center gap-3">
            {syncMsg && (
              <span className={`text-sm ${syncMsg.startsWith("✓") ? "text-green-600" : "text-red-600"}`}>
                {syncMsg}
              </span>
            )}
            <button
              onClick={handleSync}
              disabled={syncing}
              className="rounded-lg border border-orange-400 text-orange-600 px-3 py-1.5 text-sm font-medium hover:bg-orange-50 disabled:opacity-40 transition-colors"
            >
              {syncing ? "Sincronizando…" : "↺ Strava"}
            </button>
            <Link
              href="/workouts/new"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition-colors"
            >
              + Manual
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-6">
        {/* Filters */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {["", "cycling", "running", "swimming", "strength", "other"].map((s) => (
            <button
              key={s}
              onClick={() => { setSportFilter(s); setPage(1); }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                sportFilter === s
                  ? "bg-brand-600 text-white"
                  : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {s ? `${SPORT_ICON[s]} ${SPORT_LABEL[s]}` : "Todos"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-center py-16 text-gray-400">Carregando…</div>
        ) : workouts.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500 mb-4">Nenhum treino encontrado.</p>
            <button onClick={handleSync} className="text-orange-500 font-medium hover:underline">
              Sincronizar com Strava →
            </button>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {workouts.map((w) => (
                <div key={w.id} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4 hover:border-gray-300 transition-colors">
                  <div className="text-2xl w-10 text-center flex-shrink-0">
                    {SPORT_ICON[w.sport_type] ?? "⚡"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-gray-900 truncate">{w.title ?? SPORT_LABEL[w.sport_type]}</p>
                      <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded capitalize flex-shrink-0">
                        {w.source}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {w.start_time
                        ? format(parseISO(w.start_time), "EEEE, dd 'de' MMMM", { locale: ptBR })
                        : "—"}
                    </p>
                  </div>
                  <div className="hidden md:flex items-center gap-6 text-sm text-gray-500 flex-shrink-0">
                    <div className="text-center">
                      <p className="font-medium text-gray-900">{formatDuration(w.duration_seconds)}</p>
                      <p className="text-xs">duração</p>
                    </div>
                    {w.distance_meters && (
                      <div className="text-center">
                        <p className="font-medium text-gray-900">{(w.distance_meters / 1000).toFixed(1)} km</p>
                        <p className="text-xs">distância</p>
                      </div>
                    )}
                    {w.tss !== null && w.tss !== undefined && (
                      <div className="text-center">
                        <p className="font-medium text-gray-900">{w.tss.toFixed(0)}</p>
                        <p className="text-xs">TSS</p>
                      </div>
                    )}
                    {w.normalized_power_watts && (
                      <div className="text-center">
                        <p className="font-medium text-gray-900">{w.normalized_power_watts}W</p>
                        <p className="text-xs">NP</p>
                      </div>
                    )}
                    {w.avg_heart_rate && (
                      <div className="text-center">
                        <p className="font-medium text-gray-900">{w.avg_heart_rate} bpm</p>
                        <p className="text-xs">FC média</p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex justify-center gap-2 mt-5">
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                  className="px-3 py-1.5 text-sm rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-50">
                  ← Anterior
                </button>
                <span className="px-3 py-1.5 text-sm text-gray-600">{page} / {totalPages}</span>
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                  className="px-3 py-1.5 text-sm rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-50">
                  Próxima →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
