"""Batch synchronization client with Railway backend server."""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

from client.buffer import ActivityBuffer, ActivityEvent


class SyncClient:
    """Handles authenticated batch ingestion to the remote backend."""

    def __init__(
        self,
        server_url: str,
        api_token: str,
        client_id: str,
        timeout_seconds: float = 10.0,
    ):
        self.server_url = server_url.rstrip("/")
        self.api_token = api_token
        self.client_id = client_id
        self.timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "WinActivityTrackerClient/1.0",
        }

    def check_health(self) -> bool:
        """Check if backend server is online and responding."""
        health_url = f"{self.server_url}/api/v1/health"
        try:
            if HAS_REQUESTS:
                resp = requests.get(health_url, timeout=self.timeout_seconds)
                return resp.status_code == 200
            else:
                req = urllib.request.Request(health_url, method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return resp.status == 200
        except Exception:
            return False

    def send_batch(self, events: List[ActivityEvent]) -> Tuple[bool, int, str]:
        """
        Send a batch of activity records to the server.
        Returns: (success: bool, count_accepted: int, error_message: str)
        """
        if not events:
            return (True, 0, "Empty batch")

        batch_url = f"{self.server_url}/api/v1/activities/batch"
        payload = {
            "client_id": self.client_id,
            "activities": [
                {
                    "start_time": e.start_time,
                    "end_time": e.end_time,
                    "duration_seconds": e.duration_seconds,
                    "process_name": e.process_name,
                    "window_title": e.window_title,
                    "category": e.category,
                    "is_idle": e.is_idle,
                }
                for e in events
            ],
        }

        try:
            body_bytes = json.dumps(payload).encode("utf-8")
            if HAS_REQUESTS:
                resp = requests.post(
                    batch_url,
                    headers=self._headers,
                    data=body_bytes,
                    timeout=self.timeout_seconds,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    accepted = data.get("count", len(events))
                    return (True, accepted, "OK")
                else:
                    return (False, 0, f"HTTP {resp.status_code}: {resp.text}")
            else:
                req = urllib.request.Request(
                    batch_url,
                    data=body_bytes,
                    headers=self._headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    return (True, resp_data.get("count", len(events)), "OK")
        except Exception as e:
            return (False, 0, str(e))

    def sync_pending(self, buffer: ActivityBuffer, batch_size: int = 100) -> int:
        """
        Drain un-synced events from the local buffer and send to backend.
        Marks events as synced in SQLite on successful upload.
        Returns total number of events synced.
        """
        total_synced = 0

        while True:
            batch = buffer.get_unsynced_batch(limit=batch_size)
            if not batch:
                break

            success, count, err = self.send_batch(batch)
            if not success:
                # Backend offline or network failure: stop syncing without marking synced
                # Records stay preserved in SQLite buffer for later
                break

            # Extract IDs and mark as synced in SQLite
            ids = [e.id for e in batch if e.id is not None]
            buffer.mark_synced(ids)
            total_synced += count

            # If this batch had fewer records than batch_size, we're done
            if len(batch) < batch_size:
                break

        return total_synced
