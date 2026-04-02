from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import mss
import mss.tools

@dataclass(frozen=True)
class ScreenshotCapture:
    id: str
    path: Path
    width: int
    height: int
    captured_at: datetime
    monitor_index: int

class ScreenshotCollector:
    def __init__(
        self,
        output_dir: Path | None = None,
        monitor_index: int = 0,
        filename_prefix: str = "screen",
    ) -> None:
        self.output_dir = output_dir or Path("assets") / "captures"
        self.monitor_index = monitor_index
        self.filename_prefix = filename_prefix

    def capture(self) -> ScreenshotCapture:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        shot_id = str(uuid.uuid4())
        out_path = (self.output_dir / f"{self.filename_prefix}_{shot_id}.png").resolve()

        with mss.mss() as sct:
            if self.monitor_index < 0 or self.monitor_index >= len(sct.monitors):
                raise ValueError(
                    f"monitor_index {self.monitor_index} invalid (0..{len(sct.monitors) - 1})"
                )
            screenshot = sct.grab(sct.monitors[self.monitor_index])

        mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(out_path))
        w, h = screenshot.size
        return ScreenshotCapture(
            id=shot_id,
            path=out_path,
            width=w,
            height=h,
            captured_at=datetime.now(timezone.utc),
            monitor_index=self.monitor_index,
        )