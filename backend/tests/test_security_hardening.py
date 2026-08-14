from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPOSITORY_ROOT / "supabase/migrations/007_security_master_hardening.sql"


def _load_security_master():
    spec = spec_from_file_location(
        "fitcoach_security_master",
        REPOSITORY_ROOT / "scripts/security_master.py",
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rls_hardening_scopes_policies_to_authenticated():
    sql = MIGRATION.read_text(encoding="utf-8")
    for policy in (
        "admin_own_row",
        "admin_own_athletes",
        "athlete_own_row",
        "athlete_own_workouts",
        "athlete_own_strength",
        "athlete_own_metrics",
        "athlete_own_load",
        "athlete_own_recommendations",
        "athlete_own_consents",
        "admin_own_alerts",
        "admin_own_subscriptions",
    ):
        assert f'ALTER POLICY "{policy}"' in sql

    assert sql.count("TO authenticated") == 11
    assert sql.count("WITH CHECK") == 10


def test_server_only_tables_are_not_granted_to_browser_roles():
    sql = MIGRATION.read_text(encoding="utf-8")
    for table in (
        "platform_connections",
        "strength_exercises",
        "audit_logs",
        "lgpd_deletion_requests",
        "webhook_events",
    ):
        assert f"public.{table}" in sql
    assert "FROM anon, authenticated" in sql


def test_security_master_has_no_critical_static_finding():
    security_master = _load_security_master()
    report = security_master.build_report(REPOSITORY_ROOT)
    assert report["counts"]["critical"] == 0
