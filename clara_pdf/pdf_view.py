"""PDF 页面视图：渲染页面位图，叠加表单字段并支持就地编辑。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
        self._hover_xref: int | None = None

    # ---------------- 渲染 ----------------
    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._close_editor()
        self.update()

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
        if self._mode == "form" and self._show_fields:
            f = self._field_at(event.position().toPoint())
            self._hover_xref = f.xref if f is not None else None
            self.setCursor(Qt.IBeamCursor if f is not None and not f.readonly
                           else Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._mode == "form" and self._show_fields:
            f = self._field_at(event.position().toPoint())
            if f is not None:
                self._open_editor(f)
                return
        self._close_editor()
        super().mousePressEvent(event)

    def _field_at(self, point: QPoint) -> FieldInfo | None:
        for f in self._fields:
            if self._field_rect(f).contains(point):
                return f
        return None

    # ---------------- 内联编辑器 ----------------
    def _close_editor(self) -> None:
        if self._editor is not None:
            self._editor.close()
            self._editor.deleteLater()
            self._editor = None
        self._editor_xref = None

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
