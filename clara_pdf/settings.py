"""用户偏好设置（QSettings 存储到注册表）。"""

from __future__ import annotations

import json
import time
from pathlib import Path

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

    # ---------------- 最近文件 ----------------
    def recent_files(self) -> list[str]:
        raw = self.value("files/recent", [])
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw] if raw else []
        return [str(x) for x in raw]

    @property
    def recent_limit(self) -> int:
        try:
            return min(50, max(1, int(self.value("files/recent_limit", 10))))
        except (TypeError, ValueError):
            return 10

    @recent_limit.setter
    def recent_limit(self, count: int) -> None:
        count = min(50, max(1, int(count)))
        self.set_value("files/recent_limit", count)
        files = self.recent_files()[:count]
        self.set_value("files/recent", files)
        times = self._recent_times()
        self.set_value("files/recent_times",
                       json.dumps({p: times[p] for p in files if p in times}))

    @property
    def recent_hidden(self) -> bool:
        return str(self.value("files/recent_hidden", "false")).lower() == "true"

    @recent_hidden.setter
    def recent_hidden(self, hidden: bool) -> None:
        self.set_value("files/recent_hidden", "true" if hidden else "false")

    @property
    def recent_days(self) -> int:
        try:
            return max(0, int(self.value("files/recent_days", 0)))
        except (TypeError, ValueError):
            return 0

    @recent_days.setter
    def recent_days(self, days: int) -> None:
        self.set_value("files/recent_days", max(0, int(days)))

    def _recent_times(self) -> dict[str, float]:
        raw = self.value("files/recent_times", "{}")
        try:
            data = json.loads(str(raw))
            return {str(k): float(v) for k, v in data.items()}
        except (TypeError, ValueError):
            return {}

    def recent_time(self, path: str) -> float:
        timestamp = self._recent_times().get(path)
        if timestamp is not None:
            return timestamp
        try:
            return Path(path).stat().st_mtime
        except OSError:
            return 0.0

    def visible_recent_files(self) -> list[str]:
        files = [p for p in self.recent_files() if Path(p).exists()]
        days = self.recent_days
        if days > 0:
            cutoff = time.time() - days * 86400
            files = [p for p in files if self.recent_time(p) >= cutoff]
        return files[: self.recent_limit]

    def add_recent_file(self, path: str) -> None:
        files = [p for p in self.recent_files() if p != path]
        files.insert(0, path)
        files = files[: self.recent_limit]
        times = self._recent_times()
        times[path] = time.time()
        self.set_value("files/recent", files)
        self.set_value("files/recent_times",
                       json.dumps({p: times[p] for p in files if p in times}))

    def remove_recent_file(self, path: str) -> None:
        self.set_value("files/recent", [p for p in self.recent_files() if p != path])
        times = self._recent_times()
        times.pop(path, None)
        self.set_value("files/recent_times", json.dumps(times))

    def clear_recent_files(self) -> None:
        self.set_value("files/recent", [])
        self.set_value("files/recent_times", "{}")

    def save_geometry(self, data) -> None:
        self.set_value("ui/geometry", data)

    def load_geometry(self):
        return self.value("ui/geometry")

    # ---------- 会话恢复（上次编辑的 PDF + 状态）----------
    @property
    def last_path(self) -> str:
        return str(self.value("session/last_path", ""))

    @last_path.setter
    def last_path(self, path: str) -> None:
        self.set_value("session/last_path", path)

    @property
    def backup_path(self) -> str:
        return str(self.value("session/backup_path", ""))

    @backup_path.setter
    def backup_path(self, path: str) -> None:
        self.set_value("session/backup_path", path)

    @property
    def last_page(self) -> int:
        try:
            return int(self.value("session/page", 0))
        except (TypeError, ValueError):
            return 0

    @last_page.setter
    def last_page(self, idx: int) -> None:
        self.set_value("session/page", int(idx))

    @property
    def last_dpi(self) -> float:
        try:
            return float(self.value("session/dpi", 110.0))
        except (TypeError, ValueError):
            return 110.0

    @last_dpi.setter
    def last_dpi(self, dpi: float) -> None:
        self.set_value("session/dpi", float(dpi))

    @property
    def last_mode(self) -> str:
        return str(self.value("session/mode", "text"))

    @last_mode.setter
    def last_mode(self, mode: str) -> None:
        self.set_value("session/mode", mode)

    def clear_session(self) -> None:
        self._s.remove("session/last_path")
        self._s.remove("session/backup_path")
        self._s.remove("session/page")
        self._s.remove("session/dpi")
        self._s.remove("session/mode")
        self._s.sync()

