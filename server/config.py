"""Backend server configuration."""

from __future__ import annotations

import os
from pathlib import Path


class ServerSettings:
    """Server environment configuration."""

    def __init__(self):
        self.PORT = int(os.getenv("PORT", "8000"))
        self.HOST = os.getenv("HOST", "0.0.0.0")

        # Database URL resolution
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            data_dir = Path("./data")
            data_dir.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{data_dir.resolve()}/tracker.db"
        elif db_url.startswith("postgres://"):
            # SQLAlchemy 1.4+ / 2.0 requires postgresql://
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        self.DATABASE_URL = db_url
        self.API_KEY = os.getenv("API_KEY") or os.getenv("API_TOKEN") or "default-secret-token"
        self.REQUIRE_AUTH_FOR_READS = (
            os.getenv("REQUIRE_AUTH_FOR_READS", "false").lower() in ("1", "true", "yes")
        )
        self.APP_NAME = "Windows Activity Tracker - Railway Backend"
        self.VERSION = "1.0.0"


settings = ServerSettings()
