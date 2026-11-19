"""PDF 压缩：按 PPI 重采样、按目标体积、极限栅格化。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pymupdf

ProgressCb = Callable[[int], None] | None
LogCb = Callable[[str], None] | None

# 按目标体积时依次尝试的参数（PPI, JPEG 质量）
_TARGET_PRESETS = [
    (220, 88),
    (200, 82),
    (180, 78),
    (150, 72),
    (130, 65),
    (110, 58),
    (96, 50),
    (84, 45),
    (72, 40),
    (60, 32),
]


def _log(log: LogCb, text: str) -> None:
    if log is not None:
        log(text)


def _progress(progress: ProgressCb, value: int) -> None:
    if progress is not None:
        progress(max(0, min(100, int(value))))


def _threshold_for(dpi: int) -> int:
    """高于该 PPI 的图片才会被重采样；必须大于 dpi_target。"""
    return max(int(dpi) + 1, int(round(dpi * 1.25)))


def _save_optimized(doc: pymupdf.Document, output: str | Path) -> None:
    try:
        doc.subset_fonts()
    except Exception:  # noqa: BLE001 - 某些 PDF 无法子集化字体
        pass
    doc.save(
        str(output),
        garbage=4,
        deflate=True,
        deflate_images=True,
        deflate_fonts=True,
        clean=True,
        use_objstms=1,
    )


def _stats(src: str | Path, output: str | Path) -> dict:
    before = os.path.getsize(src)
    after = os.path.getsize(output)
    percent = 0.0
    if before > 0:
        percent = max(0.0, (1 - after / before) * 100)
    return {
        "output": str(output),
        "before": before,
        "after": after,
        "percent": round(percent, 1),
    }


def compress_pdf(src: str | Path, output: str | Path, mode: str = "ppi",
                 dpi: int = 150, quality: int = 70,
                 target_mb: float = 2.0,
                 progress: ProgressCb = None, log: LogCb = None) -> dict:
    """压缩 PDF。

    mode:
        "ppi"    —— 按 PPI 重压缩图片
        "target" —— 尝试多组参数逼近目标体积（MB）
        "raster" —— 每页渲染为 JPEG 重新封装（体积最小，文字不可选）
    """
    src_path = Path(src)
    out_path = Path(output)
    if not src_path.exists():
        raise FileNotFoundError(f"文件不存在：{src_path}")
    dpi = max(36, min(600, int(dpi)))
    quality = max(10, min(95, int(quality)))

    if mode == "raster":
        return _compress_raster(src_path, out_path, dpi, quality, progress, log)
    if mode == "target":
        return _compress_target(src_path, out_path, float(target_mb), progress, log)

    _log(log, f"按 {dpi} PPI / 质量 {quality} 压缩图片…")
    _progress(progress, 10)
    doc = pymupdf.open(str(src_path))
    try:
        # 必须显式指定 dpi_target，否则 MuPDF 会把图片压成空白
        doc.rewrite_images(
            dpi_threshold=_threshold_for(dpi), dpi_target=dpi, quality=quality
        )
        _progress(progress, 70)
        _save_optimized(doc, out_path)
    finally:
        doc.close()
    _progress(progress, 100)
    return _stats(src_path, out_path)


def _compress_target(src_path: Path, out_path: Path, target_mb: float,
                     progress: ProgressCb, log: LogCb) -> dict:
    target_bytes = max(0.05, target_mb) * 1024 * 1024
    best_tmp: Path | None = None
    best_size = float("inf")
    passes = len(_TARGET_PRESETS)

    for i, (dpi, quality) in enumerate(_TARGET_PRESETS):
        tmp = out_path.with_name(f".{out_path.stem}.pass{i}.pdf")
        _log(log, f"第 {i + 1} 轮：{dpi} PPI / 质量 {quality}")
        doc = pymupdf.open(str(src_path))
        try:
            doc.rewrite_images(dpi_threshold=_threshold_for(dpi), dpi_target=dpi, quality=quality)
            _save_optimized(doc, tmp)
        finally:
            doc.close()

        size = tmp.stat().st_size
        if size < best_size:
            if best_tmp is not None and best_tmp.exists():
                best_tmp.unlink(missing_ok=True)
            best_tmp, best_size = tmp, size
        else:
            tmp.unlink(missing_ok=True)

        _progress(progress, 10 + (i + 1) / passes * 80)
        if size <= target_bytes:
            _log(log, f"已达到目标体积：{size / 1048576:.2f} MB")
            break

    if best_tmp is None:
        raise RuntimeError("压缩失败：未能生成有效文件")
    if out_path.exists():
        out_path.unlink()
    best_tmp.replace(out_path)
    _progress(progress, 100)
    return _stats(src_path, out_path)


def _compress_raster(src_path: Path, out_path: Path, dpi: int, quality: int,
                     progress: ProgressCb, log: LogCb) -> dict:
    _log(log, f"栅格化压缩：{dpi} PPI / 质量 {quality}")
    src_doc = pymupdf.open(str(src_path))
    dst = pymupdf.open()
    try:
        total = src_doc.page_count
        for i, page in enumerate(src_doc):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            data = pix.tobytes("jpeg", jpg_quality=quality)
            new_page = dst.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=data)
            _progress(progress, (i + 1) / max(1, total) * 90)
        dst.save(
            str(out_path),
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True,
            use_objstms=1,
        )
    finally:
        dst.close()
        src_doc.close()
    _progress(progress, 100)
    return _stats(src_path, out_path)
