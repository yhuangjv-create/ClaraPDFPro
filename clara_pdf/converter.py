"""格式转换：PDF ↔ Word、PDF ↔ Excel。

PDF → Office 使用 PyMuPDF 抽取版式；Office → PDF 调用本机 Microsoft Office。
"""

from __future__ import annotations

import io
import statistics
from dataclasses import dataclass, replace
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
        return "Cascadia Mono", "SimSun"
    return "Microsoft YaHei UI", "Microsoft YaHei UI"


def _inside(glyph_set, name: str, point: tuple[float, float]) -> bool:
    from fontTools.pens.pointInsidePen import PointInsidePen

    pen = PointInsidePen(glyph_set, point)
    glyph_set[name].draw(pen)
    return pen.getResult()


def _classify_box_glyph(glyph_set, tt, name: str) -> str | None:
    """按字形轮廓判断制表符：│ ├ ─ └ ┌ ┐ ┘ ┤ ┬ ┴ ┼。"""
    glyf = tt["glyf"]
    glyph = glyf[name]
    contours = getattr(glyph, "numberOfContours", 0)
    if contours <= 0:
        return None
    upem = tt["head"].unitsPerEm
    adv = tt["hmtx"][name][0]
    if upem <= 0 or adv <= 0:
        return None
    x0, y0, x1, y1 = glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax
    width = x1 - x0
    height = y1 - y0
    if width < adv * 0.45 and height < upem * 0.55:
        return None

    def has_ink(xs, ys) -> bool:
        return any(_inside(glyph_set, name, (x, y)) for x, y in zip(xs, ys))

    # 四边是否贴着字身框
    left = has_ink([adv * 0.06] * 12, [y0 + height * (i + 0.5) / 12 for i in range(12)])
    right = has_ink([adv * 0.94] * 12, [y0 + height * (i + 0.5) / 12 for i in range(12)])
    top = has_ink([adv * (i + 0.5) / 12 for i in range(12)], [upem * 0.90] * 12)
    bottom = has_ink([adv * (i + 0.5) / 12 for i in range(12)], [upem * 0.06] * 12)

    # 16×16 采样：判断是否存在贯穿的横线/竖线，排除 % { ~ 等文字字形
    grid = [
        [
            _inside(glyph_set, name,
                    (adv * (c + 0.5) / 16, upem * (1 - (r + 0.5) / 16)))
            for c in range(16)
        ]
        for r in range(16)
    ]

    def line_score(lines) -> float:
        best = 0.0
        for line in lines:
            hits = [i for i, on in enumerate(line) if on]
            if len(hits) < 6:
                continue
            span = hits[-1] - hits[0] + 1
            if span < 8:
                continue
            best = max(best, len(hits) / span)
        return best

    row_score = line_score(grid)
    col_score = line_score([[grid[r][c] for r in range(16)] for c in range(16)])
    h_bar = row_score > 0.8
    v_bar = col_score > 0.8
    # 制表符的线条会越过字身框，普通字母不会
    extends_h = x0 < -adv * 0.02 or x1 > adv * 1.02
    extends_v = y0 < -upem * 0.05 or y1 > upem * 0.92

    if h_bar and not v_bar and left and right and extends_h:
        return "─"
    if v_bar and not h_bar and top and bottom and extends_v:
        return "│"
    if h_bar and v_bar and extends_h and extends_v:
        if left and right:
            if top and bottom:
                return "┼"
            return "┬" if bottom else "┴"
        if right and not left:
            if top and bottom:
                return "├"
            return "└" if top else "┌"
        if left and not right:
            if top and bottom:
                return "┤"
            return "┘" if top else "┐"
    return None


