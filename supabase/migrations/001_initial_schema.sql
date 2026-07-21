-- ============================================================
-- FitCoach AI — Initial Schema
-- Run in Supabase SQL Editor before starting the backend
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ──────────────────────────────────────────────
-- ADMIN USERS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admin_users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID UNIQUE NOT NULL,           -- Supabase Auth UID
    name                VARCHAR(255) NOT NULL,
    email               VARCHAR(255) UNIQUE NOT NULL,
    crm                 VARCHAR(50),
    stripe_account_id   VARCHAR(255),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- ATHLETES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS athletes (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID UNIQUE NOT NULL,
    admin_id                UUID NOT NULL REFERENCES admin_users(id) ON DELETE RESTRICT,
    name                    VARCHAR(255) NOT NULL,
    email                   VARCHAR(255) UNIQUE NOT NULL,
    phone                   VARCHAR(30),
    birth_date              DATE,
    gender                  VARCHAR(20),
    height_cm               NUMERIC(5, 2),
    weight_kg               NUMERIC(5, 2),
    sport_modalities        TEXT[] DEFAULT '{}',
    primary_modality        VARCHAR(50),
    fitness_level           VARCHAR(20),
    goal                    TEXT,
    weekly_availability     JSONB,
    ftp_watts               INTEGER,
    max_hr                  INTEGER,
    resting_hr              INTEGER,
    anamnese_encrypted      TEXT,                       -- pgp_sym_encrypt result
    is_active               BOOLEAN DEFAULT TRUE,
    onboarding_complete     BOOLEAN DEFAULT FALSE,
    apple_health_token      UUID DEFAULT uuid_generate_v4(),
    auto_report_enabled     BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- PLATFORM CONNECTIONS (OAuth tokens)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS platform_connections (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id                  UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    provider                    VARCHAR(50) NOT NULL,   -- 'strava' | 'trainingpeaks' | 'garmin'
    provider_athlete_id         VARCHAR(255),
    access_token_enc            TEXT,                   -- AES-256 encrypted
    refresh_token_enc           TEXT,
    token_expires_at            TIMESTAMPTZ,
    scope                       TEXT,
    webhook_subscription_id     VARCHAR(255),
    is_active                   BOOLEAN DEFAULT TRUE,
    last_sync_at                TIMESTAMPTZ,
    sync_error                  TEXT,
    consecutive_failures        INTEGER DEFAULT 0,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, provider)
);

-- ──────────────────────────────────────────────
-- WORKOUTS (endurance: cycling, running, etc.)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workouts (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id                  UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    external_id                 VARCHAR(255),
    source                      VARCHAR(50) NOT NULL,   -- 'strava' | 'trainingpeaks' | 'manual' | 'planned'
    sport_type                  VARCHAR(50) NOT NULL,   -- 'cycling' | 'running' | 'swimming' | 'triathlon' | 'rest' | 'mobility'
    title                       VARCHAR(255),
    description                 TEXT,
    start_time                  TIMESTAMPTZ NOT NULL,
    duration_seconds            INTEGER,
    distance_meters             NUMERIC(10, 2),
    elevation_gain_meters       NUMERIC(8, 2),
    avg_heart_rate              INTEGER,
    max_heart_rate              INTEGER,
    avg_power_watts             INTEGER,
    normalized_power_watts      INTEGER,
    max_power_watts             INTEGER,
    avg_cadence                 INTEGER,
    calories                    INTEGER,
    tss                         NUMERIC(8, 2),
    if_score                    NUMERIC(5, 3),
    hr_zones                    JSONB,
    power_zones                 JSONB,
    raw_data                    JSONB,
    is_completed                BOOLEAN DEFAULT TRUE,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- STRENGTH SESSIONS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strength_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    session_date    DATE NOT NULL,
    session_type    VARCHAR(50),    -- 'upper' | 'lower' | 'full_body' | 'push' | 'pull' | 'legs'
    duration_minutes INTEGER,
    rpe_overall     INTEGER CHECK (rpe_overall BETWEEN 1 AND 10),
    notes           TEXT,
    tss             NUMERIC(8, 2),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strength_exercises (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES strength_sessions(id) ON DELETE CASCADE,
    exercise_name   VARCHAR(255) NOT NULL,
    sets            INTEGER NOT NULL,
    reps            INTEGER,
    duration_seconds INTEGER,
    load_kg         NUMERIC(6, 2),
    rpe             INTEGER CHECK (rpe BETWEEN 1 AND 10),
    notes           TEXT,
    exercise_order  INTEGER
);

-- ──────────────────────────────────────────────
-- DAILY HEALTH METRICS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_metrics (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id          UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    metric_date         DATE NOT NULL,
    weight_kg           NUMERIC(5, 2),
    sleep_hours         NUMERIC(4, 2),
    sleep_quality       INTEGER CHECK (sleep_quality BETWEEN 1 AND 10),
    hrv_ms              INTEGER,
    resting_hr          INTEGER,
    fatigue_score       INTEGER CHECK (fatigue_score BETWEEN 1 AND 10),
    muscle_soreness     INTEGER CHECK (muscle_soreness BETWEEN 1 AND 10),
    stress_score        INTEGER CHECK (stress_score BETWEEN 1 AND 10),
    motivation_score    INTEGER CHECK (motivation_score BETWEEN 1 AND 10),
    notes               TEXT,
    source              VARCHAR(50) DEFAULT 'manual',   -- 'manual' | 'apple_health' | 'garmin'
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, metric_date)
);

