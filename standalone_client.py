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
    _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]

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

    def __init__(self, idle_threshold_seconds: float=120.0):
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
        PROCESS_QUERY_LIMITED_INFORMATION = 4096
        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.GetTickCount.restype = wintypes.DWORD
        try:
            self._dwmapi = ctypes.windll.dwmapi
        except Exception:
            self._dwmapi = None

    def get_idle_seconds(self) -> float:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not self._user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        current_tick = self._kernel32.GetTickCount()
        last_input_tick = lii.dwTime
        diff = current_tick - last_input_tick & 4294967295
        return float(diff) / 1000.0

    def get_foreground_process_name(self, pid: int) -> str:
        if pid <= 0:
            return ''
        h_process = self._kernel32.OpenProcess(4096, False, pid)
        if not h_process:
            return f'pid_{pid}.exe'
        buf_size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        try:
            if self._kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(buf_size)):
                return os.path.basename(buf.value)
        finally:
            self._kernel32.CloseHandle(h_process)
        return f'pid_{pid}.exe'

    def get_open_taskbar_windows(self) -> List[Dict[str, Any]]:
        EnumWindows = self._user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        GetWindowLongW = self._user32.GetWindowLongW
        GetWindow = self._user32.GetWindow
        GetForegroundWindow = self._user32.GetForegroundWindow
        GetWindowTextLengthW = self._user32.GetWindowTextLengthW
        GetWindowTextW = self._user32.GetWindowTextW
        GetWindowThreadProcessId = self._user32.GetWindowThreadProcessId
        IsWindowVisible = self._user32.IsWindowVisible
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 128
        WS_EX_APPWINDOW = 262144
        GW_OWNER = 4
        DWMWA_CLOAKED = 14
        fg_hwnd = GetForegroundWindow()
        tasks: List[Dict[str, Any]] = []

        def enum_cb(hwnd, lparam):
            if not IsWindowVisible(hwnd):
                return True
            length = GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE)
            owner = GetWindow(hwnd, GW_OWNER)
            if ex_style & WS_EX_TOOLWINDOW and (not ex_style & WS_EX_APPWINDOW):
                return True
            if owner != 0 and (not ex_style & WS_EX_APPWINDOW):
                return True
            if self._dwmapi:
                cloaked = wintypes.DWORD(0)
                hr = self._dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
                if hr == 0 and cloaked.value != 0:
                    return True
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
            if not title or title == 'Program Manager':
                return True
            pid_val = wintypes.DWORD(0)
            GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
            pid = pid_val.value
            proc = self.get_foreground_process_name(pid)
            if proc.lower() in ('shellexperiencehost.exe', 'searchapp.exe', 'startmenuexperiencehost.exe'):
                return True
            tasks.append({'hwnd': int(hwnd), 'is_focused': hwnd == fg_hwnd, 'process_name': proc, 'window_title': title, 'pid': pid})
            return True
        EnumWindows(EnumWindowsProc(enum_cb), 0)
        tasks.sort(key=lambda x: (0 if x['is_focused'] else 1, x['process_name'].lower()))
        return tasks

    def snapshot(self) -> WindowSnapshot:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            idle_s = self.get_idle_seconds()
            return WindowSnapshot('', '', 0, 0, idle_s, idle_s >= self.idle_threshold_seconds, time.time())
        length = self._user32.GetWindowTextLengthW(hwnd)
        title = ''
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
        if proc_name.lower() in ('lockapp.exe', 'logonui.exe', 'screensaver.exe'):
            is_idle = True
        return WindowSnapshot(process_name=proc_name, window_title=title, pid=pid, hwnd=int(hwnd), idle_seconds=idle_s, is_idle=is_idle, timestamp=time.time())

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
            conn.execute('\n                CREATE TABLE IF NOT EXISTS activity_buffer (\n                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n                    client_id TEXT NOT NULL,\n                    process_name TEXT NOT NULL,\n                    window_title TEXT NOT NULL,\n                    start_time TEXT NOT NULL,\n                    end_time TEXT NOT NULL,\n                    duration_seconds REAL NOT NULL,\n                    is_idle INTEGER NOT NULL,\n                    synced INTEGER NOT NULL DEFAULT 0,\n                    created_at REAL NOT NULL\n                )\n                ')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_synced ON activity_buffer(synced)')

    def insert(self, record: Dict[str, Any]) -> None:
        with self._get_conn() as conn:
            conn.execute('\n                INSERT INTO activity_buffer (\n                    client_id, process_name, window_title,\n                    start_time, end_time, duration_seconds,\n                    is_idle, synced, created_at\n                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)\n                ', (record['client_id'], record['process_name'], record['window_title'], record['start_time'], record['end_time'], record['duration_seconds'], 1 if record['is_idle'] else 0, time.time()))

    def get_unsynced(self, limit: int=100) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.execute('\n                SELECT id, client_id, process_name, window_title,\n                       start_time, end_time, duration_seconds, is_idle\n                FROM activity_buffer\n                WHERE synced = 0\n                ORDER BY id ASC\n                LIMIT ?\n                ', (limit,))
            rows = cursor.fetchall()
            return [{'_id': r['id'], 'client_id': r['client_id'], 'process_name': r['process_name'], 'window_title': r['window_title'], 'start_time': r['start_time'], 'end_time': r['end_time'], 'duration_seconds': r['duration_seconds'], 'is_idle': bool(r['is_idle'])} for r in rows]

    def mark_synced(self, record_ids: List[int]) -> None:
        if not record_ids:
            return
        placeholders = ','.join(('?' for _ in record_ids))
        with self._get_conn() as conn:
            conn.execute(f'UPDATE activity_buffer SET synced = 1 WHERE id IN ({placeholders})', record_ids)

