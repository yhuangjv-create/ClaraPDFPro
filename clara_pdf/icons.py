"""程序化绘制应用图标，避免依赖外部图片资源。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap


def make_app_icon(size: int = 128) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)

    rect = QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.88)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#3d75c9"))
    gradient.setColorAt(1.0, QColor("#22437a"))
    painter.setBrush(gradient)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(rect, size * 0.18, size * 0.18)

    # 白色装饰折角
    painter.setBrush(QColor(255, 255, 255, 42))
    corner = QRectF(rect.right() - size * 0.36, rect.top(), size * 0.36, size * 0.36)
    painter.drawRoundedRect(corner, size * 0.05, size * 0.05)

    font = QFont("Arial", int(size * 0.26), QFont.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(rect, Qt.AlignCenter, "PDF")

    painter.end()
    return QIcon(pix)
