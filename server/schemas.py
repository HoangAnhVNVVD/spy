from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ActivityItemIn(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_seconds: float = Field(..., ge=0.0)
    process_name: str
    window_title: str = ''
    category: Optional[str] = None
    is_idle: bool = False

class OpenTaskItem(BaseModel):
    process_name: str
    window_title: str = ''
    pid: Optional[int] = None
    is_focused: bool = False
    hwnd: Optional[int] = None

class BatchActivityRequest(BaseModel):
    client_id: str
    activities: List[ActivityItemIn] = []
    open_tasks: Optional[List[OpenTaskItem]] = None
    timestamp: Optional[str] = None

class BatchActivityResponse(BaseModel):
    status: str
    count: int
    client_id: str
    open_tasks_count: Optional[int] = None
    is_isolated: Optional[bool] = False

class MachineLiveStatus(BaseModel):
    client_id: str
    last_updated: str
    is_online: bool
    task_count: int
    client_ip: Optional[str] = None
    tasks: List[OpenTaskItem] = []

class ActivityItemOut(BaseModel):
    id: int
    client_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    process_name: str
    window_title: str
    category: str
    is_idle: bool
    created_at: str
    model_config = ConfigDict(from_attributes=True)

class PaginatedActivitiesResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ActivityItemOut]

class TopAppItem(BaseModel):
    process_name: str
    category: str
    duration_seconds: float
    formatted_duration: str
    percentage: float

class CategoryItem(BaseModel):
    category: str
    duration_seconds: float
    formatted_duration: str
    percentage: float

class TimelineBucketItem(BaseModel):
    bucket_start: str
    label: str
    total_seconds: float
    active_seconds: float
    idle_seconds: float

class AnalyticsSummaryResponse(BaseModel):
    client_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_tracked_seconds: float
    formatted_total_time: str
    active_seconds: float
    formatted_active_time: str
    idle_seconds: float
    formatted_idle_time: str
    productivity_score: float
    total_events: int
    top_apps: List[TopAppItem]
    categories: List[CategoryItem]
