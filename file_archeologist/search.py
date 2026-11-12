import ctypes
import fnmatch
import hashlib
import math
import os
import re
import stat
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
import navigation
import utils


# Глобальные кэши для повторных поисков
GLOBAL_CONTENT_CACHE: Dict[str, str] = {}
GLOBAL_SMART_CACHE: Dict[str, List[Tuple[str, float]]] = {}

# Базовый словарь синонимов для интеллектуального поиска
SYNONYMS_DICT = {
    "ошибка": {"error", "exception", "сбой", "fail", "failure", "баг", "bug"},
    "пароль": {"password", "pass", "pwd", "секрет", "secret", "ключ", "key"},
    "пользователь": {"user", "admin", "админ", "аккаунт", "account", "login"},
    "сеть": {"network", "ip", "хост", "host", "подключение", "connection"},
    "файл": {"file", "документ", "document", "лог", "log"},
}


# =====================================================================
# БАЗОВЫЕ ФУНКЦИИ ПОИСКА (ИСХОДНЫЙ ФУНКЦИОНАЛ)
# =====================================================================


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


# =====================================================================
# ЗАДАНИЕ 1: РЕКУРСИВНЫЙ ПОИСК ПО СОДЕРЖИМОМУ ФАЙЛОВ
# =====================================================================


