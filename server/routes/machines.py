"""API routes for managing and querying machine-specific disk partitions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from server.auth import optional_auth_for_reads, require_api_key
from server.machine_storage import machine_storage

router = APIRouter(prefix="/api/v1/machines", tags=["Machines"])


@router.get(
    "",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(optional_auth_for_reads)],
)
def list_connected_machines():
    """List all machines with dedicated disk partitions on Railway."""
    return machine_storage.list_machines()


@router.get(
    "/live",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(optional_auth_for_reads)],
)
def get_all_machines_live_tasks():
    """Retrieve real-time taskbar applications for all connected machines."""
    return machine_storage.get_all_live_tasks()


@router.get(
    "/{client_id}/live",
    response_model=Dict[str, Any],
    dependencies=[Depends(optional_auth_for_reads)],
)
def get_machine_live_tasks(client_id: str):
    """Retrieve real-time taskbar applications for a specific machine."""
    live = machine_storage.get_live_tasks(client_id)
    if not live:
        raise HTTPException(
            status_code=404,
            detail=f"No live taskbar data found for machine '{client_id}'",
        )
    return live


@router.get(
    "/{client_id}",
    response_model=Dict[str, Any],
    dependencies=[Depends(optional_auth_for_reads)],
)
def get_machine_info(client_id: str):
    """Get metadata and storage information for a specific machine."""
    machines = machine_storage.list_machines()
    for m in machines:
        if m.get("client_id") == client_id or m.get("storage_folder") == client_id:
            return m
    raise HTTPException(status_code=404, detail=f"Machine '{client_id}' not found on disk")


@router.get(
    "/{client_id}/logs",
    dependencies=[Depends(optional_auth_for_reads)],
)
def get_machine_disk_logs(
    client_id: str,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Retrieve raw activity logs directly from the machine's disk storage."""
    lines = machine_storage.get_machine_logs(client_id, date_str=date, max_lines=limit)
    return {
        "client_id": client_id,
        "date": date or "latest",
        "total_lines": len(lines),
        "lines": [line.strip() for line in lines],
    }


@router.delete(
    "/{client_id}",
    dependencies=[Depends(require_api_key)],
)
def delete_machine_partition(client_id: str):
    """Delete a machine's partitioned disk directory (requires API key)."""
    success = machine_storage.delete_machine(client_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Machine '{client_id}' not found on disk")
    return {"status": "deleted", "client_id": client_id}

