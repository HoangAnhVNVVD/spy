import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from server.app import app
from server.machine_storage import MachineStorageManager

@pytest.fixture
def temp_storage(tmp_path: Path):
    return MachineStorageManager(base_dir=tmp_path / 'machines')

def test_machine_storage_partitioning(temp_storage: MachineStorageManager):
    client_id_1 = 'DESKTOP-PC1'
    client_id_2 = 'LAPTOP-OFFICE_2'
    activities_1 = [{'client_id': client_id_1, 'start_time': '2026-10-06T19:00:00Z', 'end_time': '2026-10-06T19:05:00Z', 'duration_seconds': 300.0, 'process_name': 'code.exe', 'window_title': 'app.py - Visual Studio Code', 'category': 'Development', 'is_idle': False}]
    activities_2 = [{'client_id': client_id_2, 'start_time': '2026-10-06T19:10:00Z', 'end_time': '2026-10-06T19:12:00Z', 'duration_seconds': 120.0, 'process_name': 'excel.exe', 'window_title': 'Budget.xlsx', 'category': 'Productivity', 'is_idle': False}]
    temp_storage.record_activities(client_id_1, activities_1, client_ip='192.168.1.50')
    temp_storage.record_activities(client_id_2, activities_2, client_ip='192.168.1.60')
    dir1 = temp_storage.get_machine_dir(client_id_1)
    dir2 = temp_storage.get_machine_dir(client_id_2)
    assert dir1.exists()
    assert dir2.exists()
    assert dir1 != dir2
    jsonl_1 = dir1 / 'activities.jsonl'
    info_1 = dir1 / 'machine_info.json'
    daily_1 = dir1 / 'daily' / '2026-10-06.log'
    assert jsonl_1.exists()
    assert info_1.exists()
    assert daily_1.exists()
    with open(jsonl_1, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data['process_name'] == 'code.exe'
    with open(info_1, 'r', encoding='utf-8') as f:
        info = json.load(f)
        assert info['client_id'] == client_id_1
        assert info['total_records'] == 1
        assert info['last_active_app'] == 'code.exe'
        assert info['last_ip'] == '192.168.1.50'
    with open(daily_1, 'r', encoding='utf-8') as f:
        log_text = f.read()
        assert 'code.exe' in log_text
        assert '[ACTIVE]' in log_text
    machines = temp_storage.list_machines()
    assert len(machines) == 2
    machine_names = {m['client_id'] for m in machines}
    assert client_id_1 in machine_names
    assert client_id_2 in machine_names

def test_machines_api_endpoints(api_client):
    payload = {'client_id': 'TEST-PC-API-01', 'activities': [{'client_id': 'TEST-PC-API-01', 'start_time': '2026-10-06T19:30:00Z', 'end_time': '2026-10-06T19:31:00Z', 'duration_seconds': 60.0, 'process_name': 'chrome.exe', 'window_title': 'Railway Cloud Console', 'category': 'Browsing', 'is_idle': False}]}
    post_res = api_client.post('/api/v1/activities/batch', json=payload, headers={'Authorization': 'Bearer test-secret-token'})
    assert post_res.status_code == 201
    res = api_client.get('/api/v1/machines')
    assert res.status_code == 200
    machines = res.json()
    assert isinstance(machines, list)
    matching = [m for m in machines if m['client_id'] == 'TEST-PC-API-01']
    assert len(matching) == 1
    assert matching[0]['total_records'] >= 1
    logs_res = api_client.get('/api/v1/machines/TEST-PC-API-01/logs')
    assert logs_res.status_code == 200
    logs_data = logs_res.json()
    assert logs_data['client_id'] == 'TEST-PC-API-01'
    assert len(logs_data['lines']) >= 1
    assert any(('chrome.exe' in line for line in logs_data['lines']))

def test_live_tasks_storage_and_api(api_client):
    payload = {'client_id': 'TEST-LIVE-PC', 'activities': [], 'open_tasks': [{'process_name': 'chrome.exe', 'window_title': 'Google Search', 'pid': 1234, 'is_focused': False}, {'process_name': 'Antigravity.exe', 'window_title': 'Editor', 'pid': 5678, 'is_focused': True}, {'process_name': 'powershell.exe', 'window_title': 'Terminal', 'pid': 9999, 'is_focused': False}]}
    res = api_client.post('/api/v1/activities/batch', json=payload, headers={'Authorization': 'Bearer test-secret-token'})
    assert res.status_code == 201
    data = res.json()
    assert data['open_tasks_count'] == 3
    live_res = api_client.get('/api/v1/machines/live')
    assert live_res.status_code == 200
    all_live = live_res.json()
    assert isinstance(all_live, list)
    target_live = next((m for m in all_live if m['client_id'] == 'TEST-LIVE-PC'), None)
    assert target_live is not None
    assert target_live['task_count'] == 3
    assert target_live['is_online'] is True
    assert len(target_live['tasks']) == 3
    procs = {t['process_name'] for t in target_live['tasks']}
    assert 'chrome.exe' in procs
    assert 'Antigravity.exe' in procs
    assert 'powershell.exe' in procs
    m_live_res = api_client.get('/api/v1/machines/TEST-LIVE-PC/live')
    assert m_live_res.status_code == 200
    m_data = m_live_res.json()
    assert m_data['client_id'] == 'TEST-LIVE-PC'
    assert m_data['task_count'] == 3
