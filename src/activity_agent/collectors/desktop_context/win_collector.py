from __future__ import annotations

import ctypes
import uuid
from collections import deque
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import win32api
import win32con
import win32gui
import win32process

_FOCUS_HISTORY_MAX = 10

_last_focus_key: tuple[int, str] | None = None

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

@dataclass(frozen=True)
class FocusChange:
    at_utc: datetime
    title: str
    exe_name: str

_focus_history: deque[FocusChange] = deque(maxlen=_FOCUS_HISTORY_MAX)

@dataclass(frozen=True)
class ForegroundFocus:
    hwnd: int
    title: str
    pid: int
    exe_name: str
    exe_path: str

@dataclass(frozen=True)
class DesktopContext:
    id: str
    captured_at: datetime
    foreground: ForegroundFocus | None
    idle_seconds: float
    recent_focus_changes: tuple[FocusChange, ...]

    def prompt_section(self) -> str:
        lines: list[str] = [
            f"Seconds since last keyboard or mouse input: {self.idle_seconds:.1f}",
        ]
        fg = self.foreground
        if fg is not None:
            lines.append("Foreground window (keyboard focus):")
            lines.append(f"  title: {fg.title}")
            lines.append(f"  process: {fg.exe_name or '(unknown)'} (pid {fg.pid})")
            if fg.exe_path:
                lines.append(f"  executable path: {fg.exe_path}")
        else:
            lines.append("Foreground window: (none or unavailable)")
        if self.recent_focus_changes:
            lines.append("Recent focus switches in this Python process (oldest first):")
            for ch in self.recent_focus_changes:
                lines.append(
                    f"  {ch.at_utc.isoformat()} | {ch.exe_name or '?'} | {ch.title}"
                )
        return "\n".join(lines)

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
