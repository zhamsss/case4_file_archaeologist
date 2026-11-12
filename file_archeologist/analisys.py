import hashlib
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import navigation
import utils


# ==========================================
# БАЗОВЫЕ ФУНКЦИИ АНАЛИЗА (СУЩЕСТВУЮЩИЙ КОД)
# ==========================================

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


# ==========================================
# ЗАДАНИЕ 1: РЕКУРСИВНЫЙ ДЕТЕКТОР ДУБЛИКАТОВ
# ==========================================

def _default_block_hash(filepath: str, chunk_size: int = 65536) -> Optional[str]:
    """Вычисляет SHA-256 хеш файла блоками для экономии оперативной памяти."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None


def find_duplicate_files_recursive(
    path: str,
    checksum_func: Callable = None,
    visited: Set[str] = None,
) -> Dict[str, List[str]]:
    """
    Рекурсивный поиск дубликатов файлов по содержимому в Windows.
    """
    if checksum_func is None:
        checksum_func = _default_block_hash
    if visited is None:
        visited = set()

    # Системные директории Windows, которые лучше пропускать во избежание зависаний и ошибок доступа
    windows_system_dirs = {
        "$recycle.bin",
        "system volume information",
        "windows",
        "programdata",
        "recovery",
    }

    size_groups: Dict[int, List[str]] = defaultdict(list)

    def _scan_recursive(current_path: str):
        real_dir = os.path.realpath(current_path)
        if real_dir in visited:
            return
        visited.add(real_dir)

        success, items = navigation.list_directory(current_path)
        if not success:
            return

        for item in items:
            name_lower = item["name"].lower()
            full_path = os.path.join(current_path, item["name"])

            if os.path.islink(full_path):
                continue

            if item["type"] == "directory":
                if item["hidden"] or name_lower in windows_system_dirs:
                    continue
                _scan_recursive(full_path)
            elif item["type"] == "file":
                # Пропускаем системные служебные файлы Windows и пустые файлы
                if item["hidden"] or name_lower in {"pagefile.sys", "hiberfil.sys", "swapfile.sys", "desktop.ini", "thumbs.db"}:
                    continue
                if item["size"] > 0:
                    size_groups[item["size"]].append(full_path)

    # 1. Рекурсивно группируем файлы по размеру (оптимизация: не хешируем уникальные по размеру файлы)
    _scan_recursive(path)

    # 2. Вычисляем хеш-суммы только для файлов с совпадающим размером
    hash_groups: Dict[str, List[str]] = defaultdict(list)
    for size, file_paths in size_groups.items():
        if len(file_paths) < 2:
            continue
        for fpath in file_paths:
            file_hash = checksum_func(fpath)
            if file_hash:
                hash_groups[file_hash].append(fpath)

    # 3. Оставляем только реальные дубликаты (где больше 1 файла на хеш)
    return {h: paths for h, paths in hash_groups.items() if len(paths) > 1}


# ==========================================
# ЗАДАНИЕ 2: РЕКУРСИВНЫЙ АНАЛИЗАТОР ЗАВИСИМОСТЕЙ
# ==========================================

def analyze_file_dependencies_recursive(
    root_path: str,
    target_extensions: List[str] = None,
    dependency_tree: Dict[str, List[str]] = None,
) -> Dict[str, Any]:
    """
    Рекурсивный анализ зависимостей между файлами (например, .h -> .cpp, import в .py).
    """
    if target_extensions is None:
        target_extensions = [".c", ".cpp", ".h", ".hpp", ".py", ".js", ".ts"]
    target_extensions = [ext.lower() for ext in target_extensions]

    if dependency_tree is None:
        dependency_tree = {}

    file_index: Dict[str, str] = {}

    # Шаг 1: Рекурсивно индексируем все целевые файлы в проекте
    def _index_files(current_path: str):
        success, items = navigation.list_directory(current_path)
        if not success:
            return
        for item in items:
            if item["hidden"] and item["type"] == "directory":
                continue
            full_path = os.path.join(current_path, item["name"])
            if os.path.islink(full_path):
                continue

            if item["type"] == "directory":
                _index_files(full_path)
            elif item["type"] == "file":
                _, ext = os.path.splitext(item["name"].lower())
                if ext in target_extensions:
                    rel_path = os.path.relpath(full_path, root_path).replace("\\", "/")
                    file_index[item["name"].lower()] = rel_path
                    dependency_tree.setdefault(rel_path, [])

    _index_files(root_path)

    # Регулярные выражения для поиска включений и импортов
    include_pattern = re.compile(r'#include\s*[<"]([^>"]+)[>"]')
    import_pattern = re.compile(r'(?:from|import)\s+([a-zA-Z0-9_\.]+)')

    # Шаг 2: Рекурсивный парсинг содержимого и построение графа
    def _parse_dependencies(current_rel_path: str, visited_files: Set[str]):
        if current_rel_path in visited_files:
            return
        visited_files.add(current_rel_path)

        full_path = os.path.join(root_path, current_rel_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (OSError, PermissionError):
            return

        found_deps = set()

        # Поиск C/C++ #include
        for match in include_pattern.findall(content):
            dep_basename = os.path.basename(match).lower()
            if dep_basename in file_index:
                found_deps.add(file_index[dep_basename])

        # Поиск Python/JS импортов
        for match in import_pattern.findall(content):
            module_name = match.split(".")[-1].lower()
            for ext in target_extensions:
                candidate = f"{module_name}{ext}"
                if candidate in file_index:
                    found_deps.add(file_index[candidate])

        dependency_tree[current_rel_path] = sorted(list(found_deps))

        # Рекурсивно обходим найденные зависимости
        for dep_path in dependency_tree[current_rel_path]:
            _parse_dependencies(dep_path, visited_files)

    visited_parse: Set[str] = set()
    for rel_file in list(dependency_tree.keys()):
        _parse_dependencies(rel_file, visited_parse)

    # Шаг 3: Поиск циклических зависимостей (DFS)
    cycles: List[List[str]] = []

    def _find_cycles(node: str, path_stack: List[str], visited_dfs: Set[str]):
        visited_dfs.add(node)
        path_stack.append(node)

        for neighbor in dependency_tree.get(node, []):
            if neighbor not in visited_dfs:
                _find_cycles(neighbor, path_stack, visited_dfs)
            elif neighbor in path_stack:
                cycle_start = path_stack.index(neighbor)
                cycles.append(path_stack[cycle_start:] + [neighbor])

        path_stack.pop()

    visited_dfs: Set[str] = set()
    for node in dependency_tree:
        if node not in visited_dfs:
            _find_cycles(node, [], visited_dfs)

    # Шаг 4: Текстовая визуализация дерева
    tree_lines = []

    def _build_visual_tree(node: str, prefix: str = "", seen: Set[str] = None):
        if seen is None:
            seen = set()
        tree_lines.append(f"{prefix}└── {node}")
        if node in seen:
            tree_lines.append(f"{prefix}    └── [ЦИКЛИЧЕСКАЯ ССЫЛКА]")
            return
        seen.add(node)
        for dep in dependency_tree.get(node, []):
            _build_visual_tree(dep, prefix + "    ", seen.copy())

    for root_node in sorted(dependency_tree.keys()):
        _build_visual_tree(root_node)

    return {
        "dependency_tree": dependency_tree,
        "cycles": cycles,
        "visualization": "\n".join(tree_lines),
    }


# ==========================================
# ЗАДАНИЕ 3: РЕКУРСИВНЫЙ ПРОГНОЗ РОСТА ДАННЫХ
# ==========================================

def _calculate_linear_slope(points: List[Tuple[float, float]]) -> float:
    """
    Вычисляет коэффициент наклона (скорость роста в день) методом наименьших квадратов.
    points: список кортежей (день_от_начала, объем_в_МБ)
    """
    n = len(points)
    if n < 2:
        return 0.0

    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_x2 = sum(p[0] ** 2 for p in points)

    denominator = n * sum_x2 - sum_x ** 2
    if denominator == 0:
        return 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return max(0.0, slope)  # Отрицательный тренд приравниваем к 0 для прогноза роста


def predict_storage_growth_recursive(
    path: str,
    days_back: int = 30,
    growth_data: Dict[str, List] = None,
) -> Dict[str, float]:
    """
    Рекурсивный анализ и прогноз роста данных в Windows файловой системе.
    Возвращает: {"path": growth_rate_mb_per_day, ...}
    """
    if growth_data is None:
        growth_data = {}

    now = time.time()
    cutoff_time = now - (days_back * 86400)
    predictions: Dict[str, float] = {}

    def _analyze_dir_recursive(current_path: str) -> List[Tuple[float, float, int]]:
        """
        Возвращает список (timestamp, size_bytes, weekday) для всех файлов в директории и подпапках.
        """
        records: List[Tuple[float, float, int]] = []
        success, items = navigation.list_directory(current_path)
        if not success:
            return records

        for item in items:
            if item["hidden"] and item["type"] == "directory":
                continue
            full_path = os.path.join(current_path, item["name"])
            if os.path.islink(full_path):
                continue

            if item["type"] == "directory":
                sub_records = _analyze_dir_recursive(full_path)
                records.extend(sub_records)
            elif item["type"] == "file":
                try:
                    mtime = os.path.getmtime(full_path)
                    if mtime >= cutoff_time:
                        weekday = datetime.fromtimestamp(mtime).weekday()
                        records.append((mtime, item["size"], weekday))
                except OSError:
                    continue

        # Агрегация данных по дням для текущей директории
        daily_mb: Dict[int, float] = defaultdict(float)
        weekday_mb: Dict[int, float] = defaultdict(float)

        for mtime, size_bytes, weekday in records:
            day_index = int((mtime - cutoff_time) // 86400)
            mb = size_bytes / (1024 * 1024)
            daily_mb[day_index] += mb
            weekday_mb[weekday] += mb

        # Формируем накопительный ряд объема данных по дням для линейной регрессии
        cumulative_points: List[Tuple[float, float]] = []
        running_total = 0.0
        for d in range(days_back + 1):
            running_total += daily_mb.get(d, 0.0)
            if d in daily_mb or running_total > 0:
                cumulative_points.append((float(d), running_total))

        growth_data[current_path] = cumulative_points

        # Линейная регрессия (МБ в день)
        base_rate = _calculate_linear_slope(cumulative_points)

        # Учет недельной сезонности (если активность в пиковый день недели сильно выше среднего)
        seasonality_factor = 1.0
        if weekday_mb:
            avg_weekday = sum(weekday_mb.values()) / 7.0
            max_weekday = max(weekday_mb.values())
            if avg_weekday > 0 and (max_weekday / avg_weekday) > 2.5:
                # Повышающий коэффициент при выраженных недельных всплесках (например, бэкапы или логи)
                seasonality_factor = 1.15

        predicted_rate = round(base_rate * seasonality_factor, 4)
        predictions[current_path] = predicted_rate
        return records

    _analyze_dir_recursive(path)

    # Сортируем по убыванию скорости роста, чтобы "горячие точки" шли первыми
    sorted_predictions = dict(
        sorted(predictions.items(), key=lambda item: item[1], reverse=True)
    )
    return sorted_predictions