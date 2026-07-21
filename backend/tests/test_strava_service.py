"""
T04.5 — Strava service tests.
All external HTTP calls are mocked with httpx mock transport.
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

from app.services.strava_service import StravaService, get_valid_access_token
from app.utils.calculations import calculate_tss_cycling


# ── parse_activity_to_workout ─────────────────────────────────────────────────

class TestParseActivity:
    def _make_activity(self, **overrides) -> dict:
        base = {
            "id": 123456789,
            "name": "Morning Ride",
            "sport_type": "Ride",
            "start_date": "2024-01-15T07:30:00Z",
            "moving_time": 3600,
            "elapsed_time": 3700,
            "distance": 40000.0,
            "total_elevation_gain": 350.0,
            "average_heartrate": 145.0,
            "max_heartrate": 178.0,
            "average_watts": 195.0,
            "weighted_average_watts": 210.0,
            "max_watts": 520,
            "average_cadence": 88.5,
            "calories": 680,
            "description": "Easy endurance",
        }
        base.update(overrides)
        return base

    def test_basic_parse(self):
        svc = StravaService()
        activity = self._make_activity()
        result = svc.parse_activity_to_workout(activity, "athlete-1", ftp=250)
        assert result["external_id"] == "123456789"
        assert result["sport_type"] == "cycling"
        assert result["source"] == "strava"
        assert result["duration_seconds"] == 3600
        assert result["distance_meters"] == 40000.0
        assert result["avg_heart_rate"] == 145
        assert result["normalized_power_watts"] == 210

    def test_tss_calculated_with_power(self):
        svc = StravaService()
        activity = self._make_activity(weighted_average_watts=250, moving_time=3600)
        result = svc.parse_activity_to_workout(activity, "a1", ftp=250)
        expected = calculate_tss_cycling(3600, 250, 250)
        assert abs(result["tss"] - expected) < 0.01

    def test_tss_fallback_to_hr(self):
        svc = StravaService()
        activity = self._make_activity(weighted_average_watts=None, average_watts=None)
        result = svc.parse_activity_to_workout(activity, "a1", max_hr=185, resting_hr=55)
        assert result["tss"] is not None
        assert result["tss"] > 0

    def test_no_tss_without_context(self):
        svc = StravaService()
        activity = self._make_activity(weighted_average_watts=None, average_watts=None,
                                       average_heartrate=None)
        result = svc.parse_activity_to_workout(activity, "a1")
        assert result["tss"] is None

    def test_sport_type_mapping(self):
        svc = StravaService()
        mappings = [
            ("Ride", "cycling"), ("VirtualRide", "cycling"),
            ("Run", "running"), ("Swim", "swimming"),
            ("WeightTraining", "strength"), ("Hike", "other"),
        ]
        for strava_type, expected in mappings:
            activity = self._make_activity(sport_type=strava_type)
            result = svc.parse_activity_to_workout(activity, "a1")
            assert result["sport_type"] == expected, f"Failed for {strava_type}"

    def test_start_time_parsed_correctly(self):
        svc = StravaService()
        activity = self._make_activity(start_date="2024-06-15T14:30:00Z")
        result = svc.parse_activity_to_workout(activity, "a1")
        dt = result["start_time"]
        assert dt.year == 2024
        assert dt.month == 6
        assert dt.day == 15

    def test_intensity_factor_calculated(self):
        svc = StravaService()
        activity = self._make_activity(weighted_average_watts=250)
        result = svc.parse_activity_to_workout(activity, "a1", ftp=250)
        assert result["if_score"] == 1.0

    def test_garmin_relay_no_device_watts(self):
        # Garmin activities relayed via Strava have device_watts=False → use HR
        activity = self._make_activity(
            weighted_average_watts=None, average_watts=None,
            average_heartrate=155.0, max_heartrate=185.0,
        )
        svc = StravaService()
        result = svc.parse_activity_to_workout(activity, "a1", max_hr=185, resting_hr=55)
        # Should have a TSS from TRIMP
        assert result["tss"] is not None and result["tss"] > 0


# ── Authorization URL ─────────────────────────────────────────────────────────

class TestAuthorizationURL:
    def test_contains_client_id(self):
        svc = StravaService()
        url = svc.get_authorization_url("test-state")
        assert "client_id=" in url

    def test_contains_redirect_uri(self):
        svc = StravaService()
        url = svc.get_authorization_url("test-state")
        assert "redirect_uri=" in url

    def test_contains_state(self):
        svc = StravaService()
        url = svc.get_authorization_url("mystate")
        assert "state=mystate" in url

    def test_scope_includes_activity(self):
        svc = StravaService()
        url = svc.get_authorization_url("state")
        assert "activity%3Aread_all" in url or "activity:read_all" in url


# ── Token refresh ─────────────────────────────────────────────────────────────

class TestTokenRefresh:
    @pytest.mark.asyncio
    async def test_valid_token_returned_without_refresh(self, db_session):
        from app.models.athlete import PlatformConnection
        from app.utils.crypto import encrypt_token

        conn = MagicMock(spec=PlatformConnection)
        conn.access_token_enc = encrypt_token("valid-token")
        conn.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        conn.refresh_token_enc = encrypt_token("refresh-token")
        conn.id = uuid.uuid4()

        token = await get_valid_access_token(db_session, conn)
        assert token == "valid-token"

    @pytest.mark.asyncio
    async def test_expired_token_triggers_refresh(self, db_session):
        from app.models.athlete import PlatformConnection
        from app.utils.crypto import encrypt_token

        new_expires = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())
        fresh_token_response = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_at": new_expires,
        }

        conn = MagicMock(spec=PlatformConnection)
        conn.access_token_enc = encrypt_token("old-token")
        conn.refresh_token_enc = encrypt_token("refresh-token")
        conn.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # expired
        conn.id = uuid.uuid4()
        conn.consecutive_failures = 0
        conn.sync_error = None

        with patch(
            "app.services.strava_service._strava_service.refresh_access_token",
            new=AsyncMock(return_value=fresh_token_response),
        ):
            token = await get_valid_access_token(db_session, conn)

        assert token == "new-access-token"

    @pytest.mark.asyncio
    async def test_refresh_failure_increments_counter(self, db_session):
        from app.models.athlete import PlatformConnection
        from app.utils.crypto import encrypt_token

        conn = MagicMock(spec=PlatformConnection)
        conn.access_token_enc = encrypt_token("old-token")
        conn.refresh_token_enc = encrypt_token("refresh-token")
        conn.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        conn.id = uuid.uuid4()
        conn.consecutive_failures = 0
        conn.is_active = True
        conn.sync_error = None

        with patch(
            "app.services.strava_service._strava_service.refresh_access_token",
            new=AsyncMock(side_effect=Exception("Network error")),
        ):
            token = await get_valid_access_token(db_session, conn)

        assert token is None
        assert conn.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_three_failures_deactivates_connection(self, db_session):
        from app.models.athlete import PlatformConnection
        from app.utils.crypto import encrypt_token

        conn = MagicMock(spec=PlatformConnection)
        conn.access_token_enc = encrypt_token("old-token")
        conn.refresh_token_enc = encrypt_token("refresh-token")
        conn.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        conn.id = uuid.uuid4()
        conn.consecutive_failures = 2  # already 2 failures
        conn.is_active = True
        conn.sync_error = None

        with patch(
            "app.services.strava_service._strava_service.refresh_access_token",
            new=AsyncMock(side_effect=Exception("Persistent error")),
        ):
            token = await get_valid_access_token(db_session, conn)

        assert token is None
        assert conn.is_active is False


# ── Webhook HMAC verification ─────────────────────────────────────────────────

class TestWebhookHMAC:
    def test_valid_signature(self):
        import hashlib
        import hmac as _hmac
        from app.config import settings

        body = b'{"test": "payload"}'
        sig = _hmac.new(settings.strava_client_secret.encode(), body, hashlib.sha256).hexdigest()

        from app.routers.webhooks import _verify_strava_signature
        assert _verify_strava_signature(body, sig) is True

    def test_invalid_signature(self):
        from app.routers.webhooks import _verify_strava_signature
        assert _verify_strava_signature(b"body", "bad-signature") is False

    def test_empty_body_with_valid_sig(self):
        import hashlib
        import hmac as _hmac
        from app.config import settings
        from app.routers.webhooks import _verify_strava_signature

        body = b""
        sig = _hmac.new(settings.strava_client_secret.encode(), body, hashlib.sha256).hexdigest()
        assert _verify_strava_signature(body, sig) is True
