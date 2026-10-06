from __future__ import annotations
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from server.app import app
from server.categorizer import classify_activity
from server.config import settings
from server.machine_storage import MachineStorageManager
from server.security_engine import SecurityEngine, SecurityKnowledgeBase
client = TestClient(app)
AUTH_HEADERS = {'Authorization': f'Bearer {settings.API_KEY}'}

def test_security_knowledge_base_loading(tmp_path):
    kb = SecurityKnowledgeBase()
    summary = kb.get_summary()
    assert summary['title'] == 'Phân tích chuyên sâu cách hoạt động'
    assert summary['language'] == 'vi-VN'
    assert summary['total_topics'] >= 15
    assert 'tương quan process, file, network' in summary['core_principle']
    assert len(summary['telemetry_sources']) >= 5
    topics = kb.get_topics('c2')
    assert any((t['topic'] == 'c2' for t in topics))
    workflow = kb.get_workflow()
    assert len(workflow) == 20
    assert workflow[0]['title'] == 'Xác định endpoint nghi vấn.'
    assert workflow[10]['title'] == 'Cô lập endpoint nếu rủi ro cao.'
    assert workflow[19]['title'] == 'Document root cause và lessons learned.'

def test_security_ioc_binary_detection(tmp_path):
    storage = MachineStorageManager(base_dir=tmp_path / 'machines')
    engine = SecurityEngine(storage_manager=storage)
    normal_acts = [{'process_name': 'code.exe', 'window_title': 'main.py - VSCode', 'duration_seconds': 60, 'start_time': '2026-10-06T10:00:00Z'}, {'process_name': 'chrome.exe', 'window_title': 'GitHub Pull Requests', 'duration_seconds': 120, 'start_time': '2026-10-06T10:01:00Z'}]
    normal_res = engine.analyze_activities(normal_acts, client_id='dev-pc')
    assert normal_res['risk_score'] == 0
    assert normal_res['risk_level'] == 'NORMAL'
    assert normal_res['alert_count'] == 0
    threat_acts = [{'process_name': 'mimikatz.exe', 'window_title': 'Mimikatz 2.2.0', 'duration_seconds': 5, 'start_time': '2026-10-06T11:00:00Z'}, {'process_name': 'wireshark.exe', 'window_title': 'Capturing on eth0', 'duration_seconds': 45, 'start_time': '2026-10-06T11:00:05Z'}]
    threat_res = engine.analyze_activities(threat_acts, client_id='suspect-pc')
    assert threat_res['risk_score'] >= 40
    assert threat_res['alert_count'] >= 2
    assert any(('mimikatz' in a['message'].lower() for a in threat_res['alerts']))
    assert any(('wireshark' in a['message'].lower() for a in threat_res['alerts']))

def test_security_ioa_command_and_credential_detection(tmp_path):
    storage = MachineStorageManager(base_dir=tmp_path / 'machines')
    engine = SecurityEngine(storage_manager=storage)
    ioa_acts = [{'process_name': 'powershell.exe', 'window_title': 'powershell -EncodedCommand JABhAD0... -ExecutionPolicy Bypass', 'duration_seconds': 10, 'start_time': '2026-10-06T12:00:00Z'}, {'process_name': 'chrome.exe', 'window_title': 'Dashboard - api_key=sk_live_998822334455 secret leaked', 'duration_seconds': 30, 'start_time': '2026-10-06T12:00:10Z'}]
    res = engine.analyze_activities(ioa_acts, client_id='test-ioa')
    assert res['risk_score'] >= 35
    assert res['alert_count'] >= 2
    assert any((a['topic'] == 'execution' for a in res['alerts']))
    assert any((a['topic'] == 'ethics' for a in res['alerts']))

def test_security_rapid_hopping_anomaly(tmp_path):
    storage = MachineStorageManager(base_dir=tmp_path / 'machines')
    engine = SecurityEngine(storage_manager=storage)
    rapid_acts = [{'process_name': f'app_{i}.exe', 'window_title': f'App Window {i}', 'duration_seconds': 0.5, 'start_time': f'2026-10-06T13:00:{i:02d}Z'} for i in range(10)]
    res = engine.analyze_activities(rapid_acts, client_id='scraper-pc')
    assert any(('Automated Scraping' in a['category'] for a in res['alerts']))

