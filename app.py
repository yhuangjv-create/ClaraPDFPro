"""ClaraPDFPro 启动入口。

运行方式：
    python app.py
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from clara_pdf import APP_NAME, ORG_NAME, __version__
from clara_pdf.icons import make_app_icon
from clara_pdf.theme import build_palette, build_stylesheet


def _hide_console() -> None:
    """双击启动时隐藏附带的控制台窗口；从终端启动时保持不动。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return
        # 只有控制台里仅挂着本进程时才隐藏，避免把用户的终端窗口一起关掉
        processes = (ctypes.c_ulong * 8)()
        if kernel32.GetConsoleProcessList(processes, 8) <= 1:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def main() -> int:
    _hide_console()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(make_app_icon())
    # 固定使用 Fusion 风格 + 自有调色板，避免跟随系统主题出现绿色元素
    app.setStyle("Fusion")

    font = app.font()
    font.setFamily("Microsoft YaHei UI")
    font.setPointSize(9)
    app.setFont(font)

    from clara_pdf.i18n import install_qt_translator
    from clara_pdf.settings import Settings

    settings = Settings()
    app.setPalette(build_palette(settings.dark_mode))
    app.setStyleSheet(build_stylesheet(settings.dark_mode))
    install_qt_translator(settings.language)

    # 启动即进入 PDF 编辑器，其它工具从功能区「工具箱」打开
    from clara_pdf.editor_window import PdfEditorWindow
    from clara_pdf.i18n import I18n

    window = PdfEditorWindow(None, I18n(settings.language))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
