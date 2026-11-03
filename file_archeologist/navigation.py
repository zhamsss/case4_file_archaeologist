import datetime
import os
import string
from typing import Any, Dict, List, Tuple
import utils


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
