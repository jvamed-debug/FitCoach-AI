"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { AdminAlert, AlertSeverity, AlertSummary } from "@/lib/types";

const SEVERITY_CONFIG: Record<AlertSeverity, { label: string; dot: string; border: string; bg: string }> = {
  critical: {
    label: "Crítico",
    dot: "bg-red-500",
    border: "border-l-red-500",
    bg: "bg-red-50",
  },
  warning: {
    label: "Atenção",
    dot: "bg-yellow-500",
    border: "border-l-yellow-500",
    bg: "bg-yellow-50",
  },
  info: {
    label: "Info",
    dot: "bg-blue-400",
    border: "border-l-blue-400",
    bg: "bg-blue-50",
  },
};

const TYPE_ICON: Record<string, string> = {
  overreaching: "⚠️",
  no_workout: "🏃",
  no_metrics: "📊",
  sync_failure: "🔌",
  milestone: "🏆",
  weekly_report: "📋",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}min atrás`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h atrás`;
  return `${Math.floor(hrs / 24)}d atrás`;
}

interface AlertsListProps {
  /** Maximum number of alerts to show. Default: all. */
  limit?: number;
  /** Show only unread. Default: true. */
  unreadOnly?: boolean;
  /** Called after an alert is marked as read. */
  onRead?: () => void;
}

export default function AlertsList({ limit = 50, unreadOnly = true, onRead }: AlertsListProps) {
  const [alerts, setAlerts] = useState<AdminAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [markingAll, setMarkingAll] = useState(false);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      if (unreadOnly) params.set("unread_only", "true");
      const res = await api.get<AdminAlert[]>(`/api/admin/alerts?${params}`);
      setAlerts(res.data);
    } catch {
      // silently fail — parent page handles global error state
    } finally {
      setLoading(false);
    }
  }, [limit, unreadOnly]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const markRead = async (id: string) => {
    try {
      await api.put(`/api/admin/alerts/${id}/read`);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
      onRead?.();
    } catch {
      // ignore
    }
  };

  const markAllRead = async () => {
    setMarkingAll(true);
    try {
      await api.put("/api/admin/alerts/read-all");
      setAlerts([]);
      onRead?.();
    } finally {
      setMarkingAll(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 rounded-lg bg-gray-100 animate-pulse" />
        ))}
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <p className="text-sm text-gray-400 py-4 text-center">
        Nenhum alerta {unreadOnly ? "não lido" : ""}.
      </p>
    );
  }

  return (
    <div>
      {alerts.length > 1 && (
        <div className="flex justify-end mb-3">
          <button
            onClick={markAllRead}
            disabled={markingAll}
            className="text-xs text-sky-600 hover:text-sky-800 disabled:opacity-50"
          >
            {markingAll ? "Marcando..." : "Marcar todos como lidos"}
          </button>
        </div>
      )}

      <div className="space-y-2">
        {alerts.map((alert) => {
          const cfg = SEVERITY_CONFIG[alert.severity];
          const icon = TYPE_ICON[alert.alert_type] ?? "📌";

          return (
            <div
              key={alert.id}
              className={`border-l-4 ${cfg.border} ${cfg.bg} rounded-r-lg px-4 py-3 flex items-start gap-3`}
            >
              <span className="text-lg leading-none mt-0.5">{icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm text-gray-900">{alert.title}</span>
                  <span className={`inline-flex h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
                  <span className="text-xs text-gray-400">{timeAgo(alert.created_at)}</span>
                </div>
                {alert.body && (
                  <p className="text-xs text-gray-600 mt-1 line-clamp-2">{alert.body}</p>
                )}
                {alert.athlete_id && (
                  <Link
                    href={`/admin/athletes/${alert.athlete_id}`}
                    className="text-xs text-sky-600 hover:underline mt-1 inline-block"
                  >
                    Ver atleta →
                  </Link>
                )}
              </div>
              <button
                onClick={() => markRead(alert.id)}
                title="Marcar como lido"
                className="text-gray-300 hover:text-gray-600 text-xs flex-shrink-0 mt-0.5"
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
