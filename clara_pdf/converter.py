"""格式转换：PDF ↔ Word、PDF ↔ Excel。

PDF → Office 使用 PyMuPDF 抽取版式；Office → PDF 调用本机 Microsoft Office。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Callable

import pymupdf
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

ProgressCb = Callable[[int], None] | None
LogCb = Callable[[str], None] | None

TEXT_COLOR = RGBColor(0x1F, 0x23, 0x28)


def _report(progress: ProgressCb, value: int) -> None:
    if progress is not None:
        progress(max(0, min(100, int(value))))


def _log(log: LogCb, text: str) -> None:
    if log is not None:
        log(text)


# --------------------------------------------------------------------------
# PDF → Word
# --------------------------------------------------------------------------
def _is_ascii_word(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or ch in ")]}.,;:!?%$#@&*/+=~-'\"")


_CJK_PUNCT = set("，。、；：？！（）【】《》〈〉“”‘’…—～·「」")


def _needs_space(prev: str, nxt: str) -> bool:
    """英文单词之间、中英文交界处补空格；中英文标点两侧不补。"""
    if prev in _CJK_PUNCT or nxt in _CJK_PUNCT:
        return False
    if _is_ascii_word(prev) and _is_ascii_word(nxt):
        return True
    if prev.isascii() and prev.isalnum() and not nxt.isascii():
        return True
    if not prev.isascii() and nxt.isascii() and nxt.isalnum():
        return True
    return False


def _smart_join(parts: list[str]) -> str:
    """拼接 PDF 中的多行文本：中文直接相连，英文单词之间补空格。"""
    text = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if not text:
            text = piece
            continue
        prev, nxt = text[-1], piece[0]
        if prev == "-" and nxt.isascii() and nxt.islower():
            text = text[:-1] + piece
        elif _needs_space(prev, nxt):
            text = f"{text} {piece}"
        else:
            text += piece
    return text


def _set_run_font(run, size: float, bold: bool = False) -> None:
    run.font.name = "Microsoft YaHei"
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = TEXT_COLOR
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        from docx.oxml import OxmlElement

        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), "Microsoft YaHei")
    rfonts.set(qn("w:hAnsi"), "Microsoft YaHei")
    rfonts.set(qn("w:eastAsia"), "Microsoft YaHei")


def _configure_document(doc: Document, page_rect, base_size: float) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal.font.size = Pt(base_size)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        from docx.oxml import OxmlElement

        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), "Microsoft YaHei")
    rfonts.set(qn("w:hAnsi"), "Microsoft YaHei")
    rfonts.set(qn("w:eastAsia"), "Microsoft YaHei")

    section = doc.sections[0]
    # 页面按原 PDF 尺寸设置，限制在合理区间内
    width = max(400.0, min(page_rect.width, 1200.0))
    height = max(400.0, min(page_rect.height, 1800.0))
    section.page_width = Pt(width)
    section.page_height = Pt(height)
    section.left_margin = Pt(51)
    section.right_margin = Pt(51)
    section.top_margin = Pt(51)
    section.bottom_margin = Pt(51)


def _base_font_size(pdf) -> float:
    """按字符数统计最常见的字号，作为正文字号。"""
    counter: dict[float, int] = {}
    for page in pdf:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    key = round(span.get("size", 11.0) * 2) / 2
                    counter[key] = counter.get(key, 0) + len(text)
    if not counter:
        return 11.0
    return max(counter.items(), key=lambda item: item[1])[0]


def _block_text(block: dict) -> tuple[str, float, float]:
    """返回 (文本, 最大字号, 粗体占比)。"""
    parts: list[str] = []
    max_size = 0.0
    bold_hits = 0
    span_total = 0
    for line in block.get("lines", []):
        line_parts: list[str] = []
        for span in line.get("spans", []):
            text = span.get("text", "")
            if not text.strip():
                continue
            line_parts.append(text)
            span_total += 1
            if span.get("flags", 0) & 16:  # bold flag
                bold_hits += 1
            max_size = max(max_size, span.get("size", 0.0))
        if line_parts:
            parts.append("".join(line_parts))
    bold_ratio = bold_hits / span_total if span_total else 0.0
    return _smart_join(parts).strip(), max_size, bold_ratio


def _add_word_table(doc: Document, table, font_size: float) -> bool:
    """把 PyMuPDF 表格写入 Word；无有效内容时返回 False。"""
    try:
        data = table.extract()
    except Exception:  # noqa: BLE001
        return False
    if not data:
        return False
    cols = max((len(row) for row in data), default=0)
    if cols == 0:
        return False

    word_table = doc.add_table(rows=len(data), cols=cols)
    word_table.style = "Table Grid"
    word_table.autofit = True
    for r, row in enumerate(data):
        for c in range(cols):
            value = row[c] if c < len(row) else None
            cell = word_table.cell(r, c)
            cell.text = ""
            para = cell.paragraphs[0]
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = 1.0
            run = para.add_run("" if value is None else str(value).strip())
            _set_run_font(run, font_size, r == 0)
    return True


def pdf_to_docx(src: str | Path, output: str | Path,
                progress: ProgressCb = None, log: LogCb = None) -> str:
    pdf = pymupdf.open(str(src))
    try:
        if pdf.page_count == 0:
            raise ValueError("PDF 中没有页面")
        if pdf.needs_pass:
            raise ValueError("该 PDF 已加密，请先解密后再转换")

        first_rect = pdf[0].rect
        base_size = _base_font_size(pdf)

        doc = Document()
        _configure_document(doc, first_rect, base_size)
        usable_width = first_rect.width - 102.0
        wrote_content = False

        for pno, page in enumerate(pdf):
            _log(log, f"解析第 {pno + 1}/{pdf.page_count} 页")
            blocks = page.get_text(
                "dict", flags=pymupdf.TEXT_PRESERVE_IMAGES
            )["blocks"]

            try:
                tables = list(page.find_tables().tables)
            except Exception:  # noqa: BLE001 - 无表格或解析失败
                tables = []
            table_rects = [pymupdf.Rect(t.bbox) for t in tables]

            def in_table(bbox) -> bool:
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                return any(
                    rect.x0 - 1 <= cx <= rect.x1 + 1 and rect.y0 - 1 <= cy <= rect.y1 + 1
                    for rect in table_rects
                )

            items: list[tuple[float, str, object]] = []
            for block in blocks:
                if block.get("type") in (0, 1) and in_table(block["bbox"]):
                    continue
                items.append((block["bbox"][1], "block", block))
            for table in tables:
                items.append((pymupdf.Rect(table.bbox).y0, "table", table))
            items.sort(key=lambda item: item[0])

            last_para = None
            last_size = 0.0
            last_y1 = 0.0
            last_x0 = 0.0
            last_len = 0

            for _, kind, payload in items:
                if kind == "table":
                    if _add_word_table(doc, payload, min(base_size, 10.5)):
                        doc.add_paragraph().paragraph_format.space_after = Pt(2)
                        wrote_content = True
                    last_para = None
                    continue

                block = payload
                if block.get("type") == 1:
                    data = block.get("image")
                    if not data:
                        continue
                    try:
                        pic = doc.add_picture(io.BytesIO(data))
                    except Exception:  # noqa: BLE001
                        continue
                    max_width = Pt(usable_width)
                    if pic.width > max_width:
                        ratio = max_width / pic.width
                        pic.width = int(pic.width * ratio)
                        pic.height = int(pic.height * ratio)
                    doc.add_paragraph().paragraph_format.space_after = Pt(2)
                    wrote_content = True
                    last_para = None
                    continue

                if block.get("type") != 0:
                    continue
                text, max_size, bold_ratio = _block_text(block)
                if not text:
                    continue

                x0, y0, x1, y1 = block["bbox"]
                ratio = max_size / base_size if base_size else 1.0
                if len(text) <= 80 and ratio >= 1.45:
                    level = 1
                elif len(text) <= 80 and ratio >= 1.22:
                    level = 2
                elif len(text) <= 80 and ratio >= 1.18:
                    level = 3
                else:
                    level = 0

                centered = (
                    abs((x0 + x1) / 2 - page.rect.width / 2) < 12
                    and (x1 - x0) < page.rect.width * 0.8
                )

                if level:
                    heading = doc.add_heading("", level=level)
                    heading.alignment = (
                        WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.LEFT
                    )
                    run = heading.add_run(text)
                    _set_run_font(run, min(max(max_size, base_size * 1.1), base_size * 2.4), True)
                    wrote_content = True
                    last_para = None
                    continue

                can_merge = (
                    last_para is not None
                    and abs(max_size - last_size) <= 0.6
                    and 0 <= y0 - last_y1 <= max(4.0, max_size * 0.9)
                    and abs(x0 - last_x0) <= 20
                    and last_len > 20
                    and len(text) >= 2
                )
                if can_merge:
                    prev_text = last_para.text
                    sep = " " if prev_text and _needs_space(prev_text[-1], text[0]) else ""
                    run = last_para.add_run(sep + text)
                    _set_run_font(run, max_size, bold_ratio > 0.7)
                    last_len += len(text)
                    last_y1 = y1
                    wrote_content = True
                    continue

                para = doc.add_paragraph()
                para.paragraph_format.space_after = Pt(5)
                para.paragraph_format.line_spacing = 1.25
                if centered and len(text) < 60:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = para.add_run(text)
                _set_run_font(run, max_size if max_size > 0 else base_size, bold_ratio > 0.7)
                wrote_content = True

                last_para = para
                last_size = max_size
                last_y1 = y1
                last_x0 = x0
                last_len = len(text)

            if pno < pdf.page_count - 1:
                doc.add_page_break()
            _report(progress, (pno + 1) / pdf.page_count * 95)

        if not wrote_content:
            raise ValueError("该 PDF 没有可提取的文字或图片，可能是扫描件，请先 OCR。")
        doc.save(str(output))
    finally:
        pdf.close()
    _report(progress, 100)
    return str(output)


# --------------------------------------------------------------------------
# PDF → Excel
# --------------------------------------------------------------------------
def pdf_to_xlsx(src: str | Path, output: str | Path,
                progress: ProgressCb = None, log: LogCb = None) -> str:
    pdf = pymupdf.open(str(src))
    try:
        if pdf.page_count == 0:
            raise ValueError("PDF 中没有页面")
        if pdf.needs_pass:
            raise ValueError("该 PDF 已加密，请先解密后再转换")

        workbook = Workbook()
        workbook.remove(workbook.active)
        wrote_content = False

        for pno, page in enumerate(pdf):
            _log(log, f"识别第 {pno + 1}/{pdf.page_count} 页的表格")
            sheet = workbook.create_sheet(f"Page{pno + 1}")
            widths: dict[int, int] = {}
            row_cursor = 1

            try:
                finder = page.find_tables()
                tables = list(finder.tables)
            except Exception:  # noqa: BLE001
                tables = []

            for table in tables:
                data = table.extract()
                for row in data:
                    for col, value in enumerate(row, start=1):
                        text = "" if value is None else str(value).strip()
                        cell = sheet.cell(row=row_cursor, column=col, value=text)
                        cell.alignment = Alignment(vertical="top", wrap_text=True)
                        widths[col] = max(widths.get(col, 0), min(60, len(text)))
                    row_cursor += 1
                row_cursor += 1
                wrote_content = True

            if not tables:
                lines = [line.strip() for line in page.get_text().splitlines() if line.strip()]
                for line in lines:
                    cell = sheet.cell(row=row_cursor, column=1, value=line)
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    widths[1] = max(widths.get(1, 0), min(90, len(line)))
                    row_cursor += 1
                if lines:
                    wrote_content = True

            for col, max_len in widths.items():
                sheet.column_dimensions[get_column_letter(col)].width = min(70, max(10, max_len * 1.15 + 2))
            sheet.row_dimensions[1].font = Font(bold=False)
            _report(progress, (pno + 1) / pdf.page_count * 95)

        if not wrote_content:
            raise ValueError("该 PDF 没有可提取的文字或表格，可能是扫描件，请先 OCR。")

        workbook.save(str(output))
    finally:
        pdf.close()
    _report(progress, 100)
    return str(output)


# --------------------------------------------------------------------------
# Office → PDF（Microsoft Office COM）
# --------------------------------------------------------------------------
def office_available(kind: str) -> bool:
    import winreg

    if kind == "word":
        key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WINWORD.EXE"
    else:
        key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\EXCEL.EXE"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key) as handle:
                winreg.QueryValue(handle, None)
                return True
        except OSError:
            continue
    return False


def office_to_pdf(src: str | Path, output: str | Path, kind: str,
                  progress: ProgressCb = None, log: LogCb = None) -> str:
    """kind: "word" 或 "excel"。"""
    import pythoncom
    import win32com.client as win32

    src_path = str(Path(src).resolve())
    out_path = str(Path(output).resolve())
    _log(log, f"调用 Microsoft {'Word' if kind == 'word' else 'Excel'} 转换…")
    _report(progress, 10)

    pythoncom.CoInitialize()
    app = None
    document = None
    workbook = None
    try:
        if kind == "word":
            app = win32.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
            document = app.Documents.Open(src_path, ReadOnly=True, AddToRecentFiles=False)
            _report(progress, 45)
            document.ExportAsFixedFormat(out_path, 17)  # 17 = wdExportFormatPDF
        else:
            app = win32.DispatchEx("Excel.Application")
            app.Visible = False
            app.DisplayAlerts = False
            workbook = app.Workbooks.Open(src_path, ReadOnly=True, UpdateLinks=0)
            _report(progress, 45)
            workbook.ExportAsFixedFormat(0, out_path)  # 0 = xlTypePDF
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Office 转换失败：{exc}\n请确认本机已安装 Microsoft Office 且文件未损坏。"
        ) from exc
    finally:
        try:
            if document is not None:
                document.Close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            if workbook is not None:
                workbook.Close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            if app is not None:
                app.Quit()
        except Exception:  # noqa: BLE001
            pass
        pythoncom.CoUninitialize()

    _report(progress, 100)
    return str(output)
