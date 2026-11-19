"""主窗口：左侧工具导航 + 右侧工具页面。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, __version__
from .i18n import I18n
from .icons import make_app_icon
from .pages import (
    AboutPage,
    CompressPage,
    ConvertPage,
    ImagesToPdfPage,
    OrganizePage,
    PdfToImagesPage,
    SecurityPage,
)
from .settings import Settings
from .theme import build_stylesheet

_NAV = (
    ("convert", "nav.convert", ConvertPage),
    ("compress", "nav.compress", CompressPage),
    ("organize", "nav.organize", OrganizePage),
    ("pdf2img", "nav.pdf2img", PdfToImagesPage),
    ("img2pdf", "nav.img2pdf", ImagesToPdfPage),
    ("security", "nav.security", SecurityPage),
)
_NAV_ABOUT = ("about", "nav.about", AboutPage)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.i18n = I18n(self.settings.language)
        self._pages: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QToolButton] = {}
        self._current = "convert"

        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setWindowIcon(make_app_icon())
        self.resize(1040, 720)
        self.setMinimumSize(880, 600)

        self._build_ui()
        self.apply_theme()

        geometry = self.settings.load_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)

    # ---------------- 界面构建 ----------------
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        for key, _text_key, page_cls in _NAV + (_NAV_ABOUT,):
            page = page_cls(self.i18n)
            self._pages[key] = page
            self.stack.addWidget(page)

        self._nav_buttons[self._current].setChecked(True)
        self.stack.setCurrentWidget(self._pages[self._current])

        status = self.statusBar()
        status.showMessage(f"{APP_NAME} {__version__}")

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(212)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 22, 0, 12)
        layout.setSpacing(0)

        logo = QLabel(APP_NAME)
        logo.setObjectName("LogoTitle")
        logo.setContentsMargins(18, 0, 12, 0)
        sub = QLabel(self.i18n.t("app.slogan"))
        sub.setObjectName("LogoSub")
        sub.setContentsMargins(19, 2, 12, 16)
        layout.addWidget(logo)
        layout.addWidget(sub)

        section = QLabel(self.i18n.t("nav.section_tools"))
        section.setObjectName("NavSection")
        layout.addWidget(section)

        for key, text_key, _cls in _NAV:
            layout.addWidget(self._make_nav_button(key, self.i18n.t(text_key)))

        layout.addStretch(1)

        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(128,128,128,0.25);")
        divider.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(divider)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(12, 10, 12, 0)
        bottom.setSpacing(6)
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("SidebarMini")
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.lang_btn = QToolButton()
        self.lang_btn.setObjectName("SidebarMini")
        self.lang_btn.setText(self.i18n.t("common.lang"))
        self.lang_btn.clicked.connect(self.toggle_language)
        self.about_btn = self._make_nav_button(
            _NAV_ABOUT[0], self.i18n.t(_NAV_ABOUT[1]), compact=True
        )
        self.about_btn.clicked.connect(lambda: self._switch("about"))
        bottom.addWidget(self.theme_btn)
        bottom.addWidget(self.lang_btn)
        bottom.addStretch(1)
        bottom.addWidget(self.about_btn)
        layout.addLayout(bottom)
        return sidebar

    def _make_nav_button(self, key: str, text: str, compact: bool = False) -> QToolButton:
        button = QToolButton()
        button.setObjectName("SidebarMini" if compact else "NavButton")
        button.setText(text)
        button.setCheckable(not compact)
        button.setAutoExclusive(not compact)
        button.setCursor(Qt.PointingHandCursor)
        button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        if not compact:
            button.setMinimumHeight(38)
            button.clicked.connect(lambda _=False, k=key: self._switch(k))
            self._nav_buttons[key] = button
        return button

    # ---------------- 交互 ----------------
    def _switch(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        self._current = key
        self.stack.setCurrentWidget(page)

    def any_busy(self) -> bool:
        for page in self._pages.values():
            if hasattr(page, "is_busy") and page.is_busy():
                return True
        return False

    def apply_theme(self) -> None:
        dark = self.settings.dark_mode
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(dark))
        label_key = "common.light" if dark else "common.dark"
        self.theme_btn.setText(self.i18n.t(label_key))

    def toggle_theme(self) -> None:
        self.settings.dark_mode = not self.settings.dark_mode
        self.apply_theme()

    def toggle_language(self) -> None:
        if self.any_busy():
            return
        lang = self.i18n.toggle()
        self.settings.language = lang
        self.lang_btn.setText(self.i18n.t("common.lang"))
        self._rebuild_for_language()

    def _rebuild_for_language(self) -> None:
        current = self._current if self._current in self._nav_buttons else "convert"
        old = self.takeCentralWidget()
        self._pages.clear()
        self._nav_buttons.clear()
        self._build_ui()
        self._current = current
        self._nav_buttons[current].setChecked(True)
        self.stack.setCurrentWidget(self._pages[current])
        self.apply_theme()
        if old is not None:
            old.deleteLater()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.settings.save_geometry(self.saveGeometry())
        super().closeEvent(event)
