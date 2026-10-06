"""Analytics and reporting endpoints for dashboard visualizations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from server.auth import optional_auth_for_reads
from server.categorizer import format_duration
from server.database import get_db
from server.models import ActivityRecord
from server.routes.activities import parse_date_param
from server.schemas import (
    AnalyticsSummaryResponse,
    CategoryItem,
    TimelineBucketItem,
    TopAppItem,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    dependencies=[Depends(optional_auth_for_reads)],
)
def get_analytics_summary(
    client_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Aggregate high-level productivity summary metrics."""
    query = db.query(ActivityRecord)

    if client_id:
        query = query.filter(ActivityRecord.client_id == client_id)

    dt_from = parse_date_param(date_from, is_end_of_day=False)
    if dt_from:
        query = query.filter(ActivityRecord.start_time >= dt_from)

    dt_to = parse_date_param(date_to, is_end_of_day=True)
    if dt_to:
        query = query.filter(ActivityRecord.start_time <= dt_to)

    records = query.all()

    total_seconds = 0.0
    active_seconds = 0.0
    idle_seconds = 0.0
    app_durations: Dict[str, float] = defaultdict(float)
    app_categories: Dict[str, str] = {}
    category_durations: Dict[str, float] = defaultdict(float)

    for r in records:
        dur = float(r.duration_seconds or 0.0)
        total_seconds += dur
        if r.is_idle:
            idle_seconds += dur
        else:
            active_seconds += dur
            app_durations[r.process_name] += dur
            app_categories[r.process_name] = r.category

        category_durations[r.category] += dur

    # Top applications
    sorted_apps = sorted(app_durations.items(), key=lambda x: x[1], reverse=True)[:10]
    top_apps_list = []
    for proc, dur in sorted_apps:
        pct = (dur / active_seconds * 100.0) if active_seconds > 0 else 0.0
        top_apps_list.append(
            TopAppItem(
                process_name=proc,
                category=app_categories.get(proc, "Other"),
                duration_seconds=round(dur, 2),
                formatted_duration=format_duration(dur),
                percentage=round(pct, 1),
            )
        )

    # Categories breakdown
    sorted_categories = sorted(category_durations.items(), key=lambda x: x[1], reverse=True)
    category_list = []
    for cat, dur in sorted_categories:
        pct = (dur / total_seconds * 100.0) if total_seconds > 0 else 0.0
        category_list.append(
            CategoryItem(
                category=cat,
                duration_seconds=round(dur, 2),
                formatted_duration=format_duration(dur),
                percentage=round(pct, 1),
            )
        )

    productivity_score = 0.0
    if active_seconds > 0:
        # Productive categories vs distracting/other during active time
        productive_cats = {"Development", "Productivity & Office", "Communication", "Design & Media"}
        prod_time = sum(dur for cat, dur in category_durations.items() if cat in productive_cats and cat != "Idle / Away")
        productivity_score = round((prod_time / active_seconds) * 100.0, 1)

    return AnalyticsSummaryResponse(
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        total_tracked_seconds=round(total_seconds, 2),
        formatted_total_time=format_duration(total_seconds),
        active_seconds=round(active_seconds, 2),
        formatted_active_time=format_duration(active_seconds),
        idle_seconds=round(idle_seconds, 2),
        formatted_idle_time=format_duration(idle_seconds),
        productivity_score=productivity_score,
        total_events=len(records),
        top_apps=top_apps_list,
        categories=category_list,
    )


@router.get(
    "/timeline",
    response_model=List[TimelineBucketItem],
    dependencies=[Depends(optional_auth_for_reads)],
)
def get_activity_timeline(
    client_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    bucket_hours: int = Query(1, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """
    Generate chronological timeline buckets (e.g. hourly or multi-hour)
    for activity graphs.
    """
    query = db.query(ActivityRecord)
    if client_id:
        query = query.filter(ActivityRecord.client_id == client_id)

    dt_from = parse_date_param(date_from, is_end_of_day=False)
    if dt_from:
        query = query.filter(ActivityRecord.start_time >= dt_from)
    else:
        # Default to today at midnight UTC if not provided
        dt_from = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        query = query.filter(ActivityRecord.start_time >= dt_from)

    dt_to = parse_date_param(date_to, is_end_of_day=True)
    if dt_to:
        query = query.filter(ActivityRecord.start_time <= dt_to)

    records = query.order_by(ActivityRecord.start_time.asc()).all()

    # Bucket by intervals
    buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {"total": 0.0, "active": 0.0, "idle": 0.0})

    for r in records:
        dt = r.start_time
        # Round dt down to bucket_hours
        bucket_hour = (dt.hour // bucket_hours) * bucket_hours
        bucket_dt = dt.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)
        bucket_key = bucket_dt.strftime("%Y-%m-%d %H:00")

        dur = float(r.duration_seconds or 0.0)
        buckets[bucket_key]["total"] += dur
        if r.is_idle:
            buckets[bucket_key]["idle"] += dur
        else:
            buckets[bucket_key]["active"] += dur

    is_multi_day = bool(dt_to and dt_from and (dt_to - dt_from).total_seconds() > 86400)
    results: List[TimelineBucketItem] = []
    for key in sorted(buckets.keys()):
        data = buckets[key]
        if is_multi_day:
            label = key[5:] if len(key) >= 16 else key
        else:
            label = key[11:] if len(key) >= 16 else key
        results.append(
            TimelineBucketItem(
                bucket_start=key,
                label=label,
                total_seconds=round(data["total"], 2),
                active_seconds=round(data["active"], 2),
                idle_seconds=round(data["idle"], 2),
            )
        )

    return results


@router.get(
    "/top-apps",
    response_model=List[TopAppItem],
    dependencies=[Depends(optional_auth_for_reads)],
)
def get_top_apps(
    client_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Retrieve top applications ranked by active time."""
    summary = get_analytics_summary(client_id, date_from, date_to, db)
    return summary.top_apps[:limit]


@router.get(
    "/categories",
    response_model=List[CategoryItem],
    dependencies=[Depends(optional_auth_for_reads)],
)
def get_categories_breakdown(
    client_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Retrieve category breakdown for the selected period."""
    summary = get_analytics_summary(client_id, date_from, date_to, db)
    return summary.categories