def _font_box_map(pdf, xref: int) -> dict[int, str]:
    """从子集字体轮廓还原丢失 Unicode 的制表符字形。"""
    try:
        info = pdf.extract_font(xref)
        buffer = info[3] if len(info) > 3 else None
        if not buffer:
            return {}
        from fontTools.ttLib import TTFont

        tt = TTFont(io.BytesIO(buffer))
        glyph_set = tt.getGlyphSet()
        mapping: dict[int, str] = {}
        for gid, name in enumerate(tt.getGlyphOrder()):
            if gid == 0:
                continue
            char = _classify_box_glyph(glyph_set, tt, name)
            if char:
                mapping[gid] = char
        return mapping
    except Exception:  # noqa: BLE001 - 字体缺失或解析失败时退回原文本
        return {}


def _page_box_overrides(page, pdf, cache: dict[int, dict[int, str]]):
    """返回 (bbox, 文本)：用字形轮廓修正等宽字体里错乱的制表符。"""
    xref_by_name = {}
    for entry in page.get_fonts(full=True):
        try:
            xref_by_name[str(entry[3])] = int(entry[0])
        except Exception:  # noqa: BLE001
            continue
    overrides = []
    try:
        spans = page.get_texttrace()
    except Exception:  # noqa: BLE001
        return overrides
    for span in spans:
        font = str(span.get("font") or "")
        low = font.lower()
        if not any(key in low for key in ("mono", "consol", "courier")):
            continue
        xref = xref_by_name.get(font)
        if xref is None:
            continue
        mapping = cache.get(xref)
        if mapping is None:
            mapping = _font_box_map(pdf, xref)
            cache[xref] = mapping
        if not mapping:
            continue
        chars = span.get("chars") or []
        text = "".join(mapping.get(char[1], chr(char[0])) for char in chars)
        original = "".join(chr(char[0]) for char in chars)
        if text != original:
            overrides.append((tuple(span["bbox"]), text))
    return overrides


def _override_text(style: _SpanStyle, overrides) -> str | None:
    if not overrides or not style.mono:
        return None
    x0, y0, x1, _ = style.bbox
    for rect, text in overrides:
        if abs(rect[0] - x0) <= 1.5 and abs(rect[2] - x1) <= 1.5 and abs(rect[1] - y0) <= 3.0:
            return text
    return None


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


def _set_table_borders(table, color: str = "C9D3E3", size: int = 6) -> None:
    """还原 PDF 表格的浅色细网格线（0.75pt）。"""
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), str(size))
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), color)
        borders.append(node)
    tblPr.insert_element_before(
        borders, "w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook",
    )


def _set_cell_margins(cell, top: float = 5.5, bottom: float = 5.5,
                      left: float = 6.0, right: float = 6.0) -> None:
    """按 PDF 表格的实际留白设置单元格内边距。"""
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


def _looks_like_code(block: dict, left_edge: float) -> bool:
    """代码块/树状图：几乎没有中文且从正文左边距起排。"""
    lines = [line for line in block.get("lines", []) if _line_spans(line)]
    spans = [span for line in lines for span in line.get("spans", [])]
    text = "".join(str(span.get("text", "")) for span in spans)
    visible = [ch for ch in text if not ch.isspace()]
    if not visible:
        return False
    cjk_chars = sum(1 for ch in visible if "\u4e00" <= ch <= "\u9fff")
    return (cjk_chars / len(visible) < 0.15
            and block["bbox"][0] <= left_edge + 6.0)


