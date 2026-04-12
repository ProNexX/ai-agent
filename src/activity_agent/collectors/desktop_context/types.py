from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class FocusChange:
    at_utc: datetime
    title: str
    exe_name: str

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
