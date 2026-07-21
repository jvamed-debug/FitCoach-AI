# FitCoach AI — Status do Projeto

> Gerado em: 2026-05-04  
> Sessão: Sprint 01 → Sprint 07 concluídos  
> Progresso: **7 de 12 sprints** (~58% da implementação total)

---

## Visão Geral do Produto

Plataforma web de coaching esportivo com IA para educadores físicos/treinadores que gerenciam atletas de ciclismo, musculação, corrida, natação e triathlon. O sistema integra dados do Strava, TrainingPeaks e Apple Health, calcula carga de treino (CTL/ATL/TSB via modelo Banister PMC) e usa Claude (Anthropic) + GPT-4o (OpenAI) para gerar recomendações diárias personalizadas com plano nutricional integrado.

---

## Stack Técnica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + FastAPI + Pydantic v2 |
| ORM | SQLAlchemy 2.0 async + Alembic |
| Banco de dados | PostgreSQL via Supabase |
| Auth | Supabase Auth (JWT) + OAuth 2.0 (Strava, TrainingPeaks) |
| Frontend | Next.js 14 App Router + TypeScript + Tailwind CSS + shadcn/ui |
| Gráficos | Recharts |
| AI Router | Anthropic Claude (claude-sonnet-4-6) + OpenAI GPT-4o (fallback) |
| Email | Resend API |
| Scheduler | APScheduler (embutido no FastAPI) |
| Criptografia | Fernet (tokens OAuth) + pgp_sym_encrypt (anamnese, pgcrypto) |
| Testes | pytest + pytest-asyncio + aiosqlite (in-memory) |
| Deploy | Railway (backend) + Vercel (frontend) |

---

## O que foi construído (Sprints 01–07)

---

### Sprint 01 — Infraestrutura & Auth

**Objetivo:** projeto rodando localmente com auth funcional ✅

| Task | Entregável |
|------|-----------|
| T01.1 | `docker-compose.yml` (backend + redis), `README.md` |
| T01.2 | `app/main.py` (CORS, lifespan, routers), `app/config.py` (Pydantic Settings), `app/database.py` (SQLAlchemy async engine pool), `app/dependencies.py` (get_current_admin, get_current_athlete, require_lgpd_consent) |
| T01.3 | `supabase/migrations/001_initial_schema.sql` — 17 tabelas, RLS habilitado, políticas por role, triggers `updated_at`, índices de performance; `alembic/env.py` configurado para async |
| T01.4 | `routers/auth.py` — login admin/atleta via Supabase Auth, `/refresh`, `/logout`, `/me`, audit log em todas as ações |
| T01.6 | `routers/lgpd.py` — `POST /consent` (timestamp+IP), `DELETE /consent` (cria `LGPDDeletionRequest`), `GET /deletion-status`, `POST /export` |
| T01.7 | `tests/test_auth.py` — 15 testes: JWT válido/expirado/inválido, role separation, LGPD middleware 403 sem consent |
| T01.F | `app/auth/login` (tabs admin/atleta), `app/onboarding` (3 steps: LGPD → perfil → pronto) |

**Arquivos chave:**
- `backend/app/models/` — `admin.py`, `athlete.py`, `lgpd.py`
- `backend/app/services/scheduler.py` — APScheduler, job 06:00 BRT

---

### Sprint 02 — Gestão de Atletas

**Objetivo:** admin consegue cadastrar e gerenciar atletas ✅

