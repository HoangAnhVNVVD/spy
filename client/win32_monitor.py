"""Win32 active window and idle detection module.

Uses Windows native user32 and kernel32 APIs via ctypes.
Includes graceful fallbacks, permission handling, and test mockability.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional, Tuple


# Conditional Win32 types & structures
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("dwTime", wintypes.DWORD),
        ]
else:
    # Stubs for non-Windows test environments
    wintypes = None  # type: ignore
    LASTINPUTINFO = None  # type: ignore


# Try psutil for fast/reliable process name lookup
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class WindowActivityInfo:
    """Current active window state snapshot."""
    process_name: str
    window_title: str
    pid: int
    hwnd: int
    idle_seconds: float
    is_idle: bool
    timestamp: float


class Win32Monitor:
    """Monitors foreground window and user idle state using Win32 API."""

    def __init__(self, idle_threshold_seconds: float = 120.0):
        self.idle_threshold_seconds = idle_threshold_seconds
        self._user32 = None
        self._kernel32 = None

        if IS_WINDOWS:
            try:
                self._user32 = ctypes.windll.user32
                self._kernel32 = ctypes.windll.kernel32

                # Configure explicit 64-bit / 32-bit types for Win32 API functions
                self._user32.GetForegroundWindow.restype = wintypes.HWND
                self._user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
                self._user32.GetWindowTextLengthW.restype = ctypes.c_int
                self._user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
                self._user32.GetWindowTextW.restype = ctypes.c_int
                self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
                if LASTINPUTINFO is not None:
                    self._user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
                    self._user32.GetLastInputInfo.restype = wintypes.BOOL

                self._kernel32.GetTickCount.restype = wintypes.DWORD
                self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                self._kernel32.OpenProcess.restype = wintypes.HANDLE
                self._kernel32.QueryFullProcessImageNameW.argtypes = [
                    wintypes.HANDLE,
                    wintypes.DWORD,
                    wintypes.LPWSTR,
                    ctypes.POINTER(wintypes.DWORD),
                ]
                self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
                self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
                self._kernel32.CloseHandle.restype = wintypes.BOOL
            except Exception as e:
                print(f"[Win32Monitor] Warning: Could not load or configure user32/kernel32: {e}")

    def get_idle_seconds(self) -> float:
        """
        Return the elapsed time in seconds since the last mouse or keyboard input.
        Handles the 32-bit millisecond tick count wrap-around (approx. 49.7 days).
        """
        if not IS_WINDOWS or self._user32 is None or self._kernel32 is None:
            return 0.0

        try:
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if not self._user32.GetLastInputInfo(ctypes.byref(lii)):
                return 0.0

            # GetTickCount returns DWORD (32-bit unsigned)
            tick = self._kernel32.GetTickCount()
            # Handle unsigned 32-bit overflow
            idle_ms = (tick - lii.dwTime) & 0xFFFFFFFF
            return float(idle_ms) / 1000.0
        except Exception:
            return 0.0

    def is_user_idle(self) -> bool:
        """Check if user has been inactive for longer than idle_threshold_seconds."""
        return self.get_idle_seconds() >= self.idle_threshold_seconds

    def get_foreground_hwnd(self) -> int:
        """Return the handle of the current foreground window."""
        if not IS_WINDOWS or self._user32 is None:
            return 0
        try:
            return int(self._user32.GetForegroundWindow())
        except Exception:
            return 0

    def get_window_title(self, hwnd: int) -> str:
        """Retrieve the title text of the given window handle."""
        if not IS_WINDOWS or self._user32 is None or hwnd == 0:
            return ""

        try:
            length = self._user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buff = ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value.strip()
        except Exception:
            return ""

    def get_process_info(self, hwnd: int) -> Tuple[str, int]:
        """
        Return (process_name, pid) for the given window handle.
        Attempts ctypes QueryFullProcessImageNameW first, falls back to psutil.
        """
        if not IS_WINDOWS or self._user32 is None or hwnd == 0:
            return ("", 0)

        pid_val = wintypes.DWORD()  # type: ignore
        try:
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
        except Exception:
            return ("", 0)

        pid = pid_val.value
        if pid <= 0:
            return ("", 0)

        # Method A: Try via psutil if available
        if HAS_PSUTIL:
            try:
                proc = psutil.Process(pid)
                return (proc.name(), pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            except Exception:
                pass

        # Method B: Pure Win32 QueryFullProcessImageNameW
        if self._kernel32 is not None:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            try:
                h_process = self._kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if h_process:
                    try:
                        size = wintypes.DWORD(1024)  # type: ignore
                        buff = ctypes.create_unicode_buffer(1024)
                        if self._kernel32.QueryFullProcessImageNameW(h_process, 0, buff, ctypes.byref(size)):
                            exe_path = buff.value
                            name = os.path.basename(exe_path)
                            return (name, pid)
                    finally:
                        self._kernel32.CloseHandle(h_process)
            except Exception:
                pass

        return (f"pid_{pid}.exe", pid)

    def snapshot(self) -> WindowActivityInfo:
        """Capture the current active window snapshot and idle status."""
        idle_secs = self.get_idle_seconds()
        is_idle = idle_secs >= self.idle_threshold_seconds

        hwnd = self.get_foreground_hwnd()
        if hwnd:
            title = self.get_window_title(hwnd)
            proc_name, pid = self.get_process_info(hwnd)
        else:
            title = ""
            proc_name = ""
            pid = 0

        return WindowActivityInfo(
            process_name=proc_name,
            window_title=title,
            pid=pid,
            hwnd=hwnd,
            idle_seconds=idle_secs,
            is_idle=is_idle,
            timestamp=time.time(),
        )
