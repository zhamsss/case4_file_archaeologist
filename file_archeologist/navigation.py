import datetime
import os
import string
from typing import Any, Dict, Generator, List, Optional, Tuple
import utils

PathString = str

SYSTEM_DIRS = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "programdata",
    "recovery",
    "perflogs",
    "msocache",
}


def _is_windows_system_entry(name: str) -> bool:
    return name.lower() in SYSTEM_DIRS


def _match_pattern(name: str, pattern: str) -> bool:
    name_low = name.lower()
    pat_low = pattern.lower()

    if pat_low == "*":
        return True
    if pat_low.startswith("*") and pat_low.endswith("*") and len(pat_low) > 2:
        return pat_low[1:-1] in name_low
    if pat_low.startswith("*"):
        return name_low.endswith(pat_low[1:])
    if pat_low.endswith("*"):
        return name_low.startswith(pat_low[:-1])
    return name_low == pat_low


def get_current_drive() -> str:
    drive, _ = os.path.splitdrive(os.getcwd())
    return drive if drive else "C:"


def list_available_drives() -> List[str]:
    drives = []
    if utils.is_windows_os():
        import ctypes

        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:")
            bitmask >>= 1
    else:
        drives = [get_current_drive()]
    return drives


def list_directory(path: str) -> Tuple[bool, List[Dict[str, Any]]]:
    valid, _ = utils.validate_windows_path(path)
    if not valid:
        return False, []

    elements = utils.safe_windows_listdir(path)
    result = []

    for name in elements:
        full_path = os.path.join(path, name)
        is_dir = os.path.isdir(full_path)

        try:
            stat_info = os.stat(full_path)
            size = 0 if is_dir else stat_info.st_size
            mod_time = datetime.datetime.fromtimestamp(stat_info.st_mtime)
            modified_str = mod_time.strftime("%Y-%m-%d")
        except OSError:
            size = 0
            modified_str = "unknown"

        result.append(
            {
                "name": name,
                "type": "directory" if is_dir else "file",
                "size": size,
                "modified": modified_str,
                "hidden": utils.is_hidden_windows_file(full_path),
            }
        )

    return True, result


def format_directory_output(items: List[Dict[str, Any]]) -> None:
    if not items:
        print("Каталог пуст или недоступен.")
        return

    fmt = "{:<40} | {:<10} | {:<12} | {:<12} | {:<8}"
    print(fmt.format("Имя", "Тип", "Размер", "Изменен", "Скрытый"))
    print("-" * 90)

    for item in items:
        size_str = (
            utils.format_size(item["size"])
            if item["type"] == "file"
            else "<DIR>"
        )
        hidden_str = "Да" if item["hidden"] else "Нет"
        print(
            fmt.format(
                item["name"][:38],
                item["type"],
                size_str,
                item["modified"],
                hidden_str,
            )
        )


def move_up(current_path: str) -> str:
    parent = utils.get_parent_path(current_path)
    valid, _ = utils.validate_windows_path(parent)
    return parent if valid else current_path


def move_down(current_path: str, target_dir: str) -> Tuple[bool, str]:
    if ":" in target_dir:
        new_path = target_dir
        if len(new_path) == 2 and new_path.endswith(":"):
            new_path += "\\"
    else:
        new_path = os.path.join(current_path, target_dir)

    valid, _ = utils.validate_windows_path(new_path)
    if valid and os.path.isdir(new_path):
        return True, os.path.abspath(new_path)
    return False, current_path


def get_windows_special_folders() -> Dict[str, str]:
    user_profile = os.environ.get("USERPROFILE", "C:\\")
    return {
        "Desktop": os.path.join(user_profile, "Desktop"),
        "Documents": os.path.join(user_profile, "Documents"),
        "Downloads": os.path.join(user_profile, "Downloads"),
        "Windows": os.environ.get("SystemRoot", "C:\\Windows"),
        "Program Files": os.environ.get("ProgramFiles", "C:\\Program Files"),
    }


def build_windows_tree_recursive(
    path: PathString, depth: int = 0, max_depth: int = 5
) -> Dict[str, Any]:
    valid, _ = utils.validate_windows_path(path)
    abs_path = os.path.abspath(path)
    node_name = os.path.basename(abs_path) or abs_path

    if not valid or not os.path.exists(abs_path):
        return {}

    if not os.path.isdir(abs_path):
        return {"name": node_name, "type": "file"}

    tree: Dict[str, Any] = {
        "name": node_name,
        "type": "directory",
        "children": [],
    }

    if depth >= max_depth:
        return tree

    elements = utils.safe_windows_listdir(abs_path)
    for name in elements:
        full_path = os.path.join(abs_path, name)

        if os.path.isdir(full_path):
            if _is_windows_system_entry(name):
                continue
            child_node = build_windows_tree_recursive(
                full_path, depth=depth + 1, max_depth=max_depth
            )
            if child_node:
                tree["children"].append(child_node)
        else:
            tree["children"].append({"name": name, "type": "file"})

    return tree


def recursive_path_explorer(
    start_path: str, history: Optional[List[str]] = None
) -> Generator[Tuple[str, List[str]], None, None]:
    if history is None:
        history = []

    valid, _ = utils.validate_windows_path(start_path)
    if not valid or not os.path.isdir(start_path):
        return

    abs_path = os.path.abspath(start_path)

    if abs_path in history:
        return

    history.append(abs_path)
    yield abs_path, list(history)

    elements = utils.safe_windows_listdir(abs_path)
    for name in elements:
        full_path = os.path.join(abs_path, name)
        if os.path.isdir(full_path):
            if _is_windows_system_entry(name):
                continue

            sub_explored = False
            for next_path, current_history in recursive_path_explorer(
                full_path, history
            ):
                sub_explored = True
                yield next_path, current_history

            if sub_explored:
                yield abs_path, list(history)


def analyze_windows_structure_recursive(
    path: str, pattern: str = "*", level: int = 0
) -> List[Tuple[int, str, str]]:
    results: List[Tuple[int, str, str]] = []
    valid, _ = utils.validate_windows_path(path)
    if not valid or not os.path.exists(path):
        return results

    abs_path = os.path.abspath(path)
    name = os.path.basename(abs_path) or abs_path
    is_dir = os.path.isdir(abs_path)

    if _is_windows_system_entry(name):
        item_type = "SYSTEM"
    elif utils.is_hidden_windows_file(abs_path):
        item_type = "HIDDEN"
    elif is_dir:
        item_type = "DIR"
    else:
        item_type = "FILE"

    if level == 0 or _match_pattern(name, pattern):
        results.append((level, item_type, abs_path))

    if is_dir:
        elements = utils.safe_windows_listdir(abs_path)
        for child_name in elements:
            child_path = os.path.join(abs_path, child_name)
            results.extend(
                analyze_windows_structure_recursive(
                    child_path, pattern=pattern, level=level + 1
                )
            )

    return results