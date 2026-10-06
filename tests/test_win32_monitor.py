from unittest.mock import MagicMock
from client.win32_monitor import Win32Monitor, WindowActivityInfo

def test_monitor_initialization():
    monitor = Win32Monitor(idle_threshold_seconds=60.0)
    assert monitor.idle_threshold_seconds == 60.0

def test_monitor_idle_calculation_overflow_wrapping():
    monitor = Win32Monitor(idle_threshold_seconds=10.0)
    dw_time = 4294967040
    tick = 100
    diff_ms = tick - dw_time & 4294967295
    assert diff_ms == 356

def test_monitor_snapshot_structure():
    monitor = Win32Monitor()
    snap = monitor.snapshot()
    assert isinstance(snap, WindowActivityInfo)
    assert isinstance(snap.idle_seconds, float)
    assert isinstance(snap.is_idle, bool)
    assert isinstance(snap.process_name, str)
    assert isinstance(snap.window_title, str)
    assert isinstance(snap.pid, int)
    assert isinstance(snap.timestamp, float)

def test_monitor_mocked_foreground():
    monitor = Win32Monitor()
    mock_user32 = MagicMock()
    mock_user32.GetForegroundWindow.return_value = 0
    monitor._user32 = mock_user32
    hwnd = monitor.get_foreground_hwnd()
    assert hwnd == 0
    assert monitor.get_window_title(0) == ''
    assert monitor.get_process_info(0) == ('', 0)
