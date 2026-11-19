"""PDF 核心操作：页面管理、合并拆分、图片互转、加密解密。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

import pymupdf
from pypdf import PdfReader, PdfWriter

ProgressCb = Callable[[int], None] | None
LogCb = Callable[[str], None] | None


def _report(progress: ProgressCb, value: int) -> None:
    if progress is not None:
        progress(max(0, min(100, int(value))))


def _log(log: LogCb, text: str) -> None:
    if log is not None:
        log(text)


def parse_page_range(text: str, total: int) -> list[int]:
    """解析 "1-3,5,7-8" 形式的页码范围，返回 0 基页索引列表。

    text 为空时返回全部页面。
    """
    raw = (text or "").strip().replace("，", ",").replace(" ", "")
    if not raw:
        return list(range(total))

    indices: list[int] = []
    for part in raw.split(","):
        if not part:
            continue
        if "-" in part:
            left, _, right = part.partition("-")
            try:
                start = int(left) if left else 1
                end = int(right) if right else total
            except ValueError as exc:
                raise ValueError(f"无法识别的页码：{part}") from exc
            if start > end:
                start, end = end, start
            if start < 1 or end > total:
                raise ValueError(f"页码超出范围 1-{total}：{part}")
            indices.extend(range(start - 1, end))
        else:
            try:
                page = int(part)
            except ValueError as exc:
                raise ValueError(f"无法识别的页码：{part}") from exc
            if page < 1 or page > total:
                raise ValueError(f"页码超出范围 1-{total}：{part}")
            indices.append(page - 1)

    seen: set[int] = set()
    ordered: list[int] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            ordered.append(idx)
    if not ordered:
        raise ValueError("页码范围为空")
    return ordered


def pdf_info(path: str | Path) -> dict:
    """读取 PDF 基本信息：页数、文件大小、是否加密、标题。"""
    info = {
        "pages": 0,
        "size": 0,
        "encrypted": False,
        "title": "",
        "error": "",
    }
    try:
        info["size"] = Path(path).stat().st_size
    except OSError:
        pass
    try:
        doc = pymupdf.open(str(path))
        try:
            info["pages"] = doc.page_count
            info["encrypted"] = bool(doc.needs_pass) or bool(doc.is_encrypted)
            meta = doc.metadata or {}
            info["title"] = (meta.get("title") or "").strip()
        finally:
            doc.close()
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
        try:
            reader = PdfReader(str(path))
            info["pages"] = len(reader.pages)
            info["encrypted"] = reader.is_encrypted
        except Exception:  # noqa: BLE001
            pass
    return info


def merge_pdfs(paths: Iterable[str | Path], output: str | Path,
               progress: ProgressCb = None, log: LogCb = None) -> str:
    files = [str(p) for p in paths]
    if not files:
        raise ValueError("没有可合并的文件")

    merged = pymupdf.open()
    try:
        for i, item in enumerate(files):
            _log(log, f"合并：{Path(item).name}")
            with pymupdf.open(item) as src:
                merged.insert_pdf(src)
            _report(progress, (i + 1) / len(files) * 95)
        merged.save(str(output), garbage=4, deflate=True)
    finally:
        merged.close()
    _report(progress, 100)
    return str(output)


def extract_pages(src: str | Path, output: str | Path, pages_text: str,
                  progress: ProgressCb = None) -> str:
    with pymupdf.open(str(src)) as doc:
        pages = parse_page_range(pages_text, doc.page_count)
        dst = pymupdf.open()
        try:
            for i, idx in enumerate(pages):
                dst.insert_pdf(doc, from_page=idx, to_page=idx)
                _report(progress, (i + 1) / len(pages) * 95)
            dst.save(str(output), garbage=4, deflate=True)
        finally:
            dst.close()
    _report(progress, 100)
    return str(output)


def split_by_count(src: str | Path, out_dir: str | Path, per_file: int,
                   progress: ProgressCb = None, log: LogCb = None) -> list[str]:
    per_file = max(1, int(per_file))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    with pymupdf.open(str(src)) as doc:
        total = doc.page_count
        chunks = (total + per_file - 1) // per_file
        for chunk in range(chunks):
            start = chunk * per_file
            end = min(start + per_file, total)
            dst = pymupdf.open()
            try:
                dst.insert_pdf(doc, from_page=start, to_page=end - 1)
                name = f"{Path(src).stem}_{chunk + 1:02d}.pdf"
                target = out_dir / name
                dst.save(str(target), garbage=4, deflate=True)
                created.append(str(target))
                _log(log, f"已生成：{name}")
            finally:
                dst.close()
            _report(progress, (chunk + 1) / chunks * 100)
    return created


def transform_pages(src: str | Path, output: str | Path,
                    order: list[int], rotations: dict[int, int],
                    progress: ProgressCb = None) -> str:
    """按 order（原始 0 基索引序列）与 rotations（原索引 -> 角度）重建 PDF。"""
    if not order:
        raise ValueError("PDF 中没有页面")
    with pymupdf.open(str(src)) as doc:
        dst = pymupdf.open()
        try:
            for i, idx in enumerate(order):
                dst.insert_pdf(doc, from_page=idx, to_page=idx)
                angle = rotations.get(idx, 0) % 360
                if angle:
                    dst[-1].set_rotation(angle)
                _report(progress, (i + 1) / len(order) * 95)
            dst.save(str(output), garbage=4, deflate=True)
        finally:
            dst.close()
    _report(progress, 100)
    return str(output)


def pdf_to_images(src: str | Path, out_dir: str | Path, dpi: int = 150,
                  fmt: str = "png", pages_text: str = "",
                  progress: ProgressCb = None, log: LogCb = None) -> list[str]:
    fmt = fmt.lower()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    with pymupdf.open(str(src)) as doc:
        indices = parse_page_range(pages_text, doc.page_count)
        stem = Path(src).stem
        for i, idx in enumerate(indices):
            page = doc[idx]
            pix = page.get_pixmap(dpi=max(36, int(dpi)), alpha=False)
            if fmt in ("jpg", "jpeg"):
                data = pix.tobytes("jpeg", jpg_quality=90)
                ext = "jpg"
            else:
                data = pix.tobytes("png")
                ext = "png"
            target = out_dir / f"{stem}_{idx + 1:03d}.{ext}"
            target.write_bytes(data)
            created.append(str(target))
            _log(log, f"导出：{target.name}")
            _report(progress, (i + 1) / len(indices) * 100)
    return created


def _page_size_for_image(path: Path, mode: str) -> tuple[float, float]:
    """返回页面尺寸（点）。A4 固定 595x842；原始尺寸按 96 DPI 换算。"""
    if mode == "a4":
        return 595.0, 842.0
    try:
        pix = pymupdf.Pixmap(str(path))
        try:
            width = max(1.0, pix.width * 72.0 / 96.0)
            height = max(1.0, pix.height * 72.0 / 96.0)
        finally:
            pix = None
        return width, height
    except Exception:  # noqa: BLE001
        return 595.0, 842.0


def images_to_pdf(paths: Iterable[str | Path], output: str | Path,
                  fit: str = "a4", progress: ProgressCb = None,
                  log: LogCb = None) -> str:
    files = [Path(p) for p in paths]
    if not files:
        raise ValueError("没有可转换的图片")

    doc = pymupdf.open()
    try:
        for i, path in enumerate(files):
            width, height = _page_size_for_image(path, fit)
            page = doc.new_page(width=width, height=height)
            if fit == "a4":
                rect = page.rect
                margin = 24.0
                box = pymupdf.Rect(margin, margin, rect.width - margin, rect.height - margin)
                try:
                    page.insert_image(box, filename=str(path), keep_proportion=True)
                except Exception:  # noqa: BLE001
                    pix = pymupdf.Pixmap(str(path))
                    if pix.alpha:
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    page.insert_image(box, stream=pix.tobytes("png"), keep_proportion=True)
            else:
                try:
                    page.insert_image(page.rect, filename=str(path))
                except Exception:  # noqa: BLE001
                    pix = pymupdf.Pixmap(str(path))
                    if pix.alpha:
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    page.insert_image(page.rect, stream=pix.tobytes("png"))
            _log(log, f"添加：{path.name}")
            _report(progress, (i + 1) / len(files) * 95)
        doc.save(str(output), garbage=4, deflate=True)
    finally:
        doc.close()
    _report(progress, 100)
    return str(output)


def encrypt_pdf(src: str | Path, output: str | Path, user_password: str,
                owner_password: str = "") -> str:
    if not user_password:
        raise ValueError("密码不能为空")
    reader = PdfReader(str(src))
    if reader.is_encrypted:
        reader.decrypt("")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    try:
        writer.encrypt(user_password, owner_password or user_password, algorithm="AES-256")
    except ImportError:
        # 缺少 cryptography 时退回 RC4-128，仍可正常加密
        writer.encrypt(user_password, owner_password or user_password, algorithm="RC4-128")
    with open(str(output), "wb") as handle:
        writer.write(handle)
    return str(output)


def decrypt_pdf(src: str | Path, output: str | Path, password: str) -> str:
    reader = PdfReader(str(src))
    if reader.is_encrypted:
        result = reader.decrypt(password or "")
        if not result:
            raise ValueError("密码错误，无法解密。")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with open(str(output), "wb") as handle:
        writer.write(handle)
    return str(output)


def render_thumbnail(src: str | Path, page_index: int, width: int = 150) -> bytes:
    """渲染指定页为 PNG 字节，用于页面管理器缩略图。"""
    with pymupdf.open(str(src)) as doc:
        page = doc[page_index]
        zoom = width / max(1.0, page.rect.width)
        matrix = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix.tobytes("png")
