-- ============================================================
-- FitCoach AI — Migration 002 (Sprints 08–11)
-- Run AFTER 001_initial_schema.sql
-- ============================================================

-- ── Sprint 09: Push Notification subscriptions ────────────────────────────────
-- Stores Web Push subscriptions as JSONB array per athlete.
-- Array element schema: {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}
ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS push_subscriptions JSONB DEFAULT '[]'::jsonb;

-- ── Sprint 11: Trial subscription auto-creation ───────────────────────────────
-- Create a default trial subscription for every existing admin that doesn't have one yet.
INSERT INTO subscriptions (admin_id, plan, status, athlete_limit)
SELECT id, 'trial', 'trialing', 3
FROM admin_users
WHERE id NOT IN (SELECT admin_id FROM subscriptions)
ON CONFLICT DO NOTHING;

-- ── Sprint 08: Alert type extension ──────────────────────────────────────────
-- The alert_type column already exists (from 001). No schema change needed.
-- Adding a partial index for fast unread alert lookups per admin:
CREATE INDEX IF NOT EXISTS idx_admin_alerts_unread
  ON admin_alerts(admin_id, severity, created_at DESC)
  WHERE is_read = FALSE;

-- ── Sprint 10: Webhook events index ──────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_webhook_events_provider_id
  ON webhook_events(provider, event_id);

-- ── Sprint 11: Subscription index ────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_sub
  ON subscriptions(stripe_subscription_id)
  WHERE stripe_subscription_id IS NOT NULL;

-- ── Housekeeping: update RLS for new subscriptions rows ──────────────────────
-- The existing policy "admin_own_subscriptions" already covers rows
-- inserted by this migration because they reference admin_users.id.
-- No additional policy changes needed.

-- ── Verify migration ─────────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'athletes' AND column_name = 'push_subscriptions'
  ) THEN
    RAISE EXCEPTION 'Migration 002 failed: push_subscriptions column not found';
  END IF;
  RAISE NOTICE 'Migration 002 applied successfully.';
END $$;
