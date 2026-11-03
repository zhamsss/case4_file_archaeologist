import os
from collections import defaultdict
from typing import Any, Dict, Tuple
import navigation
import utils


def count_files(path: str) -> Tuple[bool, int]:
    success, items = navigation.list_directory(path)
    if not success:
        return False, 0

    total_files = 0
    for item in items:
        if item["hidden"] and item["type"] == "directory":
            continue

        if item["type"] == "file":
            total_files += 1
        elif item["type"] == "directory":
            full_path = os.path.join(path, item["name"])
            if not os.path.islink(full_path):
                _, sub_count = count_files(full_path)
                total_files += sub_count

    return True, total_files


def count_bytes(path: str) -> Tuple[bool, int]:
    success, items = navigation.list_directory(path)
    if not success:
        return False, 0

    total_bytes = 0
    for item in items:
        if item["hidden"] and item["type"] == "directory":
            continue

        full_path = os.path.join(path, item["name"])
        if os.path.islink(full_path):
            continue

        if item["type"] == "file":
            total_bytes += item["size"]
        elif item["type"] == "directory":
            _, sub_bytes = count_bytes(full_path)
            total_bytes += sub_bytes

    return True, total_bytes


def analyze_windows_file_types(
    path: str,
) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
    stats = defaultdict(lambda: {"count": 0, "size": 0})

    def _recursive_collect(current_path: str):
        success, items = navigation.list_directory(current_path)
        if not success:
            return

        for item in items:
            if item["hidden"] and item["type"] == "directory":
                continue
            full_path = os.path.join(current_path, item["name"])
            if os.path.islink(full_path):
                continue

            if item["type"] == "file":
                _, ext = os.path.splitext(item["name"].lower())
                if not ext:
                    ext = "no_extension"
                stats[ext]["count"] += 1
                stats[ext]["size"] += item["size"]
            elif item["type"] == "directory":
                _recursive_collect(full_path)

    _recursive_collect(path)
    return True, dict(stats)


def get_windows_file_attributes_stats(path: str) -> Dict[str, int]:
    stats = {"hidden_or_system": 0, "normal": 0}
    success, items = navigation.list_directory(path)
    if not success:
        return stats

    for item in items:
        if item["hidden"]:
            stats["hidden_or_system"] += 1
        else:
            stats["normal"] += 1
    return stats


def show_windows_directory_stats(path: str) -> bool:
    print(f"\n=== АНАЛИЗ КАТАЛОГА: {path} ===")

    ok_files, f_count = count_files(path)
    ok_bytes, b_count = count_bytes(path)

    if not ok_files and not ok_bytes:
        print("Ошибка: Не удалось проанализировать каталог.")
        return False

    print(f"Всего обнаружено файлов: {f_count}")
    print(f"Общий объем данных:      {utils.format_size(b_count)}")

    _, type_stats = analyze_windows_file_types(path)
    print("\nРаспределение по расширениям:")
    sorted_types = sorted(
        type_stats.items(), key=lambda x: x[1]["size"], reverse=True
    )
    for ext, data in sorted_types[:5]:
        print(
            f"  {ext:<12} Количество: {data['count']:<5} "
            f"Объем: {utils.format_size(data['size'])}"
        )

    attr_stats = get_windows_file_attributes_stats(path)
    print("\nАтрибуты верхнего уровня папки:")
    print(f"  Обычные элементы: {attr_stats['normal']}")
    print(f"  Скрытые/Системные: {attr_stats['hidden_or_system']}")
    return True
