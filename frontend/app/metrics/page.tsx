"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import { format, parseISO, subDays } from "date-fns";
import { ptBR } from "date-fns/locale";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import type { DailyMetrics } from "@/lib/types";

interface Trends {
  "7d":  Partial<DailyMetrics & { n: number }>;
  "30d": Partial<DailyMetrics & { n: number }>;
}

const SCALE_LABELS: Record<number, string> = {
  1: "1", 2: "2", 3: "3", 4: "4", 5: "5",
  6: "6", 7: "7", 8: "8", 9: "9", 10: "10",
};

function ScaleInput({
  label, value, onChange, color = "brand",
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  color?: string;
}) {
  const colorClass =
    color === "red"    ? "bg-red-500"    :
    color === "orange" ? "bg-orange-500" :
    color === "green"  ? "bg-green-500"  :
    "bg-brand-600";

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
      <div className="flex gap-1">
        {[1,2,3,4,5,6,7,8,9,10].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            className={`w-8 h-8 rounded-md text-xs font-medium transition-colors ${
              value === n
                ? `${colorClass} text-white`
                : "bg-gray-100 text-gray-500 hover:bg-gray-200"
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-1">
        {value === 0 ? "Não informado" : `${value}/10`}
      </p>
    </div>
  );
}

export default function MetricsPage() {
  const router = useRouter();
  const { role } = useAuthStore();
  const [today, setToday] = useState<DailyMetrics | null>(null);
  const [history, setHistory] = useState<DailyMetrics[]>([]);
  const [trends, setTrends] = useState<Trends | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Form state
  const [weightKg, setWeightKg]       = useState("");
  const [sleepHours, setSleepHours]   = useState("");
  const [sleepQuality, setSleepQuality]     = useState(0);
  const [hrvMs, setHrvMs]             = useState("");
  const [restingHr, setRestingHr]     = useState("");
  const [fatigueScore, setFatigueScore]     = useState(0);
  const [soreness, setSoreness]       = useState(0);
  const [stressScore, setStressScore] = useState(0);
  const [motivation, setMotivation]   = useState(0);
  const [notes, setNotes]             = useState("");

  useEffect(() => {
    if (!role) { router.replace("/auth/login"); return; }

    Promise.all([
      api.get("/api/metrics/today"),
      api.get("/api/metrics?per_page=30"),
      api.get("/api/metrics/trends"),
    ]).then(([todayResp, histResp, trendsResp]) => {
      const t = todayResp.data as DailyMetrics | null;
      setToday(t);
      if (t) {
        if (t.weight_kg)      setWeightKg(String(t.weight_kg));
        if (t.sleep_hours)    setSleepHours(String(t.sleep_hours));
        if (t.sleep_quality)  setSleepQuality(t.sleep_quality);
        if (t.hrv_ms)         setHrvMs(String(t.hrv_ms));
        if (t.resting_hr)     setRestingHr(String(t.resting_hr));
        if (t.fatigue_score)  setFatigueScore(t.fatigue_score);
        if (t.muscle_soreness)setSoreness(t.muscle_soreness);
        if (t.stress_score)   setStressScore(t.stress_score);
        if (t.motivation_score)setMotivation(t.motivation_score);
        if (t.notes)          setNotes(t.notes);
      }
      setHistory((histResp.data.items as DailyMetrics[]).reverse());
      setTrends(trendsResp.data as Trends);
    }).finally(() => setLoading(false));
  }, [role, router]);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const payload: Record<string, unknown> = {};
      if (weightKg)    payload.weight_kg       = parseFloat(weightKg);
      if (sleepHours)  payload.sleep_hours      = parseFloat(sleepHours);
      if (sleepQuality)payload.sleep_quality    = sleepQuality;
      if (hrvMs)       payload.hrv_ms           = parseInt(hrvMs);
      if (restingHr)   payload.resting_hr       = parseInt(restingHr);
      if (fatigueScore)payload.fatigue_score    = fatigueScore;
      if (soreness)    payload.muscle_soreness  = soreness;
      if (stressScore) payload.stress_score     = stressScore;
      if (motivation)  payload.motivation_score = motivation;
      if (notes)       payload.notes            = notes;

      await api.post("/api/metrics", payload);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  };

  const chartData = history.map((m) => ({
    date: m.metric_date,
    hrv:  m.hrv_ms,
    restHR: m.resting_hr,
    sleep: m.sleep_hours,
    fatigue: m.fatigue_score,
    motivation: m.motivation_score,
  }));

  const tickFmt = (v: string) => {
    try { return format(parseISO(v), "dd/MM"); } catch { return v; }
  };

  if (loading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">
      Carregando…
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-xl font-semibold text-gray-900">Métricas Diárias</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}
          </p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-6 space-y-6">

        {/* ── Daily form ── */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-medium text-gray-900">Registrar métricas de hoje</h2>
            {saved && <span className="text-sm text-green-600 font-medium">✓ Salvo!</span>}
          </div>

          <div className="grid grid-cols-2 gap-4 mb-6">
            {[
              { label: "Peso (kg)",     value: weightKg,   setter: setWeightKg,   placeholder: "70.5", type: "number", step: "0.1" },
              { label: "Horas de sono", value: sleepHours, setter: setSleepHours, placeholder: "7.5",  type: "number", step: "0.5" },
              { label: "HRV (ms)",      value: hrvMs,       setter: setHrvMs,      placeholder: "65",   type: "number" },
              { label: "FC repouso",    value: restingHr,  setter: setRestingHr,  placeholder: "55",   type: "number" },
            ].map(({ label, value, setter, placeholder, type, step }) => (
              <div key={label}>
                <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                <input
                  type={type}
                  step={step}
                  value={value}
                  onChange={(e) => setter(e.target.value)}
                  placeholder={placeholder}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            ))}
          </div>

          <div className="space-y-5 mb-6">
            <ScaleInput label="Qualidade do sono" value={sleepQuality} onChange={setSleepQuality} color="green" />
            <ScaleInput label="Fadiga geral" value={fatigueScore} onChange={setFatigueScore} color="red" />
            <ScaleInput label="Dor muscular" value={soreness} onChange={setSoreness} color="orange" />
            <ScaleInput label="Estresse" value={stressScore} onChange={setStressScore} color="orange" />
            <ScaleInput label="Motivação" value={motivation} onChange={setMotivation} color="green" />
          </div>

          <div className="mb-5">
            <label className="block text-sm font-medium text-gray-700 mb-1">Observações</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Como você está se sentindo hoje?"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm resize-none outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40 transition-colors"
          >
            {saving ? "Salvando…" : "Salvar métricas do dia"}
          </button>
        </div>

        {/* ── Trends ── */}
        {trends && (
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Fadiga média 7d",  value: trends["7d"]?.fatigue_score,    sub: "vs 30d: " + (trends["30d"]?.fatigue_score ?? "—"), color: "text-red-600" },
              { label: "Motivação média 7d",value: trends["7d"]?.motivation_score, sub: `n=${trends["7d"]?.n ?? 0} dias`, color: "text-green-600" },
              { label: "HRV médio 7d",     value: trends["7d"]?.hrv_ms ? `${trends["7d"].hrv_ms}ms` : null, sub: "Heart Rate Variability", color: "text-blue-600" },
              { label: "Sono médio 7d",    value: trends["7d"]?.sleep_hours ? `${trends["7d"].sleep_hours}h` : null, sub: `qualidade: ${trends["7d"]?.sleep_quality ?? "—"}/10`, color: "text-purple-600" },
            ].map(({ label, value, sub, color }) => (
              <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <p className={`text-2xl font-bold ${color}`}>{value ?? "—"}</p>
                <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
              </div>
            ))}
          </div>
        )}

        {/* ── HRV & Resting HR chart ── */}
        {chartData.length > 2 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-medium text-gray-900 mb-4">HRV e FC repouso (30 dias)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tickFormatter={tickFmt} tick={{ fontSize: 10, fill: "#9ca3af" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} tickLine={false} axisLine={false} width={30} />
                <Tooltip formatter={(v, name) => [v, name === "hrv" ? "HRV (ms)" : "FC repouso"]} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="hrv" name="HRV" stroke="#3b82f6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="restHR" name="FC repouso" stroke="#f97316" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* ── Sleep & wellbeing chart ── */}
        {chartData.length > 2 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-medium text-gray-900 mb-4">Bem-estar subjetivo (30 dias)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tickFormatter={tickFmt} tick={{ fontSize: 10, fill: "#9ca3af" }} tickLine={false} axisLine={false} />
                <YAxis domain={[1, 10]} tick={{ fontSize: 10, fill: "#9ca3af" }} tickLine={false} axisLine={false} width={20} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="fatigue"    name="Fadiga"    stroke="#ef4444" strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="motivation" name="Motivação" stroke="#22c55e" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

      </div>
    </div>
  );
}
