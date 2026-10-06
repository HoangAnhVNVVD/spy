"""Unit tests for the tracker state machine and interval coalescing."""

import time
from unittest.mock import MagicMock
from client.buffer import ActivityEvent
from client.config import ClientConfig, PrivacySettings
from client.tracker import ActivityTracker
from client.win32_monitor import WindowActivityInfo


def test_tracker_coalescing_and_switching(activity_buffer, test_client_config):
    # Set min duration to 1.0s
    test_client_config.min_duration_seconds = 1.0
    mock_sync = MagicMock()
    tracker = ActivityTracker(
        config=test_client_config,
        buffer=activity_buffer,
        sync_client=mock_sync,
    )

    t0 = 1000.0
    # Step 1: User in code.exe at t0
    snap1 = WindowActivityInfo(
        process_name="code.exe",
        window_title="main.py - editor",
        pid=123,
        hwnd=456,
        idle_seconds=0.0,
        is_idle=False,
        timestamp=t0,
    )
    tracker.process_snapshot(snap1)
    assert activity_buffer.get_stats()["total_records"] == 0  # Still open

    # Step 2: 3 seconds later, still in code.exe
    snap2 = WindowActivityInfo(
        process_name="code.exe",
        window_title="main.py - editor",
        pid=123,
        hwnd=456,
        idle_seconds=0.0,
        is_idle=False,
        timestamp=t0 + 3.0,
    )
    tracker.process_snapshot(snap2)
    assert activity_buffer.get_stats()["total_records"] == 0  # Coalesced

    # Step 3: Switch to chrome.exe at t0 + 4.0
    snap3 = WindowActivityInfo(
        process_name="chrome.exe",
        window_title="FastAPI Documentation",
        pid=789,
        hwnd=999,
        idle_seconds=0.0,
        is_idle=False,
        timestamp=t0 + 4.0,
    )
    flushed = tracker.process_snapshot(snap3)
    assert flushed is not None
    assert flushed.process_name == "code.exe"
    assert flushed.duration_seconds == 3.0
    assert activity_buffer.get_stats()["total_records"] == 1

    # Verify buffered event
    records = activity_buffer.get_unsynced_batch()
    assert len(records) == 1
    assert records[0].process_name == "code.exe"
    assert records[0].duration_seconds == 3.0


def test_tracker_idle_transition(activity_buffer, test_client_config):
    test_client_config.min_duration_seconds = 1.0
    mock_sync = MagicMock()
    tracker = ActivityTracker(
        config=test_client_config,
        buffer=activity_buffer,
        sync_client=mock_sync,
    )

    t0 = 2000.0
    # Active in terminal
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="wt.exe",
            window_title="PowerShell",
            pid=111,
            hwnd=222,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0,
        )
    )
    # User works for 5 seconds
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="wt.exe",
            window_title="PowerShell",
            pid=111,
            hwnd=222,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0 + 5.0,
        )
    )

    # User steps away -> Idle snapshot
    flushed_active = tracker.process_snapshot(
        WindowActivityInfo(
            process_name="wt.exe",
            window_title="PowerShell",
            pid=111,
            hwnd=222,
            idle_seconds=130.0,
            is_idle=True,
            timestamp=t0 + 6.0,
        )
    )
    assert flushed_active is not None
    assert flushed_active.process_name == "wt.exe"
    assert flushed_active.duration_seconds == 5.0
    assert flushed_active.is_idle is False

    # User is idle for 60 seconds
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="",
            window_title="",
            pid=0,
            hwnd=0,
            idle_seconds=190.0,
            is_idle=True,
            timestamp=t0 + 66.0,
        )
    )

    # User returns to terminal
    flushed_idle = tracker.process_snapshot(
        WindowActivityInfo(
            process_name="wt.exe",
            window_title="PowerShell",
            pid=111,
            hwnd=222,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0 + 67.0,
        )
    )
    assert flushed_idle is not None
    assert flushed_idle.is_idle is True
    assert flushed_idle.process_name == "idle"
    assert flushed_idle.duration_seconds == 60.0

    # Total records in buffer should be 2 (active + idle)
    assert activity_buffer.get_stats()["total_records"] == 2


def test_tracker_subsecond_flicker_ignored(activity_buffer, test_client_config):
    test_client_config.min_duration_seconds = 2.0
    mock_sync = MagicMock()
    tracker = ActivityTracker(
        config=test_client_config,
        buffer=activity_buffer,
        sync_client=mock_sync,
    )

    t0 = 3000.0
    # Focus for 0.5 seconds (under min_duration_seconds = 2.0)
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="popup.exe",
            window_title="Quick Alert",
            pid=1,
            hwnd=2,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0,
        )
    )
    tracker.process_snapshot(
        WindowActivityInfo(
            process_name="popup.exe",
            window_title="Quick Alert",
            pid=1,
            hwnd=2,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0 + 0.5,
        )
    )

    # Immediately switched away
    flushed = tracker.process_snapshot(
        WindowActivityInfo(
            process_name="code.exe",
            window_title="editor",
            pid=3,
            hwnd=4,
            idle_seconds=0.0,
            is_idle=False,
            timestamp=t0 + 0.6,
        )
    )
    assert flushed is None  # Dropped because duration < 2.0s
    assert activity_buffer.get_stats()["total_records"] == 0


def test_tracker_immediate_startup_sync(activity_buffer, test_client_config):
    mock_sync = MagicMock()
    mock_monitor = MagicMock()
    mock_monitor.snapshot.return_value = WindowActivityInfo(
        process_name="notepad.exe",
        window_title="Doc.txt - Notepad",
        pid=100,
        hwnd=200,
        idle_seconds=0.0,
        is_idle=False,
        timestamp=1000.0,
    )

    tracker = ActivityTracker(
        config=test_client_config,
        monitor=mock_monitor,
        buffer=activity_buffer,
        sync_client=mock_sync,
    )

    # Calling step captures first activity
    snap = tracker.monitor.snapshot()
    sanitized_title, _ = tracker.privacy.sanitize_title(snap.window_title, snap.process_name)
    initial_event = ActivityEvent(
        client_id=test_client_config.client_id,
        start_time="2026-10-06T19:00:00Z",
        end_time="2026-10-06T19:00:00Z",
        duration_seconds=1.0,
        process_name=snap.process_name,
        window_title=sanitized_title,
        category="Startup",
        is_idle=False,
    )
    tracker.buffer.insert(initial_event)
    tracker.sync_client.sync_pending(tracker.buffer)

    assert activity_buffer.get_stats()["total_records"] == 1
    mock_sync.sync_pending.assert_called_once()

