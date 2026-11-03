import ctypes
import os
import platform
from pathlib import Path
from typing import List, Tuple, Union

PathString = Union[str, Path]


def is_windows_os() -> bool:
    return platform.system() == "Windows"


def validate_windows_path(path: PathString) -> Tuple[bool, str]:
    path_str = str(path)

    if not path_str.strip():
        return False, "Путь не может быть пустым"

    if len(path_str) > 260:
        return False, "Превышена максимальная длина пути (260 символов)"

    tabu_chars = '*?"<>|'
    if any(char in tabu_chars for char in path_str):
        return False, 'Путь содержит запрещенные символы (*, ?, ", <, >, |)'

    if path_str.count(":") > 1 or (
        ":" in path_str and path_str[1:3] != ":\\" and path_str[1:3] != ":/"
    ):
        return False, "Некорректное использование двоеточия в пути"

    if not os.path.exists(path_str):
        return False, "Указанный путь не существует"

    return True, ""


def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 KB"
    suffixes = ["Bytes", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(suffixes) - 1:
        size /= 1024
        i += 1
    if i == 0:
        return f"{int(size)} {suffixes[i]}"
    return f"{size:.1f} {suffixes[i]}"


def get_parent_path(path: PathString) -> str:
    path_str = str(path)
    drive, tail = os.path.splitdrive(path_str)

    if tail in ("\\", "/", ""):
        return path_str

    parent = os.path.dirname(path_str)
    if len(parent) == 2 and parent.endswith(":"):
        parent += "\\"
    return parent


def safe_windows_listdir(path: PathString) -> List[str]:
    try:
        return os.listdir(path)
    except (PermissionError, FileNotFoundError, OSError):
        return []


def is_hidden_windows_file(path: PathString) -> bool:
    try:
        path_str = str(path)
        if not is_windows_os():
            return os.path.basename(path_str).startswith(".")

        attrs = ctypes.windll.kernel32.GetFileAttributesW(path_str)
        if attrs == -1:
            return False

        return bool(attrs & 2 or attrs & 4)
    except Exception:
        return False