| Task | Entregável |
|------|-----------|
| T02.1 | `POST /api/admin/athletes` — criação com token HMAC-SHA256 de 7 dias, email de boas-vindas via Resend em background task |
| T02.2 | `PUT/GET /api/admin/athletes/{id}/anamnese` — `pgp_sym_encrypt` no PostgreSQL, audit log em cada acesso |
| T02.3 | `PUT /api/admin/athletes/{id}` — atualiza `weekly_availability` (JSONB), `goal`, todos os campos de perfil |
| T02.4 | `GET /api/admin/athletes` — paginação, busca, TSB status em 4 níveis (good/moderate/alert/critical), badge ≥3 dias sem treino |
| T02.5 | `GET /auth/onboarding/validate?token=` + `POST /auth/athlete/set-password` — cria usuário Supabase Auth e vincula ao `athlete.user_id` |
| T02.F | `/admin/athletes` (tabela KPIs), `/admin/athletes/new` (formulário completo), `/admin/athletes/[id]` (perfil+anamnese), `/onboarding` atualizado com 4 steps |

**Arquivos chave:**
- `backend/app/routers/admin_athletes.py`
- `backend/app/utils/crypto.py` — Fernet + pgcrypto + HMAC invite tokens
- `backend/app/services/email_service.py`

---

### Sprint 03 — Engine de Carga + Musculação

**Objetivo:** CTL/ATL/TSB calculados; registro de musculação funcionando ✅

| Task | Entregável |
|------|-----------|
| T03.1 | `utils/calculations.py` — 9 funções: `calculate_tss_cycling` (TSS = NP×IF×dur/FTP/3600×100), `calculate_tss_from_hr` (TRIMP Banister), `calculate_strength_tss` (cap 150 TSS), `calculate_ctl/atl` (EMA α=1−e^(−1/τ)), `calculate_tsb`, `calculate_training_load_series` (preenche gaps, agrega mesmo dia), zonas Coggan 7-zone + Karvonen 5-zone |
| T03.1 | `tests/test_calculations.py` — 35 testes com valores de referência: 3600s@FTP=250W → TSS=100 exato, TRIMP manual, séries de carga convergindo, zonas escalando |
| T03.2 | `services/training_load.py` — `recalculate_athlete_load` (upsert ON CONFLICT, seed de CTL/ATL inicial para continuidade, TSS semanal rolling 7d), `get_current_load`, `get_load_history` |
| T03.2 | `routers/workouts.py` — `GET /load`, `GET /stats/weekly`, `POST /recalculate` (background), CRUD workouts manuais |
| T03.3 | `routers/strength.py` — CRUD completo com exercícios aninhados, TSS calculado automaticamente, validação RPE 1–10 |
| T03.F | `CTLATLTSBChart.tsx` — 3 linhas, tooltip custom, seletor 30/60/90d, ReferenceLine TSB=0 |
| T03.F | `app/strength/new` — `useFieldArray`, autocomplete 20 exercícios comuns, preview TSS estimado |
| T03.F | `app/dashboard` — 4 KPIs, gráfico CTL/ATL/TSB, stats semanais, ações rápidas |

---

### Sprint 04 — Integração Strava

**Objetivo:** Strava conectado, treinos importados e recebidos por webhook ✅

| Task | Entregável |
|------|-----------|
| T04.1 | `routers/oauth.py` — OAuth Strava e TrainingPeaks: authorize, callback (upsert tokens Fernet-encrypted), disconnect |
| T04.2 | `services/strava_service.py` — cliente completo com `@retry` Tenacity (3 tentativas, backoff exponencial), verificação de `X-RateLimit-Usage`, `parse_activity_to_workout` (potência→TSS ou TRIMP para relay Garmin com `device_watts=false`) |
| T04.3 | `routers/webhooks.py` — `GET /strava` (hub.challenge), `POST /strava` (HMAC-SHA256 + background task + upsert ON CONFLICT), `POST /apple-health/{token}` (iOS Shortcut, upsert `daily_metrics`) |
| T04.4 | `POST /api/workouts/sync/strava` — sync manual com recalc CTL/ATL/TSB; `app/workouts/page.tsx` com filtros; `app/settings/page.tsx` com conexões, URL Apple Health, botões LGPD |
| T04.5 | `services/strava_service.py` `get_valid_access_token` — auto-refresh, deactivation após 3 falhas consecutivas |
| T04.5 | `tests/test_strava_service.py` — 15 testes: parse de atividades, mapeamento sport_type, relay Garmin, token refresh válido/expirado/falha/deactivation, HMAC webhook |

