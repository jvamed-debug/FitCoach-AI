"use client";

import { useMemo } from "react";

/**
 * Editor da disponibilidade semanal.
 *
 * Produz o formato com duração — {"cycling": {"days": [...], "minutes": 90}} —
 * porque é a duração que permite ao agente caber o treino no dia. Lê também o
 * formato antigo (lista de dias), já que há perfis gravados assim.
 *
 * Uma modalidade sem nenhum dia marcado simplesmente sai do objeto: ausência
 * significa "não pratico", e é diferente de "pratico zero minutos".
 */

export type Availability = Record<string, { days: string[]; minutes: number | null }>;

const DIAS: [string, string][] = [
  ["mon", "S"], ["tue", "T"], ["wed", "Q"],
  ["thu", "Q"], ["fri", "S"], ["sat", "S"], ["sun", "D"],
];

const DIA_TITULO: Record<string, string> = {
  mon: "segunda", tue: "terça", wed: "quarta",
  thu: "quinta", fri: "sexta", sat: "sábado", sun: "domingo",
};

const MODALIDADES: [string, string][] = [
  ["cycling", "Ciclismo"],
  ["running", "Corrida"],
  ["swimming", "Natação"],
  ["strength", "Musculação"],
  ["mobility", "Mobilidade"],
];

/** Aceita o formato antigo (lista) e o novo (objeto com minutos). */
export function parseAvailability(bruto: unknown): Availability {
  const saida: Availability = {};
  if (!bruto || typeof bruto !== "object") return saida;

  for (const [modalidade, valor] of Object.entries(bruto as Record<string, unknown>)) {
    if (Array.isArray(valor)) {
      saida[modalidade] = { days: valor.filter((d): d is string => typeof d === "string"), minutes: null };
    } else if (valor && typeof valor === "object") {
      const v = valor as { days?: unknown; minutes?: unknown };
      saida[modalidade] = {
        days: Array.isArray(v.days) ? v.days.filter((d): d is string => typeof d === "string") : [],
        minutes: typeof v.minutes === "number" && v.minutes > 0 ? v.minutes : null,
      };
    }
  }
  return saida;
}

/** Remove modalidades sem dia marcado antes de enviar. */
export function serializeAvailability(av: Availability): Availability {
  const saida: Availability = {};
  for (const [modalidade, cfg] of Object.entries(av)) {
    if (cfg.days.length > 0) saida[modalidade] = cfg;
  }
  return saida;
}

interface Props {
  value: Availability;
  onChange: (v: Availability) => void;
}

export default function AvailabilityEditor({ value, onChange }: Props) {
  const totalSemanal = useMemo(
    () =>
      Object.values(value).reduce(
        (soma, cfg) => soma + (cfg.minutes ?? 0) * cfg.days.length,
        0,
      ),
    [value],
  );

  const toggleDia = (modalidade: string, dia: string) => {
    const atual = value[modalidade] ?? { days: [], minutes: null };
    const days = atual.days.includes(dia)
      ? atual.days.filter((d) => d !== dia)
      : [...atual.days, dia];
    onChange({ ...value, [modalidade]: { ...atual, days } });
  };

  const setMinutos = (modalidade: string, texto: string) => {
    const atual = value[modalidade] ?? { days: [], minutes: null };
    const n = Number(texto);
    onChange({
      ...value,
      [modalidade]: { ...atual, minutes: texto && n > 0 ? n : null },
    });
  };

  return (
    <div className="space-y-3">
      {MODALIDADES.map(([chave, rotulo]) => {
        const cfg = value[chave] ?? { days: [], minutes: null };
        const ativa = cfg.days.length > 0;
        return (
          <div
            key={chave}
            className={`rounded-lg border p-3 transition-colors ${
              ativa ? "border-accent/40 bg-surface-2" : "border-border"
            }`}
          >
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <span className="w-24 shrink-0 text-sm font-medium text-foreground">{rotulo}</span>

              <div className="flex gap-1" role="group" aria-label={`Dias de ${rotulo}`}>
                {DIAS.map(([dia, letra]) => {
                  const marcado = cfg.days.includes(dia);
                  return (
                    <button
                      key={dia}
                      type="button"
                      onClick={() => toggleDia(chave, dia)}
                      aria-pressed={marcado}
                      title={`${rotulo} — ${DIA_TITULO[dia]}`}
                      className={`h-8 w-8 rounded-md text-xs font-semibold transition ${
                        marcado
                          ? "bg-accent text-accent-foreground"
                          : "border border-border text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {letra}
                    </button>
                  );
                })}
              </div>

              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min={10}
                  max={480}
                  step={5}
                  inputMode="numeric"
                  placeholder="—"
                  value={cfg.minutes ?? ""}
                  onChange={(e) => setMinutos(chave, e.target.value)}
                  disabled={!ativa}
                  aria-label={`Duração típica de ${rotulo} em minutos`}
                  className="w-20 rounded-lg border border-border bg-background px-2 py-1.5 text-sm text-foreground disabled:opacity-40"
                />
                <span className="text-xs text-muted-foreground">min/sessão</span>
              </div>
            </div>

            {/* A ausência de duração é declarada, não escondida: o agente trata
                "não informado" como desconhecido e infere do histórico. */}
            {ativa && cfg.minutes === null && (
              <p className="mt-2 text-[11px] text-muted-foreground">
                Sem duração informada, a IA estima a partir dos seus treinos anteriores.
              </p>
            )}
          </div>
        );
      })}

      {totalSemanal > 0 && (
        <p className="text-xs text-muted-foreground">
          Volume declarado: <span className="tnum font-medium text-foreground">
            {Math.floor(totalSemanal / 60)}h{String(totalSemanal % 60).padStart(2, "0")}
          </span> por semana.
        </p>
      )}
    </div>
  );
}
