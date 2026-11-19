"""页面管理器：缩略图预览、旋转、删除、排序后另存。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap, QTransform
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from . import pdf_engine
from .settings import Settings
from .tool_widgets import error_box

THUMB_W = 132
THUMB_H = 176


class PageManagerDialog(QDialog):
    def __init__(self, i18n, pdf_path: str, parent=None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.pdf_path = str(pdf_path)
        self.saved_path: str | None = None
        self._thumbs: dict[int, bytes] = {}
        self._items: list[dict] = []

        info = pdf_engine.pdf_info(self.pdf_path)
        total = info["pages"]
        self._total = total
        self.setWindowTitle(i18n.t("pm.title", name=Path(self.pdf_path).name))
        self.resize(880, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        title = QLabel(i18n.t("pm.title", name=Path(self.pdf_path).name))
        title.setObjectName("PageTitle")
        title.setStyleSheet("font-size: 14pt;")
        layout.addWidget(title)

        hint = QLabel(i18n.t("pm.thumb_note"))
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        self.list = QListWidget()
        self.list.setObjectName("ThumbList")
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(THUMB_W, THUMB_H))
        self.list.setGridSize(QSize(THUMB_W + 34, THUMB_H + 62))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.setSpacing(6)
        layout.addWidget(self.list, 1)

        self._items = [{"idx": i, "rot": 0} for i in range(total)]

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.up_btn = QPushButton(i18n.t("common.up"))
        self.down_btn = QPushButton(i18n.t("common.down"))
        self.left_btn = QPushButton(i18n.t("pm.rotate_left"))
        self.right_btn = QPushButton(i18n.t("pm.rotate_right"))
        self.delete_btn = QPushButton(i18n.t("pm.delete"))
        self.reset_btn = QPushButton(i18n.t("common.reset"))
        for btn in (self.up_btn, self.down_btn, self.left_btn, self.right_btn,
                    self.delete_btn, self.reset_btn):
            buttons.addWidget(btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.cancel_btn = QPushButton(i18n.t("common.cancel"))
        self.save_btn = QPushButton(i18n.t("pm.save"))
        self.save_btn.setObjectName("PrimaryButton")
        bottom.addWidget(self.cancel_btn)
        bottom.addWidget(self.save_btn)
        layout.addLayout(bottom)

        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.left_btn.clicked.connect(lambda: self._rotate(-90))
        self.right_btn.clicked.connect(lambda: self._rotate(90))
        self.delete_btn.clicked.connect(self._delete)
        self.reset_btn.clicked.connect(self._reset)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

        self._load_thumbs()
        self._rebuild(0)

    # ---------------- 数据 ----------------
    def _load_thumbs(self) -> None:
        total = len(self._items)
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
            for entry in self._items:
                try:
                    self._thumbs[entry["idx"]] = pdf_engine.render_thumbnail(
                        self.pdf_path, entry["idx"], THUMB_W
                    )
                except Exception:  # noqa: BLE001
                    continue
        finally:
            QApplication.restoreOverrideCursor()

    def _icon_for(self, entry: dict) -> QIcon:
        data = self._thumbs.get(entry["idx"])
        if data is None:
            pix = QPixmap(THUMB_W, THUMB_H)
            pix.fill(Qt.transparent)
            return QIcon(pix)
        pix = QPixmap()
        pix.loadFromData(data, "PNG")
        if entry["rot"] % 360:
            transform = QTransform().rotate(entry["rot"] % 360)
            pix = pix.transformed(transform, Qt.SmoothTransformation)
        if pix.width() > THUMB_W or pix.height() > THUMB_H:
            pix = pix.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QIcon(pix)

    def _rebuild(self, select_row: int = -1) -> None:
        self.list.clear()
        for entry in self._items:
            text = self.i18n.t("pm.page", n=entry["idx"] + 1)
            if entry["rot"] % 360:
                text += f" · {entry['rot'] % 360}°"
            item = QListWidgetItem(self._icon_for(entry), text)
            item.setTextAlignment(Qt.AlignHCenter)
            self.list.addItem(item)
        if 0 <= select_row < self.list.count():
            self.list.setCurrentRow(select_row)
        self.save_btn.setEnabled(bool(self._items))

    def _current_row(self) -> int:
        row = self.list.currentRow()
        return row if row >= 0 else 0

    # ---------------- 操作 ----------------
    def _move(self, delta: int) -> None:
        row = self._current_row()
        new_row = row + delta
        if not (0 <= new_row < len(self._items)):
            return
        self._items[row], self._items[new_row] = self._items[new_row], self._items[row]
        self._rebuild(new_row)

    def _rotate(self, delta: int) -> None:
        row = self._current_row()
        if not self._items:
            return
        self._items[row]["rot"] = (self._items[row]["rot"] + delta) % 360
        self._rebuild(row)

    def _delete(self) -> None:
        if not self._items:
            return
        row = self._current_row()
        del self._items[row]
        self._rebuild(min(row, len(self._items) - 1))

    def _reset(self) -> None:
        self._items = [{"idx": i, "rot": 0} for i in range(self._total)]
        self._rebuild(0)

    def _save(self) -> None:
        if not self._items:
            return
        start = Path(self.pdf_path).with_name(f"{Path(self.pdf_path).stem}_edited.pdf")
        chosen, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("pm.save"), str(start), self.i18n.t("filter.pdf")
        )
        if not chosen:
            return
        if not chosen.lower().endswith(".pdf"):
            chosen += ".pdf"
        Settings().last_dir = str(Path(chosen).parent)

        order = [entry["idx"] for entry in self._items]
        rotations = {entry["idx"]: entry["rot"] for entry in self._items if entry["rot"] % 360}

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            pdf_engine.transform_pages(self.pdf_path, chosen, order, rotations)
        except Exception as exc:  # noqa: BLE001
            error_box(self, self.i18n, str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.saved_path = chosen
        self.accept()
