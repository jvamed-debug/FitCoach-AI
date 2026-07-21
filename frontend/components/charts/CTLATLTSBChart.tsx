"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import { useState } from "react";
import type { TrainingLoad } from "@/lib/types";

interface Props {
  data: TrainingLoad[];
}

const PERIODS = [
  { label: "30d", days: 30 },
  { label: "60d", days: 60 },
  { label: "90d", days: 90 },
];

const CustomTooltip = ({ active, payload, label }: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-medium text-gray-700 mb-2">
        {label ? format(parseISO(label), "dd 'de' MMMM", { locale: ptBR }) : ""}
      </p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex justify-between gap-4 mb-0.5">
          <span style={{ color: entry.color }} className="font-medium">{entry.name}</span>
          <span className="text-gray-700 font-mono">
            {entry.name === "TSB" && entry.value > 0 ? "+" : ""}
            {entry.value.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
};

export default function CTLATLTSBChart({ data }: Props) {
  const [period, setPeriod] = useState(60);

  const filtered = data.slice(-period);

  const tickFormatter = (val: string) => {
    try {
      return format(parseISO(val), "dd/MM");
    } catch {
      return val;
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-medium text-gray-900">Carga de Treino</h3>
          <p className="text-xs text-gray-400 mt-0.5">CTL · ATL · TSB</p>
        </div>
        <div className="flex gap-1">
          {PERIODS.map(({ label, days }) => (
            <button
              key={days}
              onClick={() => setPeriod(days)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                period === days
                  ? "bg-brand-600 text-white"
                  : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={filtered} margin={{ top: 4, right: 8, bottom: 4, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="load_date"
            tickFormatter={tickFormatter}
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={false}
            width={30}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
            iconType="circle"
            iconSize={8}
          />
          <ReferenceLine y={0} stroke="#e5e7eb" strokeDasharray="4 2" />
          <Line
            type="monotone"
            dataKey="ctl"
            name="CTL"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="atl"
            name="ATL"
            stroke="#f97316"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="tsb"
            name="TSB"
            stroke="#22c55e"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Legend annotations */}
      <div className="flex gap-4 mt-3 text-xs text-gray-400">
        <span><span className="text-blue-500 font-medium">CTL</span> = Fitness (42d)</span>
        <span><span className="text-orange-500 font-medium">ATL</span> = Fadiga (7d)</span>
        <span><span className="text-green-500 font-medium">TSB</span> = Forma (CTL−ATL)</span>
      </div>
    </div>
  );
}
