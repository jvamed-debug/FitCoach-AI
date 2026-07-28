"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { useAuthStore } from "@/lib/store/authStore";
import type { AdminProfile, AthleteProfile } from "@/lib/types";

type Mode = "login" | "signup";

function mapAuthError(msg: string): string {
  if (/invalid login credentials/i.test(msg)) return "E-mail ou senha inválidos.";
  if (/email not confirmed/i.test(msg)) return "Confirme seu e-mail antes de entrar.";
  if (/already registered|already exists/i.test(msg)) return "Este e-mail já está cadastrado.";
  return msg;
}

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const [mode, setMode] = useState<Mode>("login");
  const [role, setRole] = useState<"admin" | "athlete">("athlete");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [serverError, setServerError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Estabelece a sessão do Supabase no navegador e roteia conforme o perfil.
  async function signInAndRoute() {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(mapAuthError(error.message));

    // O interceptor do axios anexa o token da sessão recém-criada.
    const me = await api.get("/api/auth/me");
    const profile = me.data as (AdminProfile | AthleteProfile) & { role: "admin" | "athlete" };
    setAuth(profile.role, profile);

    if (profile.role === "athlete" && !(profile as AthleteProfile).onboarding_complete) {
      router.push("/onboarding");
    } else {
      router.push("/dashboard");
    }
  }

  async function onLogin() {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error("E-mail inválido.");
    if (password.length < 6) throw new Error("Senha de no mínimo 6 caracteres.");
    await signInAndRoute();
  }

  async function onSignup() {
    if (!name.trim()) throw new Error("Informe seu nome.");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error("E-mail inválido.");
    if (password.length < 6) throw new Error("A senha deve ter no mínimo 6 caracteres.");
    if (password !== confirmPassword) throw new Error("As senhas não conferem.");

    const endpoint =
      role === "admin" ? "/api/auth/admin/register" : "/api/auth/athlete/register";
    const resp = await api.post(endpoint, {
      name: name.trim(),
      email,
      password,
    });

    if (resp.data?.email_confirmation_required) {
      setInfo("Cadastro criado! Confirme seu e-mail e depois faça login.");
      setMode("login");
      return;
    }
    // Sem confirmação → já autentica e entra.
    await signInAndRoute();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);
    setInfo(null);
    setLoading(true);
    try {
      if (mode === "login") await onLogin();
      else await onSignup();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as Error)?.message ??
        "Algo deu errado. Tente novamente.";
      setServerError(msg);
    } finally {
      setLoading(false);
    }
  }

  const isSignup = mode === "signup";

  const inputCls =
    "w-full rounded-lg border border-input bg-surface px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/30";
  const labelCls = "block text-[13px] font-medium text-foreground mb-1.5";

  return (
    <div className="min-h-screen w-full bg-background lg:grid lg:grid-cols-[1.05fr_1fr]">
      {/* ── Painel-tese (só desktop) ── */}
      <aside
        className="relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex"
        style={{ background: "linear-gradient(155deg,#0a5f67 0%,#0e1626 72%)" }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.12]"
          style={{
            backgroundImage:
              "linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px)",
            backgroundSize: "46px 46px",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-28 -top-28 h-[26rem] w-[26rem] rounded-full blur-3xl"
          style={{ background: "radial-gradient(circle,rgba(42,211,198,.32),transparent 62%)" }}
        />
        <div className="relative flex items-center gap-3 text-xl font-extrabold tracking-tight">
          <span
            className="grid h-9 w-9 place-items-center rounded-[10px] font-mono text-sm"
            style={{ background: "conic-gradient(from 210deg,#2AD3C6,#5B9BFF,#3ED07E,#2AD3C6)" }}
          >
            FC
          </span>
          FitCoach<span style={{ color: "#2AD3C6" }}>.AI</span>
        </div>

        <div className="relative max-w-sm">
          <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-white/45">
            Coaching esportivo com IA
          </p>
          <h1 className="text-balance text-4xl font-extrabold leading-[1.08] tracking-tight">
            Treine pelos números que <span style={{ color: "#3ED07E" }}>importam</span>.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-white/60">
            Carga de treino (CTL / ATL / TSB) pelo modelo Banister, recomendações diárias da IA e
            integração com o Strava — uma decisão de treino por vez.
          </p>
          <div className="mt-8 flex gap-6 font-mono text-xs text-white/55">
            <span><i className="mr-1.5 inline-block h-0.5 w-2.5 align-middle" style={{ background: "#5B9BFF" }} />Fitness</span>
            <span><i className="mr-1.5 inline-block h-0.5 w-2.5 align-middle" style={{ background: "#E7A94A" }} />Fadiga</span>
            <span><i className="mr-1.5 inline-block h-0.5 w-2.5 align-middle" style={{ background: "#3ED07E" }} />Forma</span>
          </div>
        </div>

        <p className="relative font-mono text-[11px] leading-relaxed text-white/35">
          Descreve carga de treino — não avalia saúde nem prediz lesão.
        </p>
      </aside>

      {/* ── Formulário ── */}
      <main className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 text-lg font-extrabold tracking-tight lg:hidden">
            <span
              className="grid h-8 w-8 place-items-center rounded-[9px] font-mono text-xs text-white"
              style={{ background: "conic-gradient(from 210deg,#12a3ad,#2563c9,#15925a,#12a3ad)" }}
            >
              FC
            </span>
            FitCoach<span className="text-accent">.AI</span>
          </div>

          <div className="mb-1 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            {isSignup ? "Criar conta" : "Bem-vindo de volta"}
          </div>
          <h2 className="mb-6 text-2xl font-extrabold tracking-tight text-foreground">
            {isSignup ? (role === "admin" ? "Conta de treinador" : "Conta de aluno") : "Entrar"}
          </h2>

          <div className="mb-1 grid grid-cols-2 gap-1 rounded-xl border border-border bg-surface-2 p-1">
            {(["athlete", "admin"] as const).map((r) => (
              <button
                type="button"
                key={r}
                onClick={() => setRole(r)}
                className={`rounded-lg py-2 text-sm font-semibold transition-colors ${
                  role === r
                    ? "bg-surface text-accent shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {r === "athlete" ? "Aluno" : "Treinador"}
              </button>
            ))}
          </div>
          {isSignup && role === "athlete" && (
            <p className="mb-4 mt-2 text-xs leading-relaxed text-muted-foreground">
              Cadastro autônomo: você usa a IA para montar seus próprios treinos, sem treinador.
            </p>
          )}

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            {isSignup && (
              <div>
                <label className={labelCls}>Nome</label>
                <input type="text" autoComplete="name" value={name}
                  onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="Seu nome" />
              </div>
            )}
            <div>
              <label className={labelCls}>E-mail</label>
              <input type="email" autoComplete="email" value={email}
                onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="seu@email.com" />
            </div>
            <div>
              <label className={labelCls}>Senha</label>
              <input type="password" autoComplete={isSignup ? "new-password" : "current-password"}
                value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls}
                placeholder="••••••••" />
              {isSignup && <p className="mt-1.5 text-xs text-muted-foreground">Mínimo 6 caracteres.</p>}
            </div>
            {isSignup && (
              <div>
                <label className={labelCls}>Confirmar senha</label>
                <input type="password" autoComplete="new-password" value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)} className={inputCls} placeholder="••••••••" />
                {confirmPassword.length > 0 && confirmPassword !== password && (
                  <p className="mt-1.5 text-xs text-critical">As senhas não conferem.</p>
                )}
              </div>
            )}

            {serverError && (
              <div className="rounded-lg border border-critical/30 bg-critical/10 px-4 py-3 text-sm text-critical">
                {serverError}
              </div>
            )}
            {info && (
              <div className="rounded-lg border border-fresh/30 bg-fresh/10 px-4 py-3 text-sm text-fresh">
                {info}
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full rounded-xl bg-accent py-3 text-sm font-semibold text-accent-foreground transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50">
              {loading ? "Aguarde…" : isSignup ? "Criar conta" : "Entrar"}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            <button type="button"
              onClick={() => { setMode(isSignup ? "login" : "signup"); setServerError(null); setInfo(null); }}
              className="font-semibold text-accent hover:underline">
              {isSignup ? "Já tem conta? Entrar" : "Não tem conta? Criar conta"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