---

### Sprint 05 — Agente IA Coach

**Objetivo:** agente gerando planos estruturados com nutrição integrada ✅

| Task | Entregável |
|------|-----------|
| T05.1 | `services/ai_service.py` `SYSTEM_PROMPT` — regras TSB obrigatórias por faixa (−25 = rest, −15 a −5 = base, +5 a +15 = VO2max, etc.), formato por modalidade (cycling: power_pct_ftp+cadence, strength: sets/reps/load/rpe, running: pace+hr_zone, swimming: distâncias+pausas, triathlon: multi-block) |
| T05.2 | Parse progressivo 3 tentativas (JSON direto → strip markdown → busca `{}` → rest-day fallback); `safety_check()` 6 guardas; `_downgrade_plan()` step-down de intensidade |
| T05.3 | `build_athlete_context()` — busca DB: CTL/ATL/TSB atual, 14 treinos, 7 sessões força, métricas do dia, flags `is_new_athlete`/`detraining_detected`/`metrics_missing` |
| T05.4 | `format_athlete_context()` — texto estruturado por seções com estado TSB em linguagem natural |
| T05.5 | `models/recommendation.py` (`tokens_used`, `generation_time_ms`); `routers/recommendations.py` — `GET /today`, `POST /generate`, `GET /fatigue`, `POST /{id}/feedback`, histórico paginado, push para Strava/TP |
| T05.6 | Nutrição gerada no mesmo call; `generate_default_nutrition()` fallback por peso/intensidade; salvo em `nutrition_plan` JSONB separado |
| T05.7 | `app/recommendations` — card com seções expansíveis, `NutritionCard` com macros, rationale em acordeão, polling 5s (60s timeout), `StarRating` 1–5 + notas |
| Testes | `tests/test_ai_service.py` — 25 testes: fallback chain, TSB crítico→rest override, fadiga→downgrade, JSON malformado→fallback, nutrição sempre presente |

---

### Sprint 06 — Integrações TP + Garmin + Métricas

**Objetivo:** todas as integrações bidirecionais funcionando + job diário completo ✅

| Task | Entregável |
|------|-----------|
| T06.1 | `services/tp_service.py` — cliente TrainingPeaks: OAuth, `get_completed_workouts`, `create_planned_workout`, `parse_tp_workout`, mapeamento bidirecional sport_type, conversão seções→structure TP |
| T06.2 | `services/tp_sync.py` `push_recommendation_to_trainingpeaks` — converte plano AI → formato TP com steps/targets, cria treino no calendário TP (→ auto-sync Garmin nativo) |
| T06.3 | `sync_completed_workouts_from_tp` — polling workouts executados últimos 3 dias, deduplicação por `external_id`, TSS por potência ou TRIMP |
| T06.4 | `routers/metrics.py` — `POST /api/metrics` (upsert), `GET /today`, `GET /trends` (médias 7d/30d), histórico paginado; `app/metrics/page.tsx` — ScaleInput 1–10, gráficos HRV/FC e bem-estar subjetivo (Recharts) |
| T06.5 | `services/scheduler.py` completo — pipeline por atleta: Strava sync → TP sync → recalc CTL/ATL/TSB → geração IA → push TP → alertas admin; semáforo 5 atletas simultâneos; `asyncio.gather` com `return_exceptions=True` |

---

### Sprint 07 — Adaptação Pós-treino + Dashboard

**Objetivo:** ciclo de adaptação fechado; cliente vê treino e histórico completo ✅

