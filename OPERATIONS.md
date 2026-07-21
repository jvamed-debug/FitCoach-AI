# Operações — FitCoach AI

Runbook de produção: deploy, diagnóstico, backup, rotação de segredos e rollback.
Arquitetura e variáveis completas no [README.md](README.md); segurança em [SECURITY.md](SECURITY.md).

## Topologia

```
Navegador/PWA → Vercel (Next.js) → Railway (FastAPI + APScheduler) → Supabase (Postgres + Auth)
                                                 ├── Anthropic / OpenAI
                                                 ├── Strava / TrainingPeaks
                                                 ├── Stripe · Resend
                                                 └── Sentry (erros)
```

## Deploy

- **Backend (Railway):** deploy automático no push para `main` (ver `.github/workflows/deploy.yml`
  e `railway.toml`). Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Healthcheck: `/health`.
- **Frontend (Vercel):** deploy automático no push para `main`. Config em `frontend/vercel.json`.
- **Banco:** migrations aplicadas manualmente no SQL Editor do Supabase, em ordem
  (`001_initial_schema.sql`, depois `002_...`). Nunca pular versões.

## Diagnóstico rápido

| Sintoma | Verificar |
|---|---|
| API fora do ar | `GET /health` no Railway; logs do serviço; `DATABASE_URL` válido |
| 401/403 em massa | `SUPABASE_JWT_SECRET` correto; relógio/expiração do JWT; RLS |
| IA não responde | `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`; cota do provedor; fallback ativo |
| Sync Strava falhando | token expirado (refresh automático); `consecutive_failures` na conexão |
| Webhook Stripe ignorado | `STRIPE_WEBHOOK_SECRET`; assinatura HMAC; `webhook_events` (idempotência) |
| Job diário não rodou | APScheduler no processo FastAPI (uma réplica); logs de `scheduler.py` |
| Erros silenciosos | painel do Sentry (`SENTRY_DSN`) |

## Jobs agendados (APScheduler)

Rodam **dentro** do processo FastAPI — exigem **uma única réplica** ativa.

- Atualização diária: 09:00 UTC (06:00 BRT) — sync + recálculo de carga + recomendação.
- Relatório semanal: sexta 23:00 UTC.
- Lembrete de métricas: seg–sex 10:00 UTC.

> Para escalar horizontalmente, migrar o scheduler para Celery + Redis ou um worker
> dedicado, evitando execução duplicada em múltiplas réplicas.

## Backup

- **Banco:** habilitar backups automáticos do Supabase (Pro) ou `pg_dump` periódico.
  Guardar cópias fora do provedor. Testar restauração ao menos uma vez.
- **Chaves de criptografia:** `DB_ENCRYPTION_KEY` protege tokens OAuth e anamnese.
  **Se perdida, esses dados tornam-se irrecuperáveis** — guardar em cofre de segredos.

## Rotação de segredos

1. Gerar novo valor no provedor (Anthropic, Stripe, Strava, Supabase, etc.).
2. Atualizar a variável no painel do Railway/Vercel.
3. Redeploy do serviço afetado.
4. Revogar o valor antigo no provedor.

> `DB_ENCRYPTION_KEY` **não** pode ser simplesmente trocada: exige re-criptografar os
> dados existentes com a nova chave antes de aposentar a antiga.

## Rollback

- **App:** no Railway/Vercel, promover o deploy anterior (ambos mantêm histórico), ou
  `git revert <commit> && git push` para reverter via pipeline.
- **Banco:** migrations são forward-only. Reverter schema exige migration de compensação
  escrita à mão — planejar antes de aplicar mudanças destrutivas em produção.

## Incidente de segredo exposto

1. **Rotacionar imediatamente** a chave/token exposto no provedor.
2. Remover do código e commitar a correção.
3. Auditar logs de acesso do provedor por uso indevido.
4. Remover do histórico do Git não basta — considerar a chave comprometida para sempre.
