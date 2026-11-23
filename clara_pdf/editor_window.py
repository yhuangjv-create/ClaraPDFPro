"""PDF 编辑器主窗口：Office 风格功能区 + 页面缩略图 + 页面视图 + 状态栏。

窗口可以无文档启动（显示「打开 PDF」引导页），也可直接传入引擎；
功能区按「开始 / 编辑 / 视图」分组，仿照 Office 的 Ribbon 布局。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QIcon,
    QKeySequence,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import ORG_NAME
from .icons import make_app_icon
from .i18n import install_qt_translator
from .pages import (
    AboutPage,
    CompressPage,
    ConvertPage,
    ImagesToPdfPage,
    OrganizePage,
    PdfToImagesPage,
    SecurityPage,
)
from .pdf_editor_engine import PdfEditorEngine, PdfEngineError
from .pdf_view import PdfPageView
from .settings import Settings
from .theme import build_palette, build_stylesheet

# 基准 DPI 对应 100% 缩放
BASE_DPI = 110.0
THUMB_W = 128
THUMB_H = 170
THUMB_GRID_W = 134
THUMB_GRID_H = 202

# 嵌入到「工具」标签页的模块（键与 i18n 前缀一致）
_TOOLS = (
    ("convert", ConvertPage),
    ("compress", CompressPage),
    ("organize", OrganizePage),
    ("pdf2img", PdfToImagesPage),
    ("img2pdf", ImagesToPdfPage),
    ("security", SecurityPage),
    ("about", AboutPage),
)
_TOOL_CLASSES = dict(_TOOLS)


class _RibbonGroup(QWidget):
    """功能区分组：上方按钮行，下方居中的组名。"""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RibbonGroup")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 2)
        outer.setSpacing(2)
        self.row = QHBoxLayout()
        self.row.setContentsMargins(0, 2, 0, 0)
        self.row.setSpacing(2)
        outer.addLayout(self.row, 1)
        label = QLabel(title)
        label.setObjectName("RibbonGroupTitle")
        label.setAlignment(Qt.AlignHCenter)
        outer.addWidget(label)

    def add(self, widget: QWidget) -> QWidget:
        self.row.addWidget(widget)
        return widget

    def add_button(self, action: QAction, popup: bool = False) -> QToolButton:
        button = QToolButton()
        button.setObjectName("RibbonButton")
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        button.setAutoRaise(True)
        button.setMinimumHeight(32)
        if popup:
            button.setPopupMode(QToolButton.InstantPopup)
        self.row.addWidget(button)
        return button


class _RibbonBar(QWidget):
    """Office 风格功能区：顶部标签页 + 下方分组区域。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RibbonBar")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.tabs = QTabBar()
        self.tabs.setObjectName("RibbonTabs")
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.setUsesScrollButtons(False)
        self.pages = QStackedWidget()
        self.pages.setObjectName("RibbonPages")

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 10, 0)
        top.setSpacing(6)
        top.addWidget(self.tabs)
        top.addStretch(1)
        self.corner = QHBoxLayout()
        self.corner.setSpacing(4)
        top.addLayout(self.corner)

        outer.addLayout(top)
        outer.addWidget(self.pages)
        self.tabs.currentChanged.connect(self.pages.setCurrentIndex)

    def add_corner(self, widget: QWidget) -> QWidget:
        self.corner.addWidget(widget)
        return widget

    def add_tab(self, title: str) -> QHBoxLayout:
        page = QWidget()
        page.setObjectName("RibbonPage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(6, 2, 6, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        self.pages.addWidget(page)
        self.tabs.addTab(title)
        return layout

    def add_group(self, layout: QHBoxLayout, title: str) -> _RibbonGroup:
        group = _RibbonGroup(title)
        layout.insertWidget(layout.count() - 1, group)
        return group


class _SmoothScrollArea(QScrollArea):
    """在 Windows + PySide6 下，QScrollArea.wheelEvent() 本身是 no-op——

    wheel 事件到了但滚动条不动。这里 override wheelEvent，把 angleDelta
    直接转成 verticalScrollBar.setValue，让滚轮真正推动长画布。不做任
    何触边翻页逻辑——PdfPageView 已经是所有页堆叠的长画布，滚轮滚就是
    连续滚。
    """

    def wheelEvent(self, event):  # noqa: N802, ANN201
        sb = self.verticalScrollBar()
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return
        # Windows + PySide6: angleDelta.y > 0 表示滚轮向下推（手指远离身体），
        # sb.value() 增大意味着页面内容向上移动 = "看更后面"，
        # 所以直接 + delta 就是正确方向。
        sb.setValue(sb.value() + delta)
        event.accept()


class PdfEditorWindow(QMainWindow):
    def __init__(self, engine: PdfEditorEngine | None = None, i18n=None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if i18n is None:
            from .i18n import I18n

            i18n = I18n()
        self.engine = engine
        self.i18n = i18n
        self._dirty = False
        self._first_show = True
        self._thumb_dpi = 45.0
        self._tool_pages: dict[str, QWidget] = {}
        self._current_tool: str | None = None
        self._tools_tab = 2

        self.setWindowIcon(make_app_icon())
        self.setWindowTitle(self.i18n.t("editor.window_title_empty"))
        self.resize(1180, 780)
        self.setMinimumSize(820, 520)

        self._build_ui()
        self._build_ribbon()
        self._build_shortcuts()

        if self.engine is None:
            self._show_empty()
        else:
            self._attach_engine()

    # ---------------- 界面构建 ----------------
    def _build_ui(self) -> None:
        editor = QWidget()
        outer = QHBoxLayout(editor)
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

        # 右侧：文档视图与空视图叠放，编辑器界面始终常驻
        # PdfPageView 现在是多页垂直堆叠的长画布，滚轮在整个长画布上连续滚动
        self.scroll = _SmoothScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.view = PdfPageView(self.engine, self.i18n, self)
        self.scroll.setWidget(self.view)
        # 滚轮驱动 _SmoothScrollArea.wheelEvent 手动 setValue；
        # scrollBar 的 valueChanged 反向把当前页推回 view / 缩略图 / 状态栏
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        self.empty_page = self._build_empty_page()
        self.right_stack = QStackedWidget()
        self.right_stack.setObjectName("ViewerStack")
        self.right_stack.addWidget(self.empty_page)
        self.right_stack.addWidget(self.scroll)
        outer.addWidget(self.right_stack, 1)
        self.editor_page = editor

        self.tools_page = self._build_tools_page()
        self.body = QStackedWidget()
        self.body.addWidget(editor)
        self.body.addWidget(self.tools_page)
        self.setCentralWidget(self.body)

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
        self.view.content_changed.connect(self._on_field_changed)
        self.view.status.connect(lambda m: sb.showMessage(m, 4000))

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("EditorEmpty")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(8)
        layout.addStretch(1)

        icon = QLabel()
        icon.setPixmap(make_app_icon().pixmap(72, 72))
        icon.setAlignment(Qt.AlignCenter)
        title = QLabel(self.i18n.t("editor.empty_title"))
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignCenter)
        hint = QLabel(self.i18n.t("editor.empty_hint"))
        hint.setObjectName("EmptyHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)

        self.empty_open_btn = QPushButton(self.i18n.t("editor.open"))
        self.empty_open_btn.setObjectName("PrimaryButton")
        self.empty_open_btn.setCursor(Qt.PointingHandCursor)
        self.empty_open_btn.clicked.connect(self._open_file)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.empty_open_btn)
        row.addStretch(1)

        layout.addWidget(icon)
        layout.addSpacing(6)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(12)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _build_tools_page(self) -> QWidget:
        """工具首页：以卡片形式列出所有独立模块。"""
        page = QWidget()
        page.setObjectName("ToolsHome")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(6)

        title = QLabel(self.i18n.t("tools.page_title"))
        title.setObjectName("EmptyTitle")
        desc = QLabel(self.i18n.t("tools.page_desc"))
        desc.setObjectName("EmptyHint")
        desc.setWordWrap(True)

        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (key, _cls) in enumerate(_TOOLS[:6]):
            card = QPushButton(self.i18n.t(key + ".title"))
            card.setObjectName("ToolCard")
            card.setToolTip(self.i18n.t(key + ".desc"))
            card.setCursor(Qt.PointingHandCursor)
            card.setMinimumHeight(64)
            card.clicked.connect(lambda _=False, k=key: self._show_tool(k))
            grid.addWidget(card, i // 3, i % 3)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addSpacing(16)
        layout.addLayout(grid)
        layout.addStretch(1)
        return page

    def _build_ribbon(self) -> None:
        self.ribbon = _RibbonBar()
        ribbon_bar = QToolBar()
        ribbon_bar.setObjectName("RibbonToolbar")
        ribbon_bar.setMovable(False)
        ribbon_bar.setFloatable(False)
        ribbon_bar.setContentsMargins(0, 0, 0, 0)
        self.ribbon.setContentsMargins(0, 0, 0, 0)
        ribbon_bar.addWidget(self.ribbon)
        self.addToolBar(Qt.TopToolBarArea, ribbon_bar)

        # 右上角：语言切换、主题切换、关于
        self.lang_btn = QToolButton()
        self.lang_btn.setObjectName("RibbonCorner")
        self.lang_btn.setText(self.i18n.t("common.lang"))
        self.lang_btn.setToolTip(self.i18n.t("common.lang"))
        self.lang_btn.setCursor(Qt.PointingHandCursor)
        self.lang_btn.clicked.connect(self.toggle_language)
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("RibbonCorner")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.about_btn = QToolButton()
        self.about_btn.setObjectName("RibbonCorner")
        self.about_btn.setText(self.i18n.t("nav.about"))
        self.about_btn.setCursor(Qt.PointingHandCursor)
        self.about_btn.clicked.connect(lambda: self._show_tool("about"))
        self.ribbon.add_corner(self.lang_btn)
        self.ribbon.add_corner(self.theme_btn)
        self.ribbon.add_corner(self.about_btn)
        self.apply_theme()

        # ---- 动作 ----
        self.act_open = QAction(self.i18n.t("editor.open"), self)
        self.act_save = QAction(self.i18n.t("editor.save"), self)
        self.act_save_as = QAction(self.i18n.t("editor.save_as"), self)
        self.act_undo = QAction(self.i18n.t("editor.undo"), self)
        self.act_redo = QAction(self.i18n.t("editor.redo"), self)
        self.act_prev = QAction(self.i18n.t("editor.prev_page"), self)
        self.act_next = QAction(self.i18n.t("editor.next_page"), self)
        self.act_zoom_out = QAction(self.i18n.t("editor.zoom_out"), self)
        self.act_zoom_in = QAction(self.i18n.t("editor.zoom_in"), self)
        self.act_fit_width = QAction(self.i18n.t("editor.fit_width"), self)
        self.act_fit_page = QAction(self.i18n.t("editor.fit_page"), self)
        self.act_annots = QAction(self.i18n.t("editor.toggle_annots"), self)
        self.act_annots.setCheckable(True)
        self.act_annots.setChecked(True)
        self.act_fields = QAction(self.i18n.t("editor.toggle_fields"), self)
        self.act_fields.setCheckable(True)
        self.act_fields.setChecked(True)
        self.act_ocr = QAction(self.i18n.t("editor.ocr"), self)
        ocr_menu = QMenu(self)
        self.act_ocr_page = ocr_menu.addAction(self.i18n.t("editor.ocr_page"))
        self.act_ocr_all = ocr_menu.addAction(self.i18n.t("editor.ocr_all"))
        self.act_ocr.setMenu(ocr_menu)
        self.act_back_doc = QAction(self.i18n.t("editor.back_to_doc"), self)
        self.act_tools_home = QAction(self.i18n.t("tools.home"), self)
        self.tool_actions: dict[str, QAction] = {}
        for key, _cls in _TOOLS:
            self.tool_actions[key] = QAction(self.i18n.t(key + ".title"), self)
        self.act_mode_browse = QAction(self.i18n.t("editor.mode_browse"), self)
        self.act_mode_text = QAction(self.i18n.t("editor.mode_text"), self)

        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        self.act_tool_highlight = self._make_tool_action(
            "editor.annot_highlight", "highlight", checked=True)
        self.act_tool_underline = self._make_tool_action("editor.annot_underline", "underline")
        self.act_tool_note = self._make_tool_action("editor.annot_note", "note")

        self.mode_combo = QComboBox()
        self.mode_combo.setFixedWidth(112)
        self.mode_combo.setMinimumHeight(26)
        self.mode_combo.addItem(self.i18n.t("editor.mode_text"), "text")
        self.mode_combo.addItem(self.i18n.t("editor.mode_form"), "form")
        self.mode_combo.addItem(self.i18n.t("editor.mode_browse"), "browse")
        self.mode_combo.addItem(self.i18n.t("editor.mode_annot"), "annot")

        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setFixedWidth(78)
        self.zoom_combo.setMinimumHeight(26)
        for pct in (50, 75, 100, 125, 150, 200, 300, 400):
            self.zoom_combo.addItem(self.i18n.t("editor.zoom_pct", pct=pct), pct)
        self.zoom_combo.lineEdit().setAlignment(Qt.AlignCenter)

        self.page_label = QLabel("")
        self.page_label.setContentsMargins(8, 0, 8, 0)
        self.page_label.setMinimumWidth(110)
        self.page_label.setAlignment(Qt.AlignCenter)

        # ---- 开始（原「开始」+「编辑」合并：去重后保留唯一项） ----
        home = self.ribbon.add_tab(self.i18n.t("ribbon.home"))
        group = self.ribbon.add_group(home, self.i18n.t("ribbon.group_file"))
        group.add_button(self.act_open)
        group.add_button(self.act_save)
        group.add_button(self.act_save_as)
        group = self.ribbon.add_group(home, self.i18n.t("ribbon.group_undo"))
        group.add_button(self.act_undo)
        group.add_button(self.act_redo)
        group = self.ribbon.add_group(home, self.i18n.t("ribbon.group_edit"))
        group.add(self.mode_combo)
        group.add_button(self.act_fields)
        group = self.ribbon.add_group(home, self.i18n.t("ribbon.group_annot"))
        group.add_button(self.act_tool_highlight)
        group.add_button(self.act_tool_underline)
        group.add_button(self.act_tool_note)
        group = self.ribbon.add_group(home, self.i18n.t("ribbon.group_ocr"))
        group.add_button(self.act_ocr, popup=True)

        # ---- 视图 ----
        view = self.ribbon.add_tab(self.i18n.t("ribbon.view"))
        group = self.ribbon.add_group(view, self.i18n.t("ribbon.group_page"))
        group.add_button(self.act_prev)
        group.add(self.page_label)
        group.add_button(self.act_next)
        group = self.ribbon.add_group(view, self.i18n.t("ribbon.group_zoom"))
        group.add_button(self.act_zoom_out)
        group.add(self.zoom_combo)
        group.add_button(self.act_zoom_in)
        group.add_button(self.act_fit_width)
        group.add_button(self.act_fit_page)
        group = self.ribbon.add_group(view, self.i18n.t("ribbon.group_show"))
        group.add_button(self.act_annots)
        group.add_button(self.act_fields)

        # ---- 工具 ----
        tools = self.ribbon.add_tab(self.i18n.t("ribbon.tools"))
        group = self.ribbon.add_group(tools, self.i18n.t("ribbon.group_document"))
        group.add_button(self.act_back_doc)
        group.add_button(self.act_tools_home)
        group = self.ribbon.add_group(tools, self.i18n.t("ribbon.group_convert"))
        group.add_button(self.tool_actions["convert"])
        group = self.ribbon.add_group(tools, self.i18n.t("ribbon.group_compress"))
        group.add_button(self.tool_actions["compress"])
        group = self.ribbon.add_group(tools, self.i18n.t("ribbon.group_organize"))
        group.add_button(self.tool_actions["organize"])
        group = self.ribbon.add_group(tools, self.i18n.t("ribbon.group_images"))
        group.add_button(self.tool_actions["pdf2img"])
        group.add_button(self.tool_actions["img2pdf"])
        group = self.ribbon.add_group(tools, self.i18n.t("ribbon.group_security"))
        group.add_button(self.tool_actions["security"])
        group = self.ribbon.add_group(tools, self.i18n.t("ribbon.group_misc"))
        group.add_button(self.tool_actions["about"])

        # ---- 连接 ----
        self.act_open.triggered.connect(self._open_file)
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
        self.tool_group.triggered.connect(self._on_tool_action)
        self.act_annots.toggled.connect(self.view.set_annots_visible)
        self.act_fields.toggled.connect(self.view.set_fields_visible)
        self.act_ocr_page.triggered.connect(self._ocr_current)
        self.act_ocr_all.triggered.connect(self._ocr_all)
        self.act_back_doc.triggered.connect(self._back_to_document)
        self.act_tools_home.triggered.connect(self._show_tools_home)

        # ---- 工具栏 ----
        for key, action in self.tool_actions.items():
            action.triggered.connect(lambda _=False, k=key: self._show_tool(k))
        self.ribbon.tabs.currentChanged.connect(self._on_ribbon_tab_changed)
        self.act_mode_browse.triggered.connect(
            lambda: self.mode_combo.setCurrentIndex(self.mode_combo.findData("browse")))
        self.act_mode_text.triggered.connect(
            lambda: self.mode_combo.setCurrentIndex(self.mode_combo.findData("text")))

    def _make_tool_action(self, key: str, tool: str, checked: bool = False) -> QAction:
        action = QAction(self.i18n.t(key), self)
        action.setCheckable(True)
        action.setData(tool)
        action.setChecked(checked)
        self.tool_group.addAction(action)
        return action

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._open_file)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self._save_as)
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

    # ---------------- 文档状态 ----------------
    def _show_empty(self) -> None:
        self._current_tool = None
        self.right_stack.setCurrentWidget(self.empty_page)
        self.body.setCurrentWidget(self.editor_page)
        self.thumb_list.clear()
        self._set_actions_enabled(False)
        self._update_title()
        self.page_label.setText("")
        self.status_page.setText("")
        self.status_fields.setText("")
        self.status_zoom.setText("")
        self.zoom_combo.setEditText("")
        self.statusBar().showMessage(self.i18n.t("editor.empty_hint"))

    def _attach_engine(self, confirm_thumbs: bool = True, auto_fit: bool = True) -> None:
        self._current_tool = None
        self.view.set_engine(self.engine)
        self.right_stack.setCurrentWidget(self.scroll)
        self.body.setCurrentWidget(self.editor_page)
        self._set_actions_enabled(True)
        self._set_dirty(False)
        self._update_title()
        self.view.set_mode(self.mode_combo.currentData())
        self._load_thumbs(confirm_thumbs)
        self._goto(0)
        self._update_undo_redo()
        self._update_status_fields()
        self._update_zoom_label()
        if not self.engine.has_forms():
            self.statusBar().showMessage(self.i18n.t("editor.no_form"), 8000)
        if self.ribbon.tabs.currentIndex() != 0:
            self.ribbon.tabs.setCurrentIndex(0)
        if auto_fit:
            QTimer.singleShot(0, lambda: self._fit("width"))

    # ---------------- 工具页切换 ----------------
    def _on_ribbon_tab_changed(self, index: int) -> None:
        if index == self._tools_tab:
            self._current_tool = None
            self.body.setCurrentWidget(self.tools_page)
            self.page_label.setText("")
            self.status_page.setText("")
            self.status_fields.setText("")
            self.status_zoom.setText("")
            self.statusBar().showMessage("")
            self._update_title()
        else:
            self._show_editor_body()

    def _back_to_document(self) -> None:
        if self.ribbon.tabs.currentIndex() != 0:
            self.ribbon.tabs.setCurrentIndex(0)
        else:
            self._show_editor_body()

    def _show_editor_body(self) -> None:
        self._current_tool = None
        self.body.setCurrentWidget(self.editor_page)
        if self.engine is not None:
            self.right_stack.setCurrentWidget(self.scroll)
            total = self.engine.page_count
            if total:
                text = self.i18n.t("editor.page_n", n=self.view.page_idx + 1, total=total)
                self.page_label.setText(text)
                self.status_page.setText(text)
            self._update_status_fields()
            self._update_zoom_label()
        else:
            self.right_stack.setCurrentWidget(self.empty_page)
            self.page_label.setText("")
            self.status_page.setText("")
            self.status_fields.setText("")
            self.status_zoom.setText("")
        self._update_title()

    def _show_tools_home(self) -> None:
        self._current_tool = None
        if self.ribbon.tabs.currentIndex() != self._tools_tab:
            self.ribbon.tabs.setCurrentIndex(self._tools_tab)
        else:
            self.body.setCurrentWidget(self.tools_page)
            self._update_title()
        self.statusBar().showMessage("")

    def _show_tool(self, key: str) -> None:
        page = self._tool_pages.get(key)
        if page is None:
            page = _TOOL_CLASSES[key](self.i18n)
            self._tool_pages[key] = page
            self.body.addWidget(page)
        if self.ribbon.tabs.currentIndex() != self._tools_tab:
            self.ribbon.tabs.setCurrentIndex(self._tools_tab)
        self._current_tool = key
        self.body.setCurrentWidget(page)
        self.page_label.setText("")
        self.status_page.setText("")
        self.status_fields.setText("")
        self.status_zoom.setText("")
        self.statusBar().showMessage("")
        self._update_title()

    def _set_actions_enabled(self, enabled: bool) -> None:
        for action in (
            self.act_save, self.act_save_as, self.act_undo, self.act_redo,
            self.act_prev, self.act_next, self.act_zoom_in, self.act_zoom_out,
            self.act_fit_width, self.act_fit_page, self.act_annots, self.act_fields,
            self.act_ocr, self.act_ocr_page, self.act_ocr_all,
            self.act_mode_browse, self.act_mode_text,
            self.act_tool_highlight, self.act_tool_underline, self.act_tool_note,
        ):
            action.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.zoom_combo.setEnabled(enabled)

    def open_document(self, path: str) -> bool:
        """打开 PDF；已有文档未保存时先询问。返回是否成功打开。"""
        if not self._maybe_save():
            return False
        engine = self._open_engine(path)
        if engine is None:
            return False
        if self.engine is not None:
            self.engine.close()
        self.engine = engine
        Settings().last_dir = str(Path(path).parent)
        self._attach_engine()
        return True

    def _open_file(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, self.i18n.t("editor.open"), Settings().last_dir,
            self.i18n.t("filter.pdf"))
        if chosen:
            self.open_document(chosen)

    def _open_engine(self, src: str) -> PdfEditorEngine | None:
        """打开引擎；加密文档循环询问密码，返回 None 表示用户取消。"""
        password = ""
        while True:
            try:
                return PdfEditorEngine(src, password)
            except PdfEngineError:
                pw, ok = QInputDialog.getText(
                    self, self.i18n.t("editor.need_password"), self.i18n.t("common.password"),
                    echo=QLineEdit.Password)
                if not ok:
                    return None
                password = pw
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, self.i18n.t("common.error"),
                                    self.i18n.t("editor.open_error", err=exc))
                return None

    # ---------------- 语言切换 ----------------
    def toggle_language(self) -> None:
        for page in self._tool_pages.values():
            if hasattr(page, "is_busy") and page.is_busy():
                return
        lang = self.i18n.toggle()
        Settings().language = lang
        install_qt_translator(lang)
        self._rebuild_for_language()

    def _rebuild_for_language(self) -> None:
        """原地重建界面以应用新语言，保留文档、页码、缩放与当前工具。"""
        engine = self.engine
        dirty = self._dirty
        tool = self._current_tool
        tab = self.ribbon.tabs.currentIndex()
        mode = self.mode_combo.currentData()
        dpi = self.view.dpi
        page_idx = self.view.page_idx

        old_central = self.takeCentralWidget()
        for toolbar in self.findChildren(QToolBar):
            self.removeToolBar(toolbar)
            toolbar.deleteLater()
        for shortcut in self.findChildren(QShortcut):
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        for label in (self.status_page, self.status_fields, self.status_zoom):
            self.statusBar().removeWidget(label)
            label.deleteLater()
        if old_central is not None:
            old_central.deleteLater()

        self._tool_pages.clear()
        self._current_tool = None
        self.statusBar().clearMessage()

        self._build_ui()
        self._build_ribbon()
        self._build_shortcuts()

        if engine is None:
            self._show_empty()
        else:
            self._attach_engine(confirm_thumbs=False)
            self._set_dirty(dirty)
            idx = self.mode_combo.findData(mode)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
            self.view.set_mode(mode)
            self._goto(page_idx)
            self._set_dpi(dpi)
            self._update_zoom_label()
            # _attach_engine 会排队一次自适应宽度，这里在事件循环中把缩放改回来
            QTimer.singleShot(0, lambda: self._set_dpi(dpi))

        if tool is not None:
            self._show_tool(tool)
        elif tab == self._tools_tab:
            self.ribbon.tabs.setCurrentIndex(self._tools_tab)
        elif 0 <= tab <= 2:
            self.ribbon.tabs.setCurrentIndex(tab)

    # ---------------- 缩略图 ----------------
    def _load_thumbs(self, confirm: bool = True) -> None:
        self.thumb_list.clear()
        if self.engine is None:
            return
        total = self.engine.page_count
        if total > 120 and confirm:
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
        if self.engine is None:
            return
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
        """让滚动条滚到第 idx 页的顶部——因为 PdfPageView 是多页长画布。"""
        if self.engine is None or self.view._page_offsets is None:
            return
        total = self.engine.page_count
        if total <= 0:
            return
        idx = max(0, min(idx, total - 1))
        sb = self.scroll.verticalScrollBar()
        target = self.view.offset_of_page(idx)
        if sb.value() == target:
            # 已经在那一页顶部，但 label/thumb 可能还没同步（首次打开时）
            self.view.page_idx = idx
            self._sync_page_chrome(idx)
        else:
            sb.setValue(target)  # 会触发 _on_scroll_changed

    def _on_scroll_changed(self, value: int) -> None:
        """scrollBar 位置变化 → 推导出当前页 → 同步 view / 缩略图 / 状态栏。"""
        if self.engine is None or self.view._page_offsets is None:
            return
        idx = self.view.page_at_y(value)
        if idx is None:
            # 在页之间的 gap 里——归到最近的一页
            for i, top in enumerate(self.view._page_offsets):
                if top > value:
                    idx = max(0, i - 1)
                    break
            else:
                idx = len(self.view._page_offsets) - 1
        if idx != self.view.page_idx:
            self.view.page_idx = idx
            self._sync_page_chrome(idx)

    def _sync_page_chrome(self, idx: int) -> None:
        """同步页码 label、缩略图高亮、状态栏。"""
        total = self.engine.page_count if self.engine else 0
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
        if self.engine is None:
            return
        dpi = max(30.0, min(400.0, float(dpi)))
        self.view.set_dpi(dpi)
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        if self.engine is None:
            self.zoom_combo.setEditText("")
            self.status_zoom.setText("")
            return
        pct = max(1, round(self.view.dpi / BASE_DPI * 100))
        self.zoom_combo.setEditText(self.i18n.t("editor.zoom_pct", pct=pct))
        self.status_zoom.setText(self.i18n.t("editor.zoom_pct", pct=pct))

    def _apply_combo_zoom(self) -> None:
        if self.engine is None:
            return
        text = self.zoom_combo.currentText().strip().rstrip("%")
        try:
            pct = float(text)
        except ValueError:
            self._update_zoom_label()
            return
        self._set_dpi(BASE_DPI * pct / 100.0)

    def _fit(self, which: str) -> None:
        if self.engine is None:
            return
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
    def _current_annot_tool(self) -> str:
        for action in self.tool_group.actions():
            if action.isChecked():
                return action.data()
        return "highlight"

    def _on_mode_changed(self, _idx: int) -> None:
        if self.engine is None:
            return
        mode = self.mode_combo.currentData()
        self.view.set_mode(mode)
        if mode == "annot":
            self.view.set_annot_tool(self._current_annot_tool())
        elif mode == "text" and not self.view._spans:
            self.statusBar().showMessage(self.i18n.t("editor.no_text"), 5000)

    def _on_tool_action(self, action: QAction) -> None:
        if self.engine is None:
            return
        idx = self.mode_combo.findData("annot")
        if self.mode_combo.currentIndex() != idx:
            self.mode_combo.setCurrentIndex(idx)
        self.view.set_annot_tool(action.data())

    # ---------------- OCR ----------------
    def _ocr_current(self) -> None:
        self._run_ocr([self.view.page_idx])

    def _ocr_all(self) -> None:
        if self.engine is None:
            return
        self._run_ocr(range(self.engine.page_count))

    def _run_ocr(self, pages) -> None:
        """逐页识别文字并写入不可见文字层。"""
        if self.engine is None:
            return
        from . import ocr

        if not ocr.backend_available():
            QMessageBox.warning(self, self.i18n.t("common.info"),
                                self.i18n.t("editor.ocr_unavailable"))
            return
        pages = list(pages)
        lang = ocr.pick_language()
        progress = None
        if len(pages) > 1:
            progress = QProgressDialog(
                self.i18n.t("editor.ocr_running"), self.i18n.t("common.cancel"),
                0, len(pages), self)
            progress.setWindowTitle(self.i18n.t("editor.ocr"))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
        recognized = skipped = lines = 0
        try:
            for i, idx in enumerate(pages):
                if progress is not None:
                    if progress.wasCanceled():
                        break
                    progress.setLabelText(self.i18n.t(
                        "editor.ocr_progress", n=idx + 1, total=self.engine.page_count))
                    QApplication.processEvents()
                try:
                    n = self.engine.ocr_page(idx, lang)
                except Exception as exc:  # noqa: BLE001
                    self.statusBar().showMessage(str(exc), 6000)
                    continue
                if n is None:
                    skipped += 1
                elif n:
                    recognized += 1
                    lines += n
                if progress is not None:
                    progress.setValue(i + 1)
                    QApplication.processEvents()
        finally:
            if progress is not None:
                progress.close()
        if recognized:
            self.view.refresh()
            self._set_dirty(True)
            self._update_undo_redo()
            self.statusBar().showMessage(
                self.i18n.t("editor.ocr_done", pages=recognized, lines=lines), 8000)
        elif skipped:
            self.statusBar().showMessage(self.i18n.t("editor.ocr_skip"), 8000)
        else:
            self.statusBar().showMessage(self.i18n.t("editor.ocr_empty"), 8000)

    # ---------------- 编辑反馈 ----------------
    def _on_field_changed(self) -> None:
        self.view.refresh()
        self._set_dirty(True)
        self._update_undo_redo()
        self._update_status_fields()
        self._refresh_current_thumb()

    def _update_status_fields(self) -> None:
        if self.engine is None:
            self.status_fields.setText("")
            return
        n = len(self.engine.form_fields(self.view.page_idx))
        self.status_fields.setText(self.i18n.t("editor.status_fields", n=n))

    def _update_undo_redo(self) -> None:
        if self.engine is None:
            self.act_undo.setEnabled(False)
            self.act_redo.setEnabled(False)
            return
        self.act_undo.setEnabled(self.engine.can_undo())
        self.act_redo.setEnabled(self.engine.can_redo())

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._update_title()

    def _update_title(self) -> None:
        if self._current_tool is not None:
            title = self.i18n.t(self._current_tool + ".title")
            if self._current_tool == "about":
                self.setWindowTitle(title)
            else:
                self.setWindowTitle(f"{title} — ClaraPDFPro")
            return
        if self.engine is None:
            self.setWindowTitle(self.i18n.t("editor.window_title_empty"))
            return
        name = Path(self.engine.path).name
        star = " *" if self._dirty else ""
        self.setWindowTitle(self.i18n.t("editor.window_title", name=name) + star)

    # ---------------- 撤销 / 重做 ----------------
    def _undo(self) -> None:
        if self.engine is None or not self.engine.can_undo():
            return
        if self.engine.undo():
            self._after_undo_redo()

    def _redo(self) -> None:
        if self.engine is None or not self.engine.can_redo():
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
        if self.engine is None:
            return False
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
        if self.engine is None:
            return False
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
    def _maybe_save(self) -> bool:
        """有未保存更改时询问；返回 False 表示用户取消了后续操作。"""
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(self.i18n.t("editor.unsaved_title"))
        box.setText(self.i18n.t("editor.unsaved"))
        save_btn = box.addButton(self.i18n.t("editor.save"), QMessageBox.AcceptRole)
        discard_btn = box.addButton(self.i18n.t("editor.discard"), QMessageBox.DestructiveRole)
        box.addButton(self.i18n.t("common.cancel"), QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_btn:
            return self._save()
        return clicked is discard_btn

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_frame_theme()
        if self._first_show:
            self._first_show = False
            if self.engine is not None:
                QTimer.singleShot(0, lambda: self._fit("width"))

    # ---------------- 主题切换 ----------------
    def apply_theme(self) -> None:
        dark = Settings().dark_mode
        app = QApplication.instance()
        if app is not None:
            app.setPalette(build_palette(dark))
            app.setStyleSheet(build_stylesheet(dark))
        self._apply_frame_theme()
        label_key = "common.light" if dark else "common.dark"
        self.theme_btn.setText(self.i18n.t(label_key))

    def toggle_theme(self) -> None:
        Settings().dark_mode = not Settings().dark_mode
        self.apply_theme()

    def _apply_frame_theme(self) -> None:
        """固定 Windows 标题栏颜色，避免被系统强调色染色。"""
        if sys.platform != "win32" or not self.isVisible():
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute.argtypes = [
                ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
            ]
            dark = ctypes.c_int(1 if Settings().dark_mode else 0)
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))

            palette = build_palette(Settings().dark_mode)
            window = palette.color(QPalette.ColorRole.Window)
            text = palette.color(QPalette.ColorRole.WindowText)
            caption = ctypes.c_uint(window.red() | (window.green() << 8) | (window.blue() << 16))
            caption_text = ctypes.c_uint(text.red() | (text.green() << 8) | (text.blue() << 16))
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
            dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(caption_text), ctypes.sizeof(caption_text))
        except Exception:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._maybe_save():
            event.ignore()
            return
        s = Settings()
        # 持久化语言（双保险）
        s.language = self.i18n.lang
        # 持久化会话：记住正在编辑的 PDF、页码、缩放、模式、未保存改动
        if self.engine is not None:
            s.last_path = self.engine.path or ""
            s.last_page = self.view.page_idx
            s.last_dpi = self.view.dpi
            s.last_mode = self.view._mode
            if self.engine.dirty:
                # 有未保存改动 → 另存一份临时备份，下次启动先恢复这个再打开原路径
                try:
                    backup_dir = Path(os.environ.get("APPDATA", "")) / ORG_NAME
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup_file = str(backup_dir / "last_edit_backup.pdf")
                    self.engine.save(backup_file)
                    s.backup_path = backup_file
                except Exception:
                    s.backup_path = ""
            else:
                # clean → 清掉上次的临时备份，不需要了
                old_backup = s.backup_path
                s.backup_path = ""
                if old_backup:
                    try:
                        Path(old_backup).unlink(missing_ok=True)
                    except Exception:
                        pass
            self.engine.close()
        else:
            s.clear_session()
        event.accept()

    def restore_session(self) -> bool:
        """恢复上次关闭时编辑的 PDF 和状态。成功返回 True。"""
        s = Settings()
        path = s.last_path
        if not path or not Path(path).exists():
            return False
        open_path = s.backup_path if (s.backup_path and Path(s.backup_path).exists()) else path
        engine = self._open_engine(open_path)
        if engine is None:
            return False
        if self.engine is not None:
            self.engine.close()
        engine.path = path
        self.engine = engine
        self._attach_engine(confirm_thumbs=False, auto_fit=False)
        self.view.set_mode(s.last_mode)
        self.view.set_dpi(s.last_dpi)
        self._goto(s.last_page)
        self._update_zoom_label()
        self.setWindowTitle(f"{Path(path).stem} — ClaraPDFPro")
        return True
