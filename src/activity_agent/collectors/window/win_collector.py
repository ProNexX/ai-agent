from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import win32con
import win32gui

@dataclass(frozen=True)
class WindowState:
    id: str
    captured_at: datetime
    titles: tuple[str, ...]

class WindowCollector:
    def collect(self) -> WindowState:
        titles = _visible_titled_window_titles()
        return WindowState(
            id=str(uuid.uuid4()),
            captured_at=datetime.now(timezone.utc),
            titles=tuple(titles),
        )

def _is_real_app(hwnd: int) -> bool:
    if not win32gui.IsWindowVisible(hwnd):
        return False
    if not win32gui.GetWindowText(hwnd):
        return False
    if win32gui.GetParent(hwnd) != 0:
        return False
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if ex_style & win32con.WS_EX_TOOLWINDOW:
        return False
    return True

def _visible_titled_window_titles() -> list[str]:
    titles: list[str] = []

    def callback(hwnd: int, _: object) -> None:
        if _is_real_app(hwnd):
            titles.append(win32gui.GetWindowText(hwnd))

    win32gui.EnumWindows(callback, None)
    return titles
