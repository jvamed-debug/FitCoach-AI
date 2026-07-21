"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";

const ATHLETE_LINKS = [
  { href: "/dashboard",       icon: "🏠", label: "Início" },
  { href: "/recommendations", icon: "🤖", label: "Treino" },
  { href: "/workouts",        icon: "🚴", label: "Atividades" },
  { href: "/metrics",         icon: "📊", label: "Métricas" },
  { href: "/settings",        icon: "⚙️", label: "Config" },
];

const ADMIN_LINKS = [
  { href: "/admin/dashboard",  icon: "🏠", label: "Painel" },
  { href: "/admin/athletes",   icon: "👥", label: "Atletas" },
  { href: "/admin/dashboard?tab=alerts", icon: "🔔", label: "Alertas" },
  { href: "/billing",          icon: "💳", label: "Plano" },
  { href: "/settings",         icon: "⚙️", label: "Config" },
];

export default function BottomNav() {
  const pathname = usePathname();
  const { role } = useAuthStore();

  // Don't render on auth/onboarding pages or for unauthenticated users
  if (!role || pathname.startsWith("/auth") || pathname.startsWith("/onboarding")) {
    return null;
  }

  const links = role === "admin" ? ADMIN_LINKS : ATHLETE_LINKS;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden bg-white border-t border-gray-200 safe-bottom">
      <div className="flex">
        {links.map(({ href, icon, label }) => {
          const isActive = pathname === href || (href !== "/" && pathname.startsWith(href.split("?")[0]));
          return (
            <Link
              key={href}
              href={href}
              className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-xs font-medium transition-colors ${
                isActive ? "text-sky-600" : "text-gray-400 hover:text-gray-600"
              }`}
            >
              <span className="text-xl leading-none">{icon}</span>
              <span className="leading-tight">{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
