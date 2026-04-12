from __future__ import annotations

import ctypes
import uuid
from collections import deque
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

import win32api
import win32con
import win32gui
import win32process

from activity_agent.core.models import (
    DesktopContext,
    FocusChange,
    ForegroundFocus,
)

_FOCUS_HISTORY_MAX = 10

_last_focus_key: tuple[int, str] | None = None

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

_focus_history: deque[FocusChange] = deque(maxlen=_FOCUS_HISTORY_MAX)

def _input_idle_seconds() -> float:
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    tick = ctypes.windll.kernel32.GetTickCount()
    idle_ms = (tick - lii.dwTime) & 0xFFFFFFFF
    return float(idle_ms) / 1000.0

def _process_exe_path(pid: int) -> tuple[str, str]:
    path = ""
    name = ""
    if pid <= 0:
        return path, name
    access = [
        win32con.PROCESS_QUERY_LIMITED_INFORMATION,
        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
    ]
    for flags in access:
        try:
            h = win32api.OpenProcess(flags, False, pid)
            try:
                path = win32process.GetModuleFileNameEx(h, 0)
            finally:
                win32api.CloseHandle(h)
            break
        except Exception:
            continue
    if path:
        name = Path(path).name
    return path, name

def _foreground_focus() -> ForegroundFocus | None:
    hwnd = int(win32gui.GetForegroundWindow())
    if not hwnd:
        return None
    title = win32gui.GetWindowText(hwnd) or ""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        return ForegroundFocus(
            hwnd=hwnd,
            title=title,
            pid=0,
            exe_name="",
            exe_path="",
        )
    exe_path, exe_name = _process_exe_path(int(pid))
    return ForegroundFocus(
        hwnd=hwnd,
        title=title,
        pid=int(pid),
        exe_name=exe_name,
        exe_path=exe_path,
    )

def _record_focus(fg: ForegroundFocus | None) -> None:
    global _last_focus_key
    if fg is None or fg.pid <= 0:
        return
    key = (fg.pid, fg.title)
    if key == _last_focus_key:
        return
    _last_focus_key = key
    _focus_history.append(
        FocusChange(
            at_utc=datetime.now(timezone.utc),
            title=fg.title,
            exe_name=fg.exe_name,
        )
    )

class DesktopContextCollector:
    def collect(self) -> DesktopContext:
        idle = _input_idle_seconds()
        fg = _foreground_focus()
        _record_focus(fg)
        return DesktopContext(
            id=str(uuid.uuid4()),
            captured_at=datetime.now(timezone.utc),
            foreground=fg,
            idle_seconds=idle,
            recent_focus_changes=tuple(_focus_history),
        )
