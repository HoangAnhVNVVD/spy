"""FastAPI main application entrypoint."""

from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.config import settings
from server.database import init_db
from server.routes import activities, analytics, health, machines

# Ensure DB initialized on module load
init_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Privacy-respecting personal productivity & time-tracking Railway backend.",
)

# Enable CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health.router)
app.include_router(activities.router)
app.include_router(analytics.router)
app.include_router(machines.router)

# Mount static web dashboard
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_dashboard():
    """Serve the interactive productivity dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Windows Activity Tracker backend is running.", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host=settings.HOST, port=settings.PORT, reload=True)
