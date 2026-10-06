from datetime import datetime, timezone
import pytest
from client.buffer import ActivityBuffer, ActivityEvent
from client.config import PrivacySettings
from client.privacy import PrivacyEngine
from client.tracker import ActivityTracker
from client.win32_monitor import WindowActivityInfo

def test_privacy_special_regex_characters_in_keywords():
    settings = PrivacySettings(redact_keywords=['(secret)', '[pin]', 'api$key', 'c++'])
    engine = PrivacyEngine(settings)
    title = 'My doc with (secret) notes and [pin] number'
    sanitized, redacted = engine.sanitize_title(title, 'notepad.exe')
    assert redacted is True
    assert '(secret)' not in sanitized
    assert '[pin]' not in sanitized

def test_privacy_multiple_sensitive_entities_combined():
    settings = PrivacySettings()
    engine = PrivacyEngine(settings)
    complex_title = 'Billing: user@domain.com paid with 4111 2222 3333 4444 on password page'
    sanitized, redacted = engine.sanitize_title(complex_title, 'chrome.exe')
    assert redacted is True
    assert 'user@domain.com' not in sanitized
    assert '4111 2222 3333 4444' not in sanitized
    assert 'password' not in sanitized.lower()

def test_buffer_nonexistent_ids_mark_synced(activity_buffer: ActivityBuffer):
    updated = activity_buffer.mark_synced([999999, 888888])
    assert updated == 0

def test_buffer_zero_limit(activity_buffer: ActivityBuffer):
    now = datetime.now(timezone.utc).isoformat()
    activity_buffer.insert(ActivityEvent(client_id='c1', start_time=now, end_time=now, duration_seconds=5.0, process_name='test.exe', window_title='title'))
    batch = activity_buffer.get_unsynced_batch(limit=0)
    assert batch == []

def test_buffer_nested_directory_auto_creation(temp_dir):
    deep_path = temp_dir / 'nested' / 'sub' / 'folder' / 'buffer.db'
    buf = ActivityBuffer(deep_path)
    assert deep_path.exists()
    assert buf.get_stats()['total_records'] == 0

def test_tracker_flush_when_empty(test_client_config, activity_buffer):
    tracker = ActivityTracker(config=test_client_config, buffer=activity_buffer)
    flushed = tracker._flush_current_interval()
    assert flushed is None
    tracker.stop()
    assert activity_buffer.get_stats()['total_records'] == 0

def test_tracker_empty_process_name_handling(test_client_config, activity_buffer):
    test_client_config.min_duration_seconds = 1.0
    tracker = ActivityTracker(config=test_client_config, buffer=activity_buffer)
    t0 = 8000.0
    tracker.process_snapshot(WindowActivityInfo(process_name='', window_title='', pid=0, hwnd=0, idle_seconds=0.0, is_idle=False, timestamp=t0))
    tracker.process_snapshot(WindowActivityInfo(process_name='', window_title='', pid=0, hwnd=0, idle_seconds=0.0, is_idle=False, timestamp=t0 + 2.0))
    flushed = tracker.process_snapshot(WindowActivityInfo(process_name='code.exe', window_title='editor', pid=1, hwnd=2, idle_seconds=0.0, is_idle=False, timestamp=t0 + 3.0))
    assert flushed is not None
    assert flushed.process_name == 'Unknown'
    assert flushed.duration_seconds == 2.0

def test_server_empty_batch_ingest(api_client):
    payload = {'client_id': 'empty-client', 'activities': []}
    res = api_client.post('/api/v1/activities/batch', json=payload, headers={'Authorization': 'Bearer test-secret-token'})
    assert res.status_code == 201
    assert res.json()['count'] == 0

def test_server_zero_division_guard(api_client):
    res = api_client.get('/api/v1/analytics/summary', params={'client_id': 'zero-client'})
    assert res.status_code == 200
    data = res.json()
    assert data['total_tracked_seconds'] == 0.0
    assert data['active_seconds'] == 0.0
    assert data['idle_seconds'] == 0.0
    assert data['productivity_score'] == 0.0
    assert data['top_apps'] == []
    assert data['categories'] == []

def test_server_search_special_sql_characters(api_client):
    special_queries = ['%', '_', "'", '"', '\\', "'; DROP TABLE activity_records; --"]
    for q in special_queries:
        res = api_client.get('/api/v1/activities', params={'search': q})
        assert res.status_code == 200
        assert 'items' in res.json()