| Task | Entregável |
|------|-----------|
| T07.1 | `utils/adherence.py` `analyze_workout_adherence()` — compara TSS/duração/RPE planejado vs executado, calcula % desvio, gera `adjustment_hint` em inglês para o próximo prompt da IA; `GET /api/workouts/{id}/adherence` endpoint |
| T07.1 | Integração em `build_athlete_context()` — aderência do treino de ontem injetada automaticamente no contexto da IA |
| T07.2 | `DailyRecommendationCard` — 3 estados (loading/empty/rec com link de feedback) |
| T07.3 | `WeeklyTSSBar` — BarChart com badge de variação %; `RecentWorkoutsList` — 5 treinos compactos; `DailyMetricsCard` — 6 métricas com cor por severidade |
| T07.2 | `app/dashboard` completo — banner TSB crítico, 4 KPIs coloridos por estado, CTL/ATL/TSB chart, todos os 5 componentes, nav com todos os links |
| T07.4 | 4 novos endpoints admin: `GET /workouts`, `GET /load-history`, `GET /recommendations`, `GET /adherence-summary` (% seguido, avg rating, rest days) |
| T07.4 | `/admin/athletes/[id]` refatorado — 4 abas: Perfil (dados+anamnese), Plano IA (CTL/ATL/TSB + última rec), Histórico (tabela com fonte), Aderência (3 KPIs) |
| T07.5 | `StravaService.create_planned_workout()` + `POST /recommendations/{id}/push-to-strava`; `POST /recommendations/{id}/push-to-trainingpeaks` |

---

## Inventário de Arquivos

### Backend

```
backend/
├── app/
│   ├── main.py               ← FastAPI app, CORS, lifespan, 12 routers registrados
│   ├── config.py             ← Pydantic Settings (env vars)
│   ├── database.py           ← SQLAlchemy async engine, pool_size=10
│   ├── dependencies.py       ← get_current_admin, get_current_athlete, require_lgpd_consent
│   ├── models/
│   │   ├── admin.py          ← AdminUser
│   │   ├── athlete.py        ← Athlete, PlatformConnection
│   │   ├── lgpd.py           ← LGPDConsent, AuditLog, LGPDDeletionRequest
│   │   ├── workout.py        ← Workout
│   │   ├── strength.py       ← StrengthSession, StrengthExercise
│   │   ├── training_load.py  ← TrainingLoad
│   │   ├── metric.py         ← DailyMetric
│   │   └── recommendation.py ← AIRecommendation
│   ├── routers/
│   │   ├── auth.py           ← login admin/atleta, /me, refresh, logout, set-password, onboarding
│   │   ├── oauth.py          ← Strava + TrainingPeaks OAuth
│   │   ├── admin_athletes.py ← CRUD atletas + anamnese + aderência (admin)
│   │   ├── workouts.py       ← CRUD + sync Strava + aderência + load
│   │   ├── strength.py       ← CRUD sessions + exercises
│   │   ├── metrics.py        ← upsert + trends + histórico
│   │   ├── recommendations.py← today + generate + feedback + push Strava/TP
│   │   ├── lgpd.py           ← consent + revoke + export + deletion-status
│   │   └── webhooks.py       ← Strava webhook + Apple Health
│   ├── services/
│   │   ├── ai_service.py     ← AIService, AthleteContext, build_athlete_context, safety_check
│   │   ├── strava_service.py ← StravaService, get_valid_access_token
│   │   ├── tp_service.py     ← TrainingPeaksService
│   │   ├── tp_sync.py        ← push_recommendation_to_trainingpeaks, sync_completed_workouts
│   │   ├── training_load.py  ← recalculate_athlete_load, get_current_load, get_load_history
│   │   ├── email_service.py  ← send_athlete_invite, send_welcome_email, send_deletion_confirmation
│   │   └── scheduler.py      ← APScheduler job 06:00 BRT, pipeline completo por atleta
│   └── utils/
│       ├── calculations.py   ← TSS cycling/HR/strength, CTL/ATL/TSB, zonas Coggan/Karvonen
│       ├── crypto.py         ← Fernet tokens, HMAC invite, pgcrypto anamnese
│       └── adherence.py      ← analyze_workout_adherence, AdherenceReport
├── alembic/
│   ├── env.py                ← async migrations, detecta todos os modelos
│   └── versions/             ← (baseline a ser gerado com --autogenerate)
├── tests/
│   ├── conftest.py           ← SQLite in-memory, fixtures admin/athlete/consent, make_jwt
│   ├── test_auth.py          ← 15 testes
│   ├── test_calculations.py  ← 35 testes
│   ├── test_strava_service.py← 15 testes
│   └── test_ai_service.py    ← 25 testes
├── requirements.txt
├── pytest.ini
└── alembic.ini
```

