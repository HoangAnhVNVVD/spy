"""End-to-End integration test simulating Client -> Buffer -> Offline -> Server Sync."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from client.buffer import ActivityBuffer
from client.config import ClientConfig
from client.privacy import PrivacyEngine
from client.sync import SyncClient
from client.tracker import ActivityTracker
from client.win32_monitor import WindowActivityInfo
from server.app import app
from server.database import Base, get_db
from server.config import settings


def test_full_e2e_pipeline(temp_dir):
    # 1. Setup isolated database and configs
    client_db = temp_dir / "client_e2e.db"
    server_db = temp_dir / "server_e2e.db"

    # Configure isolated test server database
    test_engine = create_engine(f"sqlite:///{server_db}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    settings.API_KEY = "super-secret-sync-token"

    test_config = ClientConfig(
        server_url="http://testserver",
        api_token="super-secret-sync-token",
        client_id="e2e-laptop",
        min_duration_seconds=1.0,
        db_path=str(client_db),
    )

    buffer = ActivityBuffer(client_db)

    # 2. Simulate User Workflow through ActivityTracker
    tracker = ActivityTracker(config=test_config, buffer=buffer)

    t = 5000.0
    # Interval 1: 10 minutes in VS Code
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="code.exe",
            window_title="server.py - project",
            pid=100,
            hwnd=200,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t,
        )
    )
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="code.exe",
            window_title="server.py - project",
            pid=100,
            hwnd=200,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t + 600.0,  # 10 mins
        )
    )

    # Interval 2: 5 minutes in Edge with sensitive credit card in title
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="msedge.exe",
            window_title="Purchase 4111 2222 3333 4444 - Store",
            pid=300,
            hwnd=400,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t + 601.0,
        )
    )
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="msedge.exe",
            window_title="Purchase 4111 2222 3333 4444 - Store",
            pid=300,
            hwnd=400,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t + 901.0,  # 5 mins
        )
    )

    # Interval 3: 5 minutes in 1Password (Ignored application)
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="1password.exe",
            window_title="Vault Credentials",
            pid=500,
            hwnd=600,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t + 902.0,
        )
    )
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="1password.exe",
            window_title="Vault Credentials",
            pid=500,
            hwnd=600,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t + 1202.0,
        )
    )

    # Interval 4: 15 minutes Away / Idle
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="",
            window_title="",
            pid=0,
            hwnd=0,
            idle_seconds=200.0,
            is_idle=True,
            timestamp=t + 1203.0,
        )
    )
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="",
            window_title="",
            pid=0,
            hwnd=0,
            idle_seconds=1100.0,
            is_idle=True,
            timestamp=t + 2103.0,  # 15 mins
        )
    )

    # Flush final interval on stop
    tracker.stop()

    # Verify local SQLite buffer has recorded all events
    stats_before = buffer.get_stats()
    assert stats_before["total_records"] == 4
    assert stats_before["unsynced_records"] == 4

    buffered_records = buffer.get_unsynced_batch(limit=10)
    titles = [r.window_title for r in buffered_records]
    # Check that credit card was sanitized in local storage
    assert any("[REDACTED]" in title for title in titles)
    assert not any("4111 2222 3333 4444" in title for title in titles)
    # Check that 1Password was marked private
    assert any("[Private App" in r.process_name for r in buffered_records)

    # 3. Simulate Offline Scenario
    offline_sync = SyncClient(
        server_url="http://non-existent-server-1234.local",
        api_token="super-secret-sync-token",
        client_id="e2e-laptop",
        timeout_seconds=0.5,
    )
    synced_offline = offline_sync.sync_pending(buffer)
    assert synced_offline == 0
    # Data is STILL preserved safely in SQLite buffer!
    assert buffer.get_stats()["unsynced_records"] == 4

    # 4. Connect to Real Server (FastAPI TestClient adapter)
    try:
        with TestClient(app) as test_client:
            # Check health
            health_resp = test_client.get("/health")
            assert health_resp.status_code == 200

            # Simulate sync using test client
            batch = buffer.get_unsynced_batch(limit=100)
            payload = {
                "client_id": "e2e-laptop",
                "activities": [
                    {
                        "start_time": e.start_time,
                        "end_time": e.end_time,
                        "duration_seconds": e.duration_seconds,
                        "process_name": e.process_name,
                        "window_title": e.window_title,
                        "category": e.category,
                        "is_idle": e.is_idle,
                    }
                    for e in batch
                ],
            }
            resp = test_client.post(
                "/api/v1/activities/batch",
                json=payload,
                headers={"Authorization": "Bearer super-secret-sync-token"},
            )
            assert resp.status_code == 201
            assert resp.json()["count"] == 4

            # Mark buffer as synced
            buffer.mark_synced([e.id for e in batch if e.id is not None])

            # Verify buffer is now fully synced
            stats_after = buffer.get_stats()
            assert stats_after["unsynced_records"] == 0
            assert stats_after["synced_records"] == 4

            # 5. Query Dashboard Summary on Server
            summary_resp = test_client.get("/api/v1/analytics/summary", params={"client_id": "e2e-laptop"})
            assert summary_resp.status_code == 200
            summary = summary_resp.json()

            # Total duration = 600s (code) + 300s (edge) + 300s (1pass) + 900s (idle) = 2100s
            assert summary["total_tracked_seconds"] == 2100.0
            assert summary["idle_seconds"] == 900.0
            assert summary["active_seconds"] == 1200.0
            assert summary["formatted_active_time"] == "20m 00s"
            assert summary["formatted_idle_time"] == "15m 00s"

            top_apps = {a["process_name"]: a["duration_seconds"] for a in summary["top_apps"]}
            assert top_apps["code.exe"] == 600.0
            assert top_apps["msedge.exe"] == 300.0
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
