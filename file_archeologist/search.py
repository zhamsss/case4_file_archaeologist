import fnmatch
import os
from typing import Any, Dict, List
import analysis  # Функции аналитика
import navigation  # Функции инженера навигации
import utils  # Функции архитектора


def find_files_windows(
    pattern: str, path: str, case_sensitive: bool = False
) -> List[str]:
    """Поиск файлов по шаблону в Windows"""
    valid, _ = utils.validate_windows_path(path)
    if not valid:
        return []

    _, total_files = analysis.count_files(path)
    results = []
    processed = 0
    search_pattern = pattern if case_sensitive else pattern.lower()

    def _recursive_search(current_path: str) -> None:
        nonlocal processed
        success, items = navigation.list_directory(current_path)
        if not success:
            return

        for item in items:
            if item["hidden"] and item["type"] == "directory":
                continue

            full_path = os.path.join(current_path, item["name"])
            if os.path.islink(full_path):
                continue

            name_to_check = (
                item["name"] if case_sensitive else item["name"].lower()
            )

            if item["type"] == "file":
                processed += 1
                if fnmatch.fnmatch(name_to_check, search_pattern):
                    results.append(full_path)
            elif item["type"] == "directory":
                _recursive_search(full_path)

    _recursive_search(path)
    if total_files > 0:
        print(f"Проверено файлов: {processed} из {total_files}")
    return results


def find_by_windows_extension(extensions: List[str], path: str) -> List[str]:
    """Поиск файлов по списку расширений Windows"""
    valid, _ = utils.validate_windows_path(path)
    if not valid or not extensions:
        return []

    normalized_exts = [
        e.lower() if e.startswith(".") else f".{e.lower()}"
        for e in extensions
        if e.strip()
    ]

    _, type_stats = analysis.analyze_windows_file_types(path)
    if not any(ext in type_stats for ext in normalized_exts):
        return []

    results = []

    def _recursive_ext_search(current_path: str) -> None:
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
                if ext in normalized_exts:
                    results.append(full_path)
            elif item["type"] == "directory":
                _recursive_ext_search(full_path)

    _recursive_ext_search(path)
    return results


def find_large_files_windows(
    min_size_mb: float, path: str
) -> List[Dict[str, Any]]:
    """Поиск крупных файлов в Windows"""
    valid, _ = utils.validate_windows_path(path)
    if not valid:
        return []

    min_bytes = min_size_mb * 1024 * 1024
    _, total_bytes = analysis.count_bytes(path)
    if total_bytes < min_bytes:
        return []

    results = []

    def _recursive_large_search(current_path: str) -> None:
        success, items = navigation.list_directory(current_path)
        if not success:
            return
        for item in items:
            if item["hidden"] and item["type"] == "directory":
                continue
            full_path = os.path.join(current_path, item["name"])
            if os.path.islink(full_path):
                continue

            if item["type"] == "file" and item["size"] >= min_bytes:
                _, ext = os.path.splitext(item["name"])
                results.append(
                    {
                        "path": full_path,
                        "size_bytes": item["size"],
                        "size_mb": round(item["size"] / (1024 * 1024), 2),
                        "type": ext or "no_extension",
                    }
                )
            elif item["type"] == "directory":
                _recursive_large_search(full_path)

    _recursive_large_search(path)
    return results


def find_windows_system_files(path: str) -> List[str]:
    """Поиск системных файлов Windows"""
    special_folders = navigation.get_windows_special_folders()
    win_dir = special_folders.get("Windows", "C:\\Windows")

    search_roots = [path]
    if os.path.exists(win_dir) and os.path.abspath(path) != os.path.abspath(
        win_dir
    ):
        search_roots.append(win_dir)

    results: List[str] = []
    for target in search_roots:
        results.extend(find_by_windows_extension([".exe", ".dll", ".sys"], target))
    return results


def format_windows_search_results(results: List[Any], search_type: str) -> None:
    """Форматированный вывод результатов поиска для Windows"""
    print(f"\n--- Результаты поиска ({search_type}) ---")
    if not results:
        print("Ничего не найдено.")
        return

    for idx, item in enumerate(results, 1):
        if isinstance(item, dict):
            formatted_size = utils.format_size(item.get("size_bytes", 0))
            print(
                f"{idx}. {item['path']} | "
                f"Размер: {formatted_size} ({item['size_mb']} MB) | Тип: {item['type']}"
            )
        else:
            parent_dir = utils.get_parent_path(item)
            attr_stats = analysis.get_windows_file_attributes_stats(parent_dir)
            print(
                f"{idx}. {item} "
                f"(скрытых/системных в папке: {attr_stats['hidden_or_system']})"
            )
    print(f"Всего найдено объектов: {len(results)}\n")


def search_menu_handler(current_path: str) -> bool:
    """Обработчик меню поиска для Windows"""
    print("\n=== ПОДСИСТЕМА ПОИСКА АРТЕФАКТОВ ===")
    print("1. Поиск по маске (шаблону имени, например: *report*?.txt)")
    print("2. Поиск по списку расширений (например: exe, dll)")
    print("3. Поиск крупных файлов (по минимальному размеру в MB)")
    print("4. Поиск критических системных бинарников (.exe, .dll, .sys)")
    print("0. Вернуться в главное меню")

    choice = input("Выберите режим поиска: ").strip()

    match choice:
        case "1":
            pattern = input("Введите маску для поиска: ").strip()
            case_flag = (
                input("Учитывать регистр? (y/n): ").strip().lower() == "y"
            )
            res = find_files_windows(
                pattern, current_path, case_sensitive=case_flag
            )
            format_windows_search_results(res, "По маске имени")
        case "2":
            raw_input = input("Введите расширения через запятую: ")
            exts = [e.strip() for e in raw_input.split(",") if e.strip()]
            res = find_by_windows_extension(exts, current_path)
            format_windows_search_results(res, "По расширениям")
        case "3":
            try:
                size = float(
                    input("Введите минимальный размер файла в MB: ").strip()
                )
                res = find_large_files_windows(size, current_path)
                format_windows_search_results(res, "Крупные файлы")
            except ValueError:
                print("Некорректный ввод размера.")
        case "4":
            res = find_windows_system_files(current_path)
            format_windows_search_results(res, "Системные файлы")
        case "0":
            return False
        case _:
            print("Неизвестный режим поиска.")

    return True