"""
TrainingPeaks API client.

OAuth 2.0 flow (same pattern as Strava).
Bidirectional:
  - PUSH: send planned workout from AI recommendation → TP calendar → syncs to Garmin
  - PULL: poll completed workouts → import into FitCoach

API reference: https://developers.trainingpeaks.com/docs/
Base URL (sandbox): https://api.sandbox.trainingpeaks.com
Base URL (prod):    https://api.trainingpeaks.com
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta, date
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.utils.calculations import calculate_tss_cycling, calculate_tss_from_hr

logger = logging.getLogger(__name__)

# Switch between sandbox and production via environment
_TP_BASE = "https://api.trainingpeaks.com"
_TP_AUTH_URL  = "https://oauth.trainingpeaks.com/oauth/v2/token"
_TP_AUTHZ_URL = "https://oauth.trainingpeaks.com/oauth/v2/auth"

# TrainingPeaks → FitCoach sport mapping
_TP_SPORT_MAP: dict[str, str] = {
    "Bike":          "cycling",
    "Run":           "running",
    "Swim":          "swimming",
    "Multisport":    "triathlon",
    "Strength":      "strength",
    "Yoga":          "mobility",
    "Other":         "other",
}

# FitCoach workout_type → TrainingPeaks sport
_FC_TO_TP_SPORT: dict[str, str] = {
    "cycling_endurance":  "Bike",
    "cycling_threshold":  "Bike",
    "cycling_vo2max":     "Bike",
    "cycling_long":       "Bike",
    "running_easy":       "Run",
    "running_tempo":      "Run",
    "running_intervals":  "Run",
    "swimming_base":      "Swim",
    "swimming_intervals": "Swim",
    "strength_upper":     "Strength",
    "strength_lower":     "Strength",
    "strength_full":      "Strength",
    "strength_push":      "Strength",
    "strength_pull":      "Strength",
    "triathlon_brick":    "Multisport",
    "mobility":           "Yoga",
    "rest":               "Other",
}


class TPAPIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"TrainingPeaks API {status}: {message}")


class TrainingPeaksService:

    def get_authorization_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id":     settings.tp_client_id,
            "redirect_uri":  settings.tp_redirect_uri,
            "scope":         "workouts:write workouts:read athlete:read",
            "state":         state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{_TP_AUTHZ_URL}?{query}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    async def _post_token(self, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TP_AUTH_URL,
                data={**data, "client_id": settings.tp_client_id, "client_secret": settings.tp_client_secret},
            )
        if resp.status_code >= 400:
            raise TPAPIError(resp.status_code, resp.text[:200])
        return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    async def _request(self, method: str, path: str, access_token: str, **kwargs) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(
                method,
                f"{_TP_BASE}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
                **kwargs,
            )
        if resp.status_code == 401:
            raise TPAPIError(401, "Unauthorized — token expired")
        if resp.status_code >= 400:
            raise TPAPIError(resp.status_code, resp.text[:200])
        if resp.status_code == 204:
            return {}
        return resp.json()

    async def exchange_code_for_tokens(self, code: str) -> dict:
        return await self._post_token({
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": settings.tp_redirect_uri,
        })

    async def refresh_access_token(self, refresh_token: str) -> dict:
        return await self._post_token({
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
        })

    async def get_athlete(self, access_token: str) -> dict:
        return await self._request("GET", "/v1/athlete/profile", access_token)

    async def get_completed_workouts(
        self,
        access_token: str,
        athlete_id: str,
        from_date: date,
        to_date: date | None = None,
    ) -> list[dict]:
        """
        GET /v1/athletes/{athleteId}/workouts/{startDate}/{endDate}
        Returns list of completed workout objects.
        """
        end = (to_date or date.today()).isoformat()
        data = await self._request(
            "GET",
            f"/v1/athletes/{athlete_id}/workouts/{from_date.isoformat()}/{end}",
            access_token,
        )
        return data if isinstance(data, list) else []

    async def create_planned_workout(self, access_token: str, athlete_id: str, workout: dict) -> dict:
        """
        POST /v1/athletes/{athleteId}/workouts
        Creates a planned workout on the TP calendar.
        """
        return await self._request(
            "POST",
            f"/v1/athletes/{athlete_id}/workouts",
            access_token,
            json=workout,
        )

    async def delete_workout(self, access_token: str, workout_id: str) -> None:
        await self._request("DELETE", f"/v1/workouts/{workout_id}", access_token)

    # ── Converters ──────────────────────────────────────────────────────────

    def recommendation_to_tp_workout(
        self,
        rec_date: date,
        workout_type: str,
        title: str,
        structured_plan: dict,
        duration_minutes: int | None = None,
    ) -> dict:
        """
        Convert a FitCoach structured plan → TrainingPeaks planned workout format.
        https://developers.trainingpeaks.com/docs/workout-structure
        """
        sport = _FC_TO_TP_SPORT.get(workout_type, "Other")
        duration_s = (duration_minutes or structured_plan.get("duration_minutes") or 60) * 60

        # Build TP structure from sections
        steps = []
        for section in structured_plan.get("sections", []):
            step: dict = {
                "name":         section.get("name", ""),
                "length":       {"value": section.get("duration_minutes", 5) * 60, "unit": "second"},
                "targets":      [],
            }
            targets = section.get("targets", {})
            if targets.get("power_pct_ftp"):
                step["targets"].append({
                    "unit":    "percentOfFtp",
                    "minValue": max(0, targets["power_pct_ftp"] - 5),
                    "maxValue": targets["power_pct_ftp"] + 5,
                })
            elif targets.get("hr_zone"):
                step["targets"].append({
                    "unit":    "heartRateZone",
                    "minValue": targets["hr_zone"],
                    "maxValue": targets["hr_zone"],
                })
            steps.append(step)

        return {
            "title":       title,
            "athleteId":   None,  # filled by caller
            "workoutDay":  rec_date.isoformat(),
            "sport":       sport,
            "totalTime":   duration_s,
            "description": structured_plan.get("rationale", ""),
            "structure": {
                "primaryLengthMetric": "duration",
                "primaryIntensityMetric": "percentOfFtp" if sport == "Bike" else "heartRateZone",
                "steps": steps,
            } if steps else None,
        }

    def parse_tp_workout(self, tp_wkt: dict, athlete_id: str,
                         ftp: int | None = None, max_hr: int | None = None,
                         resting_hr: int | None = None) -> dict:
        """Convert a TP completed workout → FitCoach Workout dict."""
        sport = _TP_SPORT_MAP.get(tp_wkt.get("sport", "Other"), "other")
        start_str = tp_wkt.get("startTime") or tp_wkt.get("workoutDay", "")
        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except Exception:
            start_dt = datetime.now(timezone.utc)

        duration_s  = tp_wkt.get("totalTime")         # seconds
        np_watts    = tp_wkt.get("normalizedPower")
        avg_hr      = tp_wkt.get("averageHeartRate")
        tss: float | None = tp_wkt.get("tss") or tp_wkt.get("trainingStressScore")

        if not tss and np_watts and ftp and duration_s:
            try:
                tss = calculate_tss_cycling(int(duration_s), int(np_watts), ftp)
            except ValueError:
                pass
        if not tss and avg_hr and max_hr and resting_hr and duration_s:
            try:
                tss = calculate_tss_from_hr(int(duration_s), int(avg_hr), max_hr, resting_hr)
            except ValueError:
                pass

        return {
            "athlete_id":             athlete_id,
            "external_id":            f"tp_{tp_wkt.get('id', '')}",
            "source":                 "trainingpeaks",
            "sport_type":             sport,
            "title":                  tp_wkt.get("title"),
            "start_time":             start_dt,
            "duration_seconds":       int(duration_s) if duration_s else None,
            "distance_meters":        tp_wkt.get("distance"),
            "avg_heart_rate":         int(avg_hr) if avg_hr else None,
            "avg_power_watts":        tp_wkt.get("averagePower"),
            "normalized_power_watts": int(np_watts) if np_watts else None,
            "calories":               tp_wkt.get("calories"),
            "tss":                    tss,
            "raw_data":               {k: v for k, v in tp_wkt.items()},
            "is_completed":           True,
        }
