"""后台任务线程，避免耗时转换阻塞界面。"""

from __future__ import annotations

import traceback
from typing import Callable

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """在子线程执行 fn(log, progress) 并回传结果。

    fn 的签名：fn(log: Callable[[str], None], progress: Callable[[int], None]) -> object
    """

    done = Signal(object)
    failed = Signal(str)
    log = Signal(str)
    progress = Signal(int)

    def __init__(self, fn: Callable, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D102
        try:
            result = self._fn(self.log.emit, self.progress.emit)
        except Exception as exc:  # noqa: BLE001 - 统一反馈给界面
            self.log.emit(traceback.format_exc(limit=3))
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.done.emit(result)
