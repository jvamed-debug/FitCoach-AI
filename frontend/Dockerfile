# Dockerfile do frontend Next.js. Construído com o CONTEXTO NA RAIZ do repo
# (Easypanel), então os COPY usam caminhos `frontend/...`. No serviço Easypanel,
# defina "Arquivo" = frontend/Dockerfile.
# Build local:  docker build -f frontend/Dockerfile -t fitcoach-frontend .

# ── Dependências ──────────────────────────────────────────────────────────────
FROM node:20-slim AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# ── Build ─────────────────────────────────────────────────────────────────────
FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

# NEXT_PUBLIC_* são embutidas no bundle em tempo de BUILD (não lidas em runtime).
# O Easypanel passa as env vars do serviço como --build-arg, então elas chegam
# aqui; promovemos a ENV para o `next build` enxergá-las.
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN useradd --create-home --uid 10001 nextjs

# O output "standalone" traz server.js e o mínimo de node_modules; os assets
# estáticos e a pasta public precisam ser copiados à parte.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