def _page_line_pitches(blocks, table_rects, right_edge: float) -> dict[tuple, float]:
    """按字号统计页面真实行距，供 Word 固定行距使用。"""
    entries = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block["bbox"]
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        if any(
            rect.x0 - 1 <= cx <= rect.x1 + 1 and rect.y0 - 1 <= cy <= rect.y1 + 1
            for rect in table_rects
        ):
            continue
        lines = [
            line for line in block.get("lines", []) if _line_spans(line)
        ]
        spans = [span for line in lines for span in line.get("spans", [])]
        if not spans:
            continue
        size = max(float(span.get("size", 0)) for span in spans)
        entries.append({
            "y0": bbox[1], "size": size, "x0": bbox[0], "x1": bbox[2],
            "lines": lines, "block": block,
        })
    if not entries:
        return {}

    left_edge = min(entry["x0"] for entry in entries)
    for entry in entries:
        entry["code"] = _looks_like_code(entry["block"], left_edge)

    buckets: dict[tuple[bool, float], list[float]] = {}
    for entry in entries:
        lines = entry["lines"]
        if len(lines) < 2:
            continue
        size = entry["size"]
        step = (lines[-1]["bbox"][1] - lines[0]["bbox"][1]) / (len(lines) - 1)
        if size * 0.95 <= step <= size * 2.8:
            key = (entry["code"], round(size * 4) / 4)
            buckets.setdefault(key, []).append(step)

    ordered = sorted(entries, key=lambda entry: (entry["y0"], entry["x0"]))
    for a, b in zip(ordered, ordered[1:]):
        size = max(a["size"], b["size"])
        if abs(a["size"] - b["size"]) > 0.8:
            continue
        delta = b["y0"] - a["y0"]
        if size * 0.95 <= delta <= size * 2.8 and abs(b["x0"] - a["x0"]) <= 40:
            key = (a["code"] and b["code"], round(size * 4) / 4)
            buckets.setdefault(key, []).append(delta)
    return {
        # 代码块用均值才能还原整块高度；正文用中位数更稳
        key: (statistics.fmean if key[0] else statistics.median)(values)
        for key, values in buckets.items()
        if len(values) >= (1 if key[0] else 2)
    }


def _document_pitches(pdf, right_margin: float) -> dict[tuple, float]:
    """全文行距统计，作为单页缺少多行块时的兜底值。"""
    per_key: dict[tuple, list[float]] = {}
    for page in pdf:
        blocks = page.get_text(
            "dict", flags=pymupdf.TEXT_PRESERVE_IMAGES)["blocks"]
        try:
            table_rects = [pymupdf.Rect(t.bbox) for t in page.find_tables().tables]
        except Exception:
            table_rects = []
        values = _page_line_pitches(
            blocks, table_rects, page.rect.width - right_margin)
        for key, value in values.items():
            per_key.setdefault(key, []).append(value)
    return {
        key: statistics.median(values)
        for key, values in per_key.items()
    }


def _exact_line_spacing(block: dict, font_size: float):
    """用 PDF 的实际行距作为 Word 的固定行距，避免行距被放大或压扁。"""
    lines = block.get("lines", [])
    size = max(font_size, 1.0)
    if not lines:
        return Pt(size * 1.3)
    if len(lines) >= 2:
        step = (lines[-1]["bbox"][1] - lines[0]["bbox"][1]) / (len(lines) - 1)
    else:
        step = block["bbox"][3] - block["bbox"][1]
    return Pt(max(size * 1.05, min(size * 2.6, step)))


def _text_offset(pitch: float, size: float) -> float:
    """Word 固定行距时文字顶部相对行框顶部的下移量（经验拟合）。

    行距越大，Word 把多出来的行高放到文字上方，导致整段下移；
    排版时把这个偏移量从段前/段后间距里扣掉，文字才能对齐 PDF。
    """
    return max(0.0, 0.80 * pitch - 1.06 * max(size, 1.0))


def _set_mark_size(para, half_points: int = 2) -> None:
    """缩小段落标记字号，避免固定行距下标记字形溢出到页边距外。"""
    pPr = para._p.get_or_add_pPr()
    rPr = pPr.find(qn("w:rPr"))
    if rPr is None:
        rPr = OxmlElement("w:rPr")
        pPr.append(rPr)
    for tag in ("w:sz", "w:szCs"):
        node = OxmlElement(tag)
        node.set(qn("w:val"), str(half_points))
        rPr.append(node)


