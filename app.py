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


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(make_app_icon())

    font = app.font()
    font.setFamily("Microsoft YaHei UI")
    font.setPointSize(9)
    app.setFont(font)

    from clara_pdf.i18n import install_qt_translator
    from clara_pdf.settings import Settings

    settings = Settings()
    install_qt_translator(settings.language)

    from clara_pdf.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
