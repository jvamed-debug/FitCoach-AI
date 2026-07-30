"use client";

import type { DataQualityReport } from "@/lib/types";

/**
 * Laudo do gate de qualidade de dados (§7). Torna visível ao atleta sobre QUAL
 * base a recomendação foi construída — em vez de apresentar toda sugestão com
 * a mesma aparência de confiança.
 */
const LEVEL = {
  ok: null,
  degraded: {
    label: "Base de dados parcial",
    hint: "A sugestão abaixo foi gerada com limitações — considere-a com cautela.",
    color: "hsl(var(--fatigued))",
  },
  insufficient: {
    label: "Base de dados insuficiente",
    hint: "Há pouco histórico para individualizar: a sugestão é conservadora e genérica.",
    color: "hsl(var(--critical))",
  },
} as const;

export default function DataQualityNotice({ report }: { report: DataQualityReport | null }) {
  if (!report || report.level === "ok" || !report.checks.length) return null;
  const meta = LEVEL[report.level];
  if (!meta) return null;

  return (
    <div
      className="rounded-xl border p-4"
      style={{ borderColor: meta.color, background: `color-mix(in srgb, ${meta.color} 8%, transparent)` }}
    >
      <p className="text-sm font-semibold" style={{ color: meta.color }}>
        {meta.label}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{meta.hint}</p>
      <ul className="mt-2.5 space-y-1.5">
        {report.checks.map((c) => (
          <li key={c.code} className="flex gap-2 text-xs leading-relaxed text-foreground">
            <span aria-hidden className="select-none text-muted-foreground">•</span>
            <span>{c.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
