"""
Load test — FitCoach AI API
Simulates 20 concurrent athletes performing their daily app interactions.

Run:
  locust -f tests/locustfile.py --host http://localhost:8000 \
         --users 20 --spawn-rate 2 --run-time 60s --headless

Or for the daily job pipeline (admin POV):
  locust -f tests/locustfile.py --host http://localhost:8000 \
         -u 5 -r 1 -t 30s --headless --class-picker AdminUser

Prerequisites:
  - Backend running locally (uvicorn app.main:app --reload)
  - At least one admin account and seeded athletes in the DB
  - Set env vars: LOAD_TEST_ADMIN_TOKEN, LOAD_TEST_ATHLETE_TOKEN
"""

import os
import random

from locust import HttpUser, TaskSet, task, between, events


ADMIN_TOKEN  = os.getenv("LOAD_TEST_ADMIN_TOKEN", "")
ATHLETE_TOKEN = os.getenv("LOAD_TEST_ATHLETE_TOKEN", "")

ATHLETE_HEADERS = {"Authorization": f"Bearer {ATHLETE_TOKEN}"}
ADMIN_HEADERS   = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# ── Athlete task set ──────────────────────────────────────────────────────────

class AthleteSession(TaskSet):
    """Simulates a single athlete's typical daily app session."""

    @task(3)
    def get_dashboard_data(self):
        """Fetch all dashboard data in parallel (mirrors the frontend)."""
        self.client.get("/api/workouts/load/current", headers=ATHLETE_HEADERS,
                        name="GET /workouts/load/current")
        self.client.get("/api/workouts/stats/weekly", headers=ATHLETE_HEADERS,
                        name="GET /workouts/stats/weekly")

    @task(3)
    def get_today_recommendation(self):
        self.client.get("/api/recommendations/today", headers=ATHLETE_HEADERS,
                        name="GET /recommendations/today")

    @task(2)
    def get_recent_workouts(self):
        self.client.get("/api/workouts?per_page=10", headers=ATHLETE_HEADERS,
                        name="GET /workouts (list)")

    @task(2)
    def get_today_metrics(self):
        self.client.get("/api/metrics/today", headers=ATHLETE_HEADERS,
                        name="GET /metrics/today")

    @task(1)
    def post_daily_metrics(self):
        self.client.post(
            "/api/metrics",
            json={
                "metric_date": "2026-05-04",
                "sleep_hours": round(random.uniform(5.5, 9.0), 1),
                "sleep_quality": random.randint(4, 10),
                "fatigue_score": random.randint(1, 8),
                "motivation_score": random.randint(4, 10),
                "muscle_soreness": random.randint(1, 6),
            },
            headers=ATHLETE_HEADERS,
            name="POST /metrics",
        )

    @task(1)
    def get_load_history(self):
        self.client.get("/api/workouts/load?days=60", headers=ATHLETE_HEADERS,
                        name="GET /workouts/load (history)")

    @task(1)
    def health_check(self):
        self.client.get("/health", name="GET /health")


# ── Admin task set ────────────────────────────────────────────────────────────

class AdminSession(TaskSet):
    """Simulates an admin coach checking the dashboard and athlete statuses."""

    @task(3)
    def list_athletes(self):
        self.client.get("/api/admin/athletes?per_page=20", headers=ADMIN_HEADERS,
                        name="GET /admin/athletes")

    @task(2)
    def get_alerts(self):
        self.client.get("/api/admin/alerts?unread_only=true&limit=20", headers=ADMIN_HEADERS,
                        name="GET /admin/alerts")

    @task(1)
    def get_alerts_summary(self):
        self.client.get("/api/admin/alerts/summary", headers=ADMIN_HEADERS,
                        name="GET /admin/alerts/summary")

    @task(1)
    def get_billing_plan(self):
        self.client.get("/api/billing/plan", headers=ADMIN_HEADERS,
                        name="GET /billing/plan")

    @task(1)
    def health_check(self):
        self.client.get("/health", name="GET /health")


# ── User classes ──────────────────────────────────────────────────────────────

class AthleteUser(HttpUser):
    """Simulates one concurrent athlete. Target: 20 simultaneous athletes."""
    tasks = [AthleteSession]
    wait_time = between(1, 4)


class AdminUser(HttpUser):
    """Simulates an admin coach. Target: 2-5 simultaneous admins."""
    tasks = [AdminSession]
    wait_time = between(2, 8)


# ── Event hooks ───────────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    if not ATHLETE_TOKEN:
        print("\n⚠️  LOAD_TEST_ATHLETE_TOKEN not set — requests will return 401/403")
    if not ADMIN_TOKEN:
        print("⚠️  LOAD_TEST_ADMIN_TOKEN not set — admin requests will fail\n")
