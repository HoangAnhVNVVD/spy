"""Regression tests verifying audit fixes and edge cases.

Covers:
1. Single-snapshot interval retention (preventing silent activity drop).
2. Screen lock transitions treated as idle/locked state.
3. Full-day date_to filtering (preventing exclusion of current day's activities).
4. Timezone normalization and UTC 'Z' output format.
5. Productivity score calculated on active duration rather than penalized by idle time.
6. Privacy engine Vietnamese incognito & JWT token redactions.
7. Client config unknown key resilience.
8. Expanded process categorizer mappings (node, python, wsl, zalo, wps).
"""

from datetime import datetime, timezone
import pytest
from client.buffer import ActivityBuffer, ActivityEvent
from client.config import ClientConfig, PrivacySettings
from client.privacy import PrivacyEngine
from client.tracker import ActivityTracker
from client.win32_monitor import WindowActivityInfo
from server.categorizer import classify_activity


def test_tracker_single_snapshot_interval_retained(activity_buffer, test_client_config):
    """
    Critical fix verification:
    If an app is sampled once at t=0 and switched at t=3.0, it must NOT be
    discarded as 0 duration.
    """
    test_client_config.min_duration_seconds = 1.0
    tracker = ActivityTracker(config=test_client_config, buffer=activity_buffer)

    t0 = 10000.0
    # Single snapshot in App A
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="appA.exe",
            window_title="Document A",
            pid=10,
            hwnd=20,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0,
        )
    )

    # 3.5 seconds later, user switches to App B
    flushed = tracker.process_snapshot(
        WindowActivityInfo(
            process_name="appB.exe",
            window_title="Document B",
            pid=30,
            hwnd=40,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0 + 3.5,
        )
    )

    assert flushed is not None, "Single snapshot activity before switch must be retained"
    assert flushed.process_name == "appA.exe"
    assert flushed.duration_seconds == 3.5
    assert activity_buffer.get_stats()["total_records"] == 1


def test_tracker_screen_lock_treated_as_idle(activity_buffer, test_client_config):
    """
    When Windows locks (lockapp.exe or logonui.exe), the tracker must record it
    as idle rather than active productive time.
    """
    test_client_config.min_duration_seconds = 1.0
    tracker = ActivityTracker(config=test_client_config, buffer=activity_buffer)

    t0 = 20000.0
    # Active in code
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="code.exe",
            window_title="editor",
            pid=1,
            hwnd=2,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0,
        )
    )

    # Switch to lock screen
    flushed_active = tracker.process_snapshot(
        WindowActivityInfo(
            process_name="lockapp.exe",
            window_title="Windows Default Lock Screen",
            pid=99,
            hwnd=100,
            idle_seconds=10.0,
            is_idle=False,
            timestamp=t0 + 5.0,
        )
    )
    assert flushed_active is not None
    assert flushed_active.process_name == "code.exe"
    assert flushed_active.duration_seconds == 5.0

    # User returns 120 seconds later
    flushed_lock = tracker.process_snapshot(
        WindowActivityInfo(
            process_name="code.exe",
            window_title="editor",
            pid=1,
            hwnd=2,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0 + 125.0,
        )
    )
    assert flushed_lock is not None
    assert flushed_lock.is_idle is True
    assert flushed_lock.process_name == "idle"
    assert flushed_lock.duration_seconds == 120.0


def test_server_date_to_includes_full_day(api_client):
    """
    Verify that date_to='YYYY-MM-DD' covers the entire day up to 23:59:59.
    """
    auth_header = {"Authorization": "Bearer test-secret-token"}
    payload = {
        "client_id": "date-range-client",
        "activities": [
            {
                "start_time": "2026-10-06T15:30:00Z",
                "end_time": "2026-10-06T16:00:00Z",
                "duration_seconds": 1800.0,
                "process_name": "code.exe",
                "window_title": "Project Coding",
                "is_idle": False,
            }
        ],
    }
    api_client.post("/api/v1/activities/batch", json=payload, headers=auth_header)

    # Query with date_to as date only
    res_list = api_client.get(
        "/api/v1/activities",
        params={"client_id": "date-range-client", "date_to": "2026-10-06"},
    )
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 1
    assert items[0]["start_time"].endswith("Z")

    # Query summary for that exact day
    res_summary = api_client.get(
        "/api/v1/analytics/summary",
        params={
            "client_id": "date-range-client",
            "date_from": "2026-10-06",
            "date_to": "2026-10-06",
        },
    )
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["total_tracked_seconds"] == 1800.0
    assert summary["active_seconds"] == 1800.0

    # Query timeline for that exact day
    res_timeline = api_client.get(
        "/api/v1/analytics/timeline",
        params={
            "client_id": "date-range-client",
            "date_from": "2026-10-06",
            "date_to": "2026-10-06",
        },
    )
    assert res_timeline.status_code == 200
    assert len(res_timeline.json()) >= 1


