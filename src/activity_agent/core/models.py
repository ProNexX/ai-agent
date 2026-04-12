from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_GiB = 1024**3

@dataclass(frozen=True)
class ScreenshotCapture:
    group_id: str
    id: str
    path: Path
    width: int
    height: int
    captured_at: datetime
    monitor_index: int

@dataclass(frozen=True)
class WindowState:
    id: str
    captured_at: datetime
    titles: tuple[str, ...]

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

@dataclass(frozen=True)
class SystemLoadState:
    id: str
    captured_at: datetime
    cpu_percent: float
    cpu_count_logical: int
    memory_used_bytes: int
    memory_total_bytes: int
    memory_percent: float
    swap_percent: float

    def prompt_section(self) -> str:
        used_gib = self.memory_used_bytes / _GiB
        total_gib = self.memory_total_bytes / _GiB if self.memory_total_bytes else 0.0
        return (
            f"CPU usage (sampled ~100ms): {self.cpu_percent:.1f}% "
            f"({self.cpu_count_logical} logical processors)\n"
            f"RAM: {self.memory_percent:.1f}% used ({used_gib:.2f} / {total_gib:.2f} GiB)\n"
            f"Swap / page file use: {self.swap_percent:.1f}%"
        )

@dataclass(frozen=True)
class SavedPipelineRow:
    id: int
    capture_id: str
    image_path: str
    ocr_text: str
    llm_text: str
    captured_at: str
    processed_at: str
    worked_at: str


@dataclass(frozen=True)
class PipelineResultRecord:
    """Full `pipeline_results` row (timestamps as ISO strings from SQLite)."""

    id: int
    capture_id: str
    image_path: str
    ocr_text: str
    llm_text: str
    captured_at: str
    processed_at: str
    worked_at: str