def _add_spacer(doc: Document, height: float) -> None:
    """插入一个指定高度的空白段，用于把表格/图片推到 PDF 里的真实位置。"""
    if height <= 1.0:
        return
    para = doc.add_paragraph()
    fmt = para.paragraph_format
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing = Pt(height)
    fmt.widow_control = False
    para.add_run().font.size = Pt(1)
    _set_mark_size(para)


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
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after = Pt(0)
    para.paragraph_format.line_spacing = Pt(1)
    para.paragraph_format.widow_control = False
    _set_mark_size(para)
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
                    sep_before: str | None = None, overrides=None) -> str:
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
            fixed = _override_text(style, overrides)
            if fixed is not None:
                style = replace(style, text=fixed)
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


def _content_box(page):
    """找出页面的内容底板（内缩的整页填充块），用于精确还原页边距。"""
    page_area = page.rect.width * page.rect.height
    best = None
    for path in page.get_drawings():
        fill = path.get("fill")
        if fill is None:
            continue
        rect = pymupdf.Rect(path["rect"])
        if rect.width < page.rect.width * 0.6 or rect.height < page.rect.height * 0.6:
            continue
        if rect.width * rect.height < page_area * 0.5:
            continue
        if best is None or rect.width * rect.height > best.width * best.height:
            best = rect
    if best is None:
        return None
    return (
        best.x0,
        page.rect.width - best.x1,
        best.y0,
        page.rect.height - best.y1,
    )


def _document_margins(pdf) -> tuple[float, float, float, float]:
    """优先用页面底板推算四边页边距，多页取中位数；否则退回文字外接框。"""
    boxes = []
    for page in pdf:
        box = _content_box(page)
        if box is not None:
            boxes.append(box)
        if len(boxes) >= 8:
            break
    if not boxes:
        return _page_margins(pdf[0])

    values = [statistics.median(col) for col in zip(*boxes)]

    def clamp(value: float) -> float:
        return max(12.0, min(120.0, value))

    return tuple(clamp(v) for v in values)


def _configure_document(doc: Document, page_rect,
                        base_size: float, margins: tuple[float, float, float, float]) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei UI"
    normal.font.size = Pt(base_size)
    normal.paragraph_format.widow_control = False
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), "Microsoft YaHei UI")
    rfonts.set(qn("w:hAnsi"), "Microsoft YaHei UI")
    rfonts.set(qn("w:eastAsia"), "Microsoft YaHei UI")

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


def _table_usable(data) -> bool:
    """拒绝行内代码、代码块等被误判成表格的区域。"""
    if not data or len(data) < 2:
        return False
    cols = max((len(row) for row in data), default=0)
    if cols < 2:
        return False
    filled = [0] * cols
    for row in data:
        for col, value in enumerate(row[:cols]):
            if value is not None and str(value).strip():
                filled[col] += 1
    # 至少要有两列真正装着内容，否则是代码块/行内代码
    return sum(1 for count in filled if count >= 2) >= 2


def _row_shaded(rect, fills, usable: float) -> bool:
    if not fills or usable <= 0:
        return True
    covered = 0.0
    for fill_rect, _ in fills:
        if fill_rect.width < usable * 0.3:
            continue
        if fill_rect.height > rect.height * 8:
            # 整页或半页的背景块，不能当作表格行底色
            continue
        try:
            inter = pymupdf.Rect(fill_rect) & rect
        except Exception:  # noqa: BLE001
            continue
        if inter.is_empty:
            continue
        covered += inter.width * inter.height
    return covered >= rect.width * rect.height * 0.45


def _table_keep_rows(table, fills, usable: float) -> list[int]:
    """去掉被 find_tables 吞进来的表格外段落（无底色的整行）。"""
    rows = list(range(len(table.rows)))
    if not fills:
        return rows
    shaded = []
    for index, row in enumerate(table.rows):
        rect = pymupdf.Rect(row.bbox)
        if rect.width <= 1 or rect.height <= 1:
            continue
        if _row_shaded(rect, fills, usable):
            shaded.append(index)
    return shaded or rows


