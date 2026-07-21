"""
Strava API v3 client.

OAuth flow:
  1. Redirect athlete → get_authorization_url()
  2. Strava POSTs code to callback → exchange_code_for_tokens()
  3. Save encrypted tokens in platform_connections
  4. Every call first checks expiry → get_valid_access_token() auto-refreshes
  5. Rate limit: 200 req/15min, 2000/day — tracked via response headers

Activity import:
  - Preferred: NP + FTP → TSS via power formula
  - Fallback:  avg_hr + max_hr + resting_hr → TSS via TRIMP
  - TSS already set by Strava (from power meter): use directly
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.models.athlete import Athlete, PlatformConnection
from app.models.workout import Workout
from app.utils.calculations import calculate_tss_cycling, calculate_tss_from_hr
from app.utils.crypto import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

STRAVA_BASE = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

# Rate-limit state (per-process; for multi-process use Redis)
_rate_15min = {"count": 0, "reset_at": 0.0}
_rate_daily  = {"count": 0, "reset_at": 0.0}


def _check_rate_limits(headers: dict) -> None:
    usage = headers.get("X-RateLimit-Usage", "")
    limit = headers.get("X-RateLimit-Limit", "")
    if usage and limit:
        parts = usage.split(",")
        limits = limit.split(",")
        if len(parts) == 2 and len(limits) == 2:
            fifteen, daily = int(parts[0]), int(parts[1])
            fifteen_lim, daily_lim = int(limits[0]), int(limits[1])
            if fifteen >= fifteen_lim * 0.9:
                logger.warning("Strava 15min rate limit near: %d/%d", fifteen, fifteen_lim)
            if daily >= daily_lim * 0.9:
                logger.warning("Strava daily rate limit near: %d/%d", daily, daily_lim)


class StravaAPIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"Strava API {status}: {message}")


class StravaRateLimitError(StravaAPIError):
    pass


# ── Main service ──────────────────────────────────────────────────────────────

class StravaService:
    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": settings.strava_client_id,
            "redirect_uri": settings.strava_redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "read,activity:read_all,profile:read_all",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{STRAVA_AUTH_URL}?{query}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    async def _post(self, url: str, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, data=data)
        if resp.status_code == 429:
            raise StravaRateLimitError(429, "Rate limit exceeded")
        if resp.status_code >= 400:
            raise StravaAPIError(resp.status_code, resp.text[:200])
        return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    async def _get(self, url: str, access_token: str, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params or {},
            )
        _check_rate_limits(dict(resp.headers))
        if resp.status_code == 429:
            raise StravaRateLimitError(429, "Rate limit exceeded")
        if resp.status_code == 401:
            raise StravaAPIError(401, "Unauthorized — token expired")
        if resp.status_code >= 400:
            raise StravaAPIError(resp.status_code, resp.text[:200])
        return resp.json()

    async def exchange_code_for_tokens(self, code: str) -> dict:
        return await self._post(STRAVA_TOKEN_URL, {
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "code": code,
            "grant_type": "authorization_code",
        })

    async def refresh_access_token(self, refresh_token: str) -> dict:
        return await self._post(STRAVA_TOKEN_URL, {
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })

    async def get_athlete(self, access_token: str) -> dict:
        return await self._get(f"{STRAVA_BASE}/athlete", access_token)

    async def get_activities(
        self,
        access_token: str,
        after: int | None = None,
        before: int | None = None,
        page: int = 1,
        per_page: int = 30,
    ) -> list[dict]:
        params: dict = {"page": page, "per_page": per_page}
        if after:  params["after"] = after
        if before: params["before"] = before
        result = await self._get(f"{STRAVA_BASE}/athlete/activities", access_token, params)
        return result if isinstance(result, list) else []

    async def get_activity_detail(self, access_token: str, activity_id: int) -> dict:
        return await self._get(f"{STRAVA_BASE}/activities/{activity_id}", access_token)

    async def get_athlete_zones(self, access_token: str) -> dict:
        return await self._get(f"{STRAVA_BASE}/athlete/zones", access_token)

    async def create_planned_workout(
        self,
        access_token: str,
        name: str,
        sport_type: str,
        planned_date: str,   # YYYY-MM-DD
        description: str = "",
        duration_seconds: int | None = None,
    ) -> dict:
        """
        POST /workouts — create a planned workout on Strava.
        sport_type: 'Ride', 'Run', 'Swim', 'WeightTraining', etc.
        """
        payload: dict = {
            "name":        name,
            "sport_type":  sport_type,
            "start_date_local": f"{planned_date}T08:00:00Z",
            "description": description,
            "status":      "Planned",
        }
        if duration_seconds:
            payload["elapsed_time"] = duration_seconds
        return await self._post(f"{STRAVA_BASE}/workouts", payload)

    def parse_activity_to_workout(self, activity: dict, athlete_id: str, ftp: int | None = None,
                                   max_hr: int | None = None, resting_hr: int | None = None) -> dict:
        """Convert Strava activity JSON → internal Workout dict."""
        sport_map = {
            "Ride": "cycling", "VirtualRide": "cycling", "EBikeRide": "cycling",
            "Run": "running", "VirtualRun": "running",
            "Swim": "swimming", "WeightTraining": "strength",
            "Workout": "other", "Hike": "other", "Walk": "other",
        }
        sport = sport_map.get(activity.get("sport_type", ""), "other")

        duration_s = activity.get("moving_time") or activity.get("elapsed_time")
        np_watts   = activity.get("weighted_average_watts")
        avg_watts  = activity.get("average_watts")
        avg_hr     = activity.get("average_heartrate")
        max_hr_act = activity.get("max_heartrate")

        # TSS calculation
        tss: float | None = None
        if np_watts and ftp and duration_s:
            try:
                tss = calculate_tss_cycling(duration_s, int(np_watts), ftp)
            except ValueError:
                pass
        elif avg_hr and max_hr and resting_hr and duration_s:
            try:
                tss = calculate_tss_from_hr(duration_s, int(avg_hr), max_hr, resting_hr)
            except ValueError:
                pass

        start_dt = datetime.fromisoformat(activity["start_date"].replace("Z", "+00:00"))

        return {
            "athlete_id": athlete_id,
            "external_id": str(activity["id"]),
            "source": "strava",
            "sport_type": sport,
            "title": activity.get("name"),
            "description": activity.get("description"),
            "start_time": start_dt,
            "duration_seconds": duration_s,
            "distance_meters": activity.get("distance"),
            "elevation_gain_meters": activity.get("total_elevation_gain"),
            "avg_heart_rate": int(avg_hr) if avg_hr else None,
            "max_heart_rate": int(max_hr_act) if max_hr_act else None,
            "avg_power_watts": int(avg_watts) if avg_watts else None,
            "normalized_power_watts": int(np_watts) if np_watts else None,
            "max_power_watts": activity.get("max_watts"),
            "avg_cadence": int(activity["average_cadence"]) if activity.get("average_cadence") else None,
            "calories": activity.get("calories"),
            "tss": tss,
            "if_score": round(np_watts / ftp, 3) if np_watts and ftp else None,
            "raw_data": {k: v for k, v in activity.items() if k not in ("map", "segment_efforts")},
            "is_completed": True,
        }

    async def sync_recent_activities(
        self,
        db: AsyncSession,
        athlete_id: str,
        access_token: str,
        days_back: int = 7,
        ftp: int | None = None,
        max_hr: int | None = None,
        resting_hr: int | None = None,
    ) -> list[str]:
        """
        Import recent Strava activities. Skips already-imported ones (external_id).
        Returns list of new workout IDs created.
        """
        after_ts = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
        page, imported = 1, []

        while True:
            activities = await self.get_activities(access_token, after=after_ts, page=page, per_page=50)
            if not activities:
                break

            for activity in activities:
                ext_id = str(activity["id"])
                # Check duplicate
                exists = await db.execute(
                    select(Workout).where(
                        Workout.athlete_id == athlete_id,
                        Workout.external_id == ext_id,
                    )
                )
                if exists.scalar_one_or_none():
                    continue

                wkt_data = self.parse_activity_to_workout(activity, athlete_id, ftp, max_hr, resting_hr)
                workout = Workout(**wkt_data)
                db.add(workout)
                await db.flush()
                imported.append(str(workout.id))

            if len(activities) < 50:
                break
            page += 1

        await db.commit()
        logger.info("Strava sync: %d new workouts for athlete %s", len(imported), athlete_id)
        return imported


# ── Token management helpers ──────────────────────────────────────────────────

_strava_service = StravaService()


async def get_valid_access_token(
    db: AsyncSession,
    connection: PlatformConnection,
) -> str | None:
    """
    Returns a valid access token for a platform connection.
    Auto-refreshes if expiry < 5 minutes. Marks connection inactive on failure.
    """
    if not connection.access_token_enc:
        return None

    now = datetime.now(timezone.utc)
    expires_at = connection.token_expires_at

    # Refresh if expired or expiring in < 5 min
    needs_refresh = (
        expires_at is None
        or expires_at.replace(tzinfo=timezone.utc) - now < timedelta(minutes=5)
    )

    if needs_refresh:
        if not connection.refresh_token_enc:
            logger.warning("No refresh token for connection %s", connection.id)
            connection.is_active = False
            connection.sync_error = "No refresh token available"
            db.add(connection)
            await db.commit()
            return None
        try:
            refresh_token = decrypt_token(connection.refresh_token_enc)
            new_tokens = await _strava_service.refresh_access_token(refresh_token)

            connection.access_token_enc = encrypt_token(new_tokens["access_token"])
            connection.refresh_token_enc = encrypt_token(new_tokens["refresh_token"])
            connection.token_expires_at = datetime.fromtimestamp(
                new_tokens["expires_at"], tz=timezone.utc
            )
            connection.consecutive_failures = 0
            connection.sync_error = None
            db.add(connection)
            await db.commit()
            logger.info("Strava token refreshed for connection %s", connection.id)
            return new_tokens["access_token"]

        except Exception as e:
            connection.consecutive_failures = (connection.consecutive_failures or 0) + 1
            connection.sync_error = str(e)[:255]
            if connection.consecutive_failures >= 3:
                connection.is_active = False
                logger.error(
                    "Strava connection %s deactivated after 3 consecutive failures: %s",
                    connection.id, e,
                )
            db.add(connection)
            await db.commit()
            return None

    return decrypt_token(connection.access_token_enc)
