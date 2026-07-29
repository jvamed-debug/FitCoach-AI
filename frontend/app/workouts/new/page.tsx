"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";

const SPORTS: [string, string][] = [
  ["cycling", "🚴 Ciclismo"],
  ["running", "🏃 Corrida"],
  ["swimming", "🏊 Natação"],
  ["strength", "🏋️ Musculação"],
  ["other", "⚡ Outro"],
];

function nowLocalInput() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export default function NewWorkoutPage() {
  const router = useRouter();
  const { role } = useAuthStore();

  const [sport, setSport] = useState("cycling");
  const [title, setTitle] = useState("");
  const [when, setWhen] = useState(nowLocalInput());
  const [durationMin, setDurationMin] = useState("");
  const [distanceKm, setDistanceKm] = useState("");
  const [avgHr, setAvgHr] = useState("");
  const [avgPower, setAvgPower] = useState("");
  const [tss, setTss] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!role) router.replace("/auth/login");
  }, [role, router]);

  const num = (v: string) => (v.trim() === "" ? undefined : Number(v));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!when) { setError("Informe a data e hora."); return; }
    setSaving(true);
    try {
      await api.post("/api/workouts", {
        sport_type: sport,
        title: title.trim() || undefined,
        start_time: new Date(when).toISOString(),
        duration_seconds: durationMin.trim() ? Math.round(Number(durationMin) * 60) : undefined,
        distance_meters: distanceKm.trim() ? Math.round(Number(distanceKm) * 1000) : undefined,
        avg_heart_rate: num(avgHr),
        avg_power_watts: num(avgPower),
        tss: num(tss),
      });
      router.push("/workouts");
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Não foi possível salvar o treino."
      );
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/30";
  const labelCls = "block text-[13px] font-medium text-foreground mb-1.5";

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
        <div className="mb-1 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Treinos</div>
        <h1 className="mb-6 text-2xl font-extrabold tracking-tight text-foreground">Registrar treino manual</h1>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl border border-border bg-surface p-5 sm:p-6">
          <div>
            <label className={labelCls}>Esporte</label>
            <select value={sport} onChange={(e) => setSport(e.target.value)} className={inputCls}>
              {SPORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>

          <div>
            <label className={labelCls}>Título <span className="text-muted-foreground">(opcional)</span></label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputCls} placeholder="Ex.: Base longa na serra" />
          </div>

          <div>
            <label className={labelCls}>Data e hora</label>
            <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} className={`${inputCls} tnum`} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>Duração <span className="text-muted-foreground">(min)</span></label>
              <input inputMode="numeric" value={durationMin} onChange={(e) => setDurationMin(e.target.value)} className={`${inputCls} tnum`} placeholder="60" />
            </div>
            <div>
              <label className={labelCls}>Distância <span className="text-muted-foreground">(km)</span></label>
              <input inputMode="decimal" value={distanceKm} onChange={(e) => setDistanceKm(e.target.value)} className={`${inputCls} tnum`} placeholder="30" />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className={labelCls}>FC média</label>
              <input inputMode="numeric" value={avgHr} onChange={(e) => setAvgHr(e.target.value)} className={`${inputCls} tnum`} placeholder="145" />
            </div>
            <div>
              <label className={labelCls}>Potência</label>
              <input inputMode="numeric" value={avgPower} onChange={(e) => setAvgPower(e.target.value)} className={`${inputCls} tnum`} placeholder="W" />
            </div>
            <div>
              <label className={labelCls}>TSS</label>
              <input inputMode="numeric" value={tss} onChange={(e) => setTss(e.target.value)} className={`${inputCls} tnum`} placeholder="auto" />
            </div>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Deixe o TSS em branco para o app estimar a partir da FC ou potência e do seu perfil.
          </p>

          {error && (
            <div className="rounded-lg border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">{error}</div>
          )}

          <div className="flex items-center gap-3 pt-1">
            <button type="submit" disabled={saving}
              className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-accent-foreground transition hover:brightness-110 disabled:opacity-50">
              {saving ? "Salvando…" : "Salvar treino"}
            </button>
            <Link href="/workouts" className="text-sm font-semibold text-muted-foreground hover:text-foreground">Cancelar</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
