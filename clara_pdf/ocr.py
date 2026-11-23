"""OCR 封装：优先 Windows 内置识别（Windows.Media.Ocr），可选 EasyOCR 后备。

Windows OCR 通过 ``winrt`` 投影包调用系统自带识别引擎，无需下载模型、无需联网；
若系统缺少 winrt 组件但装有 easyocr，则退回 EasyOCR。
"""

from __future__ import annotations

import asyncio

import pymupdf


class OcrUnavailable(Exception):
    """没有任何可用的 OCR 后端。"""


def available_languages() -> list[str]:
    """Windows OCR 已安装的识别语言标签，例如 ``zh-Hans-CN`` / ``en-US``。"""
    try:
        from winrt.windows.media.ocr import OcrEngine
        return [lang.language_tag for lang in OcrEngine.available_recognizer_languages]
    except Exception:  # noqa: BLE001
        return []


def backend_available() -> bool:
    if available_languages():
        return True
    try:
        import easyocr  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def pick_language(preferred: str | None = None) -> str | None:
    """挑选识别语言：优先调用方指定，其次中文，再次英文，最后任一可用语言。"""
    langs = available_languages()
    if not langs:
        return None
    if preferred and preferred in langs:
        return preferred
    for prefix in ("zh", "en"):
        for tag in langs:
            if tag.lower().startswith(prefix):
                return tag
    return langs[0]


def ocr_pixmap(pix: pymupdf.Pixmap, lang: str | None = None) -> list[dict]:
    """识别位图中的文字。

    返回 ``[{"text": 整行文字, "bbox": (x0, y0, x1, y1)}]``，坐标单位为像素。
    """
    lines = _ocr_winrt(pix, lang)
    if lines is not None:
        return lines
    return _ocr_easyocr(pix)


# ---------------- Windows OCR ----------------
def _bgra_bytes(pix: pymupdf.Pixmap) -> tuple[bytes, int, int]:
    """把 Pixmap 转成 BGRA8 原始字节（SoftwareBitmap 要求的格式）。"""
    if pix.colorspace is None or pix.n - pix.alpha != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    w, h, n = pix.width, pix.height, pix.n
    src = pix.samples
    out = bytearray(w * h * 4)
    out[0::4] = src[2::n]
    out[1::4] = src[1::n]
    out[2::4] = src[0::n]
    if n >= 4:
        out[3::4] = src[3::n]
    else:
        out[3::4] = b"\xff" * (w * h)
    return bytes(out), w, h


async def _recognize(engine, bitmap):
    return await engine.recognize_async(bitmap)


def _ocr_winrt(pix: pymupdf.Pixmap, lang: str | None) -> list[dict] | None:
    """用 Windows.Media.Ocr 识别；winrt 不可用时返回 None。"""
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import (
            BitmapAlphaMode,
            BitmapPixelFormat,
            SoftwareBitmap,
        )
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter
    except Exception:  # noqa: BLE001
        return None

    tag = pick_language(lang)
    engine = OcrEngine.try_create_from_language(Language(tag)) if tag else None
    if engine is None:
        engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return []

    data, w, h = _bgra_bytes(pix)
    writer = DataWriter()
    writer.write_bytes(data)
    bitmap = SoftwareBitmap.create_copy_from_buffer(
        writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h,
        BitmapAlphaMode.PREMULTIPLIED)
    result = asyncio.run(_recognize(engine, bitmap))

    lines: list[dict] = []
    for line in result.lines:
        words = list(line.words)
        if not words or not line.text.strip():
            continue
        rects = [word.bounding_rect for word in words]
        x0 = min(r.x for r in rects)
        y0 = min(r.y for r in rects)
        x1 = max(r.x + r.width for r in rects)
        y1 = max(r.y + r.height for r in rects)
        lines.append({"text": line.text, "bbox": (x0, y0, x1, y1)})
    return lines


# ---------------- EasyOCR 后备 ----------------
_easy_reader = None


def _ocr_easyocr(pix: pymupdf.Pixmap) -> list[dict]:
    global _easy_reader
    try:
        import easyocr
        import numpy as np
    except Exception as exc:  # noqa: BLE001
        raise OcrUnavailable("没有可用的 OCR 组件。") from exc
    if _easy_reader is None:
        _easy_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8)
    img = img.reshape(pix.height, pix.width, pix.n)[:, :, :3][:, :, ::-1]
    lines: list[dict] = []
    for points, text, _conf in _easy_reader.readtext(img, detail=1, paragraph=False):
        if not str(text).strip():
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        lines.append({
            "text": str(text),
            "bbox": (min(xs), min(ys), max(xs), max(ys)),
        })
    return lines
