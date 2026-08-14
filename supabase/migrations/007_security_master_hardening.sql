-- Security Master: harden Supabase Data API access and existing RLS policies.
-- Applies after 001_initial_schema.sql. This project uses a backend/BFF for data
-- access; the revoke section protects tables that must never be reached directly
-- by browser clients. The service role remains server-only.

BEGIN;

-- Keep RLS explicit for every table that contains application data.
ALTER TABLE public.admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.athletes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strength_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strength_exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_load ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lgpd_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lgpd_deletion_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_events ENABLE ROW LEVEL SECURITY;

-- Existing policies were defaulted to PUBLIC. Scope them explicitly to authenticated
-- requests and state WITH CHECK for every write-capable policy. PostgreSQL would
-- otherwise reuse USING, but an explicit policy makes review and future changes safer.
ALTER POLICY "admin_own_row" ON public.admin_users
  TO authenticated
  USING ((select auth.uid()) = user_id)
  WITH CHECK ((select auth.uid()) = user_id);

ALTER POLICY "admin_own_athletes" ON public.athletes
  TO authenticated
  USING (
    admin_id IN (
      SELECT id FROM public.admin_users
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    admin_id IN (
      SELECT id FROM public.admin_users
      WHERE user_id = (select auth.uid())
    )
  );

ALTER POLICY "athlete_own_row" ON public.athletes
  TO authenticated
  USING ((select auth.uid()) = user_id);

ALTER POLICY "athlete_own_workouts" ON public.workouts
  TO authenticated
  USING (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  );

ALTER POLICY "athlete_own_strength" ON public.strength_sessions
  TO authenticated
  USING (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  );

ALTER POLICY "athlete_own_metrics" ON public.daily_metrics
  TO authenticated
  USING (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  );

ALTER POLICY "athlete_own_load" ON public.training_load
  TO authenticated
  USING (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  );

ALTER POLICY "athlete_own_recommendations" ON public.ai_recommendations
  TO authenticated
  USING (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  );

ALTER POLICY "athlete_own_consents" ON public.lgpd_consents
  TO authenticated
  USING (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    athlete_id IN (
      SELECT id FROM public.athletes
      WHERE user_id = (select auth.uid())
    )
  );

ALTER POLICY "admin_own_alerts" ON public.admin_alerts
  TO authenticated
  USING (
    admin_id IN (
      SELECT id FROM public.admin_users
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    admin_id IN (
      SELECT id FROM public.admin_users
      WHERE user_id = (select auth.uid())
    )
  );

ALTER POLICY "admin_own_subscriptions" ON public.subscriptions
  TO authenticated
  USING (
    admin_id IN (
      SELECT id FROM public.admin_users
      WHERE user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    admin_id IN (
      SELECT id FROM public.admin_users
      WHERE user_id = (select auth.uid())
    )
  );

-- These tables are used exclusively by trusted backend code. RLS already defaults
-- to deny because no client policy exists; revoking Data API grants adds a second
-- barrier against accidental browser access.
REVOKE ALL PRIVILEGES ON TABLE
  public.platform_connections,
  public.strength_exercises,
  public.audit_logs,
  public.lgpd_deletion_requests,
  public.webhook_events
FROM anon, authenticated;

COMMIT;
