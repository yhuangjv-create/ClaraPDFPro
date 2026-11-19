"""可复用的界面组件：卡片、文件选择、任务执行基类。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .worker import Worker


class Card(QFrame):
    """内容卡片容器。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 18)
        self._layout.setSpacing(10)

    def add_title(self, title: str, desc: str = "") -> None:
        label = QLabel(title)
        label.setObjectName("CardTitle")
        self._layout.addWidget(label)
        if desc:
            hint = QLabel(desc)
            hint.setObjectName("CardDesc")
            hint.setWordWrap(True)
            self._layout.addWidget(hint)

    def add(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class FileRow(QWidget):
    """单文件选择行。"""

    changed = Signal()

    def __init__(self, i18n, filter_key: str = "filter.pdf", save_mode: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self._filter_key = filter_key
        self._save_mode = save_mode

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.edit = QLineEdit()
        self.edit.setReadOnly(not save_mode)
        self.edit.setPlaceholderText("—")
        self.edit.textChanged.connect(lambda _text: self.changed.emit())
        self.button = QPushButton(i18n.t("common.browse"))
        self.button.clicked.connect(self._browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def set_filter(self, filter_key: str) -> None:
        self._filter_key = filter_key

    def path(self) -> str:
        return self.edit.text().strip()

    def set_path(self, path: str | Path) -> None:
        self.edit.setText(str(path) if path else "")

    def _browse(self) -> None:
        from .settings import Settings

        start = self.edit.text().strip() or Settings().last_dir
        filters = self.i18n.t(self._filter_key)
        if self._save_mode:
            chosen, _ = QFileDialog.getSaveFileName(self, self.i18n.t("common.output"), start, filters)
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, self.i18n.t("common.input"), start, filters)
        if chosen:
            self.edit.setText(chosen)
            Settings().last_dir = str(Path(chosen).parent)


class MultiFileRow(QWidget):
    """多文件列表 + 添加 / 移除 / 排序。"""

    changed = Signal()

    def __init__(self, i18n, filter_key: str = "filter.pdf",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self._filter_key = filter_key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.list = QListWidget()
        self.list.setFixedHeight(132)
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.list)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.add_btn = QPushButton(i18n.t("common.add"))
        self.remove_btn = QPushButton(i18n.t("common.remove"))
        self.up_btn = QPushButton(i18n.t("common.up"))
        self.down_btn = QPushButton(i18n.t("common.down"))
        self.clear_btn = QPushButton(i18n.t("common.clear"))
        for btn in (self.add_btn, self.remove_btn, self.up_btn, self.down_btn):
            buttons.addWidget(btn)
        buttons.addStretch(1)
        buttons.addWidget(self.clear_btn)
        layout.addLayout(buttons)

        self.add_btn.clicked.connect(self._add)
        self.remove_btn.clicked.connect(self._remove)
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.clear_btn.clicked.connect(self._clear)

    def set_filter(self, filter_key: str) -> None:
        self._filter_key = filter_key

    def paths(self) -> list[str]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def count(self) -> int:
        return self.list.count()

    def add_paths(self, paths: list[str]) -> None:
        existing = set(self.paths())
        for raw in paths:
            if raw and raw not in existing:
                item = QListWidgetItem(Path(raw).name)
                item.setToolTip(raw)
                item.setData(Qt.UserRole, raw)
                self.list.addItem(item)
                existing.add(raw)
        if paths:
            self.changed.emit()

    def _add(self) -> None:
        from .settings import Settings

        files, _ = QFileDialog.getOpenFileNames(
            self, self.i18n.t("common.add"), Settings().last_dir,
            self.i18n.t(self._filter_key),
        )
        if files:
            Settings().last_dir = str(Path(files[0]).parent)
            self.add_paths(files)

    def _remove(self) -> None:
        rows = sorted((self.list.row(i) for i in self.list.selectedItems()), reverse=True)
        for row in rows:
            self.list.takeItem(row)
        if rows:
            self.changed.emit()

    def _clear(self) -> None:
        if self.list.count():
            self.list.clear()
            self.changed.emit()

    def _move(self, delta: int) -> None:
        rows = sorted(self.list.row(i) for i in self.list.selectedItems())
        if not rows:
            return
        if delta < 0 and rows[0] == 0:
            return
        if delta > 0 and rows[-1] == self.list.count() - 1:
            return
        ordered = rows if delta < 0 else list(reversed(rows))
        for row in ordered:
            item = self.list.takeItem(row)
            self.list.insertItem(row + delta, item)
            item.setSelected(True)
        self.changed.emit()


class ToolPage(QWidget):
    """工具页基类：标题 + 卡片区域 + 后台任务。"""

    def __init__(self, i18n, title_key: str, desc_key: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self._worker: Worker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(34, 26, 34, 26)
        layout.setSpacing(12)

        self.title_label = QLabel(i18n.t(title_key))
        self.title_label.setObjectName("PageTitle")
        self.desc_label = QLabel(i18n.t(desc_key))
        self.desc_label.setObjectName("PageDesc")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.desc_label)
        layout.addSpacing(8)

        self.body = QVBoxLayout()
        self.body.setSpacing(14)
        layout.addLayout(self.body)
        layout.addStretch(1)

        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.status = QLabel("")
        self.status.setObjectName("TaskStatus")
        self.status.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(180)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.hide()
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.progress)
        layout.addLayout(status_row)

        self._title_key = title_key
        self._desc_key = desc_key

    # ---------------- 构建辅助 ----------------
    def add_card(self, title: str = "", desc: str = "") -> Card:
        card = Card()
        if title:
            card.add_title(title, desc)
        self.body.addWidget(card)
        return card

    def add_widget(self, widget: QWidget) -> None:
        self.body.addWidget(widget)

    def retranslate(self) -> None:
        self.title_label.setText(self.i18n.t(self._title_key))
        self.desc_label.setText(self.i18n.t(self._desc_key))

    # ---------------- 任务执行 ----------------
    def set_status(self, text: str, error: bool = False) -> None:
        self.status.setObjectName("TaskError" if error else "TaskStatus")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(text)

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def run_task(self, fn: Callable, on_done: Callable[[object], None],
                 button: QPushButton | None = None) -> None:
        if self.is_busy():
            return
        if button is not None:
            button.setEnabled(False)
        self.set_status(self.i18n.t("common.working"))
        self.progress.setValue(0)
        self.progress.show()

        worker = Worker(fn, self)
        self._worker = worker

        def finish_ok(result) -> None:
            if button is not None:
                button.setEnabled(True)
            self.progress.hide()
            self.set_status("")
            self._worker = None
            on_done(result)

        def finish_err(message: str) -> None:
            if button is not None:
                button.setEnabled(True)
            self.progress.hide()
            self.set_status(message, error=True)
            self._worker = None
            error_box(self, self.i18n, message)

        worker.progress.connect(self.progress.setValue)
        worker.done.connect(finish_ok)
        worker.failed.connect(finish_err)
        worker.finished.connect(worker.deleteLater)
        worker.start()


def error_box(parent: QWidget, i18n, message: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(i18n.t("common.error"))
    box.setText(message)
    box.addButton(i18n.t("common.ok"), QMessageBox.AcceptRole)
    box.exec()


def result_box(parent: QWidget, i18n, message: str, path: str) -> None:
    """完成提示：可打开文件或所在文件夹。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(i18n.t("common.done"))
    box.setText(message)
    open_file = box.addButton(i18n.t("common.open_file"), QMessageBox.AcceptRole)
    open_folder = box.addButton(i18n.t("common.open_folder"), QMessageBox.AcceptRole)
    box.addButton(i18n.t("common.ok"), QMessageBox.AcceptRole)
    box.exec()
    clicked = box.clickedButton()
    target = Path(path)
    if clicked is open_file and target.exists():
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
    elif clicked is open_folder:
        folder = target if target.is_dir() else target.parent
        if folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