-- ──────────────────────────────────────────────
-- TRAINING LOAD (CTL / ATL / TSB)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS training_load (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id  UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    load_date   DATE NOT NULL,
    ctl         NUMERIC(8, 4),
    atl         NUMERIC(8, 4),
    tsb         NUMERIC(8, 4),
    daily_tss   NUMERIC(8, 2),
    weekly_tss  NUMERIC(8, 2),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, load_date)
);

-- ──────────────────────────────────────────────
-- AI RECOMMENDATIONS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id              UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    recommendation_date     DATE NOT NULL,
    ai_provider             VARCHAR(50) NOT NULL,
    ai_model                VARCHAR(100),
    workout_type            VARCHAR(50),
    title                   VARCHAR(255),
    recommendation_text     TEXT NOT NULL,
    structured_plan         JSONB,
    nutrition_plan          JSONB,
    rationale               TEXT,
    input_context           JSONB,
    feedback_rating         INTEGER CHECK (feedback_rating BETWEEN 1 AND 5),
    feedback_notes          TEXT,
    was_followed            BOOLEAN,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, recommendation_date)
);

-- ──────────────────────────────────────────────
-- ADMIN ALERTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admin_alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id        UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    athlete_id      UUID REFERENCES athletes(id) ON DELETE CASCADE,
    alert_type      VARCHAR(50) NOT NULL,   -- 'overreaching' | 'sync_failure' | 'no_metrics' | 'milestone'
    severity        VARCHAR(20) DEFAULT 'info',  -- 'info' | 'warning' | 'critical'
    title           VARCHAR(255) NOT NULL,
    body            TEXT,
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- LGPD — CONSENTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lgpd_consents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id          UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    consent_version     VARCHAR(20) NOT NULL,
    consented_at        TIMESTAMPTZ NOT NULL,
    ip_address          VARCHAR(45),
    user_agent          TEXT,
    revoked_at          TIMESTAMPTZ,
    revoke_reason       TEXT
);

-- ──────────────────────────────────────────────
-- LGPD — AUDIT LOGS (retention 1 year)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id        UUID NOT NULL,
    actor_type      VARCHAR(20) NOT NULL,   -- 'admin' | 'athlete' | 'system'
    action          VARCHAR(100) NOT NULL,
    resource_type   VARCHAR(50) NOT NULL,
    resource_id     UUID,
    ip_address      VARCHAR(45),
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- LGPD — DELETION REQUESTS (≤ 72h SLA)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lgpd_deletion_requests (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id                  UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    requested_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deadline                    TIMESTAMPTZ NOT NULL,
    executed_at                 TIMESTAMPTZ,
    status                      VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'executed'
    confirmation_email_sent     BOOLEAN DEFAULT FALSE
);

