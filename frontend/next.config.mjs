/**
 * Next.js 14 não suporta config em TypeScript (next.config.ts só passou a ser
 * carregado a partir do Next 15) — com o arquivo .ts o build falhava por
 * completo. Mantido em .mjs enquanto o projeto estiver na linha 14.x.
 *
 * @type {import("next").NextConfig}
 */
const nextConfig = {
  reactStrictMode: true,
  // Gera um servidor mínimo e autossuficiente em .next/standalone para o Docker.
  output: "standalone",
  // Permite que o service worker seja servido a partir de /sw.js na raiz
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Service-Worker-Allowed", value: "/" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
      {
        source: "/manifest.webmanifest",
        headers: [
          { key: "Content-Type", value: "application/manifest+json" },
        ],
      },
    ];
  },
};

export default nextConfig;