def _detect_encoding_and_read_lines(file_path: str):
    """Генератор построчного чтения с поддержкой UTF-8 и cp1251."""
    encodings = ["utf-8", "cp1251", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                for line_num, line in enumerate(f, 1):
                    yield line_num, line
            return
        except UnicodeDecodeError:
            continue
        except (OSError, PermissionError):
            return


def recursive_content_search(
    root_path: str,
    search_pattern: str,
    file_extensions: Optional[List[str]] = None,
    content_cache: Optional[Dict[str, str]] = None,
) -> List[Tuple[str, List[int]]]:
    """Рекурсивный поиск текста в содержимом файлов с кэшированием."""
    if content_cache is None:
        content_cache = GLOBAL_CONTENT_CACHE

    normalized_exts = None
    if file_extensions:
        normalized_exts = {
            e.lower() if e.startswith(".") else f".{e.lower()}"
            for e in file_extensions
            if e.strip()
        }

    try:
        regex = re.compile(search_pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(search_pattern), re.IGNORECASE)

    results: List[Tuple[str, List[int]]] = []
    max_cache_bytes = 5 * 1024 * 1024  # Кэшируем файлы до 5 МБ

    def _search_dir(current_path: str):
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
                _search_dir(full_path)
            elif item["type"] == "file":
                if normalized_exts:
                    _, ext = os.path.splitext(item["name"].lower())
                    if ext not in normalized_exts:
                        continue

                matched_lines: List[int] = []

                if full_path in content_cache:
                    lines = content_cache[full_path].splitlines()
                    for idx, line in enumerate(lines, 1):
                        if regex.search(line):
                            matched_lines.append(idx)
                else:
                    cached_chunks = []
                    can_cache = item.get("size", 0) <= max_cache_bytes

                    for line_num, line in _detect_encoding_and_read_lines(
                        full_path
                    ):
                        if can_cache:
                            cached_chunks.append(line)
                        if regex.search(line):
                            matched_lines.append(line_num)

                    if can_cache and cached_chunks:
                        content_cache[full_path] = "".join(cached_chunks)

                if matched_lines:
                    results.append((full_path, matched_lines))

    _search_dir(root_path)
    return results


# =====================================================================
# ЗАДАНИЕ 2: РЕКУРСИВНЫЙ ИНТЕЛЛЕКТУАЛЬНЫЙ ПОИСК
# =====================================================================


def _simple_stem_and_tokenize(text: str) -> List[str]:
    """Токенизация и простая морфологическая нормализация (RU/EN)."""
    words = re.findall(r"[a-zа-яё0-9]{2,}", text.lower())
    stemmed = []
    for w in words:
        if len(w) > 4:
            w = re.sub(
                r"(ами|ями|ого|его|ому|ему|ыми|ими|ать|ять|ить|еть|ing|ed|es|s)$",
                "",
                w,
            )
        stemmed.append(w)
    return stemmed


def _expand_query_with_synonyms(tokens: List[str]) -> List[str]:
    """Расширение списка токенов синонимами."""
    expanded = set(tokens)
    for token in tokens:
        for key, syn_set in SYNONYMS_DICT.items():
            if token in key or any(token in s for s in syn_set):
                expanded.update(_simple_stem_and_tokenize(key))
                for s in syn_set:
                    expanded.update(_simple_stem_and_tokenize(s))
    return list(expanded)


def smart_recursive_search(
    root_path: str,
    query: str,
    search_context: Optional[Dict[str, Any]] = None,
    relevance_threshold: float = 0.5,
) -> List[Tuple[str, float]]:
    """Рекурсивный поиск с учетом TF-IDF, синонимов и контекста."""
    if search_context is None:
        search_context = {}

    cache_key = f"{root_path}::{query}::{relevance_threshold}::{str(search_context)}"
    if cache_key in GLOBAL_SMART_CACHE:
        return GLOBAL_SMART_CACHE[cache_key]

    documents: Dict[str, List[str]] = {}
    allowed_exts = {".txt", ".log", ".md", ".py", ".json", ".xml", ".csv", ".ini"}

    def _build_index(current_path: str):
        success, items = navigation.list_directory(current_path)
        if not success:
            return
        for item in items:
            if item["hidden"] and item["type"] == "directory":
                continue
            full_path = os.path.join(current_path, item["name"])
            if item["type"] == "directory":
                _build_index(full_path)
            elif item["type"] == "file":
                _, ext = os.path.splitext(item["name"].lower())
                if ext in allowed_exts and item.get("size", 0) <= 2 * 1024 * 1024:
                    text_lines = [
                        line
                        for _, line in _detect_encoding_and_read_lines(full_path)
                    ]
                    if text_lines:
                        full_text = f"{item['name']} " + "".join(text_lines)
                        documents[full_path] = _simple_stem_and_tokenize(
                            full_text
                        )

    _build_index(root_path)
    if not documents:
        return []

    query_tokens = _simple_stem_and_tokenize(query)
    if "history" in search_context and isinstance(
        search_context["history"], list
    ):
        for past_query in search_context["history"][-2:]:
            query_tokens.extend(_simple_stem_and_tokenize(str(past_query)))

    expanded_query = _expand_query_with_synonyms(query_tokens)
    if not expanded_query:
        return []

    total_docs = len(documents)
    doc_freq: Counter = Counter()
    for tokens in documents.values():
        doc_freq.update(set(tokens))

    scored_results: List[Tuple[str, float]] = []
    preferred_ext = search_context.get("preferred_ext", "").lower()

    for path, doc_tokens in documents.items():
        if not doc_tokens:
            continue
        tf_counter = Counter(doc_tokens)
        doc_len = len(doc_tokens)
        score = 0.0

        for q_term in expanded_query:
            if q_term in tf_counter:
                tf = tf_counter[q_term] / doc_len
                idf = math.log((total_docs + 1) / (doc_freq[q_term] + 1)) + 1.0
                score += tf * idf

        normalized_score = min(1.0, score * 5.0)

        if preferred_ext and path.lower().endswith(preferred_ext):
            normalized_score = min(1.0, normalized_score + 0.15)

        if normalized_score >= relevance_threshold:
            scored_results.append((path, round(normalized_score, 3)))

    scored_results.sort(key=lambda x: x[1], reverse=True)
    GLOBAL_SMART_CACHE[cache_key] = scored_results
    return scored_results


# =====================================================================
# ЗАДАНИЕ 3: РЕКУРСИВНЫЙ ПОИСК АНОМАЛИЙ БЕЗОПАСНОСТИ
# =====================================================================


def _calculate_sha256(file_path: str) -> str:
    """Вычисление SHA-256 хеша файла."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError):
        return "ERROR_READING_HASH"


def _check_windows_security_center() -> str:
    """Проверка статуса службы Windows Security Center (wscsvc)."""
    if os.name != "nt":
        return "Недоступно (ОС не Windows)"
    try:
        advapi32 = ctypes.windll.advapi32
        sc_manager = advapi32.OpenSCManagerW(None, None, 0x0001)
        if sc_manager:
            service = advapi32.OpenServiceW(sc_manager, "wscsvc", 0x0004)
            if service:
                advapi32.CloseServiceHandle(service)
                advapi32.CloseServiceHandle(sc_manager)
                return "Активен (wscsvc доступен)"
            advapi32.CloseServiceHandle(sc_manager)
        return "Служба wscsvc недоступна"
    except Exception:
        return "Ошибка обращения к Security Center API"


def recursive_security_scan(
    root_path: str,
    security_rules: Dict[str, Any],
    scan_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[Dict]]:
    """Рекурсивное сканирование ФС на предмет угроз безопасности Windows."""
    if scan_context is None:
        scan_context = {}

    report: Dict[str, List[Dict]] = {
        "HIGH": [],
        "MEDIUM": [],
        "LOW": [],
        "INFO": [],
    }

    suspicious_dirs = security_rules.get(
        "suspicious_dirs", ["temp", "tmp", "downloads", "appdata", "public"]
    )
    exec_exts = security_rules.get(
        "exec_extensions", [".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".scr"]
    )
    known_bad_hashes = set(security_rules.get("bad_hashes", []))
    trusted_paths = set(security_rules.get("trusted_paths", []))

    wsc_status = _check_windows_security_center()
    report["INFO"].append(
        {
            "category": "System API",
            "path": "Windows Security Center",
            "details": f"Статус центра безопасности: {wsc_status}",
        }
    )

    trust_map: Dict[str, str] = {}

    def _scan_dir(current_path: str):
        success, items = navigation.list_directory(current_path)
        if not success:
            return

        norm_current = current_path.lower()
        is_trusted_dir = any(
            norm_current.startswith(tp.lower()) for tp in trusted_paths
        )
        is_suspicious_dir = any(s in norm_current for s in suspicious_dirs)
        trust_map[current_path] = (
            "TRUSTED"
            if is_trusted_dir
            else ("UNTRUSTED" if is_suspicious_dir else "NEUTRAL")
        )

        for item in items:
            full_path = os.path.join(current_path, item["name"])
            if os.path.islink(full_path):
                continue

            if item.get("hidden", False):
                report["LOW"].append(
                    {
                        "category": "Скрытый объект",
                        "path": full_path,
                        "details": f"Обнаружен скрытый {item['type']}",
                    }
                )

            if item["type"] == "directory":
                _scan_dir(full_path)
            elif item["type"] == "file":
                _, ext = os.path.splitext(item["name"].lower())

                if ext in exec_exts:
                    file_hash = _calculate_sha256(full_path)
                    if file_hash in known_bad_hashes:
                        report["HIGH"].append(
                            {
                                "category": "Вредоносный хеш",
                                "path": full_path,
                                "details": f"Совпадение по базе SHA-256: {file_hash}",
                            }
                        )
                    elif is_suspicious_dir and not is_trusted_dir:
                        report["HIGH"].append(
                            {
                                "category": "Исполняемый файл в нетипичной директории",
                                "path": full_path,
                                "details": f"Расширение {ext} в зоне {trust_map[current_path]}. SHA-256: {file_hash[:16]}...",
                            }
                        )

                try:
                    file_stat = os.stat(full_path)
                    mode = file_stat.st_mode
                    if (mode & stat.S_IWOTH) and ext in exec_exts:
                        report["MEDIUM"].append(
                            {
                                "category": "Избыточные права доступа",
                                "path": full_path,
                                "details": "Исполняемый файл доступен для записи всем пользователям",
                            }
                        )
                except OSError:
                    pass

    _scan_dir(root_path)
    scan_context["trust_map"] = trust_map
    return report


# =====================================================================
# ФОРМАТИРОВАНИЕ И ИНТЕРФЕЙС МЕНЮ
# =====================================================================


def format_windows_search_results(results: Any, search_type: str) -> None:
    print(f"\n--- Результаты поиска ({search_type}) ---")
    if not results:
        print("Ничего не найдено.")
        return

    if isinstance(results, dict):
        total_issues = 0
        for level in ["HIGH", "MEDIUM", "LOW", "INFO"]:
            items = results.get(level, [])
            if items:
                print(f"\n[Уровень: {level}] ({len(items)})")
                for idx, entry in enumerate(items, 1):
                    print(
                        f"  {idx}. [{entry['category']}] {entry['path']} -> {entry['details']}"
                    )
                    if level != "INFO":
                        total_issues += 1
        print(f"\nВсего выявлено потенциальных аномалий: {total_issues}\n")
        return

    for idx, item in enumerate(results, 1):
        if isinstance(item, dict):
            print(
                f"{idx}. {item['path']} | "
                f"Размер: {item['size_mb']} MB | Тип: {item['type']}"
            )
        elif isinstance(item, tuple):
            path, meta = item
            if isinstance(meta, list):
                lines_str = ", ".join(map(str, meta[:10]))
                if len(meta) > 10:
                    lines_str += f" ... (всего {len(meta)})"
                print(f"{idx}. {path} | Строки: [{lines_str}]")
            else:
                print(f"{idx}. {path} | Релевантность: {meta:.3f}")
        else:
            print(f"{idx}. {item}")
    print(f"Всего найдено объектов: {len(results)}\n")


def search_menu_handler(current_path: str) -> bool:
    print("\n=== ПОДСИСТЕМА ПОИСКА АРТЕФАКТОВ ===")
    print("1. Поиск по маске (шаблону имени, например: *report*?.txt)")
    print("2. Поиск по списку расширений (например: exe, dll)")
    print("3. Поиск крупных файлов (по минимальному размеру в MB)")
    print("4. Поиск критических системных бинарников (.exe, .dll)")
    print("5. Рекурсивный поиск по содержимому файлов (текст / regex)")
    print("6. Интеллектуальный семантический поиск (TF-IDF + синонимы)")
    print("7. Сканирование аномалий безопасности Windows")
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
        case "5":
            pattern = input("Введите текст или regex для поиска: ").strip()
            raw_exts = input(
                "Фильтр расширений через запятую (Enter — все файлы): "
            ).strip()
            exts = raw_exts.replace(" ", "").split(",") if raw_exts else None
            res = recursive_content_search(current_path, pattern, exts)
            format_windows_search_results(res, "Поиск по содержимому")
        case "6":
            query = input("Введите поисковый запрос: ").strip()
            try:
                thresh_input = input(
                    "Порог релевантности 0.0–1.0 (Enter = 0.2): "
                ).strip()
                threshold = float(thresh_input) if thresh_input else 0.2
            except ValueError:
                threshold = 0.2
            res = smart_recursive_search(
                current_path, query, relevance_threshold=threshold
            )
            format_windows_search_results(res, "Интеллектуальный поиск")
        case "7":
            default_rules = {
                "suspicious_dirs": ["temp", "downloads", "appdata", "public"],
                "exec_extensions": [".exe", ".dll", ".bat", ".ps1", ".vbs"],
                "bad_hashes": [],
                "trusted_paths": [r"C:\Windows", r"C:\Program Files"],
            }
            res = recursive_security_scan(current_path, default_rules)
            format_windows_search_results(res, "Аудит безопасности")
        case "0":
            return False
        case _:
            print("Неизвестный режим поиска.")

    return True