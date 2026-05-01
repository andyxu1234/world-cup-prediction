"""
World Cup Prediction API - Locust Load Test

Usage:
    # Basic run (Web UI)
    locust -f locustfile.py --host=http://localhost:8000

    # Headless mode (CI/CD)
    locust -f locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 -t 10m

    # Run specific user class only
    locust -f locustfile.py --host=http://localhost:8000 --tags read

    # Run with specific scenario
    locust -f locustfile.py --host=http://localhost:8000 --headless -u 200 -r 10 -t 15m --csv=results
"""

import random
from locust import HttpUser, task, between, tag


# Match ID range (project has ~104 matches)
MATCH_ID_RANGE = range(1, 105)


class BrowsingUser(HttpUser):
    """
    Typical user browsing the World Cup prediction app.
    Simulates: home page -> match list -> match detail -> predictions -> leaderboard.
    Excludes: fun-fact (external API), long-term-predictions (minimal data).
    Weight: 70% of total traffic.
    """
    wait_time = between(1, 5)  # Think time 1-5s
    weight = 7

    def on_start(self):
        """Fetch match list to get valid IDs for subsequent requests."""
        resp = self.client.get("/api/v1/matches", name="/matches [init]")
        if resp.status_code == 200:
            try:
                matches = resp.json()
                self.match_ids = [m["id"] for m in matches] if matches else list(MATCH_ID_RANGE)
            except Exception:
                self.match_ids = list(MATCH_ID_RANGE)
        else:
            self.match_ids = list(MATCH_ID_RANGE)

    @task(10)
    @tag("read", "home")
    def home_stats(self):
        """Home page hero statistics (cached 5min)."""
        self.client.get("/api/v1/matches/stats", name="/matches/stats")

    @task(8)
    @tag("read", "matches")
    def match_list(self):
        """Match list with various filters (cached 5min)."""
        params = random.choice([
            {},
            {"status": "upcoming"},
            {"status": "finished"},
            {"status": "live"},
        ])
        self.client.get("/api/v1/matches", params=params, name="/matches")

    @task(6)
    @tag("read", "match_detail")
    def match_detail(self):
        """Individual match detail with predictions (cached 5min)."""
        match_id = random.choice(self.match_ids)
        self.client.get(f"/api/v1/matches/{match_id}", name="/matches/[id]")

    @task(5)
    @tag("read", "predictions")
    def predictions_for_match(self):
        """AI predictions for a specific match (cached 10min)."""
        match_id = random.choice(self.match_ids)
        self.client.get(
            f"/api/v1/predictions/match/{match_id}",
            name="/predictions/match/[id]",
        )

    @task(4)
    @tag("read", "compare")
    def prediction_compare(self):
        """Prediction comparison view (cached 10min)."""
        match_id = random.choice(self.match_ids)
        self.client.get(
            f"/api/v1/predictions/compare/{match_id}",
            name="/predictions/compare/[id]",
        )

    @task(3)
    @tag("read", "leaderboard")
    def ai_leaderboard(self):
        """AI model leaderboard (cached 5min)."""
        self.client.get("/api/v1/leaderboard/ai", name="/leaderboard/ai")

    @task(2)
    @tag("read", "leaderboard")
    def human_leaderboard(self):
        """Human vs AI leaderboard (cached 5min)."""
        self.client.get("/api/v1/leaderboard/human", name="/leaderboard/human")

    @task(2)
    @tag("read", "fun")
    def face_slaps(self):
        """Face-slap collection: high-confidence wrong predictions (cached 10min)."""
        self.client.get("/api/v1/predictions/face-slaps", name="/predictions/face-slaps")



class ActiveUser(HttpUser):
    """
    Active user who browses AND votes on matches.
    Simulates: login -> browse -> vote -> check profile.
    Weight: 20% of total traffic.
    """
    wait_time = between(2, 8)  # Longer think time for write actions
    weight = 2

    def on_start(self):
        """Fetch matches and assign a test user identity."""
        resp = self.client.get("/api/v1/matches", name="/matches [init]")
        if resp.status_code == 200:
            try:
                matches = resp.json()
                self.match_ids = [m["id"] for m in matches] if matches else list(MATCH_ID_RANGE)
            except Exception:
                self.match_ids = list(MATCH_ID_RANGE)
        else:
            self.match_ids = list(MATCH_ID_RANGE)

        # Simulate a logged-in user (JWT not enforced, user_id via query param)
        self.user_id = random.randint(1, 200)

    @task(5)
    @tag("read", "match_detail")
    def match_detail(self):
        """View match detail before voting."""
        match_id = random.choice(self.match_ids)
        self.client.get(f"/api/v1/matches/{match_id}", name="/matches/[id]")

    @task(4)
    @tag("read", "leaderboard")
    def leaderboard(self):
        """Check leaderboard rankings."""
        self.client.get("/api/v1/leaderboard/ai", name="/leaderboard/ai")

    @task(2)
    @tag("read", "votes")
    def view_vote_history(self):
        """View personal vote history (cached 60s)."""
        self.client.get(
            "/api/v1/users/votes",
            params={"user_id": self.user_id, "limit": 10},
            name="/users/votes",
        )

    @task(1)
    @tag("read", "predictions")
    def predictions_for_match(self):
        """Check AI predictions before voting."""
        match_id = random.choice(self.match_ids)
        self.client.get(
            f"/api/v1/predictions/match/{match_id}",
            name="/predictions/match/[id]",
        )


class HealthCheckUser(HttpUser):
    """
    Minimal user for continuous health monitoring.
    Weight: 10% of total traffic.
    """
    wait_time = between(10, 30)  # Low frequency
    weight = 1

    @task
    @tag("health")
    def health_check(self):
        """Health check endpoint (no cache, always hits server)."""
        self.client.get("/health", name="/health")

