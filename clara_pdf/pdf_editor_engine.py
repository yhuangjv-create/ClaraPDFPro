"""PDF 编辑器引擎：打开文档、渲染页面、读写表单字段、保存与撤销。

引擎持有一个长开的 ``pymupdf.Document``，所有编辑都在其上进行。
撤销基于「操作前整份文件字节快照」，对表单/批注这类离散操作足够可靠。
"""

from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf
from PySide6.QtGui import QImage, QPixmap


# AcroForm 字段标志位（PDF 规范 Ff）
FF_READONLY = 1 << 0
FF_REQUIRED = 1 << 1
FF_MULTILINE = 1 << 12
FF_PASSWORD = 1 << 13

# 文本 span 标志位（PyMuPDF）
SF_ITALIC = 1 << 1
SF_SERIF = 1 << 2
SF_MONO = 1 << 3
SF_BOLD = 1 << 4

# base-14 字体变体：(字族, 粗体, 斜体) → 字体名
_BASE14 = {
    ("he", False, False): "helv", ("he", True, False): "hebo",
    ("he", False, True): "heit", ("he", True, True): "hebi",
    ("ti", False, False): "tiro", ("ti", True, False): "tibo",
    ("ti", False, True): "tiit", ("ti", True, True): "tibi",
    ("co", False, False): "cour", ("co", True, False): "cobo",
    ("co", False, True): "coit", ("co", True, True): "cobi",
}


def _is_cjk_char(ch: str) -> bool:
    code = ord(ch)
    return (0x2E80 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF
            or 0xFF00 <= code <= 0xFFEF)


def _is_cjk(text: str) -> bool:
    return any(_is_cjk_char(ch) for ch in text)


def _clean_ocr_text(text: str) -> str:
    """Windows OCR 会在汉字之间插入空格，写回文字层前去掉这些空格。"""
    text = text.replace("\u00a0", " ").strip()
    if not _is_cjk(text):
        return text
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch == " ":
            prev = out[-1] if out else ""
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if _is_cjk_char(prev) or _is_cjk_char(nxt):
                continue
        out.append(ch)
    return "".join(out)


def _font_for_text(text: str, flags: int) -> str:
    """为替换文本挑选字体：中文用内置 CJK，拉丁按粗体/斜体/衬线/等宽选择 base-14。"""
    if _is_cjk(text):
        return "china-s"
    bold = bool(flags & SF_BOLD)
    italic = bool(flags & SF_ITALIC)
    if flags & SF_MONO:
        family = "co"
    elif flags & SF_SERIF:
        family = "ti"
    else:
        family = "he"
    return _BASE14[(family, bold, italic)]


