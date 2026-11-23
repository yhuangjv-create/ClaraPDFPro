"""PDF 编辑器主窗口：工具栏 + 页面缩略图 + 页面视图 + 状态栏。

围绕 :class:`PdfEditorEngine` 与 :class:`PdfPageView` 组装交互：
保存 / 另存为、撤销 / 重做、翻页、缩放、浏览 / 填表模式切换、字段高亮。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .pdf_editor_engine import PdfEditorEngine
from .pdf_view import PdfPageView
from .settings import Settings

# 基准 DPI 对应 100% 缩放
BASE_DPI = 110.0
THUMB_W = 128
THUMB_H = 170
THUMB_GRID_W = 134
THUMB_GRID_H = 202


class PdfEditorWindow(QMainWindow):
    def __init__(self, engine: PdfEditorEngine, i18n, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.i18n = i18n
        self._dirty = False
        self._first_show = True
        self._thumb_dpi = 45.0

        self.setWindowTitle(self.i18n.t("editor.window_title", name=Path(engine.path).name))
        self.resize(1180, 780)
        self.setMinimumSize(820, 520)

        self._build_ui()
        self._build_toolbar()
        self._build_shortcuts()

        self._load_thumbs()
        self._goto(0)
        self._update_undo_redo()
        self._update_zoom_label()
        self._update_status_fields()
        if not engine.has_forms():
            self.statusBar().showMessage(self.i18n.t("editor.no_form"), 8000)

    # ---------------- 界面构建 ----------------
    def _build_ui(self) -> None:
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 左侧缩略图
        thumb_panel = QWidget()
        thumb_panel.setObjectName("ThumbPanel")
        thumb_panel.setFixedWidth(THUMB_GRID_W + 28)
        tlayout = QVBoxLayout(thumb_panel)
        tlayout.setContentsMargins(8, 10, 8, 10)
        tlayout.setSpacing(6)
        self.thumb_title = QLabel(self.i18n.t("editor.thumb_title"))
        self.thumb_title.setObjectName("NavSection")
        self.thumb_title.setContentsMargins(4, 0, 0, 0)
        tlayout.addWidget(self.thumb_title)
        self.thumb_list = QListWidget()
        self.thumb_list.setObjectName("ThumbList")
        self.thumb_list.setViewMode(QListWidget.IconMode)
        self.thumb_list.setIconSize(QSize(THUMB_W, THUMB_H))
        self.thumb_list.setGridSize(QSize(THUMB_GRID_W, THUMB_GRID_H))
        self.thumb_list.setResizeMode(QListWidget.Adjust)
        self.thumb_list.setMovement(QListWidget.Static)
        self.thumb_list.setSpacing(4)
        self.thumb_list.setSelectionMode(QListWidget.SingleSelection)
        self.thumb_list.currentRowChanged.connect(self._on_thumb_selected)
        tlayout.addWidget(self.thumb_list, 1)
        outer.addWidget(thumb_panel)

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setStyleSheet("color: rgba(128,128,128,0.25);")
        outer.addWidget(divider)

        # 右侧滚动视图
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.view = PdfPageView(self.engine, self.i18n, self)
        self.scroll.setWidget(self.view)
        outer.addWidget(self.scroll, 1)

        self.setCentralWidget(central)

        # 状态栏
        self.status_page = QLabel("")
        self.status_fields = QLabel("")
        self.status_zoom = QLabel("")
        sb = self.statusBar()
        sb.addPermanentWidget(self.status_page)
        sb.addPermanentWidget(self.status_fields)
        sb.addPermanentWidget(self.status_zoom)
        sb.showMessage("")

        self.view.field_changed.connect(self._on_field_changed)
        self.view.status.connect(lambda m: sb.showMessage(m, 4000))

    def _build_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)

        self.act_save = QAction(self.i18n.t("editor.save"), self)
        self.act_save_as = QAction(self.i18n.t("editor.save_as"), self)
        tb.addAction(self.act_save)
        tb.addAction(self.act_save_as)
        tb.addSeparator()

        self.act_undo = QAction(self.i18n.t("editor.undo"), self)
        self.act_redo = QAction(self.i18n.t("editor.redo"), self)
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()

        self.act_prev = QAction(self.i18n.t("editor.prev_page"), self)
        self.act_next = QAction(self.i18n.t("editor.next_page"), self)
        self.page_label = QLabel("")
        self.page_label.setContentsMargins(8, 0, 8, 0)
        self.page_label.setMinimumWidth(110)
        self.page_label.setAlignment(Qt.AlignCenter)
        tb.addAction(self.act_prev)
        tb.addWidget(self.page_label)
        tb.addAction(self.act_next)
        tb.addSeparator()

        self.act_zoom_out = QAction(self.i18n.t("editor.zoom_out"), self)
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setFixedWidth(78)
        for pct in (50, 75, 100, 125, 150, 200, 300, 400):
            self.zoom_combo.addItem(self.i18n.t("editor.zoom_pct", pct=pct), pct)
        self.zoom_combo.lineEdit().setAlignment(Qt.AlignCenter)
        self.act_zoom_in = QAction(self.i18n.t("editor.zoom_in"), self)
        self.act_fit_width = QAction(self.i18n.t("editor.fit_width"), self)
        self.act_fit_page = QAction(self.i18n.t("editor.fit_page"), self)
        tb.addAction(self.act_zoom_out)
        tb.addWidget(self.zoom_combo)
        tb.addAction(self.act_zoom_in)
        tb.addAction(self.act_fit_width)
        tb.addAction(self.act_fit_page)
        tb.addSeparator()

        self.mode_combo = QComboBox()
        self.mode_combo.setFixedWidth(96)
        self.mode_combo.addItem(self.i18n.t("editor.mode_form"), "form")
        self.mode_combo.addItem(self.i18n.t("editor.mode_browse"), "browse")
        self.act_annots = QAction(self.i18n.t("editor.toggle_annots"), self)
        self.act_annots.setCheckable(True)
        self.act_annots.setChecked(True)
        self.act_fields = QAction(self.i18n.t("editor.toggle_fields"), self)
        self.act_fields.setCheckable(True)
        self.act_fields.setChecked(True)
        tb.addWidget(self.mode_combo)
        tb.addAction(self.act_annots)
        tb.addAction(self.act_fields)

        self.act_save.triggered.connect(self._save)
        self.act_save_as.triggered.connect(self._save_as)
        self.act_undo.triggered.connect(self._undo)
        self.act_redo.triggered.connect(self._redo)
        self.act_prev.triggered.connect(lambda: self._goto(self.view.page_idx - 1))
        self.act_next.triggered.connect(lambda: self._goto(self.view.page_idx + 1))
        self.act_zoom_out.triggered.connect(lambda: self._set_dpi(self.view.dpi / 1.25))
        self.act_zoom_in.triggered.connect(lambda: self._set_dpi(self.view.dpi * 1.25))
        self.act_fit_width.triggered.connect(lambda: self._fit("width"))
        self.act_fit_page.triggered.connect(lambda: self._fit("page"))
        self.zoom_combo.activated.connect(lambda _i: self._apply_combo_zoom())
        self.zoom_combo.lineEdit().editingFinished.connect(self._apply_combo_zoom)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.act_annots.toggled.connect(self.view.set_annots_visible)
        self.act_fields.toggled.connect(self.view.set_fields_visible)

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self._redo)
        QShortcut(QKeySequence("Ctrl+="), self,
                  activated=lambda: self._set_dpi(self.view.dpi * 1.25))
        QShortcut(QKeySequence("Ctrl+-"), self,
                  activated=lambda: self._set_dpi(self.view.dpi / 1.25))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=lambda: self._fit("width"))
        QShortcut(QKeySequence(Qt.Key_Left), self,
                  activated=lambda: self._goto(self.view.page_idx - 1),
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_Right), self,
                  activated=lambda: self._goto(self.view.page_idx + 1),
                  context=Qt.WidgetWithChildrenShortcut)

    # ---------------- 缩略图 ----------------
    def _load_thumbs(self) -> None:
        total = self.engine.page_count
        self.thumb_list.clear()
        if total > 120:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Question)
            box.setWindowTitle(self.i18n.t("common.info"))
            box.setText(self.i18n.t("pm.too_many", n=total))
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            if box.exec() != QMessageBox.Yes:
                return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for i in range(total):
                item = QListWidgetItem(self.i18n.t("pm.page", n=i + 1))
                item.setTextAlignment(Qt.AlignCenter)
                self.thumb_list.addItem(item)
            for i in range(total):
                self._render_thumb(i)
                QApplication.processEvents()
        finally:
            QApplication.restoreOverrideCursor()

    def _render_thumb(self, idx: int) -> None:
        if idx < 0 or idx >= self.thumb_list.count():
            return
        try:
            pix, _ = self.engine.render_page(idx, dpi=self._thumb_dpi,
                                             annots=self.act_annots.isChecked())
        except Exception:  # noqa: BLE001
            return
        item = self.thumb_list.item(idx)
        if item is not None:
            item.setIcon(QIcon(pix))

    def _refresh_current_thumb(self) -> None:
        self._render_thumb(self.view.page_idx)

    # ---------------- 翻页 / 缩放 ----------------
    def _goto(self, idx: int) -> None:
        total = self.engine.page_count
        if total <= 0:
            return
        idx = max(0, min(idx, total - 1))
        self.view.show_page(idx)
        self.page_label.setText(self.i18n.t("editor.page_n", n=idx + 1, total=total))
        self.status_page.setText(self.i18n.t("editor.page_n", n=idx + 1, total=total))
        self.thumb_list.blockSignals(True)
        self.thumb_list.setCurrentRow(idx)
        self.thumb_list.blockSignals(False)
        self._update_status_fields()

    def _on_thumb_selected(self, row: int) -> None:
        if row < 0 or row == self.view.page_idx:
            return
        self._goto(row)

    def _set_dpi(self, dpi: float) -> None:
        dpi = max(30.0, min(400.0, float(dpi)))
        self.view.set_dpi(dpi)
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        pct = max(1, round(self.view.dpi / BASE_DPI * 100))
        self.zoom_combo.setEditText(self.i18n.t("editor.zoom_pct", pct=pct))
        self.status_zoom.setText(self.i18n.t("editor.zoom_pct", pct=pct))

    def _apply_combo_zoom(self) -> None:
        text = self.zoom_combo.currentText().strip().rstrip("%")
        try:
            pct = float(text)
        except ValueError:
            self._update_zoom_label()
            return
        self._set_dpi(BASE_DPI * pct / 100.0)

    def _fit(self, which: str) -> None:
        vp = self.scroll.viewport()
        r = self.engine.page_rect(self.view.page_idx)
        margin = 16.0
        dpi_w = 72.0 * max(40.0, vp.width() - margin) / r.width
        if which == "width":
            self._set_dpi(dpi_w)
            return
        dpi_h = 72.0 * max(40.0, vp.height() - margin) / r.height
        self._set_dpi(min(dpi_w, dpi_h))

    # ---------------- 模式 ----------------
    def _on_mode_changed(self, _idx: int) -> None:
        mode = self.mode_combo.currentData()
        self.view.set_mode(mode)

    # ---------------- 编辑反馈 ----------------
    def _on_field_changed(self) -> None:
        self.view.refresh()
        self._set_dirty(True)
        self._update_undo_redo()
        self._update_status_fields()
        self._refresh_current_thumb()

    def _update_status_fields(self) -> None:
        n = len(self.engine.form_fields(self.view.page_idx))
        self.status_fields.setText(self.i18n.t("editor.status_fields", n=n))

    def _update_undo_redo(self) -> None:
        self.act_undo.setEnabled(self.engine.can_undo())
        self.act_redo.setEnabled(self.engine.can_redo())

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._update_title()

    def _update_title(self) -> None:
        name = Path(self.engine.path).name
        star = " *" if self._dirty else ""
        self.setWindowTitle(self.i18n.t("editor.window_title", name=name) + star)

    # ---------------- 撤销 / 重做 ----------------
    def _undo(self) -> None:
        if not self.engine.can_undo():
            return
        if self.engine.undo():
            self._after_undo_redo()

    def _redo(self) -> None:
        if not self.engine.can_redo():
            return
        if self.engine.redo():
            self._after_undo_redo()

    def _after_undo_redo(self) -> None:
        self.view.refresh()
        self._set_dirty(True)
        self._update_undo_redo()
        self._update_status_fields()
        self._refresh_current_thumb()

    # ---------------- 保存 ----------------
    def _save(self) -> bool:
        try:
            path = self.engine.save()
        except Exception as exc:  # noqa: BLE001
            self.statusBar().showMessage(self.i18n.t("editor.save_failed", err=exc), 6000)
            return False
        self._set_dirty(False)
        self._update_title()
        Settings().last_dir = str(Path(path).parent)
        self.statusBar().showMessage(self.i18n.t("editor.saved", path=Path(path).name), 4000)
        self._load_thumbs()
        return True

    def _save_as(self) -> bool:
        start = Path(self.engine.path)
        directory = str(start.parent) if start.exists() else Settings().last_dir
        chosen, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("editor.save_as"),
            str(Path(directory) / start.name),
            self.i18n.t("filter.pdf"),
        )
        if not chosen:
            return False
        if not chosen.lower().endswith(".pdf"):
            chosen += ".pdf"
        try:
            path = self.engine.save(chosen)
        except Exception as exc:  # noqa: BLE001
            self.statusBar().showMessage(self.i18n.t("editor.save_failed", err=exc), 6000)
            return False
        self._set_dirty(False)
        self._update_title()
        Settings().last_dir = str(Path(path).parent)
        self.statusBar().showMessage(self.i18n.t("editor.saved", path=Path(path).name), 4000)
        self._load_thumbs()
        return True

    # ---------------- 生命周期 ----------------
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(0, lambda: self._fit("width"))

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._dirty:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Question)
            box.setWindowTitle(self.i18n.t("editor.unsaved_title"))
            box.setText(self.i18n.t("editor.unsaved"))
            save_btn = box.addButton(self.i18n.t("editor.save"), QMessageBox.AcceptRole)
            discard_btn = box.addButton(self.i18n.t("editor.discard"), QMessageBox.DestructiveRole)
            cancel_btn = box.addButton(self.i18n.t("common.cancel"), QMessageBox.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is save_btn:
                if not self._save():
                    event.ignore()
                    return
            elif clicked is discard_btn:
                pass
            else:
                event.ignore()
                return
        self.engine.close()
        event.accept()
