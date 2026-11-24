"""PDF 页面视图：多页垂直堆叠的连续滚动画布。

所有页预渲染后首尾相连（每页之间留 gap），滚轮驱动外层 QScrollArea 在
整个长画布上平滑滚动；鼠标事件按坐标先判定落在哪一页段内，再在该页内
做表单/文本/批注 hit-test。单页视图（v1.1.4 及更早）已废弃。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPixmap
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

    PAGE_GAP = 8  # 页之间的视觉间隙（像素）

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

        # ---------- 多页画布 ----------
        self._pixmaps: list[QPixmap] = []
        self._page_offsets: list[int] = []   # 每页在 widget 中的 top y
        self._page_heights: list[int] = []
        self._page_width = 0
        self._total_height = 0
        self._all_fields: list[list[FieldInfo]] = []
        self._all_spans: list[list[dict]] = []

        # ---------- 编辑状态（当前 hit-test 命中的页）----------
        self._hover_page: int | None = None
        self._hover_xref: int | None = None
        self._hover_span: int | None = None
        self._editor: QWidget | None = None
        self._editor_page: int | None = None
        self._editor_xref: int | None = None
        self._editor_span: dict | None = None

        self._mode = "form"
        self._show_fields = True
        self._annots_visible = True
        self._annot_tool = "highlight"
        self._sel_start: QPoint | None = None
        self._sel_rect_page: int | None = None
        self._sel_rect: QRect | None = None

        if engine is not None:
            self._rebuild_pages()

    # ---------------- 渲染 ----------------
    def set_engine(self, engine: PdfEditorEngine | None) -> None:
        """切换/清空文档，重建整个长画布。"""
        self._close_editor()
        self.engine = engine
        self.page_idx = 0
        self._pixmaps = []
        self._page_offsets = []
        self._page_heights = []
        self._page_width = 0
        self._total_height = 0
        self._all_fields = []
        self._all_spans = []
        self._hover_xref = None
        self._hover_span = None
        self._sel_start = None
        self._sel_rect = None
        self._sel_rect_page = None
        if engine is not None:
            self._rebuild_pages()
        else:
            self.resize(0, 0)
        self.update()

    def _rebuild_pages(self) -> None:
        """预渲染所有页、记录每页 offset 和 fields/spans。"""
        if self.engine is None:
            return
        self._close_editor()
        self._pixmaps = []
        self._page_offsets = []
        self._page_heights = []
        self._all_fields = []
        self._all_spans = []
        top = 0
        self._page_width = 0
        for i in range(self.engine.page_count):
            pm, _ = self.engine.render_page(
                i, dpi=self.dpi, annots=self._annots_visible)
            # scale 用第 1 页的，所有页同一份缩放
            if i == 0:
                # 从 render_page 里我们已经拿到 pm，但没直接拿 scale
                # engine.render_page 返回 (QPixmap, scale) — 用那份 scale 才准
                pm2, scale = self.engine.render_page(
                    i, dpi=self.dpi, annots=self._annots_visible)
                self.scale = scale
                pm = pm2
            h = pm.height()
            w = pm.width()
            self._pixmaps.append(pm)
            self._page_offsets.append(top)
            self._page_heights.append(h)
            self._all_fields.append(self.engine.form_fields(i))
            self._all_spans.append(
                self.engine.text_spans(i) if self._mode == "text" else [])
            top += h + self.PAGE_GAP
            if w > self._page_width:
                self._page_width = w
        self._total_height = top - self.PAGE_GAP if self._pixmaps else 0
        self.resize(max(1, self._page_width), max(1, self._total_height))
        # 确保 page_idx 落在范围内
        self.page_idx = max(0, min(self.page_idx, len(self._pixmaps) - 1))
        self._hover_page = self.page_idx if self._pixmaps else None

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._close_editor()
        self._sel_start = None
        self._sel_rect = None
        self._hover_span = None
        if self.engine is not None and self._mode == "text":
            # 重载所有页的 spans
            self._all_spans = [self.engine.text_spans(i)
                               for i in range(self.engine.page_count)]
        else:
            self._all_spans = [[] for _ in self._pixmaps]
        self.update()

    def set_annot_tool(self, tool: str) -> None:
        self._annot_tool = tool
        if self._mode != "annot":
            return
        self.setCursor(Qt.CrossCursor if tool == "note" else Qt.IBeamCursor)
        self.update()

    def set_dpi(self, dpi: float) -> None:
        self.dpi = float(dpi)
        self._rebuild_pages()

    def set_annots_visible(self, visible: bool) -> None:
        self._annots_visible = visible
        self._rebuild_pages()

    def set_fields_visible(self, visible: bool) -> None:
        self._show_fields = visible
        if not visible:
            self._close_editor()
        self.update()

    def show_page(self, idx: int) -> None:
        """切换当前页引用。不再只渲染一页——长画布早已建好。"""
        if self.engine is None or not self._pixmaps:
            return
        self.page_idx = max(0, min(idx, len(self._pixmaps) - 1))
        self._hover_page = self.page_idx
        self.update()

    def refresh(self) -> None:
        """内容变化后刷新整页长画布（engine 可能已修改底层 PDF）。"""
        # 只重渲染改变了的页代价大——简单做法：重建全部
        self._rebuild_pages()

    # ---------------- 查询接口（供 editor_window 使用）----------------
    def offset_of_page(self, idx: int) -> int:
        """返回第 idx 页在 widget 中的 top y（用于 scrollBar 定位）。"""
        if 0 <= idx < len(self._page_offsets):
            return self._page_offsets[idx]
        return 0

    def page_at_y(self, y: int) -> int | None:
        """global y → page_idx（落在该页段内，不在页之间 gap 里）。"""
        for i, top in enumerate(self._page_offsets):
            bottom = top + self._page_heights[i]
            if top <= y < bottom:
                return i
        return None

    # ---------------- 绘制 ----------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        # 只画和 event.rect() 有重叠的页，节省一点
        rect = event.rect()
        for i, pm in enumerate(self._pixmaps):
            top = self._page_offsets[i]
            h = self._page_heights[i]
            if rect.bottom() < top or rect.top() > top + h:
                continue
            painter.drawPixmap(0, top, pm)
            # gap 分隔线（淡淡的）
            if i < len(self._pixmaps) - 1 and self.PAGE_GAP > 0:
                painter.setPen(Qt.lightGray)
                painter.drawLine(0, top + h + self.PAGE_GAP // 2,
                                 self.width(), top + h + self.PAGE_GAP // 2)

        # 表单高亮：只画当前 page_idx 的（避免多页时 hover 闪烁）
        if self._show_fields and self._mode == "form":
            visible_page = self._hover_page if self._hover_page is not None else self.page_idx
            if visible_page is not None and 0 <= visible_page < len(self._all_fields):
                page_top = self._page_offsets[visible_page]
                for f in self._all_fields[visible_page]:
                    self._draw_field(painter, f, page_top)

        # 文本 hover 高亮（仅 hover 那页）
        if self._mode == "text" and self._editor is None and self._hover_span is not None \
                and self._hover_page is not None \
                and 0 <= self._hover_page < len(self._all_spans):
            page_spans = self._all_spans[self._hover_page]
            if 0 <= self._hover_span < len(page_spans):
                page_top = self._page_offsets[self._hover_page]
                rect2 = self._bbox_rect(page_spans[self._hover_span]["bbox"], page_top)
                painter.fillRect(rect2, COL_TEXT_HOVER)

        # 批注框选
        if self._mode == "annot" and self._sel_rect is not None:
            painter.fillRect(self._sel_rect.normalized(), COL_SELECTION)

    def _bbox_rect(self, bbox, page_top: int = 0) -> QRect:
        s = self.scale
        return QRect(
            int(bbox[0] * s),
            int(page_top + bbox[1] * s),
            max(1, int((bbox[2] - bbox[0]) * s)),
            max(1, int((bbox[3] - bbox[1]) * s)),
        )

    def _field_rect(self, f: FieldInfo, page_top: int = 0) -> QRect:
        s = self.scale
        return QRect(
            int(f.rect[0] * s),
            int(page_top + f.rect[1] * s),
            int((f.rect[2] - f.rect[0]) * s),
            int((f.rect[3] - f.rect[1]) * s),
        )

    def _draw_field(self, painter: QPainter, f: FieldInfo, page_top: int) -> None:
        rect = self._field_rect(f, page_top)
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
        page_idx = self.page_at_y(pos.y())
        self._hover_page = page_idx
        if page_idx is None:
            self._hover_xref = None
            self._hover_span = None
            self.setCursor(Qt.ArrowCursor)
            self.update()
            return

        # 同步 self.page_idx 到命中页
        if page_idx != self.page_idx:
            self.page_idx = page_idx

        if self._mode == "form" and self._show_fields:
            local_point = QPoint(pos.x(), pos.y() - self._page_offsets[page_idx])
            f = self._field_at(page_idx, local_point)
            self._hover_xref = f.xref if f is not None else None
            self.setCursor(Qt.IBeamCursor if f is not None and not f.readonly
                           else Qt.ArrowCursor)
            self.update()
        elif self._mode == "text":
            local_point = QPoint(pos.x(), pos.y() - self._page_offsets[page_idx])
            idx = self._span_at(page_idx, local_point)
            if idx != self._hover_span:
                self._hover_span = idx
                self.setCursor(Qt.IBeamCursor if idx is not None else Qt.ArrowCursor)
                self.update()
        elif self._mode == "annot":
            if self._sel_start is not None and self._annot_tool != "note":
                self._sel_rect = QRect(self._sel_start, pos)
                self._sel_rect_page = page_idx
                self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        page_idx = self.page_at_y(pos.y())
        if page_idx is None:
            self._close_editor()
            self.update()
            return

        self.page_idx = page_idx
        page_top = self._page_offsets[page_idx]
        local_point = QPoint(pos.x(), pos.y() - page_top)

        if self._mode == "form" and self._show_fields:
            f = self._field_at(page_idx, local_point)
            if f is not None:
                self._open_editor(f, page_idx, page_top)
                return
        elif self._mode == "text":
            idx = self._span_at(page_idx, local_point)
            if idx is not None:
                self._open_text_editor(
                    self._all_spans[page_idx][idx], page_idx, page_top, pos)
                return
        elif self._mode == "annot":
            if self._annot_tool == "note":
                self._place_note(pos, page_idx)
                return
            self._close_editor(commit=True)
            self._sel_start = pos
            self._sel_rect = QRect(pos, pos)
            self._sel_rect_page = page_idx
            self.update()
            return
        self._close_editor(commit=True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._mode == "annot" and self._sel_start is not None:
            start = self._sel_start
            end = event.position().toPoint()
            self._sel_start = None
            if abs(end.x() - start.x()) >= 2 or abs(end.y() - start.y()) >= 2:
                # 框选跨页只在同页内生效；跨页就按"上到下全部"处理
                self._apply_selection(start, end)
            self._sel_rect = None
            self.update()
            return
        super().mouseReleaseEvent(event)

    def _span_at(self, page_idx: int, local_point: QPoint) -> int | None:
        spans = self._all_spans[page_idx] if page_idx < len(self._all_spans) else []
        for i, s in enumerate(spans):
            rect = self._bbox_rect(s["bbox"], page_top=0)  # local 坐标
            if rect.contains(local_point):
                return i
        return None

    def _field_at(self, page_idx: int, local_point: QPoint) -> FieldInfo | None:
        fields = self._all_fields[page_idx] if page_idx < len(self._all_fields) else []
        for f in fields:
            rect = self._field_rect(f, page_top=0)  # local 坐标
            if rect.contains(local_point):
                return f
        return None

    # ---------------- 文本编辑 / 批注 ----------------
    def _open_text_editor(self, span: dict, page_idx: int, page_top: int,
                          click: QPoint | None = None) -> None:
        """打开行内文本编辑器。

        Word 风格：不预选任何文字，只把闪烁光标放在鼠标点击的位置，
        并让编辑框背景色与页面底色一致，遮住下面原文字，避免重影。
        """
        self._close_editor(commit=True)
        rect = self._bbox_rect(span["bbox"], page_top)  # 全局坐标
        rect.setWidth(max(rect.width() + 16, 60))

        editor = _LineEdit(self)

        # ---------- 所见即所得：字体族 / 字号 / 粗斜体 / 颜色 ----------
        # _qfont_for_span 给出的是 PDF 点值；画布是 dpi 放大后的像素，
        # 必须按 scale 与屏幕 DPI 换算成显示点值，否则字会明显偏小。
        qfont = self._qfont_for_span(span)
        display_pt = self._display_point_size(qfont.pointSizeF())
        qfont.setPointSizeF(display_pt)
        editor.setFont(qfont)

        color = self._qcolor_for_span(span)
        bg = self._page_color_at(page_idx, span)
        editor.setText(span["text"])

        rect.setHeight(max(rect.height() + 4, int(display_pt * 1.9)))
        rect.adjust(-2, -2, 6, 2)
        editor.setGeometry(rect)

        # 样式表显式写 font-* 与 color，压过主题里全局 QWidget 的 9pt 规则
        editor.setStyleSheet(
            "QLineEdit {"
            f"  font-family: \"{qfont.family()}\";"
            f"  font-size: {display_pt}pt;"
            f"  font-weight: {'bold' if qfont.bold() else 'normal'};"
            f"  font-style: {'italic' if qfont.italic() else 'normal'};"
            f"  color: {color.name()};"
            f"  background: {bg.name()};"
            "  border: none;"
            "  padding: 0;"
            "}")
        editor.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        editor.show()
        editor.setFocus()

        # ---------- 光标定位到点击处，不选中任何文字 ----------
        if click is not None:
            editor.setCursorPosition(self._caret_index(span, click.x() - rect.left()))
        else:
            editor.setCursorPosition(len(span["text"]))
        editor.deselect()

        self._editor = editor
        self._editor_page = page_idx
        self._editor_span = span
        try:
            editor.commit.connect(self._commit_text_editor)
            editor.cancel.connect(self._close_editor)
        except Exception:  # noqa: BLE001
            pass

    def _caret_index(self, span: dict, offset: int) -> int:
        """按点击的横向像素偏移算出插入位置。

        优先用 PDF 每个字符的真实起点（char_x），这样和实际字形完全对齐，
        不受 Qt 字体替换 / 字体度量差异影响；缺失时退回 Qt 字体度量估算。
        """
        text = span["text"]
        n = len(text)
        if offset <= 0:
            return 0
        char_x = span.get("char_x") or []
        if len(char_x) == n and n > 0:
            import bisect

            bounds = list(char_x) + [float(span["bbox"][2])]
            target = float(span["bbox"][0]) + offset / max(self.scale, 1e-6)
            pos = bisect.bisect_left(bounds, target)
            if pos <= 0:
                return 0
            if pos >= len(bounds):
                return n
            if target - bounds[pos - 1] <= bounds[pos] - target:
                return pos - 1
            return min(pos, n)

        from PySide6.QtGui import QFontMetricsF

        font = self._qfont_for_span(span)
        font.setPointSizeF(self._display_point_size(font.pointSizeF()))
        fm = QFontMetricsF(font)
        for i in range(1, n + 1):
            if fm.horizontalAdvance(text[:i]) > offset:
                prev = fm.horizontalAdvance(text[:i - 1])
                half = (fm.horizontalAdvance(text[:i]) - prev) / 2
                return i - 1 if offset - prev < half else i
        return n

    def _display_point_size(self, pdf_pt: float) -> float:
        """PDF 点值 → 屏幕显示点值（考虑缩放与屏幕逻辑 DPI）。"""
        try:
            dpi = float(self.screen().logicalDotsPerInch() or 96.0)
        except Exception:  # noqa: BLE001
            dpi = 96.0
        return max(4.0, pdf_pt * self.scale * 72.0 / dpi)

    def _page_color_at(self, page_idx: int, span: dict) -> QColor:
        """从渲染好的页面图上采样文字周围的底色，作为编辑框背景色。"""
        if not (0 <= page_idx < len(self._pixmaps)):
            return QColor("white")
        img = self._pixmaps[page_idx].toImage()
        s = self.scale
        x0, y0, x1, y1 = span["bbox"]
        y = int((y0 + y1) / 2 * s)
        candidates = [int(x0 * s) - 3, int(x0 * s) - 8, int(x1 * s) + 3]
        best = None
        for x in candidates:
            if 0 <= x < img.width() and 0 <= y < img.height():
                c = img.pixelColor(x, y)
                if best is None or c.lightness() > best.lightness():
                    best = c
        if best is None or best.lightness() < 60:
            return QColor("white")
        return best

    @staticmethod
    def _qfont_for_span(span: dict) -> QFont:
        """从 pymupdf span dict 构造一个 QFont，尽量匹配原始 PDF 字体。"""
        from PySide6.QtGui import QFontDatabase

        size_pt = max(4.0, float(span.get("size", 11)))
        flags = int(span.get("flags", 0))
        bold = bool(flags & 4)       # SF_BOLD
        italic = bool(flags & 2)     # SF_ITALIC
        family = str(span.get("font", "")).strip()

        db = QFontDatabase()
        available = set(db.families())

        # pymupdf 内部名常见形如 "F1,Helv" / "Helv" / "china-s"
        # 先把逗号前的内部 ID 去掉，拿后面的 family 名
        if "," in family:
            family = family.split(",")[-1].strip()
        # 去掉 PDF base14 前缀（he / ti / co / cour / times / helv）
        family_lower = family.lower()
        base14_map = {
            "helv": "Helvetica", "helvetica": "Helvetica",
            "ti": "Times New Roman", "times": "Times New Roman",
            "cour": "Courier New", "courier": "Courier New",
            "he": "Helvetica", "cn": "Microsoft YaHei", "china-s": "SimSun",
        }
        candidate = base14_map.get(family_lower, family)

        if candidate in available:
            font = db.font(candidate, "", int(size_pt))
        elif family in available:
            font = db.font(family, "", int(size_pt))
        else:
            font = QFont()
            font.setPointSizeF(size_pt)

        font.setBold(bold)
        font.setItalic(italic)
        font.setPointSizeF(size_pt)
        return font

    @staticmethod
    def _qcolor_for_span(span: dict) -> QColor:
        raw = int(span.get("color", 0))
        return QColor((raw >> 16) & 255, (raw >> 8) & 255, raw & 255)

    def _commit_text_editor(self) -> None:
        span = self._editor_span
        editor = self._editor
        page_idx = self._editor_page
        if span is None or editor is None or page_idx is None:
            return
        new_text = editor.text()
        self._close_editor()
        if new_text == span["text"]:
            return
        try:
            if self.engine.replace_text(page_idx, span, new_text):
                self.content_changed.emit()
        except Exception as exc:  # noqa: BLE001
            self.status.emit(str(exc))

    def _apply_selection(self, start: QPoint, end: QPoint) -> None:
        """框选批注：start/end 是 widget 全局坐标。只在 start 所在页生效。"""
        page_idx = self.page_at_y(start.y())
        if page_idx is None:
            return
        page_top = self._page_offsets[page_idx]
        s = self.scale
        local_x0, local_y0 = start.x() / s, (start.y() - page_top) / s
        local_x1, local_y1 = end.x() / s, (end.y() - page_top) / s
        rects = self.engine.select_rects(
            page_idx, local_x0, local_y0, local_x1, local_y1)
        if not rects:
            self.status.emit(self.i18n.t("editor.no_text"))
            return
        try:
            if self._annot_tool == "underline":
                ok = self.engine.add_underline(page_idx, rects)
            else:
                ok = self.engine.add_highlight(page_idx, rects)
            if ok:
                self.content_changed.emit()
        except Exception as exc:  # noqa: BLE001
            self.status.emit(str(exc))

    def _place_note(self, point: QPoint, page_idx: int) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self, self.i18n.t("editor.annot_note"), self.i18n.t("editor.note_prompt"))
        if not ok or not text.strip():
            return
        s = self.scale
        page_top = self._page_offsets[page_idx]
        try:
            if self.engine.add_note(
                    page_idx,
                    (point.x() / s, (point.y() - page_top) / s), text):
                self.content_changed.emit()
        except Exception as exc:  # noqa: BLE001
            self.status.emit(str(exc))

    # ---------------- 内联编辑器 ----------------
    def _close_editor(self, commit: bool = False) -> None:
        """关闭行内编辑器。commit=True 时先提交当前文字（类似 Word 点击别处）。"""
        if commit and self._editor is not None:
            if self._editor_span is not None:
                self._commit_text_editor()
                return
            if self._editor_xref is not None:
                self._commit_editor()
                return
        editor = self._editor
        self._editor = None
        self._editor_page = None
        self._editor_xref = None
        self._editor_span = None
        if editor is not None:
            try:
                editor.blockSignals(True)  # 避免 close() 触发 focusOut 再进 commit
                editor.close()
            finally:
                editor.deleteLater()

    def _open_editor(self, f: FieldInfo, page_idx: int, page_top: int) -> None:
        if f.readonly:
            self.status.emit(self.i18n.t("editor.field_readonly"))
            return
        self._close_editor(commit=True)
        if f.ftype == "CheckBox":
            self.engine.set_field_value(page_idx, f.xref, not self._bool_value(f.value))
            self.field_changed.emit()
            return
        if f.ftype == "RadioButton":
            self.engine.set_field_value(page_idx, f.xref, True)
            self.field_changed.emit()
            return
        rect = self._field_rect(f, page_top)
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
        self._editor_page = page_idx
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
        page_idx = self._editor_page
        if xref is None or editor is None or page_idx is None:
            return
        if isinstance(editor, _ComboBox):
            value = editor.currentText()
        elif isinstance(editor, _TextEdit):
            value = editor.toPlainText()
        else:
            value = editor.text()
        self._close_editor()
        if self.engine.set_field_value(page_idx, xref, value):
            self.field_changed.emit()