### Frontend

```
frontend/
├── app/
│   ├── layout.tsx, page.tsx, globals.css
│   ├── auth/login/page.tsx            ← tabs admin/atleta
│   ├── onboarding/page.tsx            ← 4 steps: senha+LGPD+perfil+pronto
│   ├── dashboard/page.tsx             ← dashboard completo com 5 componentes
│   ├── workouts/page.tsx              ← lista com filtros + sync Strava
│   ├── strength/new/page.tsx          ← useFieldArray + autocomplete + TSS preview
│   ├── recommendations/page.tsx       ← card+seções+nutrição+feedback+polling
│   ├── metrics/page.tsx               ← ScaleInput 1–10 + 2 gráficos Recharts
│   ├── settings/page.tsx              ← conexões + Apple Health URL + LGPD
│   └── admin/athletes/
│       ├── page.tsx                   ← tabela KPIs + badges TSB
│       ├── new/page.tsx               ← formulário completo (modalidades, dias, fisiologia)
│       └── [id]/page.tsx             ← 4 abas: perfil/plano/histórico/aderência
├── components/
│   ├── charts/CTLATLTSBChart.tsx      ← 3 linhas, tooltip, seletor de período
│   └── dashboard/
│       ├── DailyRecommendationCard.tsx
│       ├── WeeklyTSSBar.tsx
│       ├── RecentWorkoutsList.tsx
│       └── DailyMetricsCard.tsx
└── lib/
    ├── api.ts                         ← axios + auth interceptor + auto-refresh
    ├── supabase.ts
    ├── types.ts                       ← todos os tipos TypeScript do domínio
    └── store/authStore.ts             ← Zustand persist
```

### Banco de Dados

```
supabase/migrations/001_initial_schema.sql
  Tabelas:
    admin_users, athletes, platform_connections
    workouts, strength_sessions, strength_exercises
    daily_metrics, training_load, ai_recommendations
    admin_alerts, lgpd_consents, audit_logs, lgpd_deletion_requests
    subscriptions, webhook_events
  + RLS em todas as tabelas
  + Políticas por role (admin/athlete)
  + Índices de performance
  + Trigger set_updated_at()
```

---

## Cobertura de Testes

| Suite | Testes | Cobertura |
|-------|--------|-----------|
| `test_auth.py` | 15 | JWT, roles, LGPD middleware, refresh, profile update |
| `test_calculations.py` | 35 | TSS cycling/HR/strength, CTL/ATL/TSB série, zonas, TSB labels |
| `test_strava_service.py` | 15 | Parse, sport mapping, relay Garmin, token refresh, HMAC |
| `test_ai_service.py` | 25 | JSON parse, safety check, fallback chain, nutrição, fatigue |
| **Total** | **90** | — |

---

## Próximos Passos (Sprints 08–12)

### Sprint 08 — Dashboard Admin + Alertas (dias 76–85)

- [ ] Painel admin com todos os atletas numa tela — cards com CTL/ATL/TSB, último treino, aderência
- [ ] `admin_alerts` table → criar alertas automáticos (TSB crítico, 3+ dias sem treino, sem métricas)
- [ ] Endpoint `GET /api/admin/alerts` com filtro por severidade e atleta
- [ ] Email automático para o admin quando atleta atinge TSB < −25
- [ ] Relatório semanal por atleta (resumo textual gerado pela IA)
- [ ] Frontend `/admin/dashboard` com painel geral

