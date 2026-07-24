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
    if (password.length < 6) throw new Error("Senha de no mínimo 6 caracteres.");

    const resp = await api.post("/api/auth/admin/register", {
      name: name.trim(),
      email,
      password,
    });

    if (resp.data?.email_confirmation_required) {
      setInfo("Cadastro criado! Confirme seu e-mail e depois faça login.");
      setMode("login");
      setRole("admin");
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

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand-700">FitCoach AI</h1>
          <p className="text-gray-500 mt-1 text-sm">Coaching esportivo com inteligência artificial</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">
            {isSignup ? "Criar conta de treinador" : "Entrar"}
          </h2>

          {/* Abas de papel só no login (atletas entram por convite) */}
          {!isSignup && (
            <div className="flex rounded-lg bg-gray-100 p-1 mb-6">
              {(["athlete", "admin"] as const).map((r) => (
                <button
                  type="button"
                  key={r}
                  onClick={() => setRole(r)}
                  className={`flex-1 text-center py-2 rounded-md text-sm font-medium transition-colors ${
                    role === r ? "bg-white text-brand-700 shadow-sm" : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {r === "athlete" ? "Atleta" : "Treinador"}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignup && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
                <input
                  type="text"
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  placeholder="Seu nome"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">E-mail</label>
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                placeholder="seu@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Senha</label>
              <input
                type="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                placeholder="••••••••"
              />
            </div>

            {serverError && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {serverError}
              </div>
            )}
            {info && (
              <div className="rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
                {info}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Aguarde…" : isSignup ? "Criar conta" : "Entrar"}
            </button>
          </form>

          <div className="mt-6 text-center text-sm">
            {isSignup ? (
              <button
                type="button"
                onClick={() => { setMode("login"); setServerError(null); setInfo(null); }}
                className="text-brand-700 hover:underline"
              >
                Já tem conta? Entrar
              </button>
            ) : (
              <button
                type="button"
                onClick={() => { setMode("signup"); setServerError(null); setInfo(null); }}
                className="text-brand-700 hover:underline"
              >
                É treinador? Criar conta
              </button>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          Ao continuar, você concorda com nossos termos de uso e política de privacidade.
        </p>
      </div>
    </div>
  );
}
