"""E2E tests: web dashboard health checks."""

import time

import pytest
import requests


@pytest.mark.e2e
@pytest.mark.live
class TestWebDashboard:
    def test_index_returns_html(self, web_base_url):
        r = requests.get(f"{web_base_url}/", timeout=10)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("Content-Type", "")

    def test_api_boards_structure(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/boards", timeout=10)
        assert r.status_code == 200
        data = r.json()
        for key in ("boards", "summary", "totals", "redis_ok", "timestamp"):
            assert key in data, f"Missing key '{key}' in /api/boards response"

    def test_api_boards_redis_ok(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/boards", timeout=10)
        data = r.json()
        assert data["redis_ok"] is True

    def test_api_boards_totals_non_negative(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/boards", timeout=10)
        data = r.json()
        totals = data["totals"]
        for key, val in totals.items():
            assert val >= 0, f"Total '{key}' is negative: {val}"

    def test_api_boards_timestamp_recent(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/boards", timeout=10)
        data = r.json()
        ts = data["timestamp"]
        now = time.time()
        assert abs(now - ts) < 60, f"Timestamp {ts} is not within 60s of now ({now})"

    def test_api_stats_summary(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/stats/summary", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "total_sessions" in data
        assert "total_denials" in data

    def test_api_stats_hourly(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/stats/hourly", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "hourly" in data

    def test_api_stats_users(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/stats/users", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "users" in data

    def test_api_stats_denials(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/stats/denials", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "denials" in data

    def test_api_boards_includes_config_reload_pending(self, web_base_url):
        r = requests.get(f"{web_base_url}/api/boards", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "config_reload_pending" in data, (
            "Missing 'config_reload_pending' key in /api/boards — "
            "live config reload feature may not be deployed"
        )
        assert isinstance(data["config_reload_pending"], bool)

    def test_api_config_reload_returns_ok(self, web_base_url):
        r = requests.post(f"{web_base_url}/api/config/reload", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True

    def test_api_config_reload_sets_pending_flag(self, web_base_url):
        """After posting to /api/config/reload, the boards API should reflect
        config_reload_pending=True until checkboards.py consumes it."""
        requests.post(f"{web_base_url}/api/config/reload", timeout=10)
        r = requests.get(f"{web_base_url}/api/boards", timeout=10)
        assert r.status_code == 200
        assert r.json()["config_reload_pending"] is True