class StandaloneTracker:

    def __init__(self, server_url: str, api_token: str, client_id: str, poll_interval: float=1.0, idle_threshold: float=120.0, sync_interval: float=3.0, raw_mode: bool=True):
        self.server_url = server_url.rstrip('/')
        self.api_token = api_token
        self.client_id = client_id or platform.node() or 'windows-client'
        self.poll_interval = poll_interval
        self.idle_threshold = idle_threshold
        self.sync_interval = sync_interval
        self.raw_mode = raw_mode
        db_file = str(Path.home() / '.win_activity_tracker' / 'buffer.db')
        self.buffer = SQLiteBuffer(db_file)
        self.monitor = Win32Monitor(idle_threshold_seconds=idle_threshold)
        self._last_state: Optional[Tuple[str, str, bool]] = None
        self._start_epoch: float = 0.0
        self._last_epoch: float = 0.0
        self._last_sync_epoch: float = time.time()

    def _to_iso(self, epoch: float) -> str:
        return time.strftime('%Y-%m-%dT%H:%M:%S.000000Z', time.gmtime(epoch))

    def _flush_interval(self, end_epoch: Optional[float]=None) -> None:
        if self._last_state is None:
            return
        end_time = end_epoch or self._last_epoch
        duration = end_time - self._start_epoch
        if duration < 0.5:
            return
        proc, title, is_idle = self._last_state
        record = {'client_id': self.client_id, 'process_name': proc or '(Unknown)', 'window_title': title, 'start_time': self._to_iso(self._start_epoch), 'end_time': self._to_iso(end_time), 'duration_seconds': round(duration, 2), 'is_idle': is_idle}
        self.buffer.insert(record)
        idle_tag = '[AFK]' if is_idle else '[ACTIVE]'
        print(f"[{time.strftime('%H:%M:%S')}] {idle_tag} {proc} - '{title[:45]}' ({duration:.1f}s)")

    def sync_to_server(self) -> None:
        unsynced = self.buffer.get_unsynced(limit=100)
        open_tasks = self.monitor.get_open_taskbar_windows()
        if not unsynced and (not open_tasks):
            return
        activities = [{'process_name': item['process_name'], 'window_title': item['window_title'], 'start_time': item['start_time'], 'end_time': item['end_time'], 'duration_seconds': item['duration_seconds'], 'is_idle': item['is_idle']} for item in unsynced]
        ids = [item['_id'] for item in unsynced]
        payload = {'client_id': self.client_id, 'activities': activities, 'open_tasks': open_tasks, 'timestamp': self._to_iso(time.time())}
        endpoints = [f'{self.server_url}/api/v1/activities/batch', f'{self.server_url}/api/activities/batch']
        data = json.dumps(payload).encode('utf-8')
        last_err = None
        for url in endpoints:
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_token}', 'User-Agent': 'WinActivityTrackerStandalone/1.0'}, method='POST')
            try:
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    if resp.status in (200, 201):
                        resp_body = resp.read()
                        if resp_body:
                            try:
                                resp_json = json.loads(resp_body.decode('utf-8'))
                                if resp_json.get('is_isolated'):
                                    print(f"[{time.strftime('%H:%M:%S')}] [!] CẢNH BÁO PHÒNG THỦ: Máy tính này đang trong trạng thái CÔ LẬP / QUARANTINE trên Railway.")
                            except Exception:
                                pass
                        if ids:
                            self.buffer.mark_synced(ids)
                        focused = next((t for t in open_tasks if t.get('is_focused')), None)
                        f_name = focused['process_name'] if focused else '-'
                        other_names = [t['process_name'] for t in open_tasks if not t.get('is_focused')]
                        other_str = f" | Đang mở: {', '.join(other_names)}" if other_names else ''
                        print(f"[{time.strftime('%H:%M:%S')}] [*] Đã gửi lên Railway: {len(open_tasks)} ứng dụng [FOCUS: {f_name}]{other_str}")
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
            print(f'[!] Server offline hoặc chưa kết nối được: {last_err} (Dữ liệu đã được lưu an toàn trong SQLite).')

    def run(self) -> None:
        print('=' * 65)
        print(' Windows Activity Tracker - Standalone Client')
        print('=' * 65)
        print(f' Client ID       : {self.client_id}')
        print(f' Target Server   : {self.server_url}')
        print(f' Poll Interval   : {self.poll_interval}s')
        print(f' Idle Threshold  : {self.idle_threshold}s')
        print(f' Sync Interval   : {self.sync_interval}s (Cập nhật taskbar mỗi 3s)')
        print(f" Raw Mode        : {('BẬT (Ghi 100% nguyên bản)' if self.raw_mode else 'TẮT')}")
        print('=' * 65)
        print('Đang khởi động... Đang chụp và gửi ngay lập tức lên Railway...\n')
        now = time.time()
        snap = self.monitor.snapshot()
        self._last_state = (snap.process_name, snap.window_title, snap.is_idle)
        self._start_epoch = now
        self._last_epoch = now
        initial_record = {'client_id': self.client_id, 'process_name': snap.process_name or 'System', 'window_title': snap.window_title or 'Active Window', 'start_time': self._to_iso(now), 'end_time': self._to_iso(now), 'duration_seconds': 1.0, 'is_idle': snap.is_idle}
        self.buffer.insert(initial_record)
        print(f"[*] Đẩy ngay hoạt động ban đầu: [{snap.process_name}] '{snap.window_title[:45]}'")
        self.sync_to_server()
        self._last_sync_epoch = time.time()
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
            print('\nĐã dừng Tracker.')

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description='Windows Activity Tracker Standalone Client')
    parser.add_argument('--server-url', type=str, default='https://spy-production-8aaa.up.railway.app', help='Railway server URL')
    parser.add_argument('--api-token', type=str, default='hoanganh', help='Bearer API Token')
    parser.add_argument('--client-id', type=str, default='', help='Client ID identifier')
    parser.add_argument('--poll-interval', type=float, default=1.0, help='Polling interval in seconds')
    parser.add_argument('--idle-threshold', type=float, default=120.0, help='Idle AFK threshold in seconds')
    parser.add_argument('--sync-interval', type=float, default=3.0, help='Sync interval in seconds (default: 3.0s)')
    parser.add_argument('--raw-mode', action='store_true', default=True, help='Record 100%% raw details without filtering')
    parser.add_argument('--silent', action='store_true', default=False, help='Chạy ẩn hoàn toàn dưới nền Windows (không hiện cửa sổ console)')
    args = parser.parse_args()
    if args.silent and sys.platform == 'win32':
        try:
            hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd_console:
                ctypes.windll.user32.ShowWindow(hwnd_console, 0)
        except Exception:
            pass
    tracker = StandaloneTracker(server_url=args.server_url, api_token=args.api_token, client_id=args.client_id, poll_interval=args.poll_interval, idle_threshold=args.idle_threshold, sync_interval=args.sync_interval, raw_mode=args.raw_mode)
    tracker.run()
if __name__ == '__main__':
    main()
