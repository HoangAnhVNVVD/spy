#!/usr/bin/env python3
"""
Windows Activity Tracker - Standalone Zero-Dependency Client
Requires ONLY Python 3.8+ standard library (no pip install required).
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import platform
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


@dataclass
class WindowSnapshot:
    process_name: str
    window_title: str
    pid: int
    hwnd: int
    idle_seconds: float
    is_idle: bool
    timestamp: float


class Win32Monitor:
    def __init__(self, idle_threshold_seconds: float = 120.0):
        self.idle_threshold_seconds = idle_threshold_seconds
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self._user32.GetWindowTextLengthW.restype = ctypes.c_int
        self._user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self._user32.GetWindowTextW.restype = ctypes.c_int
        self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        self._user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
        self._user32.GetLastInputInfo.restype = wintypes.BOOL

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
        ]
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.GetTickCount.restype = wintypes.DWORD

    def get_idle_seconds(self) -> float:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not self._user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        current_tick = self._kernel32.GetTickCount()
        last_input_tick = lii.dwTime
        diff = (current_tick - last_input_tick) & 0xFFFFFFFF
        return float(diff) / 1000.0

    def get_foreground_process_name(self, pid: int) -> str:
        if pid <= 0:
            return ""
        h_process = self._kernel32.OpenProcess(0x1000, False, pid)
        if not h_process:
            return f"pid_{pid}.exe"
        buf_size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        try:
            if self._kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(buf_size)):
                return os.path.basename(buf.value)
        finally:
            self._kernel32.CloseHandle(h_process)
        return f"pid_{pid}.exe"

    def snapshot(self) -> WindowSnapshot:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            idle_s = self.get_idle_seconds()
            return WindowSnapshot("", "", 0, 0, idle_s, idle_s >= self.idle_threshold_seconds, time.time())

        length = self._user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()

        pid_val = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
        pid = pid_val.value
        proc_name = self.get_foreground_process_name(pid)

        idle_s = self.get_idle_seconds()
        is_idle = idle_s >= self.idle_threshold_seconds
        if proc_name.lower() in ("lockapp.exe", "logonui.exe", "screensaver.exe"):
            is_idle = True

        return WindowSnapshot(
            process_name=proc_name,
            window_title=title,
            pid=pid,
            hwnd=int(hwnd),
            idle_seconds=idle_s,
            is_idle=is_idle,
            timestamp=time.time(),
        )


class SQLiteBuffer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    process_name TEXT NOT NULL,
                    window_title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    is_idle INTEGER NOT NULL,
                    synced INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_synced ON activity_buffer(synced)")

    def insert(self, record: Dict[str, Any]) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO activity_buffer (
                    client_id, process_name, window_title,
                    start_time, end_time, duration_seconds,
                    is_idle, synced, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    record["client_id"],
                    record["process_name"],
                    record["window_title"],
                    record["start_time"],
                    record["end_time"],
                    record["duration_seconds"],
                    1 if record["is_idle"] else 0,
                    time.time(),
                ),
            )

    def get_unsynced(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT id, client_id, process_name, window_title,
                       start_time, end_time, duration_seconds, is_idle
                FROM activity_buffer
                WHERE synced = 0
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "_id": r["id"],
                    "client_id": r["client_id"],
                    "process_name": r["process_name"],
                    "window_title": r["window_title"],
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "duration_seconds": r["duration_seconds"],
                    "is_idle": bool(r["is_idle"]),
                }
                for r in rows
            ]

    def mark_synced(self, record_ids: List[int]) -> None:
        if not record_ids:
            return
        placeholders = ",".join("?" for _ in record_ids)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE activity_buffer SET synced = 1 WHERE id IN ({placeholders})",
                record_ids,
            )


class StandaloneTracker:
    def __init__(
        self,
        server_url: str,
        api_token: str,
        client_id: str,
        poll_interval: float = 1.0,
        idle_threshold: float = 120.0,
        sync_interval: float = 30.0,
        raw_mode: bool = True,
    ):
        self.server_url = server_url.rstrip("/")
        self.api_token = api_token
        self.client_id = client_id or platform.node() or "windows-client"
        self.poll_interval = poll_interval
        self.idle_threshold = idle_threshold
        self.sync_interval = sync_interval
        self.raw_mode = raw_mode

        db_file = str(Path.home() / ".win_activity_tracker" / "buffer.db")
        self.buffer = SQLiteBuffer(db_file)
        self.monitor = Win32Monitor(idle_threshold_seconds=idle_threshold)

        self._last_state: Optional[Tuple[str, str, bool]] = None
        self._start_epoch: float = 0.0
        self._last_epoch: float = 0.0
        self._last_sync_epoch: float = time.time()

    def _to_iso(self, epoch: float) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime(epoch))

    def _flush_interval(self, end_epoch: Optional[float] = None) -> None:
        if self._last_state is None:
            return
        end_time = end_epoch or self._last_epoch
        duration = end_time - self._start_epoch
        if duration < 1.0:
            return

        proc, title, is_idle = self._last_state
        record = {
            "client_id": self.client_id,
            "process_name": proc or "(Unknown)",
            "window_title": title,
            "start_time": self._to_iso(self._start_epoch),
            "end_time": self._to_iso(end_time),
            "duration_seconds": round(duration, 2),
            "is_idle": is_idle,
        }
        self.buffer.insert(record)
        idle_tag = "[AFK]" if is_idle else "[ACTIVE]"
        print(f"[{time.strftime('%H:%M:%S')}] {idle_tag} {proc} - '{title[:45]}' ({duration:.1f}s)")

    def sync_to_server(self) -> None:
        unsynced = self.buffer.get_unsynced(limit=100)
        if not unsynced:
            return

        payload = [
            {
                "client_id": item["client_id"],
                "process_name": item["process_name"],
                "window_title": item["window_title"],
                "start_time": item["start_time"],
                "end_time": item["end_time"],
                "duration_seconds": item["duration_seconds"],
                "is_idle": item["is_idle"],
            }
            for item in unsynced
        ]
        ids = [item["_id"] for item in unsynced]

        endpoints = [
            f"{self.server_url}/api/v1/activities/batch",
            f"{self.server_url}/api/activities/batch",
        ]
        data = json.dumps(payload).encode("utf-8")
        last_err = None

        for url in endpoints:
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_token}",
                    "User-Agent": "WinActivityTrackerStandalone/1.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    if resp.status in (200, 201):
                        self.buffer.mark_synced(ids)
                        print(f"[*] Đã đồng bộ {len(ids)} bản ghi lên Railway ({self.server_url}) thành công.")
                        return
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 404:
                    continue
                break
            except Exception as e:
                last_err = e
                break

        if last_err:
            print(f"[!] Server offline hoặc chưa kết nối được: {last_err} (Dữ liệu đã được lưu an toàn trong SQLite).")

    def run(self) -> None:
        print("=" * 65)
        print(" Windows Activity Tracker - Standalone Client")
        print("=" * 65)
        print(f" Client ID       : {self.client_id}")
        print(f" Target Server   : {self.server_url}")
        print(f" Poll Interval   : {self.poll_interval}s")
        print(f" Idle Threshold  : {self.idle_threshold}s")
        print(f" Sync Interval   : {self.sync_interval}s")
        print(f" Raw Mode        : {'BẬT (Ghi 100% nguyên bản)' if self.raw_mode else 'TẮT'}")
        print("=" * 65)
        print("Đang khởi động... Đang chụp và gửi ngay lập tức lên Railway...\n")

        now = time.time()
        snap = self.monitor.snapshot()
        self._last_state = (snap.process_name, snap.window_title, snap.is_idle)
        self._start_epoch = now
        self._last_epoch = now

        # 1. INSTANT INITIAL CAPTURE & IMMEDIATE SYNC
        initial_record = {
            "client_id": self.client_id,
            "process_name": snap.process_name or "System",
            "window_title": snap.window_title or "Active Window",
            "start_time": self._to_iso(now),
            "end_time": self._to_iso(now),
            "duration_seconds": 1.0,
            "is_idle": snap.is_idle,
        }
        self.buffer.insert(initial_record)
        print(f"[*] Đẩy ngay hoạt động ban đầu: [{snap.process_name}] '{snap.window_title[:45]}'")
        self.sync_to_server()

        try:
            while True:
                time.sleep(self.poll_interval)
                now = time.time()
                snap = self.monitor.snapshot()
                current_state = (snap.process_name, snap.window_title, snap.is_idle)

                if current_state == self._last_state:
                    self._last_epoch = now
                else:
                    self._flush_interval(end_epoch=now)
                    self._last_state = current_state
                    self._start_epoch = now
                    self._last_epoch = now

                if now - self._last_sync_epoch >= self.sync_interval:
                    self.sync_to_server()
                    self._last_sync_epoch = now

        except KeyboardInterrupt:
            self._flush_interval(end_epoch=time.time())
            self.sync_to_server()
            print("\nĐã dừng Tracker.")


def main():
    parser = argparse.ArgumentParser(description="Windows Activity Tracker Standalone Client")
    parser.add_argument("--server-url", type=str, default="https://spy-production-8aaa.up.railway.app", help="Railway server URL")
    parser.add_argument("--api-token", type=str, default="hoanganh", help="Bearer API Token")
    parser.add_argument("--client-id", type=str, default="", help="Client ID identifier")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--idle-threshold", type=float, default=120.0, help="Idle AFK threshold in seconds")
    parser.add_argument("--sync-interval", type=float, default=30.0, help="Sync interval in seconds")
    parser.add_argument("--raw-mode", action="store_true", default=True, help="Record 100% raw details without filtering")

    args = parser.parse_args()

    tracker = StandaloneTracker(
        server_url=args.server_url,
        api_token=args.api_token,
        client_id=args.client_id,
        poll_interval=args.poll_interval,
        idle_threshold=args.idle_threshold,
        sync_interval=args.sync_interval,
        raw_mode=args.raw_mode,
    )
    tracker.run()


if __name__ == "__main__":
    main()
