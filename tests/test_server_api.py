"""Unit and integration tests for FastAPI backend routes."""

from datetime import datetime, timezone


def test_health_check_endpoints(api_client):
    r1 = api_client.get("/health")
    assert r1.status_code == 200
    assert r1.json()["status"] == "ok"
    assert r1.json()["database"] == "ok"

    r2 = api_client.get("/api/v1/health")
    assert r2.status_code == 200
    assert r2.json()["status"] == "ok"


def test_batch_ingest_auth(api_client):
    payload = {
        "client_id": "laptop-1",
        "activities": [
            {
                "start_time": "2026-10-06T08:00:00Z",
                "end_time": "2026-10-06T08:05:00Z",
                "duration_seconds": 300.0,
                "process_name": "code.exe",
                "window_title": "test.py",
                "is_idle": False,
            }
        ],
    }

    # Missing auth
    res_no_auth = api_client.post("/api/v1/activities/batch", json=payload)
    assert res_no_auth.status_code == 401

    # Invalid token
    res_bad_auth = api_client.post(
        "/api/v1/activities/batch",
        json=payload,
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert res_bad_auth.status_code == 401

    # Valid token
    res_ok = api_client.post(
        "/api/v1/activities/batch",
        json=payload,
        headers={"Authorization": "Bearer test-secret-token"},
    )
    assert res_ok.status_code == 201
    data = res_ok.json()
    assert data["status"] == "success"
    assert data["count"] == 1
    assert data["client_id"] == "laptop-1"


def test_batch_ingest_and_auto_categorization(api_client):
    auth_header = {"Authorization": "Bearer test-secret-token"}
    payload = {
        "client_id": "workstation-1",
        "activities": [
            {
                "start_time": "2026-10-06T09:00:00Z",
                "end_time": "2026-10-06T09:30:00Z",
                "duration_seconds": 1800.0,
                "process_name": "cursor.exe",
                "window_title": "Building React components",
                "is_idle": False,
            },
            {
                "start_time": "2026-10-06T09:30:00Z",
                "end_time": "2026-10-06T09:45:00Z",
                "duration_seconds": 900.0,
                "process_name": "slack.exe",
                "window_title": "#engineering - Slack",
                "is_idle": False,
            },
            {
                "start_time": "2026-10-06T09:45:00Z",
                "end_time": "2026-10-06T10:00:00Z",
                "duration_seconds": 900.0,
                "process_name": "idle",
                "window_title": "Idle / Away",
                "is_idle": True,
            },
        ],
    }

    res = api_client.post("/api/v1/activities/batch", json=payload, headers=auth_header)
    assert res.status_code == 201
    assert res.json()["count"] == 3

    # Fetch activities list
    res_list = api_client.get("/api/v1/activities?client_id=workstation-1")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 3

    cats = {item["process_name"]: item["category"] for item in items}
    assert cats["cursor.exe"] == "Development"
    assert cats["slack.exe"] == "Communication"
    assert cats["idle"] == "Idle / Away"


def test_activities_filtering_and_search(api_client):
    auth_header = {"Authorization": "Bearer test-secret-token"}
    payload = {
        "client_id": "filter-test",
        "activities": [
            {
                "start_time": "2026-10-06T10:00:00Z",
                "end_time": "2026-10-06T10:10:00Z",
                "duration_seconds": 600.0,
                "process_name": "chrome.exe",
                "window_title": "Stack Overflow - Python query",
                "is_idle": False,
            },
            {
                "start_time": "2026-10-06T10:10:00Z",
                "end_time": "2026-10-06T10:20:00Z",
                "duration_seconds": 600.0,
                "process_name": "spotify.exe",
                "window_title": "Lo-Fi Beats for Coding",
                "is_idle": False,
            },
        ],
    }
    api_client.post("/api/v1/activities/batch", json=payload, headers=auth_header)

    # Search filter
    res_search = api_client.get("/api/v1/activities", params={"client_id": "filter-test", "search": "Stack"})
    assert res_search.status_code == 200
    items = res_search.json()["items"]
    assert len(items) == 1
    assert items[0]["process_name"] == "chrome.exe"

    # Category filter with params dict for proper URL escaping
    res_cat = api_client.get("/api/v1/activities", params={"client_id": "filter-test", "category": "Design & Media"})
    assert res_cat.status_code == 200
    items_cat = res_cat.json()["items"]
    assert len(items_cat) == 1
    assert items_cat[0]["process_name"] == "spotify.exe"


def test_analytics_summary_and_timeline(api_client):
    auth_header = {"Authorization": "Bearer test-secret-token"}
    payload = {
        "client_id": "analytics-client",
        "activities": [
            {
                "start_time": "2026-10-06T11:00:00Z",
                "end_time": "2026-10-06T12:00:00Z",
                "duration_seconds": 3600.0,
                "process_name": "code.exe",
                "window_title": "Visual Studio Code",
                "is_idle": False,
            },
            {
                "start_time": "2026-10-06T12:00:00Z",
                "end_time": "2026-10-06T12:30:00Z",
                "duration_seconds": 1800.0,
                "process_name": "idle",
                "window_title": "Idle / Away",
                "is_idle": True,
            },
        ],
    }
    api_client.post("/api/v1/activities/batch", json=payload, headers=auth_header)

    # Summary
    res = api_client.get("/api/v1/analytics/summary", params={"client_id": "analytics-client"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_tracked_seconds"] == 5400.0
    assert data["active_seconds"] == 3600.0
    assert data["idle_seconds"] == 1800.0
    assert data["formatted_active_time"] == "1h 00m"
    assert data["formatted_idle_time"] == "30m 00s"
    assert len(data["top_apps"]) >= 1
    assert data["top_apps"][0]["process_name"] == "code.exe"

    # Timeline
    res_tl = api_client.get("/api/v1/analytics/timeline", params={"client_id": "analytics-client", "date_from": "2026-10-06T00:00:00"})
    assert res_tl.status_code == 200
    timeline = res_tl.json()
    assert len(timeline) >= 1


def test_multi_machine_isolation(api_client):
    auth_header = {"Authorization": "Bearer test-secret-token"}

    # Ingest machine A
    payload_a = {
        "client_id": "MACHINE-A",
        "activities": [
            {
                "start_time": "2026-10-06T14:00:00Z",
                "end_time": "2026-10-06T14:30:00Z",
                "duration_seconds": 1800.0,
                "process_name": "pycharm64.exe",
                "window_title": "Project Alpha",
                "is_idle": False,
            }
        ],
        "open_tasks": [
            {
                "process_name": "pycharm64.exe",
                "window_title": "Project Alpha",
                "pid": 1111,
                "is_focused": True,
            }
        ],
    }
    r_a = api_client.post("/api/v1/activities/batch", json=payload_a, headers=auth_header)
    assert r_a.status_code == 201

    # Ingest machine B
    payload_b = {
        "client_id": "MACHINE-B",
        "activities": [
            {
                "start_time": "2026-10-06T15:00:00Z",
                "end_time": "2026-10-06T15:45:00Z",
                "duration_seconds": 2700.0,
                "process_name": "excel.exe",
                "window_title": "Financial Report.xlsx",
                "is_idle": False,
            }
        ],
        "open_tasks": [
            {
                "process_name": "excel.exe",
                "window_title": "Financial Report.xlsx",
                "pid": 2222,
                "is_focused": True,
            }
        ],
    }
    r_b = api_client.post("/api/v1/activities/batch", json=payload_b, headers=auth_header)
    assert r_b.status_code == 201

    # Isolated summary for MACHINE-A
    sum_a = api_client.get("/api/v1/analytics/summary", params={"client_id": "MACHINE-A"}).json()
    assert sum_a["active_seconds"] == 1800.0
    assert len(sum_a["top_apps"]) == 1
    assert sum_a["top_apps"][0]["process_name"] == "pycharm64.exe"

    # Isolated summary for MACHINE-B
    sum_b = api_client.get("/api/v1/analytics/summary", params={"client_id": "MACHINE-B"}).json()
    assert sum_b["active_seconds"] == 2700.0
    assert len(sum_b["top_apps"]) == 1
    assert sum_b["top_apps"][0]["process_name"] == "excel.exe"

    # Isolated live tasks for MACHINE-A
    live_a = api_client.get("/api/v1/machines/MACHINE-A/live").json()
    assert live_a["client_id"] == "MACHINE-A"
    assert live_a["tasks"][0]["process_name"] == "pycharm64.exe"

    # Isolated live tasks for MACHINE-B
    live_b = api_client.get("/api/v1/machines/MACHINE-B/live").json()
    assert live_b["client_id"] == "MACHINE-B"
    assert live_b["tasks"][0]["process_name"] == "excel.exe"

