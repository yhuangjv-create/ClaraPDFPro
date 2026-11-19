"""用户偏好设置（QSettings 存储到注册表）。"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from . import APP_NAME, ORG_NAME


class Settings:
    def __init__(self) -> None:
        self._s = QSettings(ORG_NAME, APP_NAME)

    def value(self, key: str, default=None):
        return self._s.value(key, default)

    def set_value(self, key: str, value) -> None:
        self._s.setValue(key, value)
        self._s.sync()

    @property
    def language(self) -> str:
        return str(self.value("ui/language", "zh"))

    @language.setter
    def language(self, lang: str) -> None:
        self.set_value("ui/language", lang)

    @property
    def dark_mode(self) -> bool:
        return str(self.value("ui/dark", "false")).lower() == "true"

    @dark_mode.setter
    def dark_mode(self, enabled: bool) -> None:
        self.set_value("ui/dark", "true" if enabled else "false")

    @property
    def last_dir(self) -> str:
        return str(self.value("files/last_dir", ""))

    @last_dir.setter
    def last_dir(self, path: str) -> None:
        self.set_value("files/last_dir", path)

    def save_geometry(self, data) -> None:
        self.set_value("ui/geometry", data)

    def load_geometry(self):
        return self.value("ui/geometry")
