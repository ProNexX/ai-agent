from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("FLAGS_use_mkldnn", "0")
# PaddleX defaults CPU inference to mkldnn/oneDNN; Paddle 3.3+ can crash in PIR→oneDNN
# (NotImplementedError in onednn_instruction). Disable unless explicitly overridden.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("FLAGS_fraction_of_gpu_memory_to_use", "0.85")

_ocr: Any = None

_MAX_OCR_SIDE = 2400

_warned_gpu_fallback: bool = False


def paddle_gpu_diag_lines() -> list[str]:
    """Lines for logs or support (import paddle)."""
    try:
        import paddle
    except ModuleNotFoundError:
        return ["paddle: not installed"]
    lines = [
        f"paddle version: {getattr(paddle, '__version__', '?')}",
        f"compiled_with_cuda: {paddle.device.is_compiled_with_cuda()}",
        f"cuda.device_count(): {paddle.device.cuda.device_count()}",
    ]
    try:
        v = paddle.version.cuda()
        if v:
            lines.append(f"paddle.version.cuda(): {v}")
    except Exception:
        pass
    return lines


def _warn_gpu_fallback_once(requested: str, compiled: bool, count: int) -> None:
    global _warned_gpu_fallback
    if _warned_gpu_fallback:
        return
    _warned_gpu_fallback = True
    import warnings

    msg = (
        f"OCR is set to {requested!r} but Paddle reports no usable GPU "
        f"(compiled_with_cuda={compiled}, cuda.device_count()={count}). "
        "Using CPU for PaddleOCR. "
    )
    if not compiled:
        msg += (
            "Typical fix: uninstall the CPU-only `paddlepaddle` wheel and install "
            "`paddlepaddle-gpu` from Paddle's pip index for your CUDA/driver; see README."
        )
    else:
        msg += (
            "Typical fix: ensure `nvidia-smi` works in this same environment, "
            "CUDA libraries are visible (driver install), and CUDA_VISIBLE_DEVICES "
            "does not hide all GPUs."
        )
    msg += " Run: python -m activity_agent.tools.paddle_gpu_check"
    warnings.warn(msg, UserWarning, stacklevel=2)


def _ocr_line_is_useful(line: str) -> bool:
    s = line.strip()
    if len(s) < 2:
        return False
    if not any(c.isalnum() for c in s):
        return False
    return True


def _filter_ocr_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    prev_norm: str | None = None
    for raw in lines:
        if not _ocr_line_is_useful(raw):
            continue
        s = raw.strip()
        norm = s.casefold()
        if norm == prev_norm:
            continue
        out.append(s)
        prev_norm = norm
    return out


def _apply_ocr_gpu_flags_from_config() -> None:
    try:
        from activity_agent.config_local import load_local_config

        frac = load_local_config().get("ocr_gpu_memory_fraction")
        if isinstance(frac, (int, float)) and 0 < float(frac) <= 1:
            os.environ["FLAGS_fraction_of_gpu_memory_to_use"] = str(float(frac))
    except Exception:
        pass

def _ocr_device() -> str:
    import paddle

    compiled = paddle.device.is_compiled_with_cuda()
    count = int(paddle.device.cuda.device_count())
    gpu_ok = compiled and count > 0

    requested = ""
    try:
        from activity_agent.config_local import load_local_config

        raw = load_local_config().get("ocr_device")
        if isinstance(raw, str) and raw.strip():
            requested = raw.strip()
    except Exception:
        pass

    if requested:
        low = requested.lower()
        if low.startswith("gpu"):
            if gpu_ok:
                return requested
            _warn_gpu_fallback_once(requested, compiled, count)
            return "cpu"
        return requested

    if gpu_ok:
        return "gpu:0"
    return "cpu"


def _get_ocr() -> Any:
    global _ocr
    if _ocr is None:
        _apply_ocr_gpu_flags_from_config()
        try:
            import paddle
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                "Install paddlepaddle first (import name is `paddle`). "
                "Paddle ships wheels for Python 3.10–3.13 only; use one of those for the venv."
            ) from e
        from paddleocr import PaddleOCR

        _ocr = PaddleOCR(
            lang="en",
            enable_mkldnn=False,
            device=_ocr_device(),
        )
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
        return "\n".join(_filter_ocr_lines(lines))
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