### Sprint 09 — PWA + App Cliente (dias 86–95)

- [ ] `next-pwa` — service worker, manifest, ícones, offline fallback
- [ ] Push notifications (via `web-push`) — lembrete de registrar métricas às 07:00
- [ ] `/workouts/[id]` — detalhe do treino com planejado vs executado
- [ ] `/history` — histórico completo com filtros por período e tipo
- [ ] Melhoria UX mobile: bottom nav, swipe gestures, loading skeletons

### Sprint 10 — Relatórios PDF (dias 96–102)

- [ ] `WeasyPrint` — relatório mensal do atleta (CTL/ATL/TSB chart + workouts + nutrição)
- [ ] `GET /api/athletes/report/monthly` — gera PDF e retorna link temporário
- [ ] Exportação LGPD em PDF com todos os dados do atleta
- [ ] Email automático do relatório mensal (via Resend)
- [ ] Frontend — botão "Gerar relatório" no dashboard

### Sprint 11 — Assinaturas Stripe (dias 103–113)

> **Pré-requisito:** aprovação KYC Stripe (iniciada no S01)

- [ ] Modelos `subscriptions` + endpoints billing
- [ ] Planos: starter (5 atletas), pro (20), elite (ilimitado)
- [ ] Webhook Stripe — `invoice.paid`, `customer.subscription.deleted`, `payment_failed`
- [ ] Middleware de limite de atletas por plano
- [ ] Portal de billing (Stripe Customer Portal)
- [ ] Frontend `/billing` — plano atual, upgrade, histórico de faturas

### Sprint 12 — QA + Deploy Final (dias 114–121)

- [ ] Testes de integração E2E (pytest, simulando fluxo completo)
- [ ] `GitHub Actions` CI/CD — lint + testes + deploy automático
- [ ] Railway (backend) — variáveis de ambiente, health check, domínio custom
- [ ] Vercel (frontend) — domínio custom, env vars de produção
- [ ] Configuração RLS real (policies de produção)
- [ ] Rotação de chaves de criptografia
- [ ] Monitoramento — Sentry (erros) + Logfire ou Railway logs
- [ ] Teste de carga (locust) — 20 atletas simultâneos no job diário

---

## Pré-requisitos Externos Pendentes

| Item | Status | Necessário para |
|------|--------|----------------|
| Strava App criado | ⚠️ Fazer | S04 (dev local com ngrok) |
| TrainingPeaks API approval | ⚠️ Solicitado S01 | S06 (push/pull bidirecional) |
| Stripe KYC aprovado | ⚠️ Iniciado S01 | S11 |
| Domínio custom (fitcoachai.com) | ⏳ Opcional | S12 |

---

## Variáveis de Ambiente Necessárias

Copiar `backend/.env.example` → `backend/.env` e preencher:

```env
# Supabase (obrigatório)
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
SUPABASE_JWT_SECRET=
DATABASE_URL=postgresql+asyncpg://...

# Criptografia (obrigatório)
DB_ENCRYPTION_KEY=       # min 32 chars, aleatório
SECRET_KEY=              # min 32 chars, para HMAC de tokens de convite

# Strava OAuth (para S04)
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_WEBHOOK_VERIFY_TOKEN=

# TrainingPeaks OAuth (para S06)
TP_CLIENT_ID=
TP_CLIENT_SECRET=

# AI (obrigatório para S05)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Email (para S02)
RESEND_API_KEY=

# Stripe (para S11)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
```

---

## Como rodar localmente

```bash
# Backend
cd backend
cp .env.example .env
# preencher .env
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://localhost:8000/docs

# Testes
pytest tests/ -v

# Frontend
cd frontend
cp .env.example .env.local
npm install
npm run dev
# → http://localhost:3000

# Banco de dados
# Executar supabase/migrations/001_initial_schema.sql no SQL Editor do Supabase
```

---

*Última atualização: 2026-05-04 | FitCoach AI v0.7.0-dev*
