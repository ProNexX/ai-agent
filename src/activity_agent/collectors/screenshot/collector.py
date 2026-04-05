from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import mss
import mss.tools

@dataclass(frozen=True)
class ScreenshotCapture:
    group_id: str
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

    def capture_all_monitors(self) -> list[ScreenshotCapture]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        group_id = str(uuid.uuid4())
        captured_at = datetime.now(timezone.utc)
        results: list[ScreenshotCapture] = []

        with mss.mss() as sct:
            physical = sct.monitors
            for monitor_index, monitor in enumerate(physical, start=1):
                shot_id = str(uuid.uuid4())
                out_path = (self.output_dir / f"{self.filename_prefix}_{shot_id}.png").resolve()
                img = sct.grab(monitor)
                mss.tools.to_png(img.rgb, img.size, output=str(out_path))
                w, h = img.size
                results.append(
                    ScreenshotCapture(
                        group_id=group_id,
                        id=shot_id,
                        path=out_path,
                        width=w,
                        height=h,
                        captured_at=captured_at,
                        monitor_index=monitor_index,
                    )
                )

        return results