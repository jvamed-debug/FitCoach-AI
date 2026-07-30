"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import type { TrainingAnalysis, MetricProvenance } from "@/lib/types";

// §13: o status é apurado a partir da qualidade dos dados, não da confiança do
// modelo. A cor comunica quanto peso a análise suporta.
const STATUS = {
  complete: { label: "Análise completa", color: "hsl(var(--tsb))",
              hint: "A base de dados sustenta as inferências apresentadas." },
  limited:  { label: "Análise limitada", color: "hsl(var(--fatigued))",
              hint: "A base tem lacunas — as inferências abaixo são parciais." },
  blocked:  { label: "Análise bloqueada", color: "hsl(var(--critical))",
              hint: "A base não sustenta inferências; apenas medidas são apresentadas." },
} as const;

const GRADE_LABEL = { high: "alta", moderate: "moderada", low: "baixa" } as const;

// §5: a classificação epistêmica de cada métrica é a informação central —
// distinguir o que foi medido do que foi estimado ou meramente declarado.
const CLASS_COLOR: Record<string, string> = {
  "medida":       "hsl(var(--tsb))",
  "importado":    "hsl(var(--ctl))",
  "estimativa":   "hsl(var(--fatigued))",
  "convenção":    "hsl(var(--muted-foreground))",
  "dado ausente": "hsl(var(--critical))",
};

