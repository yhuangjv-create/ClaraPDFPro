"""PDF 编辑器引擎：打开文档、渲染页面、读写表单字段、保存与撤销。

引擎持有一个长开的 ``pymupdf.Document``，所有编辑都在其上进行。
撤销基于「操作前整份文件字节快照」，对表单/批注这类离散操作足够可靠。
"""

from __future__ import annotations

import io
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
        spans: list[dict] = []
        page = self.doc[idx]
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    spans.append({
                        "bbox": span["bbox"],
                        "text": span.get("text", ""),
                        "font": span.get("font", ""),
                        "size": float(span.get("size", 11)),
                        "color": span.get("color", 0),
                        "flags": span.get("flags", 0),
                    })
        return spans

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
