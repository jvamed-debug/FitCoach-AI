# FitCoach AI

Plataforma de coaching esportivo com agente IA para educadores físicos e treinadores. Integra Strava, TrainingPeaks e Apple Health, calcula carga de treino (CTL/ATL/TSB via modelo Banister PMC) e usa Claude (Anthropic) + GPT-4o para gerar recomendações diárias personalizadas com plano nutricional.

**Stack:** FastAPI + SQLAlchemy async + Supabase PostgreSQL + Next.js 14 + shadcn/ui

> ⚠️ Software proprietário — © Junior Aredes, todos os direitos reservados. Ver [LICENSE](LICENSE).

## Documentação do projeto

| Documento | Conteúdo |
|-----------|----------|
| [SECURITY.md](SECURITY.md) | Modelo de ameaças, fronteiras de confiança, requisitos de produção |
| [OPERATIONS.md](OPERATIONS.md) | Runbook: deploy, diagnóstico, backup, rotação de segredos, rollback |
| [AGENTS.md](AGENTS.md) | Convenções de código e regras de negócio para quem contribui |

---

## Início Rápido (desenvolvimento local)

### 1. Banco de dados

1. Criar projeto no [Supabase](https://supabase.com)
2. Executar as migrations no SQL Editor do Supabase:
   ```sql
   -- Execute em ordem:
   -- supabase/migrations/001_initial_schema.sql
   -- supabase/migrations/002_sprints_08_11.sql
   ```

### 2. Backend

```bash
cd backend
cp .env.example .env
# Preencher variáveis no .env (ver seção Variáveis de Ambiente abaixo)
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

### 3. Frontend

```bash
cd frontend
cp .env.example .env.local
# Preencher variáveis no .env.local
npm install
npm run dev
# → http://localhost:3000
```

### 4. Testes

```bash
cd backend
pytest tests/ -v
# Cobertura: pytest tests/ --cov=app --cov-report=term-missing
```

### 5. Load test

```bash
cd backend
export LOAD_TEST_ATHLETE_TOKEN="..."
export LOAD_TEST_ADMIN_TOKEN="..."
locust -f tests/locustfile.py --host http://localhost:8000 \
       --users 20 --spawn-rate 2 --run-time 60s
# → http://localhost:8089 (Locust UI)
```

---

## Deploy em Produção

### Pré-requisitos

| Item | Onde configurar |
|------|----------------|
| Conta Supabase (Free ou Pro) | supabase.com |
| Conta Railway | railway.app |
| Conta Vercel | vercel.com |
| Chaves Stripe (+ preços criados) | dashboard.stripe.com |
| Chave Anthropic API | console.anthropic.com |
| Conta Resend (email) | resend.com |
| App Strava criado | developers.strava.com |
| Sentry project (opcional) | sentry.io |

### Railway (Backend)

```bash
# Instalar Railway CLI
npm install -g @railway/cli
railway login

# Na raiz do projeto
railway init
railway up --service fitcoach-backend

# Configurar variáveis de ambiente no Railway Dashboard
# (todas do backend/.env.example, com valores de produção)
```

Configurações Railway → Service → Settings:
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`
- **Root directory:** `backend/`

### Vercel (Frontend)

```bash
# Instalar Vercel CLI
npm install -g vercel
cd frontend
vercel --prod

# Configurar env vars no Vercel Dashboard:
# NEXT_PUBLIC_SUPABASE_URL
# NEXT_PUBLIC_SUPABASE_ANON_KEY
# NEXT_PUBLIC_API_URL  → URL do backend no Railway
```

### CI/CD Automático (GitHub Actions)

Configurar secrets no repositório (Settings → Secrets):

| Secret | Valor |
|--------|-------|
| `RAILWAY_TOKEN` | Token de deploy Railway |
| `VERCEL_TOKEN` | Token Vercel |
| `VERCEL_ORG_ID` | ID da organização Vercel |
| `VERCEL_PROJECT_ID` | ID do projeto Vercel |

Após configurar, cada push para `main` dispara deploy automático.

### Webhook Stripe

No Stripe Dashboard → Developers → Webhooks:
- **Endpoint URL:** `https://seu-backend.railway.app/api/billing/webhook`
- **Eventos:** `checkout.session.completed`, `invoice.paid`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`

### Webhook Strava

```bash
# Registrar webhook (executar uma vez)
curl -X POST https://www.strava.com/api/v3/push_subscriptions \
  -F client_id=SEU_CLIENT_ID \
  -F client_secret=SEU_CLIENT_SECRET \
  -F callback_url=https://seu-backend.railway.app/api/webhooks/strava \
  -F verify_token=SEU_VERIFY_TOKEN
```

### Gerar VAPID Keys (Push Notifications)

```bash
cd backend
python -c "
from py_vapid import Vapid
v = Vapid()
v.generate_keys()
print('VAPID_PRIVATE_KEY=', v.private_key)
print('VAPID_PUBLIC_KEY=', v.public_key)
"
```

---

## Variáveis de Ambiente

```env
# === OBRIGATÓRIAS ===
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
SUPABASE_JWT_SECRET=
DATABASE_URL=postgresql+asyncpg://...

DB_ENCRYPTION_KEY=        # min 32 chars, aleatório
SECRET_KEY=               # min 32 chars, para HMAC tokens de convite

ANTHROPIC_API_KEY=
RESEND_API_KEY=
FROM_EMAIL=noreply@seudominio.com

# === STRAVA (obrigatório para importação) ===
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_WEBHOOK_VERIFY_TOKEN=

# === STRIPE (obrigatório para billing) ===
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_STARTER=
STRIPE_PRICE_PRO=
STRIPE_PRICE_ELITE=

# === OPCIONAIS ===
OPENAI_API_KEY=           # fallback da IA
TP_CLIENT_ID=             # TrainingPeaks
TP_CLIENT_SECRET=
VAPID_PRIVATE_KEY=        # Push notifications
VAPID_PUBLIC_KEY=
SENTRY_DSN=               # Monitoramento de erros

APP_ENV=production
FRONTEND_URL=https://seuapp.vercel.app
BACKEND_URL=https://seubackend.railway.app
```

---

## Arquitetura

```
Browser / PWA
      │
      ▼
 Vercel (Next.js 14)
      │  REST + JSON
      ▼
Railway (FastAPI + APScheduler)
      │
      ├── Supabase PostgreSQL (dados + Auth + RLS)
      ├── Anthropic Claude API (recomendações IA)
      ├── Strava API (importação treinos)
      ├── TrainingPeaks API (push/pull planos)
      ├── Stripe (billing e assinaturas)
      ├── Resend (emails transacionais)
      └── Sentry (monitoramento de erros)
```

## Sprints Concluídos

| Sprint | Entregável |
|--------|-----------|
| S01 | Auth multi-role (admin/atleta) + LGPD + infraestrutura |
| S02 | Gestão de atletas + anamnese criptografada + convite por e-mail |
| S03 | Engine CTL/ATL/TSB (modelo Banister PMC) + musculação |
| S04 | Integração Strava (OAuth + webhook + sync automático) |
| S05 | Agente IA Coach (Claude + GPT-4o fallback) + nutrição |
| S06 | TrainingPeaks bidirecional + Apple Health + job diário |
| S07 | Aderência pós-treino + dashboard completo |
| S08 | Painel admin + alertas automáticos + relatório semanal IA |
| S09 | PWA + push notifications + `/workouts/[id]` + `/history` + bottom nav |
| S10 | Relatórios PDF mensais (WeasyPrint) + exportação LGPD PDF |
| S11 | Assinaturas Stripe (checkout, portal, webhooks, limite por plano) |
| S12 | CI/CD GitHub Actions + deploy Railway+Vercel + Sentry + testes E2E + Locust |

## Cobertura de Testes

| Suite | Testes | Cobre |
|-------|--------|-------|
| `test_auth.py` | 15 | JWT, roles, LGPD middleware, refresh |
| `test_calculations.py` | 35 | TSS, CTL/ATL/TSB, zonas Coggan/Karvonen |
| `test_strava_service.py` | 15 | Parse, token refresh, webhook HMAC |
| `test_ai_service.py` | 25 | JSON parse, safety check, fallback chain |
| `test_billing.py` | 9 | Plan limits, subscription creation, API enforcement |
| `test_integration.py` | 10 | Fluxos E2E: auth, atletas, alertas, training load |
| **Total** | **109** | — |