def test_productivity_score_calculated_on_active_time(api_client):
    """
    Productivity score should measure the proportion of active time spent productively,
    not penalize the user for stepping away (idle time).
    """
    auth_header = {"Authorization": "Bearer test-secret-token"}
    payload = {
        "client_id": "prod-score-client",
        "activities": [
            {
                "start_time": "2026-10-06T08:00:00Z",
                "end_time": "2026-10-06T09:00:00Z",
                "duration_seconds": 3600.0,
                "process_name": "code.exe",
                "window_title": "Active development",
                "is_idle": False,
            },
            {
                "start_time": "2026-10-06T09:00:00Z",
                "end_time": "2026-10-06T12:00:00Z",
                "duration_seconds": 10800.0,
                "process_name": "idle",
                "window_title": "Idle / Away",
                "is_idle": True,
            },
        ],
    }
    api_client.post("/api/v1/activities/batch", json=payload, headers=auth_header)

    res = api_client.get("/api/v1/analytics/summary", params={"client_id": "prod-score-client"})
    assert res.status_code == 200
    data = res.json()
    assert data["active_seconds"] == 3600.0
    assert data["idle_seconds"] == 10800.0
    assert data["total_tracked_seconds"] == 14400.0
    # User was in Development for 100% of their ACTIVE time
    assert data["productivity_score"] == 100.0


def test_privacy_vietnamese_incognito_and_jwt_and_amex():
    """
    Test Vietnamese incognito browsing, JWT token strings, and Amex credit cards.
    """
    settings = PrivacySettings()
    engine = PrivacyEngine(settings)

    # Vietnamese incognito title
    title_vn = "Trang tìm kiếm - Cửa sổ ẩn danh - Google Chrome"
    sanitized_vn, red_vn = engine.sanitize_title(title_vn, "chrome.exe")
    assert red_vn is True
    assert sanitized_vn == "[Private Browsing]"

    # JWT Token in title
    jwt_title = "API Tester - eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc1234 - Postman"
    sanitized_jwt, red_jwt = engine.sanitize_title(jwt_title, "postman.exe")
    assert red_jwt is True
    assert "[REDACTED]" in sanitized_jwt
    assert "eyJhbGci" not in sanitized_jwt

    # Amex card (4-6-5 format)
    amex_title = "Checkout with Amex 3782 822463 10005 complete"
    sanitized_amex, red_amex = engine.sanitize_title(amex_title, "chrome.exe")
    assert red_amex is True
    assert "[REDACTED]" in sanitized_amex
    assert "3782" not in sanitized_amex


def test_config_ignores_unknown_keys():
    """
    Ensure ClientConfig.from_dict gracefully filters out unknown keys without crashing.
    """
    raw_data = {
        "server_url": "http://custom-server:9000",
        "api_token": "token123",
        "unrecognized_field_v2": 42,
        "privacy": {
            "mask_all_titles": True,
            "experimental_flag": False,
        },
    }
    cfg = ClientConfig.from_dict(raw_data)
    assert cfg.server_url == "http://custom-server:9000"
    assert cfg.api_token == "token123"
    assert cfg.privacy.mask_all_titles is True


def test_expanded_categorizer_tools():
    """
    Ensure newly added tools (python, node, wsl, zalo, wps) are correctly categorized.
    """
    assert classify_activity("python.exe", "script.py", False) == "Development"
    assert classify_activity("node.exe", "server.js", False) == "Development"
    assert classify_activity("wsl.exe", "bash", False) == "Development"
    assert classify_activity("zalo.exe", "Chat", False) == "Communication"
    assert classify_activity("wps.exe", "Report.docx", False) == "Productivity & Office"
