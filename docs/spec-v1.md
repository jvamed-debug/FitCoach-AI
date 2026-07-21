# Spec v1 — FitCoach AI
Versão: 1.0 | Data: 2026-04-30 | Fase: 06 — Spec Generation

---

## Índice

1. [Modelo de Dados](#1-modelo-de-dados)
2. [Contratos de API](#2-contratos-de-api)
3. [Estados de UI](#3-estados-de-ui)
4. [Fluxos de Integração](#4-fluxos-de-integração)
5. [Fluxo do Job Diário](#5-fluxo-do-job-diário)

---

## 1. Modelo de Dados

### 1.1 Diagrama Entidade-Relacionamento (ERD)

```
athletes ──────────────────────────────────────────────────────────────┐
    │                                                                   │
    ├──< platform_connections (Strava / Garmin / TrainingPeaks)        │
    ├──< lgpd_consents                                                  │
    ├──< audit_logs                                                     │
    ├──< workouts ──────────────────────────────────────────────────────┤
    ├──< strength_sessions ──< strength_exercises                       │
    ├──< daily_metrics                                                  │
    ├──< training_load                                                  │
    ├──< ai_recommendations ──< recommendation_feedback                 │
    ├──< nutrition_plans                                                │
    ├──< reports                                                        │
    └──< subscriptions ──< stripe_events                               │
                                                                        │
admin_users ────────────────────────────────────────────────────────────┘
    │
    └──< job_execution_logs ──< job_client_results
```

---

### 1.2 Schema SQL Completo

```sql
-- ============================================================
-- EXTENSÕES
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABELA: admin_users
-- Médicos/coaches que administram a plataforma
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID UNIQUE NOT NULL,       -- Supabase Auth user_id
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    crm             VARCHAR(50),                -- CRM do médico (opcional)
    stripe_account_id VARCHAR(255),             -- conta Stripe do admin
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: athletes
-- Clientes/atletas cadastrados pelo admin
-- ============================================================
CREATE TABLE IF NOT EXISTS athletes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID UNIQUE NOT NULL,       -- Supabase Auth user_id
    admin_id        UUID NOT NULL REFERENCES admin_users(id) ON DELETE RESTRICT,
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    phone           VARCHAR(30),
    birth_date      DATE,
    gender          VARCHAR(20),
    height_cm       NUMERIC(5,2),
    weight_kg       NUMERIC(5,2),
    -- Dados esportivos (não sensíveis)
    sport_modalities    VARCHAR(100)[] DEFAULT '{}',  -- ['cycling','strength','running','swimming','triathlon']
    primary_modality    VARCHAR(50),
    fitness_level       VARCHAR(20),                  -- 'beginner','intermediate','advanced'
    goal                TEXT,                         -- objetivo em texto livre
    weekly_availability JSONB,                        -- {"cycling":["mon","wed","fri"],"strength":["tue","thu"]}
    -- Dados fisiológicos (sensíveis — criptografados via aplicação antes de salvar)
    ftp_watts           INTEGER,
    max_hr              INTEGER,
    resting_hr          INTEGER,
    -- Anamnese (campo criptografado com pgcrypto)
    anamnese_encrypted  BYTEA,                        -- pgp_sym_encrypt(anamnese_json, key)
    -- Status
    is_active           BOOLEAN DEFAULT TRUE,
    onboarding_complete BOOLEAN DEFAULT FALSE,
    apple_health_token  UUID DEFAULT uuid_generate_v4(), -- token único para webhook Apple Health
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: lgpd_consents
-- Registro de consentimento LGPD (Art. 11 — dados sensíveis)
-- ============================================================
CREATE TABLE IF NOT EXISTS lgpd_consents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    consent_version VARCHAR(20) NOT NULL,       -- ex: "1.0", "1.1"
    consented_at    TIMESTAMPTZ NOT NULL,
    ip_address      INET,
    user_agent      TEXT,
    revoked_at      TIMESTAMPTZ,               -- NULL = ativo
    revoke_reason   TEXT
);

-- ============================================================
-- TABELA: audit_logs
-- Log de auditoria de acesso a dados de saúde (NFR-13: 1 ano)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id        UUID NOT NULL,             -- admin_user_id ou athlete_id
    actor_type      VARCHAR(20) NOT NULL,      -- 'admin' | 'athlete' | 'system'
    action          VARCHAR(100) NOT NULL,     -- 'READ_ANAMNESE' | 'EXPORT_DATA' | 'DELETE_DATA' | ...
    resource_type   VARCHAR(50) NOT NULL,      -- 'athlete' | 'workout' | 'metrics' | ...
    resource_id     UUID,
    ip_address      INET,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: platform_connections
-- Tokens OAuth de plataformas externas (criptografados)
-- ============================================================
CREATE TABLE IF NOT EXISTS platform_connections (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id          UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    provider            VARCHAR(50) NOT NULL,  -- 'strava' | 'trainingpeaks' | 'apple_health'
    provider_athlete_id VARCHAR(255),
    -- Tokens criptografados com pgcrypto (NUNCA em logs)
    access_token_enc    BYTEA,                 -- pgp_sym_encrypt(token, key)
    refresh_token_enc   BYTEA,
    token_expires_at    TIMESTAMPTZ,
    scope               TEXT,
    webhook_subscription_id VARCHAR(255),      -- ID da subscription Strava webhook
    is_active           BOOLEAN DEFAULT TRUE,
    last_sync_at        TIMESTAMPTZ,
    sync_error          TEXT,                  -- último erro de sincronização
    consecutive_failures INTEGER DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, provider)
);

-- ============================================================
-- TABELA: workouts
-- Treinos executados (importados ou manuais) e planejados
-- ============================================================
CREATE TABLE IF NOT EXISTS workouts (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id              UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    external_id             VARCHAR(255),      -- ID na plataforma de origem
    source                  VARCHAR(50) NOT NULL, -- 'strava' | 'trainingpeaks' | 'garmin_relay' | 'manual' | 'planned'
    status                  VARCHAR(20) DEFAULT 'completed', -- 'planned' | 'completed' | 'skipped'
    sport_type              VARCHAR(50) NOT NULL, -- 'cycling' | 'running' | 'strength' | 'swimming' | 'triathlon' | 'rest' | 'mobility'
    title                   VARCHAR(255),
    description             TEXT,
    start_time              TIMESTAMPTZ NOT NULL,
    duration_seconds        INTEGER,
    distance_meters         NUMERIC(10,2),
    elevation_gain_meters   NUMERIC(8,2),
    avg_heart_rate          INTEGER,
    max_heart_rate          INTEGER,
    avg_power_watts         INTEGER,
    normalized_power_watts  INTEGER,
    max_power_watts         INTEGER,
    avg_cadence             INTEGER,
    avg_pace_sec_per_km     INTEGER,           -- para corrida e natação
    calories                INTEGER,
    tss                     NUMERIC(8,2),
    if_score                NUMERIC(5,3),
    hr_zones                JSONB,             -- {"z1": 600, "z2": 1200, ...} em segundos
    power_zones             JSONB,
    -- Para treinos planejados: referência à recomendação que os gerou
    recommendation_id       UUID REFERENCES ai_recommendations(id) ON DELETE SET NULL,
    -- Envio às plataformas
    sent_to_strava          BOOLEAN DEFAULT FALSE,
    sent_to_trainingpeaks   BOOLEAN DEFAULT FALSE,
    strava_workout_id       VARCHAR(255),
    trainingpeaks_workout_id VARCHAR(255),
    raw_data                JSONB,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: strength_sessions
-- Sessões de musculação registradas
-- ============================================================
CREATE TABLE IF NOT EXISTS strength_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    workout_id      UUID REFERENCES workouts(id) ON DELETE SET NULL,
    session_date    DATE NOT NULL,
    session_type    VARCHAR(50),               -- 'upper' | 'lower' | 'full_body' | 'push' | 'pull'
    duration_minutes INTEGER,
    rpe_overall     INTEGER CHECK (rpe_overall BETWEEN 1 AND 10),
    tss             NUMERIC(8,2),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: strength_exercises
-- Exercícios de uma sessão de musculação
-- ============================================================
CREATE TABLE IF NOT EXISTS strength_exercises (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES strength_sessions(id) ON DELETE CASCADE,
    exercise_name   VARCHAR(255) NOT NULL,
    exercise_order  INTEGER NOT NULL,
    sets            INTEGER NOT NULL,
    reps            INTEGER,                   -- NULL para exercícios por tempo
    duration_seconds INTEGER,
    load_kg         NUMERIC(6,2),
    load_pct_1rm    NUMERIC(5,2),              -- % do 1RM estimado
    rpe             INTEGER CHECK (rpe BETWEEN 1 AND 10),
    rest_seconds    INTEGER,
    notes           TEXT
);

-- ============================================================
-- TABELA: daily_metrics
-- Métricas diárias de saúde e bem-estar (upsert por data)
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_metrics (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    metric_date     DATE NOT NULL,
    -- Métricas objetivas
    weight_kg       NUMERIC(5,2),
    sleep_hours     NUMERIC(4,2),
    hrv_ms          INTEGER,                   -- criptografado no nível de app
    resting_hr      INTEGER,
    -- Métricas subjetivas (1-10)
    sleep_quality   INTEGER CHECK (sleep_quality BETWEEN 1 AND 10),
    fatigue_score   INTEGER CHECK (fatigue_score BETWEEN 1 AND 10),
    muscle_soreness INTEGER CHECK (muscle_soreness BETWEEN 1 AND 10),
    stress_score    INTEGER CHECK (stress_score BETWEEN 1 AND 10),
    motivation_score INTEGER CHECK (motivation_score BETWEEN 1 AND 10),
    -- Origem dos dados
    source          VARCHAR(30) DEFAULT 'manual', -- 'manual' | 'apple_health' | 'garmin'
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, metric_date)
);

-- ============================================================
-- TABELA: training_load
-- CTL / ATL / TSB calculados diariamente (Modelo Banister)
-- ============================================================
CREATE TABLE IF NOT EXISTS training_load (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    load_date       DATE NOT NULL,
    ctl             NUMERIC(8,4),              -- Chronic Training Load (Fitness) — 42d
    atl             NUMERIC(8,4),              -- Acute Training Load (Fatigue) — 7d
    tsb             NUMERIC(8,4),              -- Training Stress Balance = CTL - ATL
    daily_tss       NUMERIC(8,2),
    weekly_tss      NUMERIC(8,2),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, load_date)
);

-- ============================================================
-- TABELA: ai_recommendations
-- Planos de treino gerados pelo agente IA
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id          UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    recommendation_date DATE NOT NULL,
    ai_provider         VARCHAR(50) NOT NULL,  -- 'anthropic' | 'openai'
    ai_model            VARCHAR(100) NOT NULL,
    workout_type        VARCHAR(50),           -- 'cycling_endurance' | 'cycling_threshold' | 'cycling_vo2max' | 'cycling_long' | 'strength_upper' | 'strength_lower' | 'strength_full' | 'running_easy' | 'running_tempo' | 'running_long' | 'swimming' | 'triathlon' | 'rest' | 'mobility'
    title               VARCHAR(255),
    recommendation_text TEXT NOT NULL,
    structured_plan     JSONB NOT NULL,        -- plano estruturado parseado
    rationale           TEXT,
    nutrition_plan      JSONB,                 -- orientação nutricional do dia
    input_context       JSONB,                 -- contexto enviado à IA (para auditoria)
    tokens_used         INTEGER,
    generation_time_ms  INTEGER,
    -- Status de envio às plataformas
    sent_to_strava      BOOLEAN DEFAULT FALSE,
    sent_to_trainingpeaks BOOLEAN DEFAULT FALSE,
    sent_at             TIMESTAMPTZ,
    send_error          TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, recommendation_date)
);

-- ============================================================
-- TABELA: recommendation_feedback
-- Feedback do cliente sobre o treino recebido
-- ============================================================
CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recommendation_id   UUID NOT NULL REFERENCES ai_recommendations(id) ON DELETE CASCADE,
    athlete_id          UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    rating              INTEGER CHECK (rating BETWEEN 1 AND 10),
    rpe_actual          INTEGER CHECK (rpe_actual BETWEEN 1 AND 10),
    completed           BOOLEAN,               -- seguiu o treino?
    notes               TEXT,
    submitted_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: nutrition_plans
-- Orientações nutricionais diárias (geradas junto ao treino)
-- ============================================================
CREATE TABLE IF NOT EXISTS nutrition_plans (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    plan_date       DATE NOT NULL,
    recommendation_id UUID REFERENCES ai_recommendations(id) ON DELETE SET NULL,
    -- Macros calculados
    calories_target INTEGER,
    carbs_g         NUMERIC(6,1),
    protein_g       NUMERIC(6,1),
    fat_g           NUMERIC(6,1),
    hydration_ml    INTEGER,
    -- Plano detalhado
    structured_plan JSONB NOT NULL,            -- {"pre_workout": {...}, "during": {...}, "post_workout": {...}, "meals": [...]}
    ai_notes        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, plan_date)
);

-- ============================================================
-- TABELA: subscriptions
-- Gestão de assinaturas dos atletas
-- ============================================================
CREATE TABLE IF NOT EXISTS subscriptions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id          UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    admin_id            UUID NOT NULL REFERENCES admin_users(id) ON DELETE RESTRICT,
    stripe_customer_id  VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    plan_name           VARCHAR(100) NOT NULL, -- 'basic' | 'premium' | 'elite'
    amount_cents        INTEGER,               -- valor em centavos BRL
    billing_cycle       VARCHAR(20) DEFAULT 'monthly', -- 'monthly' | 'annual'
    status              VARCHAR(30) NOT NULL DEFAULT 'active', -- 'active' | 'suspended' | 'cancelled' | 'past_due'
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_period_end  TIMESTAMPTZ,
    suspended_at        TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    cancel_reason       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: reports
-- Relatórios gerados (semanais/mensais)
-- ============================================================
CREATE TABLE IF NOT EXISTS reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    admin_id        UUID NOT NULL REFERENCES admin_users(id) ON DELETE RESTRICT,
    report_type     VARCHAR(20) NOT NULL,      -- 'weekly' | 'monthly'
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    content         JSONB NOT NULL,            -- dados do relatório
    pdf_storage_path TEXT,                     -- path no Supabase Storage
    sent_to_client  BOOLEAN DEFAULT FALSE,
    sent_at         TIMESTAMPTZ,
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: job_execution_logs
-- Log de execução do job diário (US-027)
-- ============================================================
CREATE TABLE IF NOT EXISTS job_execution_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_name        VARCHAR(100) NOT NULL,     -- 'daily_update'
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(20),               -- 'running' | 'completed' | 'failed'
    total_athletes  INTEGER,
    success_count   INTEGER,
    failure_count   INTEGER,
    duration_ms     INTEGER,
    error_message   TEXT
);

-- ============================================================
-- TABELA: job_client_results
-- Resultado por cliente no job diário
-- ============================================================
CREATE TABLE IF NOT EXISTS job_client_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_log_id      UUID NOT NULL REFERENCES job_execution_logs(id) ON DELETE CASCADE,
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    steps           JSONB,                     -- {"import": "ok", "recalc": "ok", "generate": "ok", "send": "failed"}
    error_message   TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: admin_alerts
-- Alertas gerados pelo job diário para o admin (US-029)
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id        UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    athlete_id      UUID REFERENCES athletes(id) ON DELETE CASCADE,
    alert_type      VARCHAR(50) NOT NULL,  -- 'overtraining_risk' | 'integration_failure' | 'inactivity' | 'job_not_run' | 'payment_failed'
    message         TEXT NOT NULL,
    metadata        JSONB,
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABELA: lgpd_deletion_requests
-- Solicitações de exclusão de dados (Art. 18 LGPD — prazo ≤ 72h)
-- ============================================================
CREATE TABLE IF NOT EXISTS lgpd_deletion_requests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deadline        TIMESTAMPTZ NOT NULL,  -- requested_at + 72h
    executed_at     TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'executed'
    confirmation_email_sent BOOLEAN DEFAULT FALSE
);

-- ============================================================
-- ÍNDICES
-- ============================================================
CREATE INDEX idx_workouts_athlete_date     ON workouts(athlete_id, start_time DESC);
CREATE INDEX idx_workouts_status           ON workouts(athlete_id, status);
CREATE INDEX idx_workouts_external        ON workouts(external_id, source);
CREATE INDEX idx_strength_athlete_date    ON strength_sessions(athlete_id, session_date DESC);
CREATE INDEX idx_metrics_athlete_date     ON daily_metrics(athlete_id, metric_date DESC);
CREATE INDEX idx_load_athlete_date        ON training_load(athlete_id, load_date DESC);
CREATE INDEX idx_recommendations_date     ON ai_recommendations(athlete_id, recommendation_date DESC);
CREATE INDEX idx_audit_logs_actor_date    ON audit_logs(actor_id, created_at DESC);
CREATE INDEX idx_audit_logs_resource      ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_platform_connections     ON platform_connections(athlete_id, provider);
CREATE INDEX idx_job_results_log          ON job_client_results(job_log_id);
CREATE INDEX idx_admin_alerts_unread      ON admin_alerts(admin_id, is_read, created_at DESC);
CREATE INDEX idx_lgpd_deletion_pending    ON lgpd_deletion_requests(status, deadline);

-- ============================================================
-- RLS (Row Level Security) — LGPD
-- ============================================================
ALTER TABLE athletes ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE workouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE strength_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE strength_exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_load ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendation_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE nutrition_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE lgpd_consents ENABLE ROW LEVEL SECURITY;

-- Policies: atleta acessa apenas seus próprios dados
CREATE POLICY "athlete_own_data" ON athletes
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "athlete_workouts" ON workouts
    FOR ALL USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

CREATE POLICY "athlete_metrics" ON daily_metrics
    FOR ALL USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

CREATE POLICY "athlete_recommendations" ON ai_recommendations
    FOR ALL USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

CREATE POLICY "athlete_nutrition" ON nutrition_plans
    FOR ALL USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

-- Admin acessa dados de seus atletas (via service role key no backend)
-- Políticas de admin gerenciadas no backend com service_role key (bypass RLS)
```

---

## 2. Contratos de API

> Base URL: `https://api.fitcoachai.com/api`
> Auth: `Authorization: Bearer {jwt_token}` em todos os endpoints protegidos
> Erros padrão: `{ "error": "CÓDIGO", "message": "descrição", "details": {} }`

---

### 2.1 Auth

#### `POST /auth/admin/login`
Login do admin.
```json
// Request
{ "email": "dr@clinica.com", "password": "senha123" }

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": { "id": "uuid", "name": "Dr. Silva", "email": "dr@clinica.com", "role": "admin" }
}
```

#### `POST /auth/athlete/login`
Login do atleta (email + senha).
```json
// Response 200 — mesmo formato + onboarding_complete: bool
```

#### `POST /auth/refresh`
Renova access token.
```json
// Request
{ "refresh_token": "eyJ..." }
// Response 200
{ "access_token": "eyJ...", "expires_in": 86400 }
```

#### `POST /auth/logout`
Invalida sessão.
```json
// Response 200
{ "message": "Logout realizado com sucesso" }
```

#### `GET /auth/me`
Retorna perfil autenticado.
```json
// Response 200 (admin)
{
  "id": "uuid", "name": "Dr. Silva", "email": "dr@clinica.com",
  "role": "admin", "crm": "CRM/SP 123456"
}
// Response 200 (atleta)
{
  "id": "uuid", "name": "João", "email": "joao@email.com",
  "role": "athlete", "onboarding_complete": true,
  "primary_modality": "cycling", "fitness_level": "intermediate"
}
```

---

### 2.2 Atletas (Admin)

#### `GET /admin/athletes`
Lista atletas do admin com filtros.
```
Query params: ?status=active&search=joão&sort=name&page=1&per_page=20
```
```json
// Response 200
{
  "total": 15, "page": 1, "per_page": 20,
  "items": [
    {
      "id": "uuid", "name": "João Silva", "email": "joao@email.com",
      "status": "active",
      "last_workout_at": "2026-04-29T07:30:00Z",
      "tsb_current": -8.3,
      "tsb_status": "moderate",       // "good" (>-5) | "moderate" (-5 a -20) | "alert" (<-20) | "critical" (<-25)
      "integrations": ["strava", "trainingpeaks"],
      "subscription_status": "active",
      "days_without_workout": 1
    }
  ]
}
```

#### `POST /admin/athletes`
Cadastra novo atleta e envia email de boas-vindas.
```json
// Request
{
  "name": "João Silva",
  "email": "joao@email.com",
  "phone": "11999999999",
  "birth_date": "1990-05-15",
  "gender": "male",
  "height_cm": 178,
  "weight_kg": 75.0,
  "sport_modalities": ["cycling", "strength"],
  "primary_modality": "cycling",
  "fitness_level": "intermediate",
  "goal": "Preparação para Granfondo 2026 — completar 160km",
  "weekly_availability": {
    "cycling": ["tue", "thu", "sat"],
    "strength": ["mon", "fri"]
  }
}
// Response 201
{ "id": "uuid", "email": "joao@email.com", "onboarding_link": "https://app.fitcoachai.com/onboarding?token=..." }
```

#### `GET /admin/athletes/{id}`
Perfil completo do atleta.
```json
// Response 200
{
  "id": "uuid", "name": "João Silva",
  "anamnese": {                        // descriptografado pelo backend
    "injuries_history": "Tendinite no joelho direito (2023, resolvida)",
    "medications": "Nenhum",
    "contraindications": "Nenhuma",
    "ftp_watts": 260,
    "max_hr": 185,
    "resting_hr": 52
  },
  "training_load": { "ctl": 65.2, "atl": 73.5, "tsb": -8.3 },
  "integrations": [
    { "provider": "strava", "is_active": true, "last_sync_at": "2026-04-30T06:02:00Z" },
    { "provider": "trainingpeaks", "is_active": true, "last_sync_at": "2026-04-30T06:05:00Z" }
  ],
  "subscription": { "status": "active", "plan": "premium", "current_period_end": "2026-05-30" }
}
```

#### `PUT /admin/athletes/{id}`
Atualiza perfil/anamnese.

#### `PUT /admin/athletes/{id}/anamnese`
Atualiza dados médicos sensíveis (requer confirmação de senha do admin).
```json
// Request
{
  "injuries_history": "...",
  "medications": "...",
  "contraindications": "...",
  "ftp_watts": 265,
  "max_hr": 185,
  "resting_hr": 50,
  "admin_password": "senha_do_admin"   // confirmação de identidade
}
```

---

### 2.3 Plataformas (OAuth)

#### `GET /auth/oauth/{provider}/authorize`
Inicia fluxo OAuth (redirect ao provider).
```
provider: 'strava' | 'trainingpeaks'
Query: ?athlete_id=uuid
Response 302: redirect para URL OAuth do provider
```

#### `GET /auth/oauth/{provider}/callback`
Recebe code, troca por tokens, salva conexão.
```
Query: ?code=abc&state=uuid&athlete_id=uuid
Response 302: redirect para /settings?integration=connected
```

#### `DELETE /auth/oauth/{provider}`
Desconecta plataforma.
```
Body: { "athlete_id": "uuid" }
Response 200: { "message": "Desconectado com sucesso" }
```

#### `POST /health/apple-health/{token}`
Webhook do iOS Shortcut — recebe dados do Apple Health.
```json
// Request (sem auth JWT — autenticado pelo token único do atleta)
{
  "date": "2026-04-30",
  "resting_hr": 52,
  "hrv_ms": 68,
  "sleep_hours": 7.5,
  "sleep_quality": 7,
  "activities": [
    { "type": "cycling", "duration_seconds": 3600, "calories": 750, "avg_hr": 145 }
  ]
}
// Response 200
{ "received": true, "metrics_updated": true }
```

#### `POST /webhooks/strava`
Webhook Strava — recebe eventos de atividades.
```json
// Headers: X-Strava-Signature: sha256=...
// Body (atividade criada)
{
  "aspect_type": "create",
  "event_time": 1714483200,
  "object_id": 1234567890,
  "object_type": "activity",
  "owner_id": 9876543,
  "subscription_id": 999
}
// Response 200 — processa em background
```

---

### 2.4 Treinos

#### `GET /workouts`
Lista treinos do atleta autenticado.
```
Query: ?start_date=2026-04-01&end_date=2026-04-30&sport_type=cycling&status=completed&page=1&per_page=30
```
```json
// Response 200
{
  "total": 42,
  "items": [
    {
      "id": "uuid", "title": "Treino Z2 — Endurance",
      "sport_type": "cycling", "status": "completed",
      "start_time": "2026-04-29T07:00:00Z",
      "duration_seconds": 5400, "distance_meters": 45000,
      "avg_power_watts": 195, "normalized_power_watts": 210,
      "tss": 78.5, "if_score": 0.81, "source": "strava"
    }
  ]
}
```

#### `GET /workouts/{id}`
Detalhes completos incluindo zonas.

#### `GET /workouts/stats/weekly`
Estatísticas semanais.
```json
// Response 200
{
  "week_start": "2026-04-28",
  "total_tss": 285.5,
  "total_duration_hours": 8.3,
  "total_distance_km": 142.5,
  "workouts_count": 5,
  "by_type": {
    "cycling": { "count": 3, "tss": 210.0, "duration_hours": 6.5 },
    "strength": { "count": 2, "tss": 75.5, "duration_hours": 1.8 }
  },
  "vs_previous_week": { "tss_delta_pct": +12.3 }
}
```

#### `GET /workouts/load`
CTL/ATL/TSB atual e histórico.
```json
// Query: ?days=60
// Response 200
{
  "current": { "ctl": 65.2, "atl": 73.5, "tsb": -8.3, "date": "2026-04-30" },
  "history": [
    { "date": "2026-04-01", "ctl": 55.1, "atl": 60.2, "tsb": -5.1, "daily_tss": 95.0 }
  ]
}
```

#### `POST /workouts/sync/strava`
Força sincronização manual com Strava.
```json
// Request
{ "days_back": 7 }
// Response 200
{ "synced": 3, "new": 2, "updated": 1, "errors": 0 }
```

---

### 2.5 Musculação

#### `GET /strength`
Lista sessões de musculação.
```
Query: ?start_date=&end_date=&page=1
```

#### `POST /strength`
Registra nova sessão.
```json
// Request
{
  "session_date": "2026-04-30",
  "session_type": "upper",
  "duration_minutes": 55,
  "rpe_overall": 7,
  "notes": "Puxada com aumento de carga no supino",
  "exercises": [
    {
      "exercise_name": "Supino Reto",
      "exercise_order": 1,
      "sets": 4,
      "reps": 8,
      "load_kg": 80.0,
      "rpe": 8,
      "rest_seconds": 90
    },
    {
      "exercise_name": "Remada Curvada",
      "exercise_order": 2,
      "sets": 4,
      "reps": 10,
      "load_kg": 70.0,
      "rpe": 7,
      "rest_seconds": 90
    }
  ]
}
// Response 201
{ "id": "uuid", "tss": 62.5 }
```

#### `GET /strength/{id}`
Detalhes com lista de exercícios.

#### `PUT /strength/{id}`
Edita sessão e exercícios.

#### `DELETE /strength/{id}`

---

### 2.6 Métricas Diárias

#### `GET /metrics`
Histórico de métricas.
```
Query: ?start_date=2026-04-01&end_date=2026-04-30
```

#### `POST /metrics`
Registra/atualiza métricas do dia (upsert por data).
```json
// Request
{
  "metric_date": "2026-04-30",
  "weight_kg": 74.8,
  "sleep_hours": 7.5,
  "sleep_quality": 7,
  "hrv_ms": 68,
  "resting_hr": 51,
  "fatigue_score": 4,
  "muscle_soreness": 3,
  "stress_score": 3,
  "motivation_score": 8,
  "notes": "Semana pesada no trabalho mas treinos bons"
}
// Response 200 | 201
{ "id": "uuid", "metric_date": "2026-04-30", "source": "manual" }
```

#### `GET /metrics/today`
Métricas de hoje.

#### `GET /metrics/trends`
Tendências 7d e 30d.
```json
// Response 200
{
  "7d": { "avg_sleep_hours": 7.2, "avg_hrv_ms": 65, "avg_fatigue": 4.5, "avg_motivation": 7.1 },
  "30d": { "avg_sleep_hours": 7.0, "avg_hrv_ms": 63, "avg_fatigue": 5.0, "avg_motivation": 6.8 }
}
```

---

### 2.7 Recomendações IA

#### `GET /recommendations/today`
Recomendação de hoje (gera se não existir).
```json
// Response 200
{
  "id": "uuid",
  "recommendation_date": "2026-04-30",
  "workout_type": "cycling_threshold",
  "title": "Treino de Limiar — Blocos Z4",
  "ai_provider": "anthropic",
  "structured_plan": {
    "duration_minutes": 75,
    "intensity": "hard",
    "sections": [
      {
        "name": "Aquecimento",
        "duration_minutes": 15,
        "description": "Pedalada progressiva saindo de Z1 até Z2",
        "targets": { "power_pct_ftp": 65, "hr_zone": 2, "rpe": 3 }
      },
      {
        "name": "Série Principal — 3×12min Z4",
        "duration_minutes": 48,
        "description": "3 blocos de 12min em potência de limiar com 4min de recuperação Z1 entre blocos",
        "targets": { "power_pct_ftp": 95, "hr_zone": 4, "rpe": 7 }
      },
      {
        "name": "Desaquecimento",
        "duration_minutes": 12,
        "description": "Retorno progressivo a Z1, spinning leve",
        "targets": { "power_pct_ftp": 50, "hr_zone": 1, "rpe": 2 }
      }
    ],
    "key_metrics_considered": ["CTL: 65.2", "ATL: 73.5", "TSB: -8.3", "Último treino: 2d atrás"],
    "cautions": []
  },
  "nutrition_plan": {
    "calories_target": 2800,
    "carbs_g": 340,
    "protein_g": 155,
    "fat_g": 78,
    "hydration_ml": 2800,
    "pre_workout": "90min antes: 1 banana + 40g aveia + café. 30min antes: gel de carboidrato (25g).",
    "during": "A cada 45min: gel ou barra de 30g carboidrato. 500ml água por hora.",
    "post_workout": "Até 30min após: 30g whey + 60g carboidrato simples (fruta + arroz).",
    "meals": ["Almoço: frango 200g + batata-doce 150g + salada", "Jantar: salmão 180g + macarrão integral 120g"]
  },
  "rationale": "TSB de -8.3 indica carga moderada. Seu último treino de qualidade foi há 3 dias e CTL está crescendo bem (65 → meta de 75 para o Granfondo). É o momento ideal para um estímulo de limiar para continuar a progressão sem acumular fadiga excessiva. Dormir 7.5h e HRV de 68ms confirmam boa recuperação.",
  "sent_to_strava": true,
  "sent_to_trainingpeaks": true
}
```

#### `POST /recommendations/generate`
Força nova geração (substitui a do dia).
```json
// Request
{ "provider": "anthropic" }  // opcional — usa default se omitido
// Response 201 — mesmo formato acima
```

#### `POST /recommendations/{id}/feedback`
Feedback do atleta.
```json
// Request
{
  "rating": 8,
  "rpe_actual": 7,
  "completed": true,
  "notes": "Consegui completar os 3 blocos, último ficou um pouco mais pesado"
}
// Response 200
{ "message": "Feedback registrado. Obrigado!" }
```

#### `GET /recommendations`
Histórico de recomendações.
```
Query: ?days=30&page=1
```

#### `GET /admin/athletes/{id}/recommendations/weekly-plan`
Plano semanal do atleta (admin).
```json
// Response 200
{
  "week_start": "2026-04-28",
  "total_planned_tss": 380,
  "days": [
    { "date": "2026-04-28", "workout_type": "rest", "title": "Descanso ativo", ... },
    { "date": "2026-04-29", "workout_type": "cycling_endurance", ... }
  ]
}
```

---

### 2.8 Dashboard Admin

#### `GET /admin/dashboard`
Dados consolidados para o dashboard.
```json
// Response 200
{
  "total_athletes": 12,
  "active_athletes": 11,
  "alerts": [
    { "type": "overtraining_risk", "athlete_id": "uuid", "athlete_name": "João", "tsb": -27.5 },
    { "type": "integration_failure", "athlete_id": "uuid", "athlete_name": "Maria", "provider": "strava", "hours_failed": 26 },
    { "type": "inactivity", "athlete_id": "uuid", "athlete_name": "Pedro", "days_without_workout": 5 }
  ],
  "job_last_run": {
    "started_at": "2026-04-30T06:00:00Z",
    "status": "completed",
    "success_count": 11,
    "failure_count": 1
  }
}
```

#### `GET /admin/job-logs`
Histórico do job diário.
```
Query: ?days=7
```
```json
// Response 200
{
  "items": [
    {
      "started_at": "2026-04-30T06:00:00Z",
      "status": "completed",
      "total_athletes": 12,
      "success_count": 11,
      "failure_count": 1,
      "duration_ms": 145000,
      "client_results": [
        { "athlete_name": "João", "steps": { "import": "ok", "recalc": "ok", "generate": "ok", "send": "ok" } },
        { "athlete_name": "Maria", "steps": { "import": "failed", "recalc": "skipped", "generate": "skipped", "send": "skipped" }, "error": "Strava token expired" }
      ]
    }
  ]
}
```

---

### 2.9 Relatórios

#### `POST /admin/athletes/{id}/reports/generate`
Gera relatório PDF.
```json
// Request
{ "report_type": "weekly", "period_start": "2026-04-21", "period_end": "2026-04-27" }
// Response 202 — processamento em background
{ "report_id": "uuid", "status": "generating" }
```

#### `GET /admin/athletes/{id}/reports/{report_id}/download`
Download do PDF gerado.
```
Response 200: application/pdf | 202: { "status": "generating" }
```

#### `POST /admin/athletes/{id}/reports/{report_id}/send`
Envia relatório por email ao atleta.
```json
// Response 200
{ "sent": true, "sent_to": "joao@email.com" }
```

---

### 2.10 Assinaturas

#### `GET /admin/athletes/{id}/subscription`
Status da assinatura.

#### `PUT /admin/athletes/{id}/subscription`
Atualiza status da assinatura.
```json
// Request
{ "action": "suspend" | "reactivate" | "cancel", "reason": "motivo opcional" }
```

#### `GET /admin/financials`
Visão financeira (MRR, clientes ativos, inadimplentes).

#### `POST /webhooks/stripe`
Webhook Stripe — events de pagamento.
```
Headers: Stripe-Signature
Events handled: payment_succeeded, payment_failed, subscription_cancelled
```

---

### 2.11 LGPD

#### `GET /lgpd/my-data`
Exporta todos os dados do atleta autenticado (ZIP).

#### `DELETE /lgpd/my-data`
Solicita exclusão de dados (processa em ≤ 72h).
```json
// Response 202
{ "request_id": "uuid", "deadline": "2026-05-03T10:00:00Z" }
```

#### `GET /lgpd/consent`
Status do consentimento LGPD.

#### `POST /lgpd/consent`
Registra consentimento.
```json
// Request
{ "consent_version": "1.0", "consented": true }
```

---

## 3. Estados de UI

### 3.1 Fluxo de Onboarding do Atleta

```
[Email recebido] → Clicar link → [Definir senha] → [Aceitar LGPD*] → [Completar perfil]
                                                                        ↓
                                                               [Conectar plataformas]
                                                                        ↓
                                                               [Dashboard (treino do dia)]

* LGPD: modal obrigatório, não pode fechar sem aceitar
```

### 3.2 App do Atleta — Páginas

| Rota | Componente Principal | Estados |
|------|---------------------|---------|
| `/` | Redirect para `/dashboard` ou `/login` | — |
| `/login` | LoginForm | idle / loading / error |
| `/onboarding` | OnboardingWizard (4 steps) | step 1-4 / submitting |
| `/dashboard` | DashboardPage | loading / loaded / error |
| `/workouts` | WorkoutList | loading / loaded / empty |
| `/workouts/[id]` | WorkoutDetail | loading / loaded / not-found |
| `/strength/new` | StrengthForm | idle / submitting / success |
| `/metrics` | MetricsPage | loading / form / history |
| `/training` | TrainingPlanPage | loading / has-plan / no-plan |
| `/settings` | SettingsPage | profile / integrations / lgpd |

### 3.3 Componentes com Estados Críticos

#### `DailyRecommendationCard`
```
States:
  loading       → skeleton loader
  no_plan       → "Gerando seu treino..." + spinner (polling 5s por até 60s)
  plan_ready    → card completo com tipo, título, seções expansíveis, nutrição
  error         → "Erro ao gerar treino" + botão "Tentar novamente"
  rest_day      → card especial verde com orientações de recuperação
```

#### `IntegrationStatus` (Settings)
```
States por provider:
  not_connected → botão "Conectar [Provider]"
  connecting    → loading após redirect OAuth
  connected     → ícone ✓ verde + "Última sync: Xh atrás" + botão "Desconectar"
  error         → ícone ✗ vermelho + "Falha na última sync" + botão "Reconectar"
```

#### `CTLATLTSBChart`
```
States:
  loading   → skeleton
  no_data   → "Sem dados suficientes (mín. 7 dias de treino)"
  loaded    → gráfico de linha triplo (CTL azul / ATL laranja / TSB verde-vermelho)
Controles: selector de período [30d | 60d | 90d]
Tooltip: hover mostra data + CTL + ATL + TSB + TSS do dia
```

#### `WorkoutOfTheDay` (Atleta)
```
sections — cada seção:
  collapsed   → nome + duração + intensidade (badge)
  expanded    → descrição completa + targets em watts/zona FC/RPE
```

### 3.4 Painel Admin — Páginas

| Rota | Componente Principal | Estados |
|------|---------------------|---------|
| `/admin` | Redirect para `/admin/dashboard` | — |
| `/admin/dashboard` | AdminDashboard | loading / loaded / alerts |
| `/admin/athletes` | AthleteList | loading / loaded / empty / filtered |
| `/admin/athletes/new` | AthleteCreateForm | idle / submitting / success |
| `/admin/athletes/[id]` | AthleteProfile | loading / loaded / tabs |
| `/admin/athletes/[id]/plan` | AthletePlanView | loading / has-plan / no-plan |
| `/admin/athletes/[id]/reports` | ReportsPage | loading / list / generating |
| `/admin/logs` | JobLogsPage | loading / loaded |
| `/admin/financials` | FinancialsPage | loading / loaded |
| `/admin/settings` | AdminSettings | — |

### 3.5 Cores de Status TSB (NFR visual — US-011, US-028)

| TSB | Cor | Label | Significado |
|-----|-----|-------|-------------|
| > +5 | Verde escuro `#16a34a` | Forma ótima | Atleta fresco, pronto para qualidade |
| -5 a +5 | Verde claro `#4ade80` | Boa forma | Treino moderado-alto |
| -20 a -5 | Amarelo `#facc15` | Carga normal | Acúmulo saudável |
| -25 a -20 | Laranja `#f97316` | Atenção | Monitorar recuperação |
| < -25 | Vermelho `#dc2626` | Risco | Overtraining — alerta admin |

### 3.6 Notificações / Alertas Admin

| Tipo | Trigger | Prioridade | Ação |
|------|---------|-----------|------|
| `overtraining_risk` | TSB < -25 | Crítico (vermelho) | Badge + item no topo do dashboard |
| `integration_failure` | ≥ 3 falhas consecutivas | Alto (laranja) | Badge + descrição técnica |
| `inactivity` | ≥ 5 dias sem treino | Médio (amarelo) | Item na lista de alertas |
| `job_not_run` | Job não executou em 30min após 06h | Crítico | Banner no topo do admin |
| `payment_failed` | Webhook Stripe `payment_failed` | Alto | Email ao admin + atleta |

---

## 4. Fluxos de Integração

### 4.1 Strava — Envio de Treino Planejado (OUTBOUND)
```
FitCoach gera plano
  → POST /api/workouts/create_planned (Strava API v3)
     body: { sport_type, name, description, start_date_local, elapsed_time, workout_type }
  → Strava retorna workout_id
  → Salvar strava_workout_id em ai_recommendations
  → Marcar sent_to_strava = true
```

### 4.2 Strava — Recebimento de Treino Executado (INBOUND)
```
Atleta conclui atividade (Garmin ou Strava diretamente)
  → Strava Webhook → POST /webhooks/strava
     { object_type: "activity", object_id: 123, aspect_type: "create" }
  → FitCoach busca detalhes: GET /activities/{id} (Strava API)
  → Parse → calcula TSS (potência ou TRIMP)
  → Salva em workouts (source: "strava" ou "garmin_relay")
  → Recalcula CTL/ATL/TSB do atleta
  → Agenda análise de adaptação para próximo job diário
```

### 4.3 Garmin Bidirecional (via Relay)
```
OUTBOUND: FitCoach → TrainingPeaks → Garmin
  FitCoach cria workout no TrainingPeaks (API)
    → TrainingPeaks sincroniza com Garmin Connect (nativo)
    → Aparece no dispositivo Garmin do atleta

INBOUND: Garmin → Strava → FitCoach
  Atleta treina com Garmin
    → Garmin Connect sincroniza com Strava (automático)
    → Strava Webhook notifica FitCoach
    → FitCoach processa atividade (source: "garmin_relay")
```

### 4.4 Apple Health — iOS Shortcut
```
1. Admin gera link de instalação do Shortcut para o atleta
   → GET /athletes/{id}/apple-health-shortcut-link
   → Gera link: https://www.icloud.com/shortcuts/... (template preenchido com token)

2. Atleta instala o Shortcut (1x) e configura como automação diária

3. Shortcut executa todo dia às 07h:
   → Coleta HealthKit: resting_hr, hrv, sleep_hours, sleep_quality, activities
   → POST /health/apple-health/{athlete_apple_health_token}
     { date, resting_hr, hrv_ms, sleep_hours, sleep_quality, activities: [...] }

4. FitCoach upsert em daily_metrics (source: "apple_health")
```

---

## 5. Fluxo do Job Diário

```
CRON: 06:00 BRT — execute_daily_job()

Para cada atleta ativo (paralelo, máx 10 concurrent):

  STEP 1 — IMPORT (timeout: 30s por atleta)
    ├── Strava: GET /athlete/activities?after=yesterday_unix
    │   └── Para cada atividade nova: parse + calcular TSS + salvar workouts
    ├── TrainingPeaks: polling GET /workouts?from=yesterday (se conectado)
    └── Apple Health: já foi recebido via webhook (não polling aqui)

  STEP 2 — RECALCULATE (timeout: 5s)
    ├── Buscar todos workouts dos últimos 90 dias do atleta
    ├── Calcular TSS de cada um (cycling: NP+FTP; hr: TRIMP; strength: formula)
    └── Recalcular série CTL/ATL/TSB → upsert training_load

  STEP 3 — GENERATE (timeout: 60s)
    ├── Montar AthleteContext (perfil + últimos 10 treinos + métricas + CTL/ATL/TSB)
    ├── Chamar Claude API (primary) ou GPT-4o (fallback)
    ├── Parse JSON da resposta
    ├── Gerar nutrition_plan junto (mesmo prompt ou segundo call)
    └── Salvar ai_recommendations + nutrition_plans

  STEP 4 — SEND (timeout: 30s)
    ├── Se Strava conectado: POST planned workout → salvar strava_workout_id
    ├── Se TrainingPeaks conectado: POST planned workout → salvar tp_workout_id
    └── Atualizar sent_to_strava / sent_to_trainingpeaks = true

  STEP 5 — LOG
    └── Salvar resultado em job_client_results
        { steps: { import, recalc, generate, send }, error, duration_ms }

Ao final: salvar job_execution_logs com totais de sucesso/falha
```

---

*Próxima fase: Spec Enricher (Fase 07) — edge cases, tratamento de erros, validações, segurança*
