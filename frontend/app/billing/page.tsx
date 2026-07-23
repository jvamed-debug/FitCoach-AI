"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import type { CurrentPlan, BillingPlan } from "@/lib/types";

// ── Plan display config ───────────────────────────────────────────────────────

const PLAN_COLOR: Record<string, { ring: string; badge: string; btn: string }> = {
  trial:   { ring: "ring-gray-200",  badge: "bg-gray-100 text-gray-600",   btn: "bg-gray-600 hover:bg-gray-700" },
  starter: { ring: "ring-sky-400",   badge: "bg-sky-100 text-sky-700",     btn: "bg-sky-600 hover:bg-sky-700" },
  pro:     { ring: "ring-violet-400",badge: "bg-violet-100 text-violet-700",btn: "bg-violet-600 hover:bg-violet-700" },
  elite:   { ring: "ring-amber-400", badge: "bg-amber-100 text-amber-700", btn: "bg-amber-600 hover:bg-amber-700" },
};

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  active:     { text: "Ativo",       cls: "bg-green-100 text-green-700" },
  trialing:   { text: "Trial",       cls: "bg-blue-100 text-blue-700" },
  past_due:   { text: "Pagamento atrasado", cls: "bg-red-100 text-red-700" },
  canceled:   { text: "Cancelado",   cls: "bg-gray-100 text-gray-500" },
  incomplete: { text: "Incompleto",  cls: "bg-yellow-100 text-yellow-700" },
};

// ── Main component ────────────────────────────────────────────────────────────

// useSearchParams() força bailout para renderização no cliente e, no App Router,
// precisa estar sob um limite de Suspense — sem isso o `next build` falha ao
// pré-renderizar /billing (é a página de retorno do checkout do Stripe, que lê
// ?success=1 / ?canceled=1).
export default function BillingPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-gray-400">Carregando…</div>}>
      <BillingPageContent />
    </Suspense>
  );
}

function BillingPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { role } = useAuthStore();

  const [plan, setPlan] = useState<CurrentPlan | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);

  const success = searchParams.get("success") === "1";
  const canceled = searchParams.get("canceled") === "1";

  useEffect(() => {
    if (role !== "admin") router.replace("/auth/login");
  }, [role, router]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [planRes, plansRes] = await Promise.all([
        api.get<CurrentPlan>("/api/billing/plan"),
        api.get<BillingPlan[]>("/api/billing/plans"),
      ]);
      setPlan(planRes.data);
      setPlans(plansRes.data);
    } catch {
      // keep empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCheckout = async (planKey: string) => {
    setCheckoutLoading(planKey);
    try {
      const res = await api.post<{ checkout_url: string }>(`/api/billing/checkout/${planKey}`);
      window.location.href = res.data.checkout_url;
    } catch {
      setCheckoutLoading(null);
    }
  };

  const handlePortal = async () => {
    setPortalLoading(true);
    try {
      const res = await api.post<{ portal_url: string }>("/api/billing/portal");
      window.location.href = res.data.portal_url;
    } catch {
      setPortalLoading(false);
    }
  };

  const isCurrentPlan = (key: string) => plan?.plan === key;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Assinatura & Billing</h1>
            <p className="text-sm text-gray-500 mt-0.5">Gerencie seu plano e pagamentos</p>
          </div>
          <Link href="/admin/dashboard" className="text-sm text-sky-600 hover:text-sky-800">
            ← Painel
          </Link>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">

        {/* Success / cancel banners */}
        {success && (
          <div className="bg-green-50 border border-green-200 text-green-800 rounded-xl px-5 py-4 flex items-center gap-3">
            <span className="text-xl">✅</span>
            <div>
              <p className="font-semibold">Assinatura ativada com sucesso!</p>
              <p className="text-sm mt-0.5">Seu plano foi atualizado. Você já pode adicionar mais atletas.</p>
            </div>
          </div>
        )}
        {canceled && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-xl px-5 py-4">
            <p className="font-semibold">Pagamento cancelado.</p>
            <p className="text-sm mt-0.5">Nenhuma cobrança foi realizada. Seu plano não foi alterado.</p>
          </div>
        )}

        {/* Current plan card */}
        {loading ? (
          <div className="h-36 rounded-xl bg-gray-100 animate-pulse" />
        ) : plan && (
          <div className={`bg-white rounded-xl ring-2 ${PLAN_COLOR[plan.plan]?.ring ?? "ring-gray-200"} p-6`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${PLAN_COLOR[plan.plan]?.badge}`}>
                    {plan.label}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_LABEL[plan.status]?.cls ?? "bg-gray-100 text-gray-500"}`}>
                    {STATUS_LABEL[plan.status]?.text ?? plan.status}
                  </span>
                </div>
                <h2 className="text-2xl font-bold text-gray-900">
                  {plan.price_brl === 0 ? "Gratuito" : `R$${plan.price_brl}/mês`}
                </h2>
                <p className="text-sm text-gray-500 mt-1">{plan.description}</p>
              </div>

              {/* Athlete usage */}
              <div className="text-right flex-shrink-0">
                <p className="text-3xl font-bold text-gray-900">
                  {plan.athlete_count}
                  <span className="text-lg text-gray-400 font-normal">
                    /{plan.athlete_limit >= 999_999 ? "∞" : plan.athlete_limit}
                  </span>
                </p>
                <p className="text-xs text-gray-400 mt-0.5">atletas ativos</p>
                {!plan.can_add_athlete && (
                  <p className="text-xs text-red-500 mt-1 font-medium">Limite atingido</p>
                )}
              </div>
            </div>

            {/* Usage bar */}
            {plan.athlete_limit < 999_999 && (
              <div className="mt-4">
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-2 rounded-full transition-all ${
                      plan.athlete_count / plan.athlete_limit > 0.9 ? "bg-red-500" :
                      plan.athlete_count / plan.athlete_limit > 0.7 ? "bg-yellow-500" : "bg-sky-500"
                    }`}
                    style={{ width: `${Math.min(100, (plan.athlete_count / plan.athlete_limit) * 100)}%` }}
                  />
                </div>
              </div>
            )}

            {/* Manage / renewal */}
            <div className="mt-4 flex items-center justify-between">
              {plan.current_period_end && (
                <p className="text-xs text-gray-400">
                  Próxima cobrança: {new Date(plan.current_period_end).toLocaleDateString("pt-BR")}
                </p>
              )}
              {plan.stripe_customer_id && (
                <button
                  onClick={handlePortal}
                  disabled={portalLoading}
                  className="text-sm text-sky-600 hover:text-sky-800 font-medium disabled:opacity-50"
                >
                  {portalLoading ? "Abrindo portal…" : "Gerenciar assinatura →"}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Plan upgrade cards */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Planos disponíveis</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {plans.map((p) => {
              const isCurrent = isCurrentPlan(p.key);
              const cfg = PLAN_COLOR[p.key] ?? PLAN_COLOR.starter;
              return (
                <div
                  key={p.key}
                  className={`bg-white rounded-xl border-2 p-6 flex flex-col ${
                    isCurrent ? "border-sky-400" : "border-gray-200"
                  }`}
                >
                  {isCurrent && (
                    <span className="self-start text-xs font-bold bg-sky-100 text-sky-700 px-2 py-0.5 rounded-full mb-3">
                      Plano atual
                    </span>
                  )}
                  <h3 className="text-lg font-bold text-gray-900">{p.label}</h3>
                  <p className="text-3xl font-extrabold text-gray-900 mt-1">
                    R${p.price_brl}
                    <span className="text-sm font-normal text-gray-400">/mês</span>
                  </p>
                  <p className="text-sm text-gray-500 mt-2">{p.description}</p>
                  <ul className="mt-4 space-y-1.5 flex-1">
                    <Feature text={`Até ${p.athlete_limit >= 999_999 ? "atletas ilimitados" : `${p.athlete_limit} atletas`}`} />
                    <Feature text="Recomendações diárias por IA" />
                    <Feature text="Integração Strava + TrainingPeaks" />
                    <Feature text="Relatórios mensais em PDF" />
                    {p.key === "pro" && <Feature text="Dashboard com alertas avançados" />}
                    {p.key === "elite" && <Feature text="Suporte prioritário" />}
                  </ul>
                  <button
                    onClick={() => !isCurrent && p.purchasable && handleCheckout(p.key)}
                    disabled={isCurrent || !p.purchasable || checkoutLoading !== null}
                    className={`mt-5 w-full py-2 rounded-lg text-sm font-semibold text-white transition-colors disabled:opacity-50 ${cfg.btn}`}
                  >
                    {checkoutLoading === p.key
                      ? "Aguarde…"
                      : isCurrent
                      ? "Plano atual"
                      : `Assinar ${p.label}`}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* FAQ */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h2 className="text-base font-semibold text-gray-900">Perguntas frequentes</h2>
          <FAQ q="Posso cancelar a qualquer momento?" a='Sim. Acesse "Gerenciar assinatura" para cancelar. Você manterá o acesso até o fim do período pago.' />
          <FAQ q="Meus atletas perdem acesso se eu cancelar?" a="Não imediatamente. Você terá acesso completo até o fim do ciclo de cobrança atual." />
          <FAQ q="Como funciona o trial?" a="Ao criar sua conta, você recebe 14 dias com até 3 atletas gratuitamente, sem cartão de crédito." />
          <FAQ q="Aceito quais formas de pagamento?" a="Cartão de crédito (Visa, Mastercard, Amex) via Stripe. Boleto bancário disponível para planos anuais." />
        </div>
      </div>
    </div>
  );
}

function Feature({ text }: { text: string }) {
  return (
    <li className="flex items-center gap-2 text-sm text-gray-700">
      <span className="text-green-500 flex-shrink-0">✓</span>
      {text}
    </li>
  );
}

function FAQ({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-800 hover:text-gray-900"
      >
        {q}
        <span className="text-gray-400 ml-3">{open ? "−" : "+"}</span>
      </button>
      {open && <p className="mt-2 text-sm text-gray-500">{a}</p>}
    </div>
  );
}
