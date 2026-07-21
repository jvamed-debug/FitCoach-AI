"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";

interface AthleteItem {
  id: string;
  name: string;
  email: string;
  primary_modality: string | null;
  onboarding_complete: boolean;
  is_active: boolean;
  training_load: {
    ctl: number | null;
    atl: number | null;
    tsb: number | null;
    tsb_status: "good" | "moderate" | "alert" | "critical" | "unknown";
    load_date: string | null;
  };
  days_since_last_workout: number | null;
  no_workout_alert: boolean;
}

const TSB_BADGE: Record<string, { label: string; className: string }> = {
  good:     { label: "Ótimo",    className: "bg-green-100 text-green-700" },
  moderate: { label: "Neutro",   className: "bg-yellow-100 text-yellow-700" },
  alert:    { label: "Fatigado", className: "bg-orange-100 text-orange-700" },
  critical: { label: "Crítico",  className: "bg-red-100 text-red-700" },
  unknown:  { label: "Sem dados",className: "bg-gray-100 text-gray-500" },
};

export default function AdminAthletesPage() {
  const router = useRouter();
  const { role } = useAuthStore();
  const [athletes, setAthletes] = useState<AthleteItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const perPage = 20;

  useEffect(() => {
    if (role !== "admin") router.replace("/auth/login");
  }, [role, router]);

  const fetchAthletes = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, per_page: perPage };
      if (search) params.search = search;
      const resp = await api.get("/api/admin/athletes", { params });
      setAthletes(resp.data.items);
      setTotal(resp.data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    fetchAthletes();
  }, [fetchAthletes]);

  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Atletas</h1>
            <p className="text-sm text-gray-500">{total} atleta{total !== 1 ? "s" : ""} cadastrado{total !== 1 ? "s" : ""}</p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/admin/dashboard"
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              ← Painel
            </Link>
            <Link
              href="/admin/athletes/new"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition-colors"
            >
              + Novo atleta
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        {/* Search */}
        <div className="mb-4">
          <input
            type="search"
            placeholder="Buscar por nome ou e-mail…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full max-w-sm rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400">Carregando…</div>
        ) : athletes.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 mb-4">Nenhum atleta encontrado.</p>
            <Link href="/admin/athletes/new" className="text-brand-600 font-medium hover:underline">
              Cadastrar primeiro atleta →
            </Link>
          </div>
        ) : (
          <>
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Atleta</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Modalidade</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-600">Forma (TSB)</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-600">CTL</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-600">ATL</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-600">Último treino</th>
                    <th className="text-center px-4 py-3 font-medium text-gray-600">Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {athletes.map((a) => {
                    const badge = TSB_BADGE[a.training_load.tsb_status];
                    return (
                      <tr key={a.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3">
                          <div className="font-medium text-gray-900">{a.name}</div>
                          <div className="text-xs text-gray-400">{a.email}</div>
                        </td>
                        <td className="px-4 py-3 text-gray-600 capitalize">
                          {a.primary_modality ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${badge.className}`}>
                            {badge.label}
                          </span>
                          {a.training_load.tsb !== null && (
                            <div className="text-xs text-gray-400 mt-0.5">
                              {a.training_load.tsb > 0 ? "+" : ""}{a.training_load.tsb?.toFixed(1)}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center text-gray-700">
                          {a.training_load.ctl?.toFixed(1) ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-center text-gray-700">
                          {a.training_load.atl?.toFixed(1) ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {a.days_since_last_workout !== null ? (
                            <span className={a.no_workout_alert ? "text-orange-600 font-medium" : "text-gray-600"}>
                              {a.days_since_last_workout === 0 ? "hoje" : `${a.days_since_last_workout}d atrás`}
                              {a.no_workout_alert && " ⚠️"}
                            </span>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {!a.onboarding_complete ? (
                            <span className="text-xs text-yellow-600 bg-yellow-50 px-2 py-0.5 rounded-full">
                              Pendente
                            </span>
                          ) : (
                            <span className="text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                              Ativo
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <Link
                            href={`/admin/athletes/${a.id}`}
                            className="text-brand-600 hover:underline text-xs font-medium"
                          >
                            Ver perfil →
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center gap-2 mt-4">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-sm rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-50"
                >
                  ← Anterior
                </button>
                <span className="px-3 py-1.5 text-sm text-gray-600">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 text-sm rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-50"
                >
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