-- ──────────────────────────────────────────────
-- SUBSCRIPTIONS (Stripe)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id                UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    stripe_subscription_id  VARCHAR(255) UNIQUE,
    stripe_customer_id      VARCHAR(255),
    plan                    VARCHAR(50) NOT NULL,    -- 'starter' | 'pro' | 'elite'
    status                  VARCHAR(30) NOT NULL,   -- 'active' | 'past_due' | 'canceled' | 'trialing'
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    athlete_limit           INTEGER DEFAULT 5,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- WEBHOOK EVENTS (idempotency log)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS webhook_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider        VARCHAR(50) NOT NULL,
    event_id        VARCHAR(255) NOT NULL,
    event_type      VARCHAR(100),
    payload         JSONB,
    processed_at    TIMESTAMPTZ,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, event_id)
);

-- ──────────────────────────────────────────────
-- PERFORMANCE INDEXES
-- ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_athletes_admin ON athletes(admin_id);
CREATE INDEX IF NOT EXISTS idx_workouts_athlete_time ON workouts(athlete_id, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_workouts_external ON workouts(external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_strength_athlete_date ON strength_sessions(athlete_id, session_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_athlete_date ON daily_metrics(athlete_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_training_load_athlete_date ON training_load(athlete_id, load_date DESC);
CREATE INDEX IF NOT EXISTS idx_recommendations_athlete_date ON ai_recommendations(athlete_id, recommendation_date DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_alerts_admin ON admin_alerts(admin_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lgpd_consents_athlete ON lgpd_consents(athlete_id, revoked_at);

-- ──────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ──────────────────────────────────────────────
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE athletes ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE workouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE strength_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE strength_exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_load ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE lgpd_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE lgpd_deletion_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;

-- Admin sees their own row
CREATE POLICY "admin_own_row" ON admin_users FOR ALL
    USING (user_id = auth.uid());

-- Admin sees athletes they manage
CREATE POLICY "admin_own_athletes" ON athletes FOR ALL
    USING (admin_id IN (SELECT id FROM admin_users WHERE user_id = auth.uid()));

-- Athlete sees their own row
CREATE POLICY "athlete_own_row" ON athletes FOR SELECT
    USING (user_id = auth.uid());

-- All athlete-owned tables: access by the athlete themselves
CREATE POLICY "athlete_own_workouts" ON workouts FOR ALL
    USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

CREATE POLICY "athlete_own_strength" ON strength_sessions FOR ALL
    USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

CREATE POLICY "athlete_own_metrics" ON daily_metrics FOR ALL
    USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

CREATE POLICY "athlete_own_load" ON training_load FOR ALL
    USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

CREATE POLICY "athlete_own_recommendations" ON ai_recommendations FOR ALL
    USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

CREATE POLICY "athlete_own_consents" ON lgpd_consents FOR ALL
    USING (athlete_id IN (SELECT id FROM athletes WHERE user_id = auth.uid()));

-- Admin alerts visible to the owning admin
CREATE POLICY "admin_own_alerts" ON admin_alerts FOR ALL
    USING (admin_id IN (SELECT id FROM admin_users WHERE user_id = auth.uid()));

-- Subscriptions visible to the owning admin
CREATE POLICY "admin_own_subscriptions" ON subscriptions FOR ALL
    USING (admin_id IN (SELECT id FROM admin_users WHERE user_id = auth.uid()));

-- ──────────────────────────────────────────────
-- UPDATED_AT trigger helper
-- ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_admin_users_updated_at
    BEFORE UPDATE ON admin_users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_athletes_updated_at
    BEFORE UPDATE ON athletes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_platform_connections_updated_at
    BEFORE UPDATE ON platform_connections
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
