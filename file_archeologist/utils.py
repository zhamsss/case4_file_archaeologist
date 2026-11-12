import ctypes
import os
import platform
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

PathString = Union[str, Path]

MAX_RECURSION_DEPTH = 100
WINDOWS_MAX_PATH = 260
TABU_CHARS = set('*?"<>|')
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


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


def _is_segment_valid(segment: str, is_root_drive: bool = False) -> bool:
    if not segment:
        return True

    if is_root_drive:
        if len(segment) >= 2 and segment[0].isalpha() and segment[1] == ":":
            rest = segment[2:].lstrip("\\/")
            return rest == "" and not any(ch in TABU_CHARS for ch in segment)
        return not any(ch in TABU_CHARS for ch in segment)

    if any(ch in TABU_CHARS for ch in segment) or ":" in segment:
        return False

    if segment.endswith(" ") or segment.endswith("."):
        return False

    base_name = segment.split(".")[0].upper()
    if base_name in RESERVED_NAMES:
        return False

    return True


def validate_windows_path_recursive(
    path: PathString, depth: int = 0
) -> Tuple[bool, List[str]]:
    """
    Рекурсивная проверка пути и всех его родительских каталогов в Windows
    Возвращает (валидность, список проблемных участков пути)
    """
    path_str = str(path)

    if depth > MAX_RECURSION_DEPTH:
        return False, [f"{path_str} (превышена максимальная глубина рекурсии)"]

    if not path_str.strip():
        return False, ["<пустой путь>"]

    normalized = path_str.rstrip("\\/") if len(path_str) > 3 else path_str
    drive, tail = os.path.splitdrive(normalized)
    is_root = tail in ("\\", "/", "")

    segment = normalized if is_root else os.path.basename(normalized)
    current_issues: List[str] = []

    if not _is_segment_valid(segment, is_root_drive=is_root):
        current_issues.append(path_str)

    if is_root:
        return len(current_issues) == 0, current_issues

    parent = get_parent_path(normalized)
    if parent == normalized:
        return len(current_issues) == 0, current_issues

    parent_valid, parent_issues = validate_windows_path_recursive(parent, depth + 1)
    all_issues = current_issues + parent_issues
    return (len(all_issues) == 0 and parent_valid), all_issues


def collect_windows_metadata_recursive(
    path: PathString, max_depth: int = 10
) -> Dict[str, Any]:
    """
    Рекурсивный сбор метаданных файловой системы Windows
    """
    root_path = str(path)
    level_stats: Dict[int, Dict[str, int]] = {}
    type_distribution_by_depth: Dict[int, Dict[str, int]] = {}

    def _walk(current_path: str, current_depth: int) -> Dict[str, Any]:
        level_stats.setdefault(
            current_depth,
            {
                "directories": 0,
                "files": 0,
                "hidden": 0,
                "total_size": 0,
            },
        )
        type_distribution_by_depth.setdefault(current_depth, {})

        name = os.path.basename(current_path.rstrip("\\/")) or current_path
        is_dir = os.path.isdir(current_path)
        hidden = is_hidden_windows_file(current_path)

        try:
            stat_info = os.stat(current_path)
            size = 0 if is_dir else stat_info.st_size
            mtime = stat_info.st_mtime
        except OSError:
            size = 0
            mtime = None

        node: Dict[str, Any] = {
            "name": name,
            "path": current_path,
            "depth": current_depth,
            "type": "directory" if is_dir else "file",
            "hidden": hidden,
            "size": size,
            "modified": mtime,
        }

        if is_dir:
            level_stats[current_depth]["directories"] += 1
            if hidden:
                level_stats[current_depth]["hidden"] += 1

            children: List[Dict[str, Any]] = []
            if current_depth < max_depth:
                for entry in sorted(safe_windows_listdir(current_path)):
                    child_path = os.path.join(current_path, entry)
                    children.append(_walk(child_path, current_depth + 1))
            node["children"] = children
        else:
            level_stats[current_depth]["files"] += 1
            level_stats[current_depth]["total_size"] += size
            if hidden:
                level_stats[current_depth]["hidden"] += 1

            ext = os.path.splitext(name)[1].lower() or "<no_ext>"
            type_distribution_by_depth[current_depth][ext] = (
                type_distribution_by_depth[current_depth].get(ext, 0) + 1
            )

        return node

    tree = _walk(root_path, 0)

    return {
        "root": root_path,
        "max_depth": max_depth,
        "tree": tree,
        "level_stats": level_stats,
        "type_distribution_by_depth": type_distribution_by_depth,
    }


def _apply_long_path_prefix(path_str: str, prefix: str = "\\\\?\\") -> str:
    if path_str.startswith("\\\\?\\"):
        return path_str

    if path_str.startswith("\\\\"):
        unc_prefix = "\\\\?\\UNC\\"
        clean_unc = path_str.lstrip("\\")
        return f"{unc_prefix}{clean_unc}"

    return f"{prefix}{path_str}"


def resolve_long_paths_recursive(
    path: PathString,
    prefix: str = "\\\\?\\",
    _depth: int = 0,
) -> str:
    """
    Рекурсивное преобразование длинных путей Windows с поддержкой UNC
    """
    path_str = str(path)

    if _depth > MAX_RECURSION_DEPTH:
        return (
            _apply_long_path_prefix(path_str, prefix)
            if len(path_str) > WINDOWS_MAX_PATH
            else path_str
        )

    raw_path = path_str
    if raw_path.startswith("\\\\?\\UNC\\"):
        raw_path = "\\\\" + raw_path[8:]
    elif raw_path.startswith("\\\\?\\"):
        raw_path = raw_path[4:]

    parent = get_parent_path(raw_path)
    if parent and parent != raw_path:
        resolved_parent = resolve_long_paths_recursive(parent, prefix, _depth + 1)
        leaf = os.path.basename(raw_path.rstrip("\\/"))
        if leaf:
            rebuilt = os.path.join(resolved_parent, leaf)
            if len(raw_path) > WINDOWS_MAX_PATH:
                return _apply_long_path_prefix(rebuilt, prefix)
            return rebuilt

    if len(raw_path) > WINDOWS_MAX_PATH:
        return _apply_long_path_prefix(raw_path, prefix)

    return path_str