"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";

interface WeekStats {
  workout_count: number;
  total_seconds: number;
  total_meters: number;
  total_tss: number;
}

interface Props {
  thisWeek: WeekStats | null;
  lastWeek: WeekStats | null;
}

function formatDuration(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${m}min` : `${m}min`;
}

export default function WeeklyTSSBar({ thisWeek, lastWeek }: Props) {
  const data = [
    { label: "Semana passada", tss: lastWeek?.total_tss ?? 0, fill: "#e2e8f0" },
    { label: "Esta semana",    tss: thisWeek?.total_tss ?? 0, fill: "#0ea5e9" },
  ];

  const delta = (thisWeek?.total_tss ?? 0) - (lastWeek?.total_tss ?? 0);
  const pct   = lastWeek?.total_tss
    ? Math.round((delta / lastWeek.total_tss) * 100)
    : null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-900">TSS Semanal</h3>
        {pct !== null && (
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            pct > 10 ? "bg-orange-100 text-orange-700" :
            pct > 0  ? "bg-green-100 text-green-700"   :
                       "bg-gray-100 text-gray-500"
          }`}>
            {pct > 0 ? "+" : ""}{pct}% vs semana passada
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={110}>
        <BarChart data={data} barSize={40} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#6b7280" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
          <Tooltip
            formatter={(val) => [`${Number(val).toFixed(0)} TSS`, ""]}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Bar dataKey="tss" radius={[4, 4, 0, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {thisWeek && (
        <div className="flex gap-4 mt-3 text-xs text-gray-500">
          <span>🏋️ {thisWeek.workout_count} treinos</span>
          <span>⏱ {formatDuration(thisWeek.total_seconds)}</span>
          {thisWeek.total_meters > 0 && (
            <span>📍 {(thisWeek.total_meters / 1000).toFixed(0)}km</span>
          )}
        </div>
      )}
    </div>
  );
}