def test_20_step_triage_generation_and_isolation(tmp_path):
    storage = MachineStorageManager(base_dir=tmp_path / 'machines')
    engine = SecurityEngine(storage_manager=storage)
    cid = 'test-triage-pc'
    storage.record_activities(cid, [{'process_name': 'cmd.exe', 'window_title': 'Administrator: Command Prompt', 'duration_seconds': 15, 'start_time': '2026-10-06T14:00:00Z'}, {'process_name': 'code.exe', 'window_title': 'server.py - spy', 'duration_seconds': 120, 'start_time': '2026-10-06T14:00:15Z'}], client_ip='192.168.1.50')
    triage = engine.generate_triage_report(cid)
    assert triage['client_id'] == cid
    assert len(triage['workflow_steps']) == 20
    assert triage['workflow_steps'][0]['step_number'] == 1
    assert '192.168.1.50' in triage['workflow_steps'][0]['finding']
    assert triage['is_isolated'] is False
    iso_res = engine.isolate_machine(cid, reason='Test quarantine for malicious activity')
    assert iso_res['is_isolated'] is True
    assert iso_res['client_id'] == cid
    triage_isolated = engine.generate_triage_report(cid)
    assert triage_isolated['is_isolated'] is True
    assert '[ĐÃ CÔ LẬP' in triage_isolated['workflow_steps'][10]['finding']
    uniso_res = engine.unisolate_machine(cid)
    assert uniso_res['is_isolated'] is False
    triage_normal = engine.generate_triage_report(cid)
    assert triage_normal['is_isolated'] is False

def test_forensic_timeline_export(tmp_path):
    storage = MachineStorageManager(base_dir=tmp_path / 'machines')
    engine = SecurityEngine(storage_manager=storage)
    cid = 'forensic-target-pc'
    storage.record_activities(cid, [{'process_name': 'wireshark.exe', 'window_title': 'Capture Session 1', 'duration_seconds': 40, 'start_time': '2026-10-06T15:00:00Z'}])
    export = engine.export_forensic_timeline(cid)
    assert export['client_id'] == cid
    assert export['total_timeline_events'] == 1
    assert len(export['evidence_hash_sha256']) == 64
    assert export['timeline'][0]['forensic_flag'] == 'SUSPICIOUS_IOA'

def test_security_routes_integration(api_client):
    auth_headers = {'Authorization': f'Bearer {settings.API_KEY}'}
    res = api_client.get('/api/v1/security/knowledge')
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'success'
    assert data['summary']['total_topics'] >= 15
    wf_res = api_client.get('/api/v1/security/workflow')
    assert wf_res.status_code == 200
    wf_data = wf_res.json()
    assert wf_data['total_steps'] == 20
    alerts_res = api_client.get('/api/v1/security/alerts')
    assert alerts_res.status_code == 200
    assert 'risk_score' in alerts_res.json()
    test_machine = 'MACHINE-A'
    triage_res = api_client.get(f'/api/v1/machines/{test_machine}/security-triage')
    assert triage_res.status_code == 200
    t_data = triage_res.json()
    assert len(t_data['workflow_steps']) == 20
    unauth_iso = api_client.post(f'/api/v1/machines/{test_machine}/isolate')
    assert unauth_iso.status_code == 401
    auth_iso = api_client.post(f'/api/v1/machines/{test_machine}/isolate', headers=auth_headers)
    assert auth_iso.status_code == 200
    assert auth_iso.json()['is_isolated'] is True
    auth_uniso = api_client.post(f'/api/v1/machines/{test_machine}/unisolate', headers=auth_headers)
    assert auth_uniso.status_code == 200
    assert auth_uniso.json()['is_isolated'] is False
    forensics_res = api_client.get(f'/api/v1/machines/{test_machine}/forensics')
    assert forensics_res.status_code == 200
    assert 'evidence_hash_sha256' in forensics_res.json()

def test_cybersecurity_categorization():
    assert classify_activity('wireshark.exe', 'Capturing on Adapter 1', False) == 'Cybersecurity & Defense'
    assert classify_activity('procexp.exe', 'Process Explorer - Sysinternals', False) == 'Cybersecurity & Defense'
    assert classify_activity('mimikatz.exe', 'Console', False) == 'Cybersecurity & Defense'
    assert classify_activity('eventvwr.exe', 'Event Viewer (Local)', False) == 'System Administration & Shells'
    assert classify_activity('resmon.exe', 'Resource Monitor', False) == 'System Administration & Shells'
