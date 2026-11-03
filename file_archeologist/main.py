import os
import sys
from typing import NoReturn
import analysis
import navigation
import search
import utils


def check_windows_environment() -> bool:
    if not utils.is_windows_os():
        print("[КРИТИЧЕСКАЯ ОШИБКА]: Проект 'Файловый археолог' спроектирован")
        print("исключительно под архитектуру файловой системы ОС Windows!")
        print("Выполнение на текущей ОС прервано.")
        sys.exit(1)
    return True


def display_windows_banner() -> None:
    print("=" * 60)
    print("   АРХЕОЛОГИЧЕСКИЙ ТЕРМИНАЛЬНЫЙ НАВИГАТОР 'WINDOWS-2142'")
    print("=" * 60)
    print(f"Текущий активный накопитель: {navigation.get_current_drive()}")
    print("Специальные сектора ОС обнаружены.")
    print("-" * 60)


def display_main_menu(current_path: str) -> None:
    print(f"\n[ТЕКУЩИЙ СЕКТОР]: {current_path}")
    drives = navigation.list_available_drives()
    print("Доступные накопители в системе:", drives)
    print("\nКоманды управления:")
    print("  1. Вывести содержимое каталога (ls)")
    print("  2. Сменить директорию (cd <имя_папки> или <Диск:>)")
    print("  3. Подняться выше (cd ..)")
    print("  4. Запустить рекурсивный анализ данных (статистика)")
    print("  5. Открыть меню глубокого поиска артефактов (найти)")
    print("  6. Перейти в Специальную Windows-папку")
    print("  0. Выход из программы")


def run_windows_command(command: str, current_path: str) -> str:
    parts = command.strip().split(maxsplit=1)
    cmd_type = parts[0].lower() if parts else ""

    match cmd_type:
        case "1" | "ls":
            success, items = navigation.list_directory(current_path)
            if success:
                navigation.format_directory_output(items)
            else:
                print("Не удалось прочитать содержимое сектора.")

        case "2" | "cd":
            if len(parts) < 2:
                print("Укажите имя папки или диска для перехода.")
                return current_path
            target = parts[1]
            if target == "..":
                return navigation.move_up(current_path)
            success, new_path = navigation.move_down(current_path, target)
            if not success:
                print(f"Ошибка: Не удается перейти в '{target}'")
            return new_path

        case "3" | "..":
            return navigation.move_up(current_path)

        case "4" | "stat" | "анализ":
            analysis.show_windows_directory_stats(current_path)

        case "5" | "find" | "поиск":
            searching = True
            while searching:
                searching = search.search_menu_handler(current_path)

        case "6" | "special":
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
                    else:
                        print("Данный сектор поврежден или отсутствует.")
            except ValueError:
                print("Некорректный выбор.")

        case "0" | "exit" | "quit":
            print("Завершение сессии цифровой археологии. До связи в 2142 году!")
            sys.exit(0)

        case _:
            print("Команда не распознана системным интерпретатором.")

    return current_path


def main() -> NoReturn:
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
