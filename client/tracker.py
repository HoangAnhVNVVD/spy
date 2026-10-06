"""Activity tracking engine with state coalescing, idle detection, and privacy redaction."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from client.buffer import ActivityBuffer, ActivityEvent
from client.config import ClientConfig
from client.privacy import PrivacyEngine
from client.sync import SyncClient
from client.win32_monitor import Win32Monitor, WindowActivityInfo


class ActivityTracker:
    """Coordinates foreground monitoring, idle tracking, privacy redaction, and syncing."""

    def __init__(
        self,
        config: ClientConfig,
        monitor: Optional[Win32Monitor] = None,
        buffer: Optional[ActivityBuffer] = None,
        sync_client: Optional[SyncClient] = None,
    ):
        self.config = config
        self.monitor = monitor or Win32Monitor(idle_threshold_seconds=config.idle_threshold_seconds)
        self.privacy = PrivacyEngine(config.privacy)
        self.buffer = buffer or ActivityBuffer(config.db_path)
        self.sync_client = sync_client or SyncClient(
            server_url=config.server_url,
            api_token=config.api_token,
            client_id=config.client_id,
        )

        # Current interval state
        self._current_process: Optional[str] = None
        self._current_title: Optional[str] = None
        self._current_is_idle: bool = False
        self._current_category: str = "Uncategorized"
        self._start_time_iso: Optional[str] = None
        self._start_epoch: float = 0.0
        self._last_epoch: float = 0.0
        self._last_sync_epoch: float = time.time()
        self._running: bool = False

    def _flush_current_interval(self, end_timestamp: Optional[float] = None) -> Optional[ActivityEvent]:
        """Commit the currently tracked interval to the local SQLite buffer."""
        if self._current_process is None or self._start_time_iso is None:
            return None

        # Determine effective end time of interval:
        # If the interval only had the initial snapshot (no same-state extensions),
        # use the transition end_timestamp so single-poll intervals aren't dropped as 0s.
        if end_timestamp is not None and self._last_epoch == self._start_epoch:
            end_epoch = end_timestamp
        else:
            end_epoch = self._last_epoch

        duration = max(0.0, end_epoch - self._start_epoch)
        if duration < self.config.min_duration_seconds:
            # Ignore sub-threshold flicker
            self._current_process = None
            self._current_title = None
            self._start_time_iso = None
            return None

        end_time_iso = datetime.fromtimestamp(end_epoch, tz=timezone.utc).isoformat()

        event = ActivityEvent(
            client_id=self.config.client_id,
            start_time=self._start_time_iso,
            end_time=end_time_iso,
            duration_seconds=round(duration, 2),
            process_name=self._current_process,
            window_title=self._current_title or "",
            category=self._current_category,
            is_idle=self._current_is_idle,
        )

        self.buffer.insert(event)

        # Reset state
        self._current_process = None
        self._current_title = None
        self._start_time_iso = None

        return event

    def _start_new_interval(
        self,
        process_name: str,
        window_title: str,
        is_idle: bool,
        category: str = "Uncategorized",
        timestamp: Optional[float] = None,
    ) -> None:
        """Begin a new tracking interval."""
        ts = timestamp or time.time()
        self._current_process = process_name
        self._current_title = window_title
        self._current_is_idle = is_idle
        self._current_category = category
        self._start_epoch = ts
        self._last_epoch = ts
        self._start_time_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    def process_snapshot(self, snapshot: WindowActivityInfo) -> Optional[ActivityEvent]:
        """
        Process a single window/idle snapshot.
        Transitions state if process/title/idle state changed.
        Returns the committed ActivityEvent if an interval was flushed.
        """
        flushed_event: Optional[ActivityEvent] = None
        now = snapshot.timestamp

        is_screen_locked = (snapshot.process_name or "").lower() in ("lockapp.exe", "logonui.exe", "screensaver.exe")

        if snapshot.is_idle or is_screen_locked:
            target_proc = "idle"
            target_title = "Idle / Locked" if is_screen_locked else "Idle / Away"
            target_idle = True
            target_cat = "Idle / Away"
        else:
            # Check privacy ignore list
            if self.privacy.should_ignore_process(snapshot.process_name):
                target_proc = "[Private App]"
                target_title = "[Private Application Ignored]"
                target_cat = "Privacy / Ignored"
            else:
                sanitized_title, _ = self.privacy.sanitize_title(
                    snapshot.window_title, snapshot.process_name
                )
                target_proc = snapshot.process_name or "Unknown"
                target_title = sanitized_title
                target_cat = "Uncategorized"
            target_idle = False

        # Check if state matches current tracked interval
        same_state = (
            self._current_process == target_proc
            and self._current_title == target_title
            and self._current_is_idle == target_idle
        )

        if same_state:
            # Extend interval
            self._last_epoch = now
        else:
            # State changed: flush previous interval if any with transition timestamp
            if self._current_process is not None:
                flushed_event = self._flush_current_interval(end_timestamp=now)

            # Start new interval
            self._start_new_interval(
                process_name=target_proc,
                window_title=target_title,
                is_idle=target_idle,
                category=target_cat,
                timestamp=now,
            )

        # Periodic background sync check
        if now - self._last_sync_epoch >= self.config.sync_interval_seconds:
            self.sync_client.sync_pending(
                self.buffer, batch_size=self.config.sync_batch_size
            )
            self._last_sync_epoch = now

        return flushed_event

    def step(self) -> Optional[ActivityEvent]:
        """Capture one snapshot from Win32 monitor and process it."""
        snapshot = self.monitor.snapshot()
        return self.process_snapshot(snapshot)

    def stop(self) -> None:
        """Stop tracking and flush current state."""
        self._running = False
        self._flush_current_interval(end_timestamp=time.time())
        # Perform final sync
        try:
            self.sync_client.sync_pending(self.buffer, batch_size=self.config.sync_batch_size)
        except Exception:
            pass

    def run(self) -> None:
        """Start tracking loop with immediate startup capture and instant push."""
        self._running = True
        print(f"[Tracker] Started activity tracker for client '{self.config.client_id}'")
        print(f"[Tracker] Server: {self.config.server_url}")
        print(f"[Tracker] Local SQLite buffer: {self.config.db_path}")
        print(f"[Tracker] Idle threshold: {self.config.idle_threshold_seconds}s | Poll: {self.config.poll_interval_seconds}s")

        # 1. INSTANT INITIAL CAPTURE & IMMEDIATE SYNC
        now = time.time()
        initial_snap = self.monitor.snapshot()
        sanitized_title, _ = self.privacy.sanitize_title(
            initial_snap.window_title, initial_snap.process_name
        )
        proc = initial_snap.process_name or "System"
        title = sanitized_title or "Active Window"
        now_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()

        initial_event = ActivityEvent(
            client_id=self.config.client_id,
            start_time=now_iso,
            end_time=now_iso,
            duration_seconds=1.0,
            process_name=proc,
            window_title=title,
            category="Startup",
            is_idle=initial_snap.is_idle,
        )
        self.buffer.insert(initial_event)
        print(f"[*] Đang đẩy ngay hoạt động ban đầu lên Railway: [{proc}] '{title[:40]}'...")
        try:
            self.sync_client.sync_pending(self.buffer, batch_size=self.config.sync_batch_size)
            print("[*] Đã đẩy ngay hoạt động ban đầu lên Railway thành công!")
        except Exception as e:
            print(f"[!] Lỗi kết nối ban đầu (sẽ tự động thử lại): {e}")

        # Start continuous tracking
        self._start_new_interval(
            process_name=proc,
            window_title=title,
            is_idle=initial_snap.is_idle,
            category="Uncategorized",
            timestamp=now,
        )

        try:
            while self._running:
                self.step()
                time.sleep(self.config.poll_interval_seconds)
        except KeyboardInterrupt:
            print("\n[Tracker] Caught interrupt, stopping...")
        finally:
            self.stop()
            print("[Tracker] Stopped. All buffered activities saved.")
