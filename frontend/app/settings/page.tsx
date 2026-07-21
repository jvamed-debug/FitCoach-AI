"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import type { AthleteProfile } from "@/lib/types";

interface Connection {
  provider: string;
  is_active: boolean;
  provider_athlete_id: string | null;
  last_sync_at: string | null;
  sync_error: string | null;
  consecutive_failures: number;
}

const PROVIDER_META: Record<string, { label: string; icon: string; color: string }> = {
  strava:        { label: "Strava",        icon: "🟠", color: "border-orange-200 bg-orange-50" },
  trainingpeaks: { label: "TrainingPeaks", icon: "🔵", color: "border-blue-200 bg-blue-50" },
  garmin:        { label: "Garmin",        icon: "🟢", color: "border-green-200 bg-green-50" },
};

export default function SettingsPage() {
  const router = useRouter();
  const { role, profile } = useAuthStore();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [appleToken, setAppleToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  useEffect(() => {
    if (!role || !profile) { router.replace("/auth/login"); return; }
    if (role !== "athlete") { router.replace("/dashboard"); return; }
  }, [role, profile, router]);

  useEffect(() => {
    Promise.all([
      api.get("/api/auth/oauth/connections"),
      api.get("/api/auth/me"),
    ]).then(([connResp, meResp]) => {
      setConnections(connResp.data);
      setAppleToken((meResp.data as AthleteProfile).apple_health_token ?? null);
    }).finally(() => setLoading(false));
  }, []);

  // Check URL params for OAuth redirect result
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const stravaResult = params.get("strava");
    if (stravaResult === "connected") {
      api.get("/api/auth/oauth/connections").then((r) => setConnections(r.data));
    }
  }, []);

  const handleConnect = (provider: string) => {
    if (provider === "strava") {
      window.location.href = `${process.env.NEXT_PUBLIC_API_URL}/api/auth/oauth/strava/authorize`;
    }
  };

  const handleDisconnect = async (provider: string) => {
    setDisconnecting(provider);
    try {
      await api.delete(`/api/auth/oauth/${provider}`);
      setConnections((prev) =>
        prev.map((c) => c.provider === provider ? { ...c, is_active: false } : c)
      );
    } finally {
      setDisconnecting(null);
    }
  };

  const athlete = profile as AthleteProfile;

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const appleHealthUrl = appleToken
    ? `${apiBaseUrl}/api/webhooks/apple-health/${appleToken}`
    : null;

  if (loading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">
      Carregando…
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-xl font-semibold text-gray-900">Configurações</h1>
          <p className="text-sm text-gray-500 mt-0.5">Integrações e preferências da conta</p>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">

        {/* ── Platform integrations ── */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-medium text-gray-900 mb-1">Plataformas de treino</h2>
          <p className="text-xs text-gray-400 mb-5">
            Conecte suas plataformas para importar treinos automaticamente.
          </p>

          <div className="space-y-3">
            {(["strava", "trainingpeaks", "garmin"] as const).map((provider) => {
              const meta = PROVIDER_META[provider];
              const conn = connections.find((c) => c.provider === provider);
              const isConnected = conn?.is_active ?? false;
              const hasError = (conn?.consecutive_failures ?? 0) > 0;

              return (
                <div
                  key={provider}
                  className={`rounded-lg border p-4 flex items-center justify-between ${
                    isConnected ? meta.color : "border-gray-200 bg-white"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{meta.icon}</span>
                    <div>
                      <p className="font-medium text-gray-900 text-sm">{meta.label}</p>
                      {isConnected ? (
                        <p className="text-xs text-gray-500">
                          {conn?.last_sync_at
                            ? `Última sync: ${new Date(conn.last_sync_at).toLocaleDateString("pt-BR")}`
                            : "Conectado — sincronize para importar treinos"}
                          {hasError && (
                            <span className="ml-2 text-orange-500">⚠ {conn?.consecutive_failures} falha(s)</span>
                          )}
                        </p>
                      ) : (
                        <p className="text-xs text-gray-400">
                          {provider === "garmin"
                            ? "Via Strava relay (automático quando Strava conectado)"
                            : provider === "trainingpeaks"
                            ? "Aguardando aprovação da API"
                            : "Não conectado"}
                        </p>
                      )}
                    </div>
                  </div>

                  <div>
                    {provider === "garmin" || provider === "trainingpeaks" ? (
                      <span className="text-xs text-gray-400 italic">Em breve</span>
                    ) : isConnected ? (
                      <button
                        onClick={() => handleDisconnect(provider)}
                        disabled={disconnecting === provider}
                        className="text-sm text-red-500 hover:text-red-700 disabled:opacity-40"
                      >
                        {disconnecting === provider ? "Desconectando…" : "Desconectar"}
                      </button>
                    ) : (
                      <button
                        onClick={() => handleConnect(provider)}
                        className="rounded-lg bg-orange-500 text-white px-3 py-1.5 text-sm font-medium hover:bg-orange-600 transition-colors"
                      >
                        Conectar
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Apple Health ── */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-start gap-3 mb-4">
            <span className="text-xl">🍎</span>
            <div>
              <h2 className="font-medium text-gray-900">Apple Health</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Configure um iOS Shortcut para enviar dados diários automaticamente.
              </p>
            </div>
          </div>

          {appleHealthUrl && (
            <div className="space-y-3">
              <div>
                <p className="text-xs font-medium text-gray-600 mb-1">Seu URL único de ingestão:</p>
                <code className="block bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-700 break-all">
                  {appleHealthUrl}
                </code>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
                <p className="font-medium mb-1">📱 Como configurar (iOS Shortcut):</p>
                <ol className="list-decimal list-inside space-y-1">
                  <li>Abra o app Atalhos no iPhone</li>
                  <li>Crie um novo atalho com automação "Hora do dia" às 07:00</li>
                  <li>Adicione a ação "Obter conteúdo do URL" com método POST</li>
                  <li>Cole o URL acima e adicione os campos de saúde desejados</li>
                  <li>Inclua as variáveis do Apple Health (sono, FC repouso, etc.)</li>
                </ol>
                <p className="mt-2">
                  Consulte <code>docs/STRAVA_SETUP.md</code> para um template completo do Shortcut.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ── LGPD ── */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-medium text-gray-900 mb-1">Privacidade e dados (LGPD)</h2>
          <p className="text-xs text-gray-400 mb-4">
            Conforme a Lei 13.709/2018, você tem direito de acessar, exportar ou excluir seus dados.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => api.post("/api/lgpd/export").then(() => alert("Solicitação enviada! Você receberá um e-mail em até 72 horas."))}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Exportar meus dados
            </button>
            <button
              onClick={() => {
                if (confirm("Tem certeza? Todos os seus dados serão excluídos em até 72 horas e você perderá o acesso.")) {
                  api.delete("/api/lgpd/consent", { data: { reason: "Solicitação pelo app" } })
                    .then(() => alert("Solicitação de exclusão registrada. Você receberá um e-mail de confirmação."))
                    .catch(() => alert("Erro ao processar solicitação."));
                }
              }}
              className="rounded-lg border border-red-300 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
            >
              Excluir minha conta
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
