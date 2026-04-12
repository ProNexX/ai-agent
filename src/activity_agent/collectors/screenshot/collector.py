from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import mss
import mss.tools
from mss.exception import ScreenShotError

from activity_agent.core.models import ScreenshotCapture

def _png_ihdr_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        sig = f.read(8)
        if len(sig) != 8 or sig != b"\x89PNG\r\n\x1a\n":
            raise ValueError("not a PNG file")
        f.read(4)  # IHDR length
        ctype = f.read(4)
        if ctype != b"IHDR":
            raise ValueError("missing IHDR chunk")
        w = int.from_bytes(f.read(4), "big")
        h = int.from_bytes(f.read(4), "big")
    return w, h

def _grim_output_names() -> list[str] | None:
    try:
        r = subprocess.run(
            ["grim", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    names: list[str] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("Output "):
            parts = line.split()
            if len(parts) >= 2:
                names.append(parts[1])
    return names if names else None

def _run_capture_cmd(cmd: list[str], label: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(
            f"{label} failed (exit {r.returncode})"
            + (f": {err}" if err else "")
        )

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
        failures: list[str] = []
        wayland = bool(sys.platform == "linux" and os.environ.get("WAYLAND_DISPLAY"))

        if wayland and shutil.which("grim"):
            try:
                return self._capture_all_grim(group_id, captured_at)
            except RuntimeError as e:
                failures.append(str(e))

        if wayland and shutil.which("spectacle"):
            try:
                return self._capture_all_spectacle(group_id, captured_at)
            except RuntimeError as e:
                failures.append(str(e))

        if wayland and shutil.which("gnome-screenshot"):
            try:
                return self._capture_all_gnome_screenshot(group_id, captured_at)
            except RuntimeError as e:
                failures.append(str(e))

        try:
            return self._capture_all_mss(group_id, captured_at)
        except ScreenShotError as e:
            failures.append(f"mss (X11): {e}")
            if sys.platform == "linux" and not wayland:
                if shutil.which("spectacle"):
                    try:
                        return self._capture_all_spectacle(group_id, captured_at)
                    except RuntimeError as de:
                        failures.append(str(de))
                if shutil.which("gnome-screenshot"):
                    try:
                        return self._capture_all_gnome_screenshot(group_id, captured_at)
                    except RuntimeError as de:
                        failures.append(str(de))
            hint = (
                "Could not capture the screen. Attempts:\n"
                + "\n".join(f"  - {x}" for x in failures)
                + "\n\n"
                "On KDE Wayland, install `spectacle` (e.g. `sudo pacman -S spectacle`). "
                "On GNOME, install `gnome-screenshot`. "
                "On wlroots (Sway/Hyprland), `grim` needs compositor support for the "
                "wlr screencopy protocol."
            )
            raise RuntimeError(hint) from e

    def _capture_all_mss(self, group_id: str, captured_at: datetime) -> list[ScreenshotCapture]:
        results: list[ScreenshotCapture] = []
        with mss.mss() as sct:
            monitors = sct.monitors[1:] or [sct.monitors[0]]
            for monitor_index, monitor in enumerate(monitors, start=1):
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

    def _capture_all_grim(self, group_id: str, captured_at: datetime) -> list[ScreenshotCapture]:
        results: list[ScreenshotCapture] = []
        names = _grim_output_names()
        specs: list[str | None] = names if names else [None]
        for monitor_index, oname in enumerate(specs, start=1):
            shot_id = str(uuid.uuid4())
            out_path = (self.output_dir / f"{self.filename_prefix}_{shot_id}.png").resolve()
            cmd = ["grim", "-t", "png"]
            if oname is not None:
                cmd.extend(["-o", oname])
            cmd.append(str(out_path))
            _run_capture_cmd(cmd, "grim")
            if not out_path.is_file():
                raise RuntimeError("grim did not write an image file")
            w, h = _png_ihdr_size(out_path)
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

    def _capture_all_spectacle(self, group_id: str, captured_at: datetime) -> list[ScreenshotCapture]:
        shot_id = str(uuid.uuid4())
        out_path = (self.output_dir / f"{self.filename_prefix}_{shot_id}.png").resolve()
        _run_capture_cmd(
            ["spectacle", "-b", "-f", "-o", str(out_path)],
            "spectacle",
        )
        if not out_path.is_file():
            raise RuntimeError("spectacle did not write a file")
        w, h = _png_ihdr_size(out_path)
        return [
            ScreenshotCapture(
                group_id=group_id,
                id=shot_id,
                path=out_path,
                width=w,
                height=h,
                captured_at=captured_at,
                monitor_index=1,
            )
        ]

    def _capture_all_gnome_screenshot(self, group_id: str, captured_at: datetime) -> list[ScreenshotCapture]:
        shot_id = str(uuid.uuid4())
        out_path = (self.output_dir / f"{self.filename_prefix}_{shot_id}.png").resolve()
        _run_capture_cmd(
            ["gnome-screenshot", f"--file={out_path}"],
            "gnome-screenshot",
        )
        if not out_path.is_file():
            raise RuntimeError("gnome-screenshot did not write a file")
        w, h = _png_ihdr_size(out_path)
        return [
            ScreenshotCapture(
                group_id=group_id,
                id=shot_id,
                path=out_path,
                width=w,
                height=h,
                captured_at=captured_at,
                monitor_index=1,
            )
        ]