export default function AnalysisPage() {
  const router = useRouter();
  const { role, profile } = useAuthStore();

  const [analysis, setAnalysis] = useState<TrainingAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!role || !profile) router.replace("/auth/login");
  }, [role, profile, router]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/api/ai/analysis");
      setAnalysis(res.data);
    } catch {
      setError("Não foi possível gerar a análise.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (profile) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile]);

  if (!profile) return null;

  const status = analysis ? STATUS[analysis.status] : null;

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-4xl space-y-5 px-6 py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[26px] font-extrabold tracking-tight text-foreground">
              Análise técnica
            </h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Leitura auditável do estado de treino — para validação de um treinador.
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="rounded-lg border border-border px-3.5 py-2 text-xs font-semibold text-foreground transition hover:bg-surface-2 disabled:opacity-50"
          >
            {loading ? "Analisando…" : "↺ Atualizar"}
          </button>
        </div>

        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-28 animate-pulse rounded-2xl border border-border bg-surface" />
            ))}
          </div>
        )}

        {error && !loading && (
          <div className="rounded-xl border border-border bg-surface p-5 text-center">
            <p className="text-sm text-muted-foreground">{error}</p>
            <button onClick={load} className="mt-2 text-sm font-medium text-accent hover:underline">
              Tentar novamente
            </button>
          </div>
        )}

        {analysis && !loading && status && (
          <>
            {/* 1 — Qualidade dos dados */}
            <section
              className="rounded-2xl border p-5"
              style={{
                borderColor: status.color,
                background: `color-mix(in srgb, ${status.color} 7%, transparent)`,
              }}
            >
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="text-sm font-bold" style={{ color: status.color }}>
                  {status.label}
                </h2>
                <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  qualidade {GRADE_LABEL[analysis.data_quality.grade]}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{status.hint}</p>

              {analysis.data_quality.issues.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                  {analysis.data_quality.issues.map((it, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-foreground">
                      <span aria-hidden className="select-none text-muted-foreground">•</span>
                      <span>{it}</span>
                    </li>
                  ))}
                </ul>
              )}
              {analysis.data_quality.missing_data.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {analysis.data_quality.missing_data.map((it, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
                      <span aria-hidden className="select-none">◦</span>
                      <span>{it}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Sinais que merecem atenção humana (§13 safety_flags) */}
            {analysis.safety_flags.length > 0 && (
              <Section title="Padrões que merecem atenção">
                <ul className="space-y-2">
                  {analysis.safety_flags.map((f, i) => (
                    <li
                      key={i}
                      className="rounded-lg border-l-2 py-1 pl-3 text-sm leading-relaxed text-foreground"
                      style={{ borderColor: "hsl(var(--critical))" }}
                    >
                      {f}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* 2 — Medidas observadas */}
            <Section
              title="Medidas observadas"
              caption="Valores da própria série do atleta."
            >
              <Bullets items={analysis.observed_measures} empty="Nenhuma medida disponível." />
            </Section>

            {/* 3 — Inferências permitidas */}
            <Section
              title="Inferências permitidas"
              caption="Padrões que a série sustenta — não são fatos nem causas."
            >
              <Bullets
                items={analysis.permitted_inferences}
                empty="A base de dados não sustenta inferências neste momento."
              />
            </Section>

            {/* 4 — Opções para validação do treinador */}
            <Section
              title="Opções para validação do treinador"
              caption="Caminhos possíveis — a decisão é humana."
            >
              {analysis.coach_options.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nenhuma opção pôde ser derivada da base atual.
                </p>
              ) : (
                <div className="space-y-3">
                  {analysis.coach_options.map((o, i) => (
                    <div key={i} className="rounded-xl border border-border bg-surface-2 p-4">
                      <p className="text-sm font-semibold text-foreground">{o.option}</p>
                      {o.rationale && (
                        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                          <span className="font-semibold text-foreground">Por quê: </span>
                          {o.rationale}
                        </p>
                      )}
                      {o.tradeoff && (
                        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                          <span className="font-semibold text-foreground">Custo: </span>
                          {o.tradeoff}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Section>

            {/* Proveniência das métricas (§13) */}
            <Section
              title="Origem das métricas"
              caption="De onde vem cada número e o que ele é."
            >
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] border-collapse text-left">
                  <thead>
                    <tr className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                      <th className="pb-2 pr-3 font-normal">Métrica</th>
                      <th className="pb-2 pr-3 font-normal">Classificação</th>
                      <th className="pb-2 pr-3 font-normal">Origem</th>
                      <th className="pb-2 font-normal">Detalhe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.metric_provenance.map((p: MetricProvenance, i) => (
                      <tr key={i} className="border-t border-border align-top">
                        <td className="py-2 pr-3 text-xs font-semibold text-foreground">{p.metric}</td>
                        <td className="py-2 pr-3">
                          <span
                            className="inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold"
                            style={{
                              color: CLASS_COLOR[p.classification] ?? "hsl(var(--muted-foreground))",
                              background: `color-mix(in srgb, ${
                                CLASS_COLOR[p.classification] ?? "hsl(var(--muted-foreground))"
                              } 14%, transparent)`,
                            }}
                          >
                            {p.classification}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-xs text-muted-foreground">{p.source}</td>
                        <td className="py-2 text-xs text-muted-foreground">{p.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>

            {/* 5 — Limitações e dados ausentes */}
            <Section title="Limitações e dados ausentes">
              <Bullets items={analysis.limitations} empty="—" muted />
            </Section>

            <p className="px-2 pt-1 text-center text-[11px] leading-relaxed text-muted-foreground/70">
              Esta análise descreve carga registrada e exige validação de um treinador humano.
              Não avalia saúde, não diagnostica e não prediz lesão.
              {analysis.ai_provider && ` · via ${analysis.ai_provider}`}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Section({
  title, caption, children,
}: { title: string; caption?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      <h2 className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
        {title}
      </h2>
      {caption && <p className="mt-0.5 text-xs text-muted-foreground/70">{caption}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Bullets({
  items, empty, muted,
}: { items: string[]; empty: string; muted?: boolean }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((it, i) => (
        <li
          key={i}
          className={`flex gap-2.5 text-sm leading-relaxed ${
            muted ? "text-muted-foreground" : "text-foreground"
          }`}
        >
          <span aria-hidden className="select-none text-muted-foreground">•</span>
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}
