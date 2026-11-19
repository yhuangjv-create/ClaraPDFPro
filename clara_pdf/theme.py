"""浅色 / 深色主题样式表。"""

from __future__ import annotations

ACCENT = "#2b579a"          # Clara 蓝
ACCENT_PRESSED = "#1f4276"


def build_stylesheet(dark: bool = False) -> str:
    if dark:
        c = {
            "win": "#1b1c1e",
            "panel": "#232528",
            "card": "#26282b",
            "border": "#35383c",
            "text": "#e9eaec",
            "subtext": "#9aa0a6",
            "accent": "#4a86d8",
            "accent_pressed": "#3a6cb0",
            "accent_light": "#2c3a4d",
            "hover": "#2e3135",
            "input": "#1f2124",
            "shadow": "#16171a",
        }
    else:
        c = {
            "win": "#f2f3f5",
            "panel": "#ffffff",
            "card": "#ffffff",
            "border": "#e3e5e8",
            "text": "#1f2328",
            "subtext": "#6b7280",
            "accent": ACCENT,
            "accent_pressed": ACCENT_PRESSED,
            "accent_light": "#eaf1fb",
            "hover": "#f3f6fa",
            "input": "#ffffff",
            "shadow": "#d8dde3",
        }

    return f"""
    QMainWindow, QDialog {{
        background: {c['win']};
        color: {c['text']};
        font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
        font-size: 9pt;
    }}
    QWidget {{
        color: {c['text']};
        font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
        font-size: 9pt;
    }}
    QWidget#Sidebar {{
        background: {c['panel']};
        border-right: 1px solid {c['border']};
    }}
    QLabel#LogoTitle {{
        color: {c['accent']};
        font-size: 15pt;
        font-weight: bold;
        padding: 0px;
    }}
    QLabel#LogoSub {{
        color: {c['subtext']};
        font-size: 8pt;
    }}
    QLabel#NavSection {{
        color: {c['subtext']};
        font-size: 8pt;
        font-weight: bold;
        padding: 10px 14px 4px 18px;
    }}
    QToolButton#NavButton {{
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
        text-align: left;
        padding: 9px 12px 9px 15px;
        color: {c['text']};
        font-size: 10pt;
    }}
    QToolButton#NavButton:hover {{
        background: {c['hover']};
    }}
    QToolButton#NavButton:checked {{
        background: {c['accent_light']};
        border-left: 3px solid {c['accent']};
        color: {c['accent']};
        font-weight: bold;
    }}
    QToolButton#SidebarMini {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px 8px;
        color: {c['subtext']};
    }}
    QToolButton#SidebarMini:hover {{
        background: {c['hover']};
        border-color: {c['border']};
        color: {c['text']};
    }}
    QFrame#Card {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 8px;
    }}
    QLabel#PageTitle {{
        font-size: 20pt;
        font-weight: bold;
        color: {c['text']};
        background: transparent;
    }}
    QLabel#PageDesc {{
        font-size: 9.5pt;
        color: {c['subtext']};
        background: transparent;
    }}
    QLabel#CardTitle {{
        font-size: 11pt;
        font-weight: bold;
        color: {c['text']};
        background: transparent;
    }}
    QLabel#CardDesc {{
        font-size: 9pt;
        color: {c['subtext']};
        background: transparent;
    }}
    QLabel#FieldLabel {{
        font-size: 9pt;
        color: {c['text']};
        background: transparent;
    }}
    QLabel#Hint {{
        font-size: 8.5pt;
        color: {c['subtext']};
        background: transparent;
    }}
    QLabel#TaskStatus {{
        font-size: 9pt;
        color: {c['accent']};
        background: transparent;
    }}
    QLabel#TaskError {{
        font-size: 9pt;
        color: #c0392b;
        background: transparent;
    }}
    QLabel#DropHint {{
        color: {c['subtext']};
        background: {c['input']};
        border: 1px dashed {c['border']};
        border-radius: 6px;
        padding: 14px;
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {c['input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 20px;
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {c['accent']};
    }}
    QLineEdit:read-only {{
        color: {c['subtext']};
    }}
    QComboBox QAbstractItemView {{
        background: {c['card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
        outline: none;
    }}
    QPushButton {{
        background: {c['card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        background: {c['accent_light']};
        border-color: {c['accent']};
    }}
    QPushButton:pressed {{
        background: {c['accent_light']};
    }}
    QPushButton:disabled {{
        color: {c['subtext']};
        background: {c['win']};
        border-color: {c['border']};
    }}
    QPushButton#PrimaryButton {{
        background: {c['accent']};
        color: #ffffff;
        border: 1px solid {c['accent']};
        font-weight: bold;
        padding: 8px 22px;
    }}
    QPushButton#PrimaryButton:hover {{
        background: {c['accent_pressed']};
        border-color: {c['accent_pressed']};
    }}
    QPushButton#PrimaryButton:disabled {{
        background: {c['border']};
        border-color: {c['border']};
        color: {c['subtext']};
    }}
    QListWidget {{
        background: {c['input']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        outline: none;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 4px 6px;
        border-radius: 4px;
    }}
    QListWidget::item:hover {{
        background: {c['hover']};
    }}
    QListWidget::item:selected {{
        background: {c['accent']};
        color: #ffffff;
    }}
    QListWidget#ThumbList {{
        background: {c['win']};
        border: 1px solid {c['border']};
    }}
    QListWidget#ThumbList::item {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px;
        margin: 4px;
        color: {c['text']};
    }}
    QListWidget#ThumbList::item:selected {{
        background: {c['accent_light']};
        border: 2px solid {c['accent']};
        color: {c['text']};
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 11px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: #b9bfc7;
        border-radius: 4px;
        min-height: 28px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #98a1ab; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 11px;
    }}
    QScrollBar::handle:horizontal {{
        background: #b9bfc7;
        border-radius: 4px;
        min-width: 28px;
        margin: 2px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
    QStatusBar {{
        background: {c['panel']};
        border-top: 1px solid {c['border']};
        color: {c['subtext']};
    }}
    QStatusBar::item {{ border: none; }}
    QCheckBox {{
        background: transparent;
        color: {c['text']};
        spacing: 6px;
    }}
    QProgressBar {{
        background: {c['input']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        text-align: center;
        color: {c['text']};
    }}
    QProgressBar::chunk {{
        background: {c['accent']};
        border-radius: 3px;
    }}
    QMenu {{
        background: {c['card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 22px 6px 16px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background: {c['accent']};
        color: #ffffff;
    }}
    QToolTip {{
        background: {c['card']};
        color: {c['text']};
        border: 1px solid {c['border']};
        padding: 4px;
    }}
    QMessageBox {{
        background: {c['card']};
    }}
    QDialog {{
        background: {c['win']};
    }}
    QScrollBar:vertical:disabled {{ background: transparent; }}
    """
