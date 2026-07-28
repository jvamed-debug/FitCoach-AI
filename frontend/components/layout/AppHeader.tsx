"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { supabase } from "@/lib/supabase";
import { useAuthStore } from "@/lib/store/authStore";

const ATHLETE_LINKS: [string, string][] = [
  ["/dashboard", "Painel"],
  ["/workouts", "Treinos"],
  ["/strength/new", "Musculação"],
  ["/recommendations", "Recomendações"],
  ["/metrics", "Métricas"],
];

const ADMIN_LINKS: [string, string][] = [
  ["/admin/dashboard", "Painel"],
  ["/admin/athletes", "Atletas"],
  ["/billing", "Plano"],
];

export default function AppHeader() {
  const pathname = usePathname() || "";
  const router = useRouter();
  const { role, profile, clearAuth } = useAuthStore();
  const [menuOpen, setMenuOpen] = useState(false);

  // Some nas rotas públicas e quando não há sessão.
  if (pathname.startsWith("/auth") || pathname.startsWith("/onboarding")) return null;
  if (!role) return null;

  const links = role === "admin" ? ADMIN_LINKS : ATHLETE_LINKS;
  const name = (profile as { name?: string })?.name ?? "";
  const initials =
    name.trim().split(/\s+/).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("") || "•";
  const isActive = (href: string) =>
    href === "/dashboard" || href === "/admin/dashboard"
      ? pathname === href
      : pathname.startsWith(href);

  async function logout() {
    try {
      await supabase.auth.signOut();
    } catch {
      /* segue mesmo se o signOut remoto falhar */
    }
    clearAuth();
    router.push("/auth/login");
  }

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-2.5 sm:px-6">
        <Link href={role === "admin" ? "/admin/dashboard" : "/dashboard"}
          className="flex items-center gap-2.5 text-[17px] font-extrabold tracking-tight text-foreground">
          <span className="grid h-8 w-8 place-items-center rounded-[9px] font-mono text-xs text-white"
            style={{ background: "conic-gradient(from 210deg,#12a3ad,#2563c9,#15925a,#12a3ad)" }}>
            FC
          </span>
          <span className="hidden sm:inline">FitCoach<span className="text-accent">.AI</span></span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {links.map(([href, label]) => (
            <Link key={href} href={href}
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
                isActive(href)
                  ? "bg-surface-2 text-accent"
                  : "text-muted-foreground hover:text-foreground"
              }`}>
              {label}
            </Link>
          ))}
        </nav>

        <div className="relative">
          <button type="button" onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-full border border-border bg-surface py-1 pl-1 pr-2.5 transition hover:bg-surface-2">
            <span className="grid h-7 w-7 place-items-center rounded-full text-xs font-bold text-white"
              style={{ background: "linear-gradient(135deg,#0e7c86,#2563c9)" }}>
              {initials}
            </span>
            <span className="hidden max-w-[9rem] truncate text-sm font-semibold text-foreground sm:inline">
              {name.split(" ")[0] || "Conta"}
            </span>
            <span className="text-muted-foreground">▾</span>
          </button>

          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-xl border border-border bg-surface shadow-lg">
                <div className="border-b border-border px-4 py-3">
                  <div className="truncate text-sm font-semibold text-foreground">{name || "Conta"}</div>
                  <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                    {role === "admin" ? "Treinador" : "Aluno"}
                  </div>
                </div>
                <Link href="/settings" onClick={() => setMenuOpen(false)}
                  className="block px-4 py-2.5 text-sm text-foreground hover:bg-surface-2">
                  Configurações
                </Link>
                <button type="button" onClick={logout}
                  className="block w-full px-4 py-2.5 text-left text-sm font-semibold text-critical hover:bg-critical/10">
                  Sair
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