def _color_tuple(color: int | None) -> tuple[float, float, float]:
    c = int(color or 0)
    return (((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0)


def _resolve_fontname(span: dict, text: str) -> str:
    """优先用原字体名写入；若该字体不可用（子集字体没有字体文件），退回 base-14。"""
    flags = int(span.get("flags", 0))
    fallback = _font_for_text(text, flags)
    orig = str(span.get("font", "")).strip()
    if not orig:
        return fallback
    # 去掉子集前缀，例如 "ABCDEF+Calibri"
    if "+" in orig:
        orig = orig.split("+", 1)[1].strip()
    if not orig:
        return fallback
    try:
        pymupdf.Font(fontname=orig)
        return orig
    except Exception:  # noqa: BLE001
        return fallback


# 系统字体文件名映射（紧凑族名关键词 → 常规 / 粗体 / 斜体 / 粗斜体）
_FONT_FILES: dict[str, tuple[str, str, str, str]] = {
    "microsoftyaheiui": ("msyh.ttc", "msyhbd.ttc", "msyh.ttc", "msyhbd.ttc"),
    "microsoftyahei": ("msyh.ttc", "msyhbd.ttc", "msyh.ttc", "msyhbd.ttc"),
    "simsun": ("simsun.ttc", "simsun.ttc", "simsun.ttc", "simsun.ttc"),
    "nsimsun": ("simsun.ttc", "simsun.ttc", "simsun.ttc", "simsun.ttc"),
    "simhei": ("simhei.ttf", "simhei.ttf", "simhei.ttf", "simhei.ttf"),
    "kaiti": ("simkai.ttf", "simkai.ttf", "simkai.ttf", "simkai.ttf"),
    "fangsong": ("simfang.ttf", "simfang.ttf", "simfang.ttf", "simfang.ttf"),
    "arial": ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    "timesnewroman": ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
    "couriernew": ("cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
    "calibri": ("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
    "cambria": ("cambria.ttc", "cambriab.ttf", "cambriai.ttf", "cambriaz.ttf"),
    "segoeui": ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    "consolas": ("consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf"),
    "cascadiamono": ("CascadiaMono.ttf", "CascadiaMono-Bold.ttf",
                     "CascadiaMono-Italic.ttf", "CascadiaMono-BoldItalic.ttf"),
    "cascadiacode": ("CascadiaCode.ttf", "CascadiaCode-Bold.ttf",
                     "CascadiaCode-Italic.ttf", "CascadiaCode-BoldItalic.ttf"),
    "verdana": ("verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"),
    "georgia": ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
}

# 已加载的系统字体对象（路径 → Font），避免每次替换都重新解析字体文件
_FONT_CACHE: dict[str, pymupdf.Font | None] = {}


def _family_hint(raw_name: str) -> str:
    """从 PDF 字体名里提取紧凑的族名关键词，用于查找系统字体文件。"""
    compact = re.sub(r"[^a-z]", "", raw_name.lower())
    for key in _FONT_FILES:
        if key in compact:
            return key
    return ""


def _font_file_for_span(span: dict) -> str | None:
    """按字族 + 粗斜体挑出系统字体文件路径；找不到返回 None。"""
    raw = str(span.get("font", ""))
    flags = int(span.get("flags", 0))
    bold = bool(flags & SF_BOLD) or any(
        k in raw.lower() for k in ("bold", "black", "heavy", "demi"))
    italic = bool(flags & SF_ITALIC)
    style_index = (2 if italic else 0) + (1 if bold else 0)
    dirs = [
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
        os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local",
                     "Microsoft", "Windows", "Fonts"),
    ]

    def pick(family: str) -> str | None:
        names = _FONT_FILES.get(family)
        if not names:
            return None
        for idx in (style_index, 0):
            for base in dirs:
                path = os.path.join(base, names[idx])
                if os.path.isfile(path):
                    return path
        return None

    key = _family_hint(raw)
    if key:
        path = pick(key)
        if path:
            return path
    # 字体文件缺失时按类别兜底：等宽 / 衬线 / 默认（中文优先 YaHei）
    low = raw.lower()
    if any(k in low for k in ("mono", "cour", "consol", "code")):
        return pick("consolas") or pick("couriernew")
    if any(k in low for k in ("times", "serif", "tiro", "georgia", "cambria")):
        return pick("timesnewroman") or pick("georgia")
    return pick("microsoftyahei") or pick("arial")


@dataclass
class FieldInfo:
    xref: int
    page: int
    name: str
    ftype: str            # field_type_string: Text / CheckBox / RadioButton / ...
    value: Any
    rect: tuple[float, float, float, float]
    choices: list[str] = field(default_factory=list)
    flags: int = 0

    @property
    def readonly(self) -> bool:
        return bool(self.flags & FF_READONLY)

    @property
    def required(self) -> bool:
        return bool(self.flags & FF_REQUIRED)

    @property
    def multiline(self) -> bool:
        return bool(self.flags & FF_MULTILINE)


class PdfEngineError(Exception):
    pass


class PdfEditorEngine:
    def __init__(self, path: str | Path, password: str = "") -> None:
        self.path = str(path)
        self.password = password
        self.doc: pymupdf.Document = pymupdf.open(self.path)
        if self.doc.needs_pass:
            if not self.doc.authenticate(password or ""):
                self.doc.close()
                raise PdfEngineError("密码错误或文档已加密，无法打开。")
        self._dirty = False
        self._undo: list[bytes] = []
        self._redo: list[bytes] = []
        # 缓存页面对象：Widget 的 annot 绑定依赖 Page 存活，见 _page()
        self._page_cache: dict[int, pymupdf.Page] = {}
        # 字体保真用的缓存：basefont → xref 列表、xref → Font 对象
        self._font_xref_cache: dict[str, list[int]] | None = None
        self._font_obj_cache: dict[int, pymupdf.Font | None] = {}

    # ---------------- 生命周期 ----------------
    def close(self) -> None:
        self._page_cache.clear()
        try:
            self.doc.close()
        except Exception:
            pass

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def _page(self, idx: int) -> pymupdf.Page:
        """返回并缓存页面对象。

        必须保持 Page 的强引用：PyMuPDF 中 Widget 内部 annot 的页面绑定
        依赖 Page 对象存活；若用 ``self.doc[idx]`` 临时取值后即被回收，
        ``doc.save()`` 之后再取 widget 会失去页面绑定，调用
        ``widget.update()`` 抛 ``Annot is not bound to a page``。
        """
        page = self._page_cache.get(idx)
        if page is None:
            page = self.doc[idx]
            self._page_cache[idx] = page
        return page

    def page_rect(self, idx: int) -> pymupdf.Rect:
        return self._page(idx).rect

    @property
    def dirty(self) -> bool:
        return self._dirty

    # ---------------- 渲染 ----------------
    def render_page(self, idx: int, dpi: float = 110.0,
                    annots: bool = True) -> tuple[QPixmap, float]:
        """渲染页面为 QPixmap，返回 (pixmap, 像素/点 的缩放比)。"""
        scale = float(dpi) / 72.0
        matrix = pymupdf.Matrix(scale, scale)
        pix = self._page(idx).get_pixmap(matrix=matrix, alpha=False, annots=annots)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        return QPixmap.fromImage(img.copy()), scale

    # ---------------- 文本 ----------------
    def text_spans(self, idx: int) -> list[dict]:
        """返回可编辑文字 span；附带每个字符的起点 x（PDF 坐标），用于光标定位。"""
        spans: list[dict] = []
        page = self._page(idx)
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    chars = span.get("chars") or []
                    # 系统字体（雅黑 / Consolas / Times 等）重新嵌入后，空格可能被
                    # 提取成不换行空格 U+00A0，这里统一还原为普通空格。
                    text = "".join(ch.get("c", "") for ch in chars).replace("\u00a0", " ")
                    if not text.strip():
                        continue
                    spans.append({
                        "bbox": tuple(float(v) for v in span["bbox"]),
                        "origin": tuple(float(v) for v in span.get("origin", (0.0, 0.0))),
                        "text": text,
                        "font": span.get("font", ""),
                        "size": float(span.get("size", 11)),
                        "color": span.get("color", 0),
                        "flags": span.get("flags", 0),
                        "char_x": [float(ch["origin"][0]) for ch in chars],
                        "char_bboxes": [tuple(float(v) for v in ch["bbox"]) for ch in chars],
                    })
        return spans

    def _span_font(self, page, span: dict, text: str) -> pymupdf.Font | None:
        """挑一段与原 span 一致的字体：优先 PDF 内嵌字体，其次系统同族字体。

        这样改写 / 插入的新文字才会和原文的字体、粗细、字形保持一致。
        """
        chars = [ch for ch in text if not ch.isspace()]
        if not chars:
            return None
        # 1) PDF 内嵌字体：子集字形齐全时与原文完全一致
        for font in self._embedded_fonts(str(span.get("font", ""))):
            if self._font_covers(font, chars):
                return font
        # 2) 系统同族字体：新输入的字不一定在子集里，用它才能继续“长得像”
        path = _font_file_for_span(span)
        if not path:
            return None
        if path not in _FONT_CACHE:
            try:
                _FONT_CACHE[path] = pymupdf.Font(fontfile=path)
            except Exception:  # noqa: BLE001
                _FONT_CACHE[path] = None
        font = _FONT_CACHE[path]
        if font is not None and self._font_covers(font, chars):
            return font
        return None

    def _embedded_fonts(self, basefont: str) -> list[pymupdf.Font]:
        """收集文档内所有同名内嵌字体（不同页可能是不同子集）。"""
        if self._font_xref_cache is None:
            mapping: dict[str, list[int]] = {}
            for page in self.doc:
                try:
                    entries = page.get_fonts(full=True)
                except Exception:  # noqa: BLE001
                    continue
                for entry in entries:
                    xref, _ext, _type, name = entry[:4]
                    key = name.split("+")[-1]
                    mapping.setdefault(key, [])
                    if xref not in mapping[key]:
                        mapping[key].append(xref)
            self._font_xref_cache = mapping
        fonts: list[pymupdf.Font] = []
        for xref in self._font_xref_cache.get(basefont.split("+")[-1], []):
            if xref not in self._font_obj_cache:
                try:
                    info = self.doc.extract_font(xref)
                    buf = info[3] if info else None
                    self._font_obj_cache[xref] = (
                        pymupdf.Font(fontbuffer=buf) if buf else None)
                except Exception:  # noqa: BLE001
                    self._font_obj_cache[xref] = None
            font = self._font_obj_cache[xref]
            if font is not None:
                fonts.append(font)
        return fonts

    @staticmethod
    def _font_covers(font: pymupdf.Font, chars: list[str]) -> bool:
        try:
            return all(font.has_glyph(ord(ch)) for ch in chars)
        except Exception:  # noqa: BLE001
            return False

    def replace_text(self, idx: int, span: dict, new_text: str) -> bool:
        """用涂黑 + 重写的方式替换一段文本，尽量保留位置、字号、颜色与原字体。"""
        old_text = span.get("text", "")
        if new_text == old_text:
            return False
        self._push_undo()
        page = self._page(idx)
        bbox = pymupdf.Rect(span["bbox"])
        try:
            page.add_redact_annot(bbox)
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                text=pymupdf.PDF_REDACT_TEXT_REMOVE,
            )
            if new_text:
                origin = span.get("origin") or (bbox.x0, bbox.y1)
                size = float(span.get("size", 11))
                color = _color_tuple(span.get("color", 0))
                font = self._span_font(page, span, new_text)
                if font is not None:
                    # 用原字体文件写回，字形 / 粗细 / 斜体与原文一致
                    writer = pymupdf.TextWriter(page.rect)
                    writer.append(tuple(origin), new_text, font=font, fontsize=size)
                    writer.write_text(page, color=color)
                else:
                    page.insert_text(
                        origin,
                        new_text,
                        fontsize=size,
                        fontname=_resolve_fontname(span, new_text),
                        color=color,
                    )
        except Exception as exc:  # noqa: BLE001
            self._undo.pop()
            raise PdfEngineError(f"无法替换文本：{exc}") from exc
        self._dirty = True
        return True

    def select_rects(self, idx: int, x0: float, y0: float,
                     x1: float, y1: float) -> list[tuple[float, float, float, float]]:
        """把矩形选择转换为逐字符文本矩形，仅合并同行连续选中的字符。"""
        sel = pymupdf.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        rects: list[tuple[float, float, float, float]] = []
        for block in self._page(idx).get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                run: pymupdf.Rect | None = None
                for span in line.get("spans", []):
                    for char in span.get("chars", []):
                        char_rect = pymupdf.Rect(char["bbox"])
                        overlap = char_rect & sel
                        if char_rect.intersects(sel) and not overlap.is_empty:
                            run = run | char_rect if run is not None else char_rect
                        elif run is not None:
                            rects.append(tuple(run))
                            run = None
                if run is not None:
                    rects.append(tuple(run))
        return rects

    # ---------------- 批注 ----------------
    def add_highlight(self, idx: int, rects: list,
                      color: tuple[float, float, float] | None = None) -> bool:
        return self._add_markup(idx, "highlight", rects, color)

    def add_underline(self, idx: int, rects: list,
                      color: tuple[float, float, float] | None = None) -> bool:
        return self._add_markup(idx, "underline", rects, color)

    def _add_markup(self, idx: int, kind: str, rects: list,
                    color: tuple[float, float, float] | None = None) -> bool:
        if not rects:
            return False
        self._push_undo()
        page = self._page(idx)
        try:
            prects = [pymupdf.Rect(*r) for r in rects]
            if kind == "underline":
                annot = page.add_underline_annot(prects)
            else:
                annot = page.add_highlight_annot(prects)
            if color is not None:
                annot.set_colors(stroke=color)
            annot.update()
        except Exception as exc:  # noqa: BLE001
            self._undo.pop()
            raise PdfEngineError(f"无法添加批注：{exc}") from exc
        self._dirty = True
        return True

    def add_note(self, idx: int, point: tuple[float, float], text: str) -> bool:
        self._push_undo()
        page = self._page(idx)
        try:
            annot = page.add_text_annot(pymupdf.Point(*point), text or "", icon="Note")
            annot.update()
        except Exception as exc:  # noqa: BLE001
            self._undo.pop()
            raise PdfEngineError(f"无法添加便签：{exc}") from exc
        self._dirty = True
        return True

    def annot_count(self, idx: int) -> int:
        try:
            return sum(1 for _ in self._page(idx).annots())
        except Exception:  # noqa: BLE001
            return 0

    # ---------------- OCR ----------------
    def ocr_page(self, idx: int, lang: str | None = None,
                 dpi: float = 200.0, force: bool = False) -> int | None:
        """识别一页文字并写入不可见文字层，返回写入的行数。

        页面已有可选中文字且未指定 ``force`` 时返回 ``None``（跳过）。
        """
        from . import ocr  # 延迟导入：缺少 winrt / easyocr 时不影响其它功能

        page = self._page(idx)
        if not force and len(page.get_text("text").strip()) >= 10:
            return None
        scale = float(dpi) / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        lines = ocr.ocr_pixmap(pix, lang)
        if not lines:
            return 0
        self._push_undo()
        written = 0
        try:
            for line in lines:
                text = _clean_ocr_text(line["text"])
                if not text:
                    continue
                x0, y0, x1, y1 = line["bbox"]
                height = max(1.0, (y1 - y0) / scale)
                page.insert_text(
                    (x0 / scale, (y1 - (y1 - y0) * 0.2) / scale),
                    text,
                    fontsize=max(4.0, min(48.0, height * 0.8)),
                    fontname=_font_for_text(text, 0),
                    color=(0, 0, 0),
                    render_mode=3,  # 3 = 不可见，仅用于复制与检索
                )
                written += 1
            if written == 0:
                self._undo.pop()
                return 0
        except Exception as exc:  # noqa: BLE001
            self._undo.pop()
            raise PdfEngineError(f"OCR 文字层写入失败：{exc}") from exc
        self._dirty = True
        return written

    # ---------------- 表单 ----------------
    def has_forms(self) -> bool:
        for page in self.doc:
            w = page.first_widget
            if w is not None:
                return True
        return False

    def form_fields(self, idx: int) -> list[FieldInfo]:
        fields: list[FieldInfo] = []
        for w in self._page(idx).widgets():
            fields.append(FieldInfo(
                xref=w.xref,
                page=idx,
                name=w.field_name or "",
                ftype=w.field_type_string or "",
                value=w.field_value,
                rect=tuple(float(v) for v in w.rect),
                choices=list(getattr(w, "choice_values", None) or []),
                flags=int(getattr(w, "field_flags", 0) or 0),
            ))
        return fields

    def _load_widget(self, idx: int, xref: int) -> pymupdf.Widget | None:
        return self._page(idx).load_widget(xref)

    def set_field_value(self, idx: int, xref: int, value: Any) -> bool:
        """设置字段值并刷新外观。成功返回 True。"""
        widget = self._load_widget(idx, xref)
        if widget is None:
            return False
        if widget.field_flags & FF_READONLY:
            return False
        ftype = widget.field_type_string
        name = widget.field_name
        self._push_undo()
        # doc.save 后先前的 widget 可能失效，从缓存页面重新加载（页面保持存活）
        widget = self._load_widget(idx, xref)
        if widget is None:
            self._undo.pop()
            return False
        try:
            if ftype == "CheckBox":
                widget.field_value = bool(value)
            elif ftype == "RadioButton":
                self._set_radio(idx, widget, value)
            else:
                widget.field_value = "" if value is None else str(value)
            widget.update()
        except Exception as exc:  # noqa: BLE001
            self._undo.pop()  # 失败回滚快照
            raise PdfEngineError(f"无法写入字段 {name!r}：{exc}") from exc
        self._dirty = True
        return True

    def _set_radio(self, idx: int, widget: pymupdf.Widget, value: Any) -> None:
        """单选组：同名字段里选中目标，其余置为 Off。"""
        name = widget.field_name
        on_state = None
        try:
            on_state = widget.on_state()
        except Exception:  # noqa: BLE001
            on_state = "Yes"
        chosen = on_state if value else "Off"
        for sibling in self._page(idx).widgets():
            if sibling.field_name != name:
                continue
            sibling.field_value = chosen if sibling.xref == widget.xref else "Off"
            sibling.update()

    # ---------------- 保存 ----------------
    def save(self, path: str | Path | None = None) -> str:
        target = str(path) if path else self.path
        if not target.lower().endswith(".pdf"):
            target += ".pdf"
        incremental = (path is None and target == self.path)
        kwargs = {"garbage": 4, "deflate": True}
        if incremental:
            try:
                self.doc.saveIncr()
            except Exception:
                self.doc.save(target, **kwargs)
        else:
            self.doc.save(target, **kwargs)
        self._dirty = False
        self.path = target
        return target

    # ---------------- 撤销 / 重做 ----------------
    def _push_undo(self) -> None:
        buf = io.BytesIO()
        self.doc.save(buf, garbage=0, deflate=False)
        self._undo.append(buf.getvalue())
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> bool:
        if not self._undo:
            return False
        current = io.BytesIO()
        self.doc.save(current, garbage=0, deflate=False)
        snapshot = self._undo.pop()
        self._redo.append(current.getvalue())
        self._reload_from(snapshot)
        self._dirty = True
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        current = io.BytesIO()
        self.doc.save(current, garbage=0, deflate=False)
        snapshot = self._redo.pop()
        self._undo.append(current.getvalue())
        self._reload_from(snapshot)
        self._dirty = True
        return True

    def _reload_from(self, data: bytes) -> None:
        page = self.doc[0].number if self.doc.page_count else 0
        self.doc.close()
        self._page_cache.clear()  # 旧文档的页面对象已失效，必须清空缓存
        self.doc = pymupdf.open(stream=data, filetype="pdf")
        if self.doc.needs_pass:
            self.doc.authenticate(self.password or "")
        _ = page
