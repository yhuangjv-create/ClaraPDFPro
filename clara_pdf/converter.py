"""格式转换：PDF ↔ Word、PDF ↔ Excel。

PDF → Office 使用 PyMuPDF 抽取版式；Office → PDF 调用本机 Microsoft Office。
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pymupdf
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

ProgressCb = Callable[[int], None] | None
LogCb = Callable[[str], None] | None


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
    return ch.isascii() and (ch.isalnum() or ch in ")]}.,;:!?%$#@&*/+=~-'\"`")


_CJK_PUNCT = set("，。、；：？！（）【】《》〈〉“”‘’…—～·「」")


def _needs_space(prev: str, nxt: str) -> bool:
    """英文单词之间、中英文交界处补空格；中英文标点两侧不补。"""
    if not prev or not nxt:
        return False
    if prev in _CJK_PUNCT or nxt in _CJK_PUNCT:
        return False
    if _is_ascii_word(prev) and _is_ascii_word(nxt):
        return True
    if prev.isascii() and prev.isalnum() and not nxt.isascii():
        return True
    if not prev.isascii() and nxt.isascii() and nxt.isalnum():
        return True
    return False


@dataclass
class _SpanStyle:
    text: str
    size: float
    color: str
    bold: bool
    italic: bool
    mono: bool
    bbox: tuple[float, float, float, float]


def _span_style(span: dict) -> _SpanStyle:
    font = str(span.get("font", ""))
    low = font.lower()
    flags = int(span.get("flags", 0))
    bbox = span.get("bbox") or (0.0, 0.0, 0.0, 0.0)
    return _SpanStyle(
        text=str(span.get("text", "")),
        size=float(span.get("size", 11.0)),
        color=f"{int(span.get('color', 0)):06X}",
        bold=bool(flags & 16) or "bold" in low or "700" in low,
        italic=bool(flags & 2) or "italic" in low or "oblique" in low,
        mono=bool(flags & 8) or any(k in low for k in ("mono", "courier", "consol")),
        bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
    )


def _line_spans(line: dict) -> list[_SpanStyle]:
    return [
        style for style in (_span_style(s) for s in line.get("spans", []))
        if style.text.strip()
    ]


def _mono_block(block: dict) -> bool:
    mono_chars = 0
    total = 0
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            total += len(text)
            if _span_style(span).mono:
                mono_chars += len(text)
    return total > 0 and mono_chars / total > 0.6


def _font_pair(style: _SpanStyle) -> tuple[str, str]:
    if style.mono:
        return "Consolas", "SimSun"
    return "Microsoft YaHei", "Microsoft YaHei"


def _shade_paragraph(para, fill: str) -> None:
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pPr.insert_element_before(
        shd,
        "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
        "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN",
        "w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
        "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
        "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
        "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr",
        "w:pPrChange",
    )


def _shade_run(run, fill: str) -> None:
    rPr = run._element.get_or_add_rPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    rPr.insert_element_before(
        shd,
        "w:fitText", "w:vertAlign", "w:rtl", "w:cs", "w:em", "w:lang",
        "w:eastAsianLayout", "w:specVanish", "w:oMath",
    )


def _shade_cell(cell, fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.insert_element_before(
        shd,
        "w:noWrap", "w:tcMar", "w:textDirection", "w:tcFitText", "w:vAlign",
        "w:hideMark", "w:headers", "w:cellIns", "w:cellDel", "w:cellMerge",
        "w:tcPrChange",
    )


def _set_cell_margins(cell, top: float = 0.6, bottom: float = 0.6,
                      left: float = 3.0, right: float = 3.0) -> None:
    """收紧单元格内边距，贴近 PDF 表格的紧凑排版。"""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for tag, value in (("w:top", top), ("w:left", left),
                       ("w:bottom", bottom), ("w:right", right)):
        node = OxmlElement(tag)
        node.set(qn("w:w"), str(int(round(value * 20))))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.insert_element_before(
        tcMar,
        "w:textDirection", "w:tcFitText", "w:vAlign", "w:hideMark",
        "w:headers", "w:cellIns", "w:cellDel", "w:cellMerge", "w:tcPrChange",
    )


def _exact_line_spacing(block: dict, font_size: float):
    """用 PDF 的实际行高作为 Word 的固定行距，避免行距被放大。"""
    lines = block.get("lines", [])
    size = max(font_size, 1.0)
    if not lines:
        return Pt(size * 1.3)
    height = (block["bbox"][3] - block["bbox"][1]) / len(lines)
    return Pt(max(size * 1.05, min(size * 2.0, height)))


def _append_run(para, style: _SpanStyle, fill: str | None = None):
    run = para.add_run(style.text)
    run.font.size = Pt(max(4.0, style.size))
    run.bold = style.bold
    run.italic = style.italic
    run.font.color.rgb = RGBColor.from_string(style.color)
    west, east = _font_pair(style)
    run.font.name = west
    rPr = run._element.get_or_add_rPr()
    rfonts = rPr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rPr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), west)
    rfonts.set(qn("w:hAnsi"), west)
    rfonts.set(qn("w:eastAsia"), east)
    if fill:
        _shade_run(run, fill)
    return run


def _rgb_hex(color) -> str:
    return "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in color)


def _page_fills(page) -> list[tuple[pymupdf.Rect, str]]:
    """收集页面中的填充色块（排除整页白底）。"""
    area_limit = page.rect.width * page.rect.height * 0.7
    fills: list[tuple[pymupdf.Rect, str]] = []
    for path in page.get_drawings():
        fill = path.get("fill")
        if fill is None:
            continue
        rect = pymupdf.Rect(path["rect"])
        if rect.width < 2 or rect.height < 2:
            continue
        if rect.width * rect.height > area_limit:
            continue
        hex_color = _rgb_hex(fill)
        if hex_color == "FFFFFF":
            continue
        fills.append((rect, hex_color))
    return fills


def _block_fill(block: dict, fills: list[tuple[pymupdf.Rect, str]],
                usable: float) -> str | None:
    """整段底色（代码块等）：每一行都落在同宽的浅色块内。"""
    if not fills or usable <= 0:
        return None
    colors: list[str] = []
    for line in block.get("lines", []):
        x0, y0, x1, y1 = line["bbox"]
        point = pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)
        hits = [
            (rect.width * rect.height, hex_color)
            for rect, hex_color in fills
            if rect.width >= usable * 0.55 and rect.contains(point)
        ]
        if not hits:
            return None
        hits.sort()
        colors.append(hits[0][1])
    if not colors:
        return None
    return max(set(colors), key=colors.count)


def _chip_fill(style: _SpanStyle, fills: list[tuple[pymupdf.Rect, str]],
               usable: float) -> str | None:
    """行内底色（反引号代码等）：较窄、接近单行高度的浅色块。"""
    if not fills or usable <= 0:
        return None
    x0, y0, x1, y1 = style.bbox
    point = pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)
    hits = [
        (rect.width * rect.height, hex_color)
        for rect, hex_color in fills
        if rect.width < usable * 0.55
        and rect.height <= style.size * 2.4
        and rect.contains(point)
    ]
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def _cell_fill(rect, fills: list[tuple[pymupdf.Rect, str]]) -> str | None:
    if not fills:
        return None
    box = pymupdf.Rect(rect)
    area = box.width * box.height
    if area <= 0:
        return None
    point = pymupdf.Point((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)
    hits = [
        (bg.width * bg.height, hex_color)
        for bg, hex_color in fills
        if bg.width * bg.height >= area * 0.5 and bg.contains(point)
    ]
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def _page_bullets(page) -> list[pymupdf.Rect]:
    bullets = []
    for path in page.get_drawings():
        fill = path.get("fill")
        if fill is None:
            continue
        rect = pymupdf.Rect(path["rect"])
        if rect.width <= 8 and rect.height <= 8 and max(fill) < 0.55:
            bullets.append(rect)
    return bullets


def _bullet_rect(block: dict, bullets: list[pymupdf.Rect]):
    if not bullets or not block.get("lines"):
        return None
    x0, _, _, _ = block["bbox"]
    _, y0, _, y1 = block["lines"][0]["bbox"]
    for bullet in bullets:
        center_y = (bullet.y0 + bullet.y1) / 2
        if bullet.x1 <= x0 + 2 and y0 - 1 <= center_y <= y1 + 1:
            return bullet
    return None


def _page_rules(page, usable: float) -> list[tuple[pymupdf.Rect, str, float]]:
    """收集横向分割线（细长描边或细长填充）。"""
    rules = []
    for path in page.get_drawings():
        rect = pymupdf.Rect(path["rect"])
        if rect.width < usable * 0.4 or rect.height > 3:
            continue
        color = path.get("color") or path.get("fill")
        if color is None:
            continue
        hex_color = _rgb_hex(color)
        if hex_color == "FFFFFF":
            continue
        rules.append((rect, hex_color, float(path.get("width") or 0.5)))
    return rules


def _add_rule(doc: Document, color: str, width: float) -> None:
    """插入一条横向分割线（段落底边框）。"""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after = Pt(8)
    para.paragraph_format.line_spacing = Pt(1)
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(max(2, min(18, int(round(width * 8))))))
    bottom.set(qn("w:space"), "0")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.insert_element_before(
        pBdr,
        "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
        "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN",
        "w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
        "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
        "w:textDirection", "w:textAlignment", "w:textboxTightWrap",
        "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr",
        "w:pPrChange",
    )


def _add_block_runs(para, block: dict, fills, usable: float,
                    sep_before: str | None = None) -> str:
    """按 span 写入文字，保留字体、字号、颜色、粗斜体与底色。"""
    mono = _mono_block(block)
    first_line = True
    prev_char = ""
    for line in block.get("lines", []):
        spans = _line_spans(line)
        if not spans:
            continue
        if first_line:
            if sep_before == "\n":
                para.add_run().add_break()
            elif sep_before:
                para.add_run(sep_before)
        else:
            if mono:
                para.add_run().add_break()
            elif prev_char and _needs_space(prev_char, spans[0].text.lstrip()[:1]):
                para.add_run(" ")
        for style in spans:
            fill = _chip_fill(style, fills or [], usable)
            _append_run(para, style, fill)
        tail = spans[-1].text.rstrip()
        if tail:
            prev_char = tail[-1]
        first_line = False
    return prev_char


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
            if _span_style(span).bold:
                bold_hits += 1
            max_size = max(max_size, span.get("size", 0.0))
        if line_parts:
            parts.append("".join(line_parts))
    text = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if not text:
            text = piece
        elif _needs_space(text[-1], piece[0]):
            text = f"{text} {piece}"
        else:
            text += piece
    bold_ratio = bold_hits / span_total if span_total else 0.0
    return text.strip(), max_size, bold_ratio


def _page_margins(page) -> tuple[float, float, float, float]:
    xs0: list[float] = []
    xs1: list[float] = []
    ys0: list[float] = []
    ys1: list[float] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        x0, y0, x1, y1 = block["bbox"]
        if x1 - x0 < 4:
            continue
        xs0.append(x0)
        xs1.append(x1)
        ys0.append(y0)
        ys1.append(y1)
    left = min(xs0) if xs0 else 57.0
    right = page.rect.width - max(xs1) if xs1 else 57.0
    top = min(ys0) if ys0 else 57.0
    bottom = page.rect.height - max(ys1) if ys1 else 57.0

    def clamp(value: float) -> float:
        return max(18.0, min(90.0, value))

    return clamp(left), clamp(right), clamp(top), clamp(bottom)


def _configure_document(doc: Document, page_rect,
                        base_size: float, margins: tuple[float, float, float, float]) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal.font.size = Pt(base_size)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), "Microsoft YaHei")
    rfonts.set(qn("w:hAnsi"), "Microsoft YaHei")
    rfonts.set(qn("w:eastAsia"), "Microsoft YaHei")

    left, right, top, bottom = margins
    section = doc.sections[0]
    width = max(400.0, min(page_rect.width, 1200.0))
    height = max(400.0, min(page_rect.height, 1800.0))
    section.page_width = Pt(width)
    section.page_height = Pt(height)
    section.left_margin = Pt(left)
    section.right_margin = Pt(right)
    section.top_margin = Pt(top)
    section.bottom_margin = Pt(bottom)


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


def _add_word_table(doc: Document, table, data, page,
                    fills, font_size: float) -> bool:
    """把 PyMuPDF 表格写入 Word：无黑框、保留单元格底色与文字样式。"""
    if not data:
        return False
    cols = max((len(row) for row in data), default=0)
    if cols == 0:
        return False

    word_table = doc.add_table(rows=len(data), cols=cols)
    word_table.autofit = True

    for r, row in enumerate(data):
        for c in range(cols):
            cell = word_table.cell(r, c)
            cell.text = ""
            _set_cell_margins(cell)
            para = cell.paragraphs[0]
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = Pt(font_size * 1.3)

            rect = None
            try:
                rect = table.rows[r].cells[c]
            except Exception:  # noqa: BLE001 - 合并单元格
                rect = None

            added = False
            first_block = None
            if rect is not None:
                try:
                    clipped = page.get_text("dict", clip=pymupdf.Rect(rect))
                except Exception:  # noqa: BLE001
                    clipped = {"blocks": []}
                for block in clipped.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    text, _, _ = _block_text(block)
                    if not text:
                        continue
                    if added:
                        para.add_run(" ")
                    _add_block_runs(para, block, None, 0.0)
                    if first_block is None:
                        first_block = block
                    added = True
            if first_block is not None:
                para.paragraph_format.line_spacing = _exact_line_spacing(
                    first_block, font_size
                )

            if not added:
                value = row[c] if c < len(row) else None
                text = "" if value is None else str(value).strip()
                if text:
                    run = para.add_run(text)
                    run.font.size = Pt(font_size)
                    run.font.name = "Microsoft YaHei"
                    run.bold = r == 0
                    run.font.color.rgb = RGBColor.from_string("1F2328")

            if rect is not None:
                fill = _cell_fill(rect, fills)
                if fill:
                    _shade_cell(cell, fill)

    widths: list[float] = []
    # 表头行常被识别为合并单元格，改用前几行中列数完整的行来取列宽
    for probe in range(min(4, len(table.rows))):
        try:
            boxes = table.rows[probe].cells
        except Exception:  # noqa: BLE001
            continue
        if len(boxes) == cols and all(box is not None for box in boxes):
            widths = [box[2] - box[0] for box in boxes]
            break
    if widths and sum(widths) > 4:
        word_table.autofit = False
        for c, width in enumerate(widths):
            word_table.columns[c].width = Pt(width)
            for cell in word_table.columns[c].cells:
                cell.width = Pt(width)
        tblPr = word_table._tbl.tblPr
        tblW = tblPr.find(qn("w:tblW"))
        if tblW is None:
            tblW = OxmlElement("w:tblW")
            tblPr.append(tblW)
        tblW.set(qn("w:w"), str(int(round(sum(widths) * 20))))
        tblW.set(qn("w:type"), "dxa")
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
        margins = _page_margins(pdf[0])
        left_margin, right_margin = margins[0], margins[1]

        doc = Document()
        _configure_document(doc, first_rect, base_size, margins)
        usable_width = first_rect.width - left_margin - right_margin
        wrote_content = False

        for pno, page in enumerate(pdf):
            _log(log, f"解析第 {pno + 1}/{pdf.page_count} 页")
            fills = _page_fills(page)
            bullets = _page_bullets(page)
            rules = _page_rules(page, usable_width)
            blocks = page.get_text(
                "dict", flags=pymupdf.TEXT_PRESERVE_IMAGES
            )["blocks"]

            tables: list[tuple[object, list]] = []
            try:
                for table in page.find_tables().tables:
                    data = table.extract()
                    if not data:
                        continue
                    cols = max((len(row) for row in data), default=0)
                    # 单行/单列多半是行内代码或背景块被误判为表格
                    if len(data) < 2 or cols < 2:
                        continue
                    tables.append((table, data))
            except Exception:  # noqa: BLE001 - 无表格或解析失败
                tables = []
            table_rects = [pymupdf.Rect(t.bbox) for t, _ in tables]

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
            for table, data in tables:
                items.append((pymupdf.Rect(table.bbox).y0, "table", (table, data)))
            for rect, color, width in rules:
                if in_table(rect):
                    continue
                items.append((rect.y0, "rule", (color, width)))
            items.sort(key=lambda item: item[0])

            last_para = None
            last_size = 0.0
            last_y1 = 0.0
            last_x0 = 0.0
            last_len = 0
            last_mono = False
            last_shaded = False
            last_bullet = False

            for index, (top_y, kind, payload) in enumerate(items):
                next_y = items[index + 1][0] if index + 1 < len(items) else top_y + 24.0

                if kind == "rule":
                    color, width = payload
                    _add_rule(doc, color, width)
                    wrote_content = True
                    last_para = None
                    continue

                if kind == "table":
                    table, data = payload
                    if _add_word_table(doc, table, data, page, fills,
                                       min(base_size, 10.5)):
                        spacer = doc.add_paragraph()
                        spacer.paragraph_format.space_after = Pt(4)
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
                    spacer = doc.add_paragraph()
                    spacer.paragraph_format.space_after = Pt(2)
                    wrote_content = True
                    last_para = None
                    continue

                if block.get("type") != 0:
                    continue
                text, max_size, _ = _block_text(block)
                if not text:
                    continue

                x0, y0, x1, y1 = block["bbox"]
                mono = _mono_block(block)
                ratio = max_size / base_size if base_size else 1.0
                if len(text) <= 80 and ratio >= 1.45:
                    level = 1
                elif len(text) <= 80 and ratio >= 1.22:
                    level = 2
                elif len(text) <= 80 and ratio >= 1.18:
                    level = 3
                else:
                    level = 0

                has_bullet = _bullet_rect(block, bullets)
                centered = (
                    abs((x0 + x1) / 2 - page.rect.width / 2) < 8
                    and x0 - left_margin > 30
                    and page.rect.width - right_margin - x1 > 30
                )

                if level:
                    heading = doc.add_heading("", level=level)
                    heading.alignment = (
                        WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.LEFT
                    )
                    _add_block_runs(heading, block, fills, usable_width)
                    wrote_content = True
                    last_para = None
                    continue

                fill = _block_fill(block, fills, usable_width)
                gap = y0 - last_y1
                tight = 0 <= gap <= max(4.0, max_size * 0.9)
                tail_merge = len(text) <= 4 and 0 <= gap <= max_size * 1.6
                can_merge = (
                    last_para is not None
                    and not fill
                    and not last_shaded
                    and not has_bullet
                    and not last_bullet
                    and mono == last_mono
                    and abs(max_size - last_size) <= 0.6
                    and (tight or tail_merge)
                    and abs(x0 - last_x0) <= 20
                    and last_len > 20
                    and len(text) >= 2
                )
                if can_merge:
                    prev_char = last_para.text[-1:] if last_para.text else ""
                    if mono:
                        sep = "\n"
                    elif prev_char and _needs_space(prev_char, text[0]):
                        sep = " "
                    else:
                        sep = ""
                    _add_block_runs(last_para, block, fills, usable_width, sep)
                    last_len += len(text)
                    last_y1 = y1
                    last_mono = mono
                    wrote_content = True
                    continue

                para = doc.add_paragraph()
                para.paragraph_format.line_spacing = _exact_line_spacing(
                    block, max_size or base_size
                )
                if fill:
                    _shade_paragraph(para, fill)
                    para.paragraph_format.space_before = Pt(0)
                    para.paragraph_format.space_after = Pt(0)
                else:
                    gap = max(0.0, next_y - y1)
                    para.paragraph_format.space_after = Pt(min(12.0, max(1.0, gap)))

                if centered and not has_bullet and len(text) < 60:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if has_bullet:
                    indent = max(0.0, x0 - left_margin)
                    para.paragraph_format.left_indent = Pt(indent)
                    para.paragraph_format.first_line_indent = Pt(
                        max(0.0, has_bullet.x0 - left_margin) - indent
                    )
                    bullet_style = _line_spans(block["lines"][0])
                    marker = para.add_run("• ")
                    marker.font.size = Pt(max_size if max_size > 0 else base_size)
                    if bullet_style:
                        marker.font.color.rgb = RGBColor.from_string(bullet_style[0].color)

                _add_block_runs(para, block, fills, usable_width)
                wrote_content = True

                last_para = para
                last_size = max_size
                last_y1 = y1
                last_x0 = x0
                last_len = len(text)
                last_mono = mono
                last_shaded = bool(fill)
                last_bullet = has_bullet

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
