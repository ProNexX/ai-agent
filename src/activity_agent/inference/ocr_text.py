from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("FLAGS_use_mkldnn", "0")

_ocr: Any = None

_MAX_OCR_SIDE = 2400


def _get_ocr() -> Any:
    global _ocr
    if _ocr is None:
        try:
            import paddle  # noqa: F401
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                "Install paddlepaddle first (import name is `paddle`). "
                "Paddle ships wheels for Python 3.10–3.13 only; use one of those for the venv."
            ) from e
        from paddleocr import PaddleOCR

        _ocr = PaddleOCR(lang="en", enable_mkldnn=False)
    return _ocr


def _work_path_for_ocr(image_path: Path) -> tuple[Path, Path | None]:
    from PIL import Image

    with Image.open(image_path) as im:
        w, h = im.size
        if max(w, h) <= _MAX_OCR_SIDE:
            return image_path, None
        s = _MAX_OCR_SIDE / max(w, h)
        nw, nh = int(w * s), int(h * s)
        rgb = im.convert("RGB").resize((nw, nh), Image.Resampling.LANCZOS)
        fd, name = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        out = Path(name)
        rgb.save(out, "PNG")
        return out, out


def image_to_text(image_path: Path, ocr: Any = None) -> str:
    engine = ocr or _get_ocr()
    path, tmp = _work_path_for_ocr(image_path.resolve())
    try:
        lines: list[str] = []
        for item in engine.predict(str(path)):
            rec = item["rec_texts"] if "rec_texts" in item else []
            for t in rec:
                if isinstance(t, (list, tuple)):
                    lines.append(str(t[0]))
                else:
                    lines.append(str(t))
        return "\n".join(lines)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
