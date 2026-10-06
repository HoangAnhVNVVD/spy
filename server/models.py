from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from server.database import Base

class ActivityRecord(Base):
    __tablename__ = 'activity_records'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    client_id = Column(String(100), index=True, nullable=False)
    start_time = Column(DateTime, index=True, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    process_name = Column(String(255), index=True, nullable=False)
    window_title = Column(Text, nullable=False, default='')
    category = Column(String(100), index=True, nullable=False, default='Uncategorized')
    is_idle = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
