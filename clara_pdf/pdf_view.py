"""PDF 页面视图：渲染页面位图，叠加表单字段并支持就地编辑。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QRadioButton,
    QWidget,
)

from .pdf_editor_engine import FieldInfo, PdfEditorEngine


# 不使用绿色
COL_FIELD = QColor("#7fa8d6")
COL_FOCUS = QColor("#2b579a")
COL_REQUIRED = QColor("#c0392b")
COL_READONLY = QColor("#909090")
COL_TEXT_OVERLAY = QColor(43, 87, 154, 30)
COL_TEXT_HOVER = QColor(43, 87, 154, 45)
COL_SELECTION = QColor(43, 87, 154, 70)


class _LineEdit(QLineEdit):
    commit = Signal()
    cancel = Signal()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.commit.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.commit.emit()
            return
        if event.key() == Qt.Key_Escape:
            self.cancel.emit()
            return
        super().keyPressEvent(event)


class _TextEdit(QPlainTextEdit):
    commit = Signal()
    cancel = Signal()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.commit.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.cancel.emit()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and \
                event.modifiers() & Qt.ControlModifier:
            self.commit.emit()
            return
        super().keyPressEvent(event)


class _ComboBox(QComboBox):
    commit = Signal()
    cancel = Signal()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.commit.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.commit.emit()
            return
        if event.key() == Qt.Key_Escape:
            self.cancel.emit()
            return
        super().keyPressEvent(event)


class PdfPageView(QWidget):
    field_changed = Signal()  # 字段值写入后触发，由窗口刷新
    content_changed = Signal()  # 文本替换 / 批注后触发，由窗口刷新
    status = Signal(str)

    def __init__(self, engine: PdfEditorEngine, i18n, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.i18n = i18n
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self.page_idx = 0
        self.dpi = 110.0
        self.scale = 1.0
        self._pixmap = None
        self._fields: list[FieldInfo] = []
        self._mode = "form"
        self._show_fields = True
        self._annots_visible = True
        self._editor: QWidget | None = None
        self._editor_xref: int | None = None
        self._editor_span: dict | None = None
        self._hover_xref: int | None = None
        # 文本 / 批注模式状态
        self._spans: list[dict] = []
        self._hover_span: int | None = None
        self._annot_tool = "highlight"
        self._sel_start: QPoint | None = None
        self._sel_rect: QRect | None = None

    # ---------------- 渲染 ----------------
    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._close_editor()
        self._sel_start = None
        self._sel_rect = None
        self._hover_span = None
        self._load_spans()
        self.update()

    def set_annot_tool(self, tool: str) -> None:
        self._annot_tool = tool
        if self._mode != "annot":
            return
        self.setCursor(Qt.CrossCursor if tool == "note" else Qt.IBeamCursor)
        self.update()

    def _load_spans(self) -> None:
        if self._mode == "text":
            self._spans = self.engine.text_spans(self.page_idx)
        else:
            self._spans = []

    def set_dpi(self, dpi: float) -> None:
        self.dpi = float(dpi)
        self.show_page(self.page_idx)

    def set_annots_visible(self, visible: bool) -> None:
        self._annots_visible = visible
        self.show_page(self.page_idx)

    def set_fields_visible(self, visible: bool) -> None:
        self._show_fields = visible
        if not visible:
            self._close_editor()
        self.update()

    def show_page(self, idx: int) -> None:
        self._close_editor()
        self.page_idx = max(0, min(idx, self.engine.page_count - 1))
        self._pixmap, self.scale = self.engine.render_page(
            self.page_idx, dpi=self.dpi, annots=self._annots_visible)
        self._fields = self.engine.form_fields(self.page_idx)
        self._hover_span = None
        self._sel_start = None
        self._sel_rect = None
        self._load_spans()
        self.resize(self._pixmap.size())
        self.update()

    def refresh(self) -> None:
        self.show_page(self.page_idx)

    # ---------------- 绘制 ----------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        if self._pixmap is not None:
            painter.drawPixmap(0, 0, self._pixmap)
        if self._show_fields and self._mode == "form":
            for f in self._fields:
                self._draw_field(painter, f)
        if self._mode == "text" and self._editor is None and self._hover_span is not None:
            if 0 <= self._hover_span < len(self._spans):
                rect = self._bbox_rect(self._spans[self._hover_span]["bbox"])
                painter.fillRect(rect, COL_TEXT_HOVER)
        if self._mode == "annot" and self._sel_rect is not None:
            painter.fillRect(self._sel_rect.normalized(), COL_SELECTION)

    def _bbox_rect(self, bbox) -> QRect:
        s = self.scale
        return QRect(
            int(bbox[0] * s),
            int(bbox[1] * s),
            max(1, int((bbox[2] - bbox[0]) * s)),
            max(1, int((bbox[3] - bbox[1]) * s)),
        )

    def _field_rect(self, f: FieldInfo) -> QRect:
        s = self.scale
        return QRect(
            int(f.rect[0] * s),
            int(f.rect[1] * s),
            int((f.rect[2] - f.rect[0]) * s),
            int((f.rect[3] - f.rect[1]) * s),
        )

    def _draw_field(self, painter: QPainter, f: FieldInfo) -> None:
        rect = self._field_rect(f)
        color = COL_READONLY if f.readonly else COL_FIELD
        if f.xref == self._hover_xref and self._editor is None:
            color = COL_FOCUS
        pen = QPen(color, 2)
        if f.readonly:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect.adjusted(1, 1, -1, -1))
        if f.required and not f.readonly:
            pen2 = QPen(COL_REQUIRED, 1)
            painter.setPen(pen2)
            painter.setBrush(COL_REQUIRED)
            painter.drawEllipse(rect.right() - 6, rect.top() + 2, 4, 4)

    # ---------------- 鼠标 ----------------
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._mode == "form" and self._show_fields:
            f = self._field_at(pos)
            self._hover_xref = f.xref if f is not None else None
            self.setCursor(Qt.IBeamCursor if f is not None and not f.readonly
                           else Qt.ArrowCursor)
            self.update()
        elif self._mode == "text":
            idx = self._span_at(pos)
            if idx != self._hover_span:
                self._hover_span = idx
                self.setCursor(Qt.IBeamCursor if idx is not None else Qt.ArrowCursor)
                self.update()
        elif self._mode == "annot":
            if self._sel_start is not None and self._annot_tool != "note":
                self._sel_rect = QRect(self._sel_start, pos)
                self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._mode == "form" and self._show_fields:
            f = self._field_at(pos)
            if f is not None:
                self._open_editor(f)
                return
        elif self._mode == "text":
            idx = self._span_at(pos)
            if idx is not None:
                self._open_text_editor(self._spans[idx])
                return
        elif self._mode == "annot":
            if self._annot_tool == "note":
                self._place_note(pos)
                return
            self._close_editor()
            self._sel_start = pos
            self._sel_rect = QRect(pos, pos)
            self.update()
            return
        self._close_editor()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._mode == "annot" and self._sel_start is not None:
            start = self._sel_start
            end = event.position().toPoint()
            self._sel_start = None
            self._sel_rect = None
            if abs(end.x() - start.x()) >= 2 or abs(end.y() - start.y()) >= 2:
                self._apply_selection(start, end)
            self.update()
            return
        super().mouseReleaseEvent(event)

    def _span_at(self, point: QPoint) -> int | None:
        for i, s in enumerate(self._spans):
            if self._bbox_rect(s["bbox"]).contains(point):
                return i
        return None

    def _field_at(self, point: QPoint) -> FieldInfo | None:
        for f in self._fields:
            if self._field_rect(f).contains(point):
                return f
        return None

    # ---------------- 文本编辑 / 批注 ----------------
    def _open_text_editor(self, span: dict) -> None:
        self._close_editor()
        rect = self._bbox_rect(span["bbox"])
        rect.setWidth(max(rect.width() + 24, 120))
        rect.setHeight(max(rect.height() + 6, 22))
        editor = _LineEdit(self)
        editor.setText(span["text"])
        font = editor.font()
        font.setPointSizeF(max(6.0, float(span.get("size", 11)) * self.scale * 0.75))
        editor.setFont(font)
        editor.setGeometry(rect)
        editor.show()
        editor.setFocus()
        editor.selectAll()
        self._editor = editor
        self._editor_span = span
        try:
            editor.commit.connect(self._commit_text_editor)
            editor.cancel.connect(self._close_editor)
        except Exception:  # noqa: BLE001
            pass

    def _commit_text_editor(self) -> None:
        span = self._editor_span
        editor = self._editor
        if span is None or editor is None:
            return
        new_text = editor.text()
        self._close_editor()
        if new_text == span["text"]:
            return
        try:
            if self.engine.replace_text(self.page_idx, span, new_text):
                self.content_changed.emit()
        except Exception as exc:  # noqa: BLE001
            self.status.emit(str(exc))

    def _apply_selection(self, start: QPoint, end: QPoint) -> None:
        s = self.scale
        rects = self.engine.select_rects(
            self.page_idx,
            start.x() / s, start.y() / s,
            end.x() / s, end.y() / s,
        )
        if not rects:
            self.status.emit(self.i18n.t("editor.no_text"))
            return
        try:
            if self._annot_tool == "underline":
                ok = self.engine.add_underline(self.page_idx, rects)
            else:
                ok = self.engine.add_highlight(self.page_idx, rects)
            if ok:
                self.content_changed.emit()
        except Exception as exc:  # noqa: BLE001
            self.status.emit(str(exc))

    def _place_note(self, point: QPoint) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self, self.i18n.t("editor.annot_note"), self.i18n.t("editor.note_prompt"))
        if not ok or not text.strip():
            return
        s = self.scale
        try:
            if self.engine.add_note(self.page_idx, (point.x() / s, point.y() / s), text):
                self.content_changed.emit()
        except Exception as exc:  # noqa: BLE001
            self.status.emit(str(exc))

    # ---------------- 内联编辑器 ----------------
    def _close_editor(self) -> None:
        if self._editor is not None:
            self._editor.close()
            self._editor.deleteLater()
            self._editor = None
        self._editor_xref = None
        self._editor_span = None

    def _open_editor(self, f: FieldInfo) -> None:
        if f.readonly:
            self.status.emit(self.i18n.t("editor.field_readonly"))
            return
        self._close_editor()
        rect = self._field_rect(f)
        if f.ftype == "CheckBox":
            self.engine.set_field_value(self.page_idx, f.xref, not self._bool_value(f.value))
            self.field_changed.emit()
            return
        if f.ftype == "RadioButton":
            self.engine.set_field_value(self.page_idx, f.xref, True)
            self.field_changed.emit()
            return
        if f.ftype in ("ComboBox", "ListBox"):
            editor = _ComboBox(self)
            editor.setEditable(f.ftype == "ComboBox")
            for ch in f.choices:
                editor.addItem(ch)
            val = "" if f.value is None else str(f.value)
            editor.setEditText(val)
            editor.setCurrentText(val)
        elif f.multiline:
            editor = _TextEdit(self)
            editor.setPlainText("" if f.value is None else str(f.value))
        else:
            editor = _LineEdit(self)
            editor.setText("" if f.value is None else str(f.value))
        editor.setGeometry(rect)
        editor.show()
        editor.setFocus()
        self._editor = editor
        self._editor_xref = f.xref
        try:
            editor.commit.connect(self._commit_editor)
            editor.cancel.connect(self._close_editor)
        except Exception:
            pass

    @staticmethod
    def _bool_value(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() not in ("off", "", "false", "0", "none")

    def _commit_editor(self) -> None:
        xref = self._editor_xref
        editor = self._editor
        if xref is None or editor is None:
            return
        if isinstance(editor, _ComboBox):
            value = editor.currentText()
        elif isinstance(editor, _TextEdit):
            value = editor.toPlainText()
        else:
            value = editor.text()
        self._close_editor()
        if self.engine.set_field_value(self.page_idx, xref, value):
            self.field_changed.emit()