def _add_word_table(doc: Document, table, data, rows, page,
                    fills, font_size: float, overrides=None) -> bool:
    """把 PyMuPDF 表格写入 Word：无黑框、保留单元格底色与文字样式。"""
    if not data:
        return False
    cols = max((len(row) for row in data), default=0)
    if cols == 0:
        return False

    # 先扫描每个单元格的文字行数、首行位置和行距，用来精确还原行高
    cell_blocks: dict[tuple[int, int], tuple] = {}
    row_meta: list[tuple] = []
    samples: list[float] = []
    for r in range(len(data)):
        src_row = rows[r] if r < len(rows) else r
        try:
            row_box = pymupdf.Rect(table.rows[src_row].bbox)
        except Exception:  # noqa: BLE001 - 合并单元格
            row_box = None
        n_lines = 1
        first_top = None
        cell_size = font_size
        for c in range(cols):
            rect = None
            try:
                rect = table.rows[src_row].cells[c]
            except Exception:  # noqa: BLE001
                rect = None
            blocks = []
            if rect is not None:
                try:
                    clipped = page.get_text("dict", clip=pymupdf.Rect(rect))
                except Exception:  # noqa: BLE001
                    clipped = {"blocks": []}
                blocks = [
                    block for block in clipped.get("blocks", [])
                    if block.get("type") == 0
                ]
            cell_blocks[(r, c)] = (rect, blocks)
            tops: list[float] = []
            for block in blocks:
                for line in block.get("lines", []):
                    spans = _line_spans(line)
                    if not spans:
                        continue
                    tops.append(float(line["bbox"][1]))
                    cell_size = max(
                        cell_size, max(style.size for style in spans)
                    )
            if tops:
                tops.sort()
                n_lines = max(n_lines, len(tops))
                first_top = tops[0] if first_top is None else min(first_top, tops[0])
                for a, b in zip(tops, tops[1:]):
                    if cell_size * 0.95 <= b - a <= cell_size * 2.8:
                        samples.append(b - a)
        row_meta.append((row_box, n_lines, first_top, cell_size))

    pitch = statistics.median(samples) if len(samples) >= 2 else font_size * 2.1

    word_table = doc.add_table(rows=len(data), cols=cols)
    word_table.autofit = True
    _set_table_borders(word_table)

    for r, row in enumerate(data):
        src_row = rows[r] if r < len(rows) else r
        for c in range(cols):
            cell = word_table.cell(r, c)
            cell.text = ""
            para = cell.paragraphs[0]
            para.paragraph_format.space_after = Pt(0)
            para.paragraph_format.line_spacing = Pt(pitch)
            para.paragraph_format.widow_control = False

            rect, blocks = cell_blocks.get((r, c), (None, []))
            if rect is None:
                try:
                    rect = table.rows[src_row].cells[c]
                except Exception:  # noqa: BLE001
                    rect = None

            added = False
            for block in blocks:
                text, _, _ = _block_text(block)
                if not text:
                    continue
                if added:
                    para.add_run(" ")
                _add_block_runs(para, block, None, 0.0, None, overrides)
                added = True

            if not added:
                value = row[c] if c < len(row) else None
                text = "" if value is None else str(value).strip()
                if text:
                    run = para.add_run(text)
                    run.font.size = Pt(font_size)
                    run.font.name = "Microsoft YaHei UI"
                    run.bold = r == 0
                    run.font.color.rgb = RGBColor.from_string("1F2328")

            if rect is not None:
                fill = _cell_fill(rect, fills)
                if fill:
                    _shade_cell(cell, fill)

    # 按 PDF 行高分配上下内边距：固定行距会把文字压低，需从上方留白里扣掉
    for r, (row_box, n_lines, first_top, cell_size) in enumerate(row_meta):
        if row_box is not None:
            row_h = row_box.height
            offset = first_top - row_box.y0 if first_top is not None else 5.8
        else:
            row_h = n_lines * pitch + 11.5
            offset = 5.8
        delta = _text_offset(pitch, cell_size)
        top = max(0.0, min(8.0, offset - delta))
        # Word 会把 0.75pt 边框计入行高，扣掉它才能让表格总高度与 PDF 一致
        bottom = max(1.0, row_h - n_lines * pitch - top - 0.75)
        for c in range(cols):
            _set_cell_margins(word_table.cell(r, c), top=top, bottom=bottom)

    widths: list[float] = []
    # 表头行常被识别为合并单元格，改用前几行中列数完整的行来取列宽
    for probe in rows[:4]:
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
        margins = _document_margins(pdf)
        left_margin, right_margin = margins[0], margins[1]

        doc = Document()
        _configure_document(doc, first_rect, base_size, margins)
        usable_width = first_rect.width - left_margin - right_margin
        wrote_content = False
        glyph_cache: dict[int, dict[int, str]] = {}
        global_pitches = _document_pitches(pdf, right_margin)

        for pno, page in enumerate(pdf):
            _log(log, f"解析第 {pno + 1}/{pdf.page_count} 页")
            if pno > 0:
                # 用「段前分页」代替分页符，避免上一页刚好排满时产生空白页
                brk = doc.add_paragraph()
                brk.paragraph_format.page_break_before = True
                brk.paragraph_format.space_before = Pt(0)
                brk.paragraph_format.space_after = Pt(0)
                brk.paragraph_format.line_spacing = Pt(1)
                brk.paragraph_format.widow_control = False
                brk.add_run().font.size = Pt(1)
                _set_mark_size(brk)
            fills = _page_fills(page)
            bullets = _page_bullets(page)
            rules = _page_rules(page, usable_width)
            overrides = _page_box_overrides(page, pdf, glyph_cache)
            blocks = page.get_text(
                "dict", flags=pymupdf.TEXT_PRESERVE_IMAGES
            )["blocks"]
            content = _content_box(page)
            content_rect = None
            if content is not None:
                content_rect = pymupdf.Rect(
                    content[0], content[2],
                    page.rect.width - content[1],
                    page.rect.height - content[3],
                )

            tables: list[tuple[object, list, list, pymupdf.Rect]] = []
            try:
                for table in page.find_tables().tables:
                    data = table.extract()
                    # 单行/单列、代码块等误判表格直接丢弃
                    if not _table_usable(data):
                        continue
                    keep = _table_keep_rows(table, fills, usable_width)
                    if not keep:
                        continue
                    trim = pymupdf.Rect(table.bbox)
                    trim.y0 = table.rows[keep[0]].bbox[1]
                    trim.y1 = table.rows[keep[-1]].bbox[3]
                    trimmed = [data[i] if i < len(data) else [] for i in keep]
                    tables.append((table, trimmed, keep, trim))
            except Exception:  # noqa: BLE001 - 无表格或解析失败
                tables = []
            table_rects = [rect for _, _, _, rect in tables]

            def in_table(bbox) -> bool:
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                return any(
                    rect.x0 - 1 <= cx <= rect.x1 + 1 and rect.y0 - 1 <= cy <= rect.y1 + 1
                    for rect in table_rects
                )

            items: list[tuple[float, str, object]] = []
            for block in blocks:
                bbox = block["bbox"]
                if content_rect is not None and (
                    bbox[3] <= content_rect.y0 + 1
                    or bbox[1] >= content_rect.y1 - 1
                    or bbox[2] <= content_rect.x0 + 1
                    or bbox[0] >= content_rect.x1 - 1
                ):
                    # 被裁剪到页面底板之外的隐藏文本
                    continue
                if block.get("type") in (0, 1) and in_table(bbox):
                    continue
                items.append((bbox[1], "block", block))
            for table, data, keep, rect in tables:
                items.append((rect.y0, "table", (table, data, keep, rect)))
            for rect, color, width in rules:
                if in_table(rect):
                    continue
                items.append((rect.y0, "rule", (color, width)))
            items.sort(key=lambda item: item[0])
            pitches = _page_line_pitches(
                blocks, table_rects, page.rect.width - right_margin
            )
            page_left_edge = min(
                (block["bbox"][0] for block in blocks if block.get("type") == 0),
                default=left_margin,
            )

            margins_top = margins[2]
            page_offset = 1.0 if pno > 0 else 0.0
            page_started = False

            def body_pitch(size_ref: float, block: dict, mono: bool) -> float:
                """正文行距：先用本页统计值，再退回全文统计值。"""
                ref = size_ref or base_size
                key = (mono, round(ref * 4) / 4)
                value = pitches.get(key) or global_pitches.get(key)
                if not value:
                    value = _exact_line_spacing(block, ref).pt
                return max(ref * 1.05, min(ref * 2.8, value))

            def natural_pitch(size_ref: float) -> float:
                ref = size_ref or base_size
                return max(ref * 1.05, min(ref * 1.35, ref * 1.3))

            last_para = None
            last_size = 0.0
            last_y0 = 0.0
            last_y1 = 0.0
            last_x0 = 0.0
            last_x1 = 0.0
            last_len = 0
            last_pitch = 0.0
            last_delta = 0.0
            last_mono = False
            last_shaded = False
            last_bullet = False
            last_forced = False
            pending_space = None

            def finish_para(next_top: float, next_delta: float = 0.0) -> None:
                """用真实行距补齐段后间距，避免整页内容上下漂移。"""
                nonlocal last_para
                if last_para is not None and last_pitch > 0:
                    if last_mono and next_top - last_y0 <= last_pitch * 1.5:
                        # 代码块内部行距已由固定行距还原，逐行补差会累积误差
                        last_para.paragraph_format.space_after = Pt(0)
                    else:
                        bottom = last_y0 - last_delta + last_pitch
                        gap = (next_top - next_delta) - bottom
                        last_para.paragraph_format.space_after = Pt(
                            min(200.0, max(0.0, gap))
                        )
                last_para = None

            for index, (top_y, kind, payload) in enumerate(items):
                next_y = items[index + 1][0] if index + 1 < len(items) else top_y + 24.0

                if kind == "rule":
                    finish_para(top_y, 0.0)
                    if not page_started:
                        _add_spacer(doc, top_y - margins_top - page_offset)
                    color, width = payload
                    _add_rule(doc, color, width)
                    pending_space = top_y + 1.0
                    wrote_content = True
                    page_started = True
                    continue

                if kind == "table":
                    table, data, keep, rect = payload
                    finish_para(rect.y0, 0.0)
                    if not page_started:
                        _add_spacer(doc, rect.y0 - margins_top - page_offset)
                    if _add_word_table(doc, table, data, keep, page, fills,
                                       min(base_size, 10.5), overrides):
                        pending_space = rect.y1
                        wrote_content = True
                        page_started = True
                    continue

                block = payload
                if block.get("type") == 1:
                    finish_para(top_y, 0.0)
                    data = block.get("image")
                    if not data:
                        continue
                    if not page_started:
                        _add_spacer(doc, top_y - margins_top - page_offset)
                    try:
                        pic = doc.add_picture(io.BytesIO(data))
                    except Exception:  # noqa: BLE001
                        continue
                    max_width = Pt(usable_width)
                    if pic.width > max_width:
                        ratio = max_width / pic.width
                        pic.width = int(pic.width * ratio)
                        pic.height = int(pic.height * ratio)
                    pending_space = top_y + pic.height / 12700.0
                    wrote_content = True
                    page_started = True
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
                    size_ref = max_size or base_size
                    head_pitch = _exact_line_spacing(block, size_ref).pt
                    head_delta = _text_offset(head_pitch, size_ref)
                    finish_para(y0, head_delta)
                    heading = doc.add_heading("", level=level)
                    heading.alignment = (
                        WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.LEFT
                    )
                    heading.paragraph_format.line_spacing = Pt(head_pitch)
                    heading.paragraph_format.widow_control = False
                    if not page_started:
                        space_before = y0 - margins_top - head_delta - page_offset
                    elif pending_space is not None:
                        space_before = y0 - head_delta - pending_space
                    else:
                        space_before = 0.0
                    heading.paragraph_format.space_before = Pt(max(0.0, space_before))
                    heading.paragraph_format.space_after = Pt(0)
                    pending_space = None
                    _add_block_runs(heading, block, fills, usable_width, None, overrides)
                    wrote_content = True
                    page_started = True
                    # 交给 finish_para 计算段后间距
                    last_para = heading
                    last_y0 = y0
                    last_y1 = y1
                    last_pitch = head_pitch
                    last_delta = head_delta
                    last_len = 0
                    last_shaded = False
                    last_forced = False
                    last_bullet = False
                    continue

                fill = _block_fill(block, fills, usable_width)
                gap = y0 - last_y1
                tight = 0 <= gap <= max(4.0, max_size * 0.9)
                tail_merge = len(text) <= 4 and 0 <= gap <= max_size * 1.6
                # 上一行几乎占满整行宽度，说明是自动换行而非新段落
                wrap_merge = (
                    0 <= gap <= max_size * 1.8
                    and abs(x0 - last_x0) <= 20
                    and last_x1 >= page.rect.width - right_margin - max(max_size, last_size) * 1.6
                )
                # 代码块里的框线字符会让行框底边上下浮动，用更宽松的垂直容差合并
                mono_tight = (
                    mono and mono == last_mono
                    and -max_size * 1.2 <= gap <= max_size * 1.8
                )
                can_merge = (
                    last_para is not None
                    and not fill
                    and not last_shaded
                    and not last_forced
                    and not has_bullet
                    and (not last_bullet or wrap_merge)
                    and mono == last_mono
                    and abs(max_size - last_size) <= 0.6
                    and (tight or tail_merge or wrap_merge or mono_tight)
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
                    _add_block_runs(last_para, block, fills, usable_width, sep, overrides)
                    last_len += len(text)
                    last_y0 = y0
                    last_y1 = y1
                    last_x1 = x1
                    last_mono = mono
                    wrote_content = True
                    continue

                size_ref = max_size or base_size
                pitch = body_pitch(
                    size_ref, block,
                    _looks_like_code(block, page_left_edge))
                forced = False
                if not page_started:
                    # 页首段落的行框顶部无法上移：首行用自然行距定位，
                    # 其余行再回到真实行距，避免整页文字被压低。
                    pitch = natural_pitch(size_ref)
                    forced = True
                delta = _text_offset(pitch, size_ref)

                finish_para(y0, delta)
                para = doc.add_paragraph()
                para.paragraph_format.line_spacing = Pt(pitch)
                para.paragraph_format.widow_control = False
                if not page_started:
                    space_before = y0 - margins_top - delta - page_offset
                elif pending_space is not None:
                    space_before = y0 - delta - pending_space
                else:
                    space_before = 0.0
                pending_space = None
                para.paragraph_format.space_before = Pt(max(0.0, space_before))
                para.paragraph_format.space_after = Pt(0)
                indent = max(0.0, x0 - left_margin)
                if indent > 2 and not centered:
                    para.paragraph_format.left_indent = Pt(indent)
                if fill:
                    _shade_paragraph(para, fill)

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

                _add_block_runs(para, block, fills, usable_width, None, overrides)
                wrote_content = True
                page_started = True

                last_para = para
                last_size = max_size
                last_y0 = y0
                last_y1 = y1
                last_x0 = x0
                last_x1 = x1
                last_len = len(text)
                last_pitch = pitch
                last_delta = delta
                last_mono = mono
                last_shaded = bool(fill)
                last_bullet = has_bullet
                last_forced = forced

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
