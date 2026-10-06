"""Activities ingestion and retrieval routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from server.auth import optional_auth_for_reads, require_api_key
from server.categorizer import classify_activity
from server.database import get_db
from server.machine_storage import machine_storage
from server.models import ActivityRecord
from server.schemas import (
    ActivityItemOut,
    BatchActivityRequest,
    BatchActivityResponse,
    PaginatedActivitiesResponse,
)

router = APIRouter(prefix="/api/v1/activities", tags=["Activities"])


def parse_date_param(val: Optional[str], is_end_of_day: bool = False) -> Optional[datetime]:
    """Parse date or ISO timestamp parameter, normalizing to naive UTC."""
    if not val:
        return None
    val = val.strip()
    try:
        if len(val) == 10:  # YYYY-MM-DD
            dt = datetime.strptime(val, "%Y-%m-%d")
            if is_end_of_day:
                dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            return dt
        # Handle ISO format
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


@router.post(
    "/batch",
    response_model=BatchActivityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def ingest_activities_batch(
    payload: BatchActivityRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Ingest a batch of activity records from a Windows client.
    Requires Bearer token authentication.
    Saves to both SQL database and dedicated machine disk storage.
    """
    inserted_count = 0
    records: List[ActivityRecord] = []
    disk_items: List[dict] = []

    for item in payload.activities:
        # Determine category automatically if not supplied or left as Uncategorized
        cat = item.category or ""
        if not cat or cat == "Uncategorized":
            cat = classify_activity(
                process_name=item.process_name,
                window_title=item.window_title,
                is_idle=item.is_idle,
            )

        # Normalize datetimes to naive UTC for consistent SQL querying
        st = item.start_time
        if st.tzinfo is not None:
            st = st.astimezone(timezone.utc).replace(tzinfo=None)
        et = item.end_time
        if et.tzinfo is not None:
            et = et.astimezone(timezone.utc).replace(tzinfo=None)

        record = ActivityRecord(
            client_id=payload.client_id,
            start_time=st,
            end_time=et,
            duration_seconds=float(item.duration_seconds),
            process_name=item.process_name,
            window_title=item.window_title,
            category=cat,
            is_idle=bool(item.is_idle),
        )
        records.append(record)

        disk_items.append({
            "client_id": payload.client_id,
            "start_time": st.isoformat() + "Z",
            "end_time": et.isoformat() + "Z",
            "duration_seconds": float(item.duration_seconds),
            "process_name": item.process_name,
            "window_title": item.window_title,
            "category": cat,
            "is_idle": bool(item.is_idle),
        })

    if records:
        db.add_all(records)
        db.commit()
        inserted_count = len(records)

    # Save to dedicated machine storage on Railway disk
    if disk_items:
        client_ip = request.client.host if request.client else ""
        machine_storage.record_activities(payload.client_id, disk_items, client_ip=client_ip)

    return BatchActivityResponse(
        status="success",
        count=inserted_count,
        client_id=payload.client_id,
    )


@router.get(
    "",
    response_model=PaginatedActivitiesResponse,
    dependencies=[Depends(optional_auth_for_reads)],
)
def list_activities(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or ISO)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD or ISO)"),
    process_name: Optional[str] = Query(None, description="Filter by process name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_idle: Optional[bool] = Query(None, description="Filter idle records"),
    search: Optional[str] = Query(None, description="Search term in process or title"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Query activities with optional filtering and pagination."""
    query = db.query(ActivityRecord)

    if client_id:
        query = query.filter(ActivityRecord.client_id == client_id)

    dt_from = parse_date_param(date_from, is_end_of_day=False)
    if dt_from:
        query = query.filter(ActivityRecord.start_time >= dt_from)

    dt_to = parse_date_param(date_to, is_end_of_day=True)
    if dt_to:
        query = query.filter(ActivityRecord.start_time <= dt_to)

    if process_name:
        query = query.filter(ActivityRecord.process_name.ilike(f"%{process_name}%"))

    if category:
        query = query.filter(ActivityRecord.category == category)

    if is_idle is not None:
        query = query.filter(ActivityRecord.is_idle == is_idle)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (ActivityRecord.process_name.ilike(search_term))
            | (ActivityRecord.window_title.ilike(search_term))
        )

    total = query.count()
    records = (
        query.order_by(ActivityRecord.start_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        ActivityItemOut(
            id=r.id,
            client_id=r.client_id,
            start_time=f"{r.start_time.isoformat()}Z",
            end_time=f"{r.end_time.isoformat()}Z",
            duration_seconds=r.duration_seconds,
            process_name=r.process_name,
            window_title=r.window_title,
            category=r.category,
            is_idle=r.is_idle,
            created_at=f"{r.created_at.isoformat()}Z",
        )
        for r in records
    ]

    return PaginatedActivitiesResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )
