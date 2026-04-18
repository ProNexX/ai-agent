"""Print whether Paddle can see CUDA (same checks as PaddleX OCR)."""

from __future__ import annotations

from activity_agent.inference.ocr.text import paddle_gpu_diag_lines


def main() -> None:
    print("Paddle GPU diagnostics (for OCR):")
    for line in paddle_gpu_diag_lines():
        print(" ", line)
    try:
        import paddle

        ok = paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
    except Exception as e:
        print(" error:", e)
        raise SystemExit(1) from e
    print(" usable for PaddleOCR GPU:", "yes" if ok else "no")
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
