"""文件路径与大小处理工具。"""

from __future__ import annotations

from pathlib import Path


def human_size(num_bytes: float) -> str:
    """把字节数格式化为 B / KB / MB / GB。"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GB"


def unique_path(path: Path) -> Path:
    """目标存在时返回同目录下 name (1).ext 形式的可用路径。"""
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def default_output(src: str | Path, suffix: str, tag: str = "") -> Path:
    """根据源文件生成默认输出路径，例如 report_converted.docx。"""
    path = Path(src)
    stem = f"{path.stem}_{tag}" if tag else path.stem
    return unique_path(path.with_name(f"{stem}{suffix}"))


def ensure_suffix(path: str | Path, suffix: str) -> Path:
    p = Path(path)
    if p.suffix.lower() != suffix.lower():
        p = p.with_suffix(suffix)
    return p
