"""Unit tests for machine-specific partitioned disk storage."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.machine_storage import MachineStorageManager


@pytest.fixture
def temp_storage(tmp_path: Path):
    return MachineStorageManager(base_dir=tmp_path / "machines")


def test_machine_storage_partitioning(temp_storage: MachineStorageManager):
    client_id_1 = "DESKTOP-PC1"
    client_id_2 = "LAPTOP-OFFICE_2"

    activities_1 = [
        {
            "client_id": client_id_1,
            "start_time": "2026-10-06T19:00:00Z",
            "end_time": "2026-10-06T19:05:00Z",
            "duration_seconds": 300.0,
            "process_name": "code.exe",
            "window_title": "app.py - Visual Studio Code",
            "category": "Development",
            "is_idle": False,
        }
    ]

    activities_2 = [
        {
            "client_id": client_id_2,
            "start_time": "2026-10-06T19:10:00Z",
            "end_time": "2026-10-06T19:12:00Z",
            "duration_seconds": 120.0,
            "process_name": "excel.exe",
            "window_title": "Budget.xlsx",
            "category": "Productivity",
            "is_idle": False,
        }
    ]

    temp_storage.record_activities(client_id_1, activities_1, client_ip="192.168.1.50")
    temp_storage.record_activities(client_id_2, activities_2, client_ip="192.168.1.60")

    # Verify dedicated directories exist
    dir1 = temp_storage.get_machine_dir(client_id_1)
    dir2 = temp_storage.get_machine_dir(client_id_2)

    assert dir1.exists()
    assert dir2.exists()
    assert dir1 != dir2

    # Check machine 1 files
    jsonl_1 = dir1 / "activities.jsonl"
    info_1 = dir1 / "machine_info.json"
    daily_1 = dir1 / "daily" / "2026-10-06.log"

    assert jsonl_1.exists()
    assert info_1.exists()
    assert daily_1.exists()

    with open(jsonl_1, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["process_name"] == "code.exe"

    with open(info_1, "r", encoding="utf-8") as f:
        info = json.load(f)
        assert info["client_id"] == client_id_1
        assert info["total_records"] == 1
        assert info["last_active_app"] == "code.exe"
        assert info["last_ip"] == "192.168.1.50"

    with open(daily_1, "r", encoding="utf-8") as f:
        log_text = f.read()
        assert "code.exe" in log_text
        assert "[ACTIVE]" in log_text

    # Verify listing machines
    machines = temp_storage.list_machines()
    assert len(machines) == 2
    machine_names = {m["client_id"] for m in machines}
    assert client_id_1 in machine_names
    assert client_id_2 in machine_names


def test_machines_api_endpoints(api_client):
    # Ingest a test batch to generate a machine partition
    payload = {
        "client_id": "TEST-PC-API-01",
        "activities": [
            {
                "client_id": "TEST-PC-API-01",
                "start_time": "2026-10-06T19:30:00Z",
                "end_time": "2026-10-06T19:31:00Z",
                "duration_seconds": 60.0,
                "process_name": "chrome.exe",
                "window_title": "Railway Cloud Console",
                "category": "Browsing",
                "is_idle": False,
            }
        ]
    }
    post_res = api_client.post(
        "/api/v1/activities/batch",
        json=payload,
        headers={"Authorization": "Bearer test-secret-token"}
    )
    assert post_res.status_code == 201

    # Query machines list
    res = api_client.get("/api/v1/machines")
    assert res.status_code == 200
    machines = res.json()
    assert isinstance(machines, list)
    matching = [m for m in machines if m["client_id"] == "TEST-PC-API-01"]
    assert len(matching) == 1
    assert matching[0]["total_records"] >= 1

    # Query machine logs
    logs_res = api_client.get("/api/v1/machines/TEST-PC-API-01/logs")
    assert logs_res.status_code == 200
    logs_data = logs_res.json()
    assert logs_data["client_id"] == "TEST-PC-API-01"
    assert len(logs_data["lines"]) >= 1
    assert any("chrome.exe" in line for line in logs_data["lines"])
