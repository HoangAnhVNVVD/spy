from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from server.auth import optional_auth_for_reads, require_api_key
from server.machine_storage import MachineStorageManager
from server.security_engine import SecurityEngine
router = APIRouter(prefix='/api/v1', tags=['Cybersecurity & Defense'])
storage_mgr = MachineStorageManager()
security_engine = SecurityEngine(storage_manager=storage_mgr)

@router.get('/security/knowledge', summary='Get cybersecurity operating principles & metadata')
def get_security_knowledge(q: Optional[str]=Query(None, description='Search term for principles or topics'), _: None=Depends(optional_auth_for_reads)) -> Dict[str, Any]:
    summary = security_engine.kb.get_summary()
    topics = security_engine.kb.get_topics(query=q or '')
    return {'status': 'success', 'summary': summary, 'topics': topics}

@router.get('/security/workflow', summary='Get 20-step incident response playbook')
def get_defensive_workflow(_: None=Depends(optional_auth_for_reads)) -> Dict[str, Any]:
    workflow = security_engine.kb.get_workflow()
    return {'status': 'success', 'workflow_name': 'Quy trình 20 bước ứng phó sự cố và điều tra số', 'total_steps': len(workflow), 'steps': workflow}

@router.get('/security/alerts', summary='Get security alerts and threat detections')
def get_security_alerts(client_id: Optional[str]=Query(None, description='Filter alerts by specific machine ID'), limit: int=Query(300, ge=1, le=1000, description='Max activities to analyze'), _: None=Depends(optional_auth_for_reads)) -> Dict[str, Any]:
    if client_id:
        activities = storage_mgr.get_recent_activities(client_id, limit=limit)
        return security_engine.analyze_activities(activities, client_id=client_id)
    all_activities = []
    machines = storage_mgr.list_machines()
    for m in machines:
        cid = m.get('client_id')
        if cid:
            acts = storage_mgr.get_recent_activities(cid, limit=50)
            all_activities.extend(acts)
    return security_engine.analyze_activities(all_activities, client_id='all_machines')

@router.get('/machines/{client_id}/security-triage', summary='Run 20-step defensive security triage')
def get_machine_security_triage(client_id: str, _: None=Depends(optional_auth_for_reads)) -> Dict[str, Any]:
    return security_engine.generate_triage_report(client_id)

@router.post('/machines/{client_id}/isolate', summary='Isolate / quarantine endpoint')
def isolate_endpoint(client_id: str, reason: str=Query('Defensive security containment', description='Reason for isolation'), _: str=Depends(require_api_key)) -> Dict[str, Any]:
    return security_engine.isolate_machine(client_id, reason=reason)

@router.post('/machines/{client_id}/unisolate', summary='Remove isolation from endpoint')
def unisolate_endpoint(client_id: str, _: str=Depends(require_api_key)) -> Dict[str, Any]:
    return security_engine.unisolate_machine(client_id)

@router.get('/machines/{client_id}/forensics', summary='Export forensic evidence timeline')
def get_forensic_timeline(client_id: str, _: None=Depends(optional_auth_for_reads)) -> Dict[str, Any]:
    return security_engine.export_forensic_timeline(client_id)
