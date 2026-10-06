"""Health check endpoints for Railway deployment probes and client ping."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.config import settings
from server.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for container orchestrators and client diagnostics."""
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
