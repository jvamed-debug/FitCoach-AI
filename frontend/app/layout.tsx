import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import PWAInit from "@/components/layout/PWAInit";
import BottomNav from "@/components/layout/BottomNav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "FitCoach AI",
    template: "%s · FitCoach AI",
  },
  description: "Plataforma de coaching esportivo com IA para ciclismo, musculação e mais.",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "FitCoach AI",
  },
  formatDetection: { telephone: false },
  openGraph: {
    type: "website",
    siteName: "FitCoach AI",
    title: "FitCoach AI",
    description: "Coaching esportivo com IA",
  },
};

export const viewport: Viewport = {
  themeColor: "#0284c7",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body className={`${inter.className} pb-16 md:pb-0`}>
        <PWAInit />
        {children}
        <BottomNav />
      </body>
    </html>
  );
}
