import fnmatch
import os
from typing import Any, Dict, List
import navigation
import utils


def find_files_windows(
    pattern: str, path: str, case_sensitive: bool = False
) -> List[str]:
    results = []
    search_pattern = pattern if case_sensitive else pattern.lower()

    def _recursive_search(current_path: str):
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
                if fnmatch.fnmatch(name_to_check, search_pattern):
                    results.append(full_path)
            elif item["type"] == "directory":
                _recursive_search(full_path)

    _recursive_search(path)
    return results


def find_by_windows_extension(extensions: List[str], path: str) -> List[str]:
    normalized_exts = [
        e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions
    ]
    results = []

    def _recursive_ext_search(current_path: str):
        success, items = navigation.list_directory(current_path)
        if not success:
            return
        for item in items:
            if item["hidden"] and item["type"] == "directory":
                continue
            full_path = os.path.join(current_path, item["name"])
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
    min_bytes = min_size_mb * 1024 * 1024
    results = []

    def _recursive_large_search(current_path: str):
        success, items = navigation.list_directory(current_path)
        if not success:
            return
        for item in items:
            if item["hidden"] and item["type"] == "directory":
                continue
            full_path = os.path.join(current_path, item["name"])
            if item["type"] == "file" and item["size"] >= min_bytes:
                _, ext = os.path.splitext(item["name"])
                results.append(
                    {
                        "path": full_path,
                        "size_mb": round(item["size"] / (1024 * 1024), 2),
                        "type": ext,
                    }
                )
            elif item["type"] == "directory":
                _recursive_large_search(full_path)

    _recursive_large_search(path)
    return results


def find_windows_system_files(path: str) -> List[str]:
    return find_by_windows_extension([".exe", ".dll", ".sys"], path)


def format_windows_search_results(results: List, search_type: str) -> None:
    print(f"\n--- Результаты поиска ({search_type}) ---")
    if not results:
        print("Ничего не найдено.")
        return

    for idx, item in enumerate(results, 1):
        if isinstance(item, dict):
            print(
                f"{idx}. {item['path']} | "
                f"Размер: {item['size_mb']} MB | Тип: {item['type']}"
            )
        else:
            print(f"{idx}. {item}")
    print(f"Всего найдено объектов: {len(results)}\n")


def search_menu_handler(current_path: str) -> bool:
    print("\n=== ПОДСИСТЕМА ПОИСКА АРТЕФАКТОВ ===")
    print("1. Поиск по маске (шаблону имени, например: *report*?.txt)")
    print("2. Поиск по списку расширений (например: exe, dll)")
    print("3. Поиск крупных файлов (по минимальному размеру в MB)")
    print("4. Поиск критических системных бинарников (.exe, .dll)")
    print("0. Вернуться в главное меню")

    choice = input("Выберите режим поиска: ").strip()

    match choice:
        case "1":
            pattern = input("Введите маску для поиска: ").strip()
            res = find_files_windows(pattern, current_path)
            format_windows_search_results(res, "По маске имени")
        case "2":
            raw_input = input("Введите расширения через запятую: ")
            exts = raw_input.replace(" ", "").split(",")
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
