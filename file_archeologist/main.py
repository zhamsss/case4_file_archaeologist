import os
import sys
from typing import NoReturn
import analysis  # Модуль аналитика
import navigation  # Модуль инженера навигации
import search  # Модуль эксперта поиска
import utils  # Собственный модуль


def check_windows_environment() -> bool:
    """Проверка что программа запущена в Windows"""
    if not utils.is_windows_os():
        print("[КРИТИЧЕСКАЯ ОШИБКА]: Проект 'Файловый археолог' спроектирован")
        print("исключительно под архитектуру файловой системы ОС Windows!")
        print("Выполнение на текущей ОС прервано.")
        sys.exit(1)
    return True


def display_windows_banner() -> None:
    """Отображение баннера с информацией о Windows"""
    print("=" * 60)
    print("   АРХЕОЛОГИЧЕСКИЙ ТЕРМИНАЛЬНЫЙ НАВИГАТОР 'WINDOWS-2142'")
    print("=" * 60)
    print(f"Текущий активный накопитель: {navigation.get_current_drive()}")
    print("Специальные сектора ОС обнаружены.")
    print("-" * 60)


def display_main_menu(current_path: str) -> None:
    """Отображение главного меню для Windows"""
    print(f"\n[ТЕКУЩИЙ СЕКТОР]: {current_path}")
    drives = navigation.list_available_drives()
    print("Доступные накопители в системе:", drives)
    print("\nКоманды управления:")
    print("  1. Вывести содержимое каталога (ls)")
    print("  2. Запустить полный анализ каталога (stat)")
    print("  3. Открыть меню поиска файлов (find)")
    print("  4. Показать статистику атрибутов и объема")
    print("  5. Перейти в подкаталог или сменить диск (cd <имя> или <Диск:>)")
    print("  6. Подняться в родительский каталог (cd ..)")
    print("  7. Перейти в Специальную Windows-папку (special)")
    print("  0. Выход из программы (exit)")


def handle_windows_navigation(command: str, current_path: str) -> str:
    """Обработка команд навигации в Windows"""
    parts = command.strip().split(maxsplit=1)
    cmd_type = parts[0].lower() if parts else ""

    if cmd_type in ("1", "ls"):
        success, items = navigation.list_directory(current_path)
        if success:
            navigation.format_directory_output(items)
        else:
            print("Не удалось прочитать содержимое сектора.")
        return current_path

    if cmd_type in ("6", ".."):
        return navigation.move_up(current_path)

    if cmd_type in ("5", "cd"):
        if len(parts) < 2:
            print("Укажите имя папки или букву диска (например: C:).")
            return current_path

        target = parts[1].strip()
        if target == "..":
            return navigation.move_up(current_path)

        # Проверка смены диска через список доступных дисков
        if len(target) == 2 and target.endswith(":"):
            drives = [d.upper() for d in navigation.list_available_drives()]
            if target.upper() not in drives:
                print(f"Ошибка: Диск '{target}' недоступен. Доступны: {drives}")
                return current_path

        success, new_path = navigation.move_down(current_path, target)
        if not success:
            print(f"Ошибка: Не удается перейти в '{target}'")
        return new_path

    if cmd_type in ("7", "special"):
        folders = navigation.get_windows_special_folders()
        print("\nДоступные системные хранилища:")
        for idx, (k, v) in enumerate(folders.items(), 1):
            print(f"  {idx}. {k} -> {v}")
        f_choice = input(
            "Выберите номер папки для быстрого перехода (или 0): "
        ).strip()
        folder_keys = list(folders.keys())
        try:
            idx_int = int(f_choice) - 1
            if 0 <= idx_int < len(folder_keys):
                target_dir = folders[folder_keys[idx_int]]
                if os.path.exists(target_dir):
                    return target_dir
                print("Данный сектор поврежден или отсутствует.")
        except ValueError:
            print("Некорректный выбор.")

    return current_path


def handle_windows_analysis(command: str, current_path: str) -> None:
    """Обработка команд анализа Windows файловой системы"""
    cmd_type = command.strip().split(maxsplit=1)[0].lower()

    if cmd_type in ("2", "stat", "анализ"):
        analysis.show_windows_directory_stats(current_path)
    elif cmd_type == "4":
        ok_f, files_cnt = analysis.count_files(current_path)
        ok_b, bytes_cnt = analysis.count_bytes(current_path)
        attrs = analysis.get_windows_file_attributes_stats(current_path)
        if ok_f and ok_b:
            print(f"\nФайлов: {files_cnt}, Общий размер: {utils.format_size(bytes_cnt)}")
            print(
                f"Обычных: {attrs['normal']}, Скрытых/системных: {attrs['hidden_or_system']}"
            )
        else:
            print("Ошибка сбора быстрой статистики.")


def handle_windows_search(command: str, current_path: str) -> None:
    """Обработка команд поиска в Windows"""
    searching = True
    while searching:
        searching = search.search_menu_handler(current_path)


def run_windows_command(command: str, current_path: str) -> str:
    """Главный обработчик команд с использованием match case"""
    parts = command.strip().split(maxsplit=1)
    cmd_type = parts[0].lower() if parts else ""

    match cmd_type:
        case "1" | "ls" | "5" | "cd" | "6" | ".." | "7" | "special":
            return handle_windows_navigation(command, current_path)

        case "2" | "stat" | "анализ" | "4":
            handle_windows_analysis(command, current_path)

        case "3" | "find" | "поиск":
            handle_windows_search(command, current_path)

        case "0" | "exit" | "quit":
            print("Завершение сессии цифровой археологии. До связи в 2142 году!")
            sys.exit(0)

        case _:
            print("Команда не распознана системным интерпретатором.")

    return current_path


def main() -> NoReturn:
    """Главная функция программы для Windows"""
    check_windows_environment()
    display_windows_banner()

    current_path = os.path.abspath(os.getcwd())

    while True:
        try:
            display_main_menu(current_path)
            user_input = input("\nВвод археолога > ").strip()
            if not user_input:
                continue
            current_path = run_windows_command(user_input, current_path)
        except KeyboardInterrupt:
            print("\nЭкстренное завершение работы системы.")
            sys.exit(0)
        except Exception as e:
            print(f"\n[Критический сбой архитектуры]: {e}")


if __name__ == "__main__":
    main()
