#!/usr/bin/env python3
import shutil
import subprocess
import sys
import traceback
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
EXPORT_SCRIPT = SCRIPT_DIR / "patches_and_gucs_csv.py"
SUMM_SCRIPT = SCRIPT_DIR / "summ_patches_and_gucs_csv_all_versions.py"
TEMP_OUTPUT = SCRIPT_DIR / "patches_and_gucs.csv"

TARGETS = [
    ("18", Path("/home/kot/repo/tantor-db-18_3/")),
    ("17", Path("/home/kot/repo/tantor-db-17_10/")),
    ("16", Path("/home/kot/repo/tantor-db-16_14/")),
    ("15", Path("/home/kot/repo/tantor-db-15_18/")),
    ("14", Path("/home/kot/repo/tantor-db-14_23/")),
]


def run_one(version: str, repo_path: Path) -> None:
    if not repo_path.is_dir():
        raise NotADirectoryError(f"Репозиторий не найден: {repo_path}")

    print(f"\n=== Версия {version}: {repo_path} ===")
    cmd = [
        sys.executable,
        str(EXPORT_SCRIPT),
        str(repo_path),
        "--exclude-empty",
    ]
    subprocess.run(
        cmd,
        cwd=str(SCRIPT_DIR),
        check=True,
        stdin=subprocess.DEVNULL,
    )

    if not TEMP_OUTPUT.exists():
        raise FileNotFoundError(f"После запуска не найден файл: {TEMP_OUTPUT}")

    target = SCRIPT_DIR / f"patches_and_gucs_{version}.csv"
    shutil.copyfile(TEMP_OUTPUT, target)
    print(f"Сохранено: {target}")


def main() -> None:
    if not EXPORT_SCRIPT.exists():
        raise FileNotFoundError(f"Не найден скрипт: {EXPORT_SCRIPT}")

    print("Старт пакетной генерации patches_and_gucs_<version>.csv")
    for version, repo in TARGETS:
        run_one(version, repo)

    if not SUMM_SCRIPT.is_file():
        raise FileNotFoundError(f"Не найден скрипт агрегации: {SUMM_SCRIPT}")

    print("\n=== Агрегация в summ_patches_and_gucs_all_versions.csv ===")
    subprocess.run(
        [sys.executable, str(SUMM_SCRIPT)],
        cwd=str(SCRIPT_DIR),
        check=True,
        stdin=subprocess.DEVNULL,
    )
    print("\nГотово. Все версии обработаны и сводка собрана.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\nОшибка при выполнении:", file=sys.stderr)
        traceback.print_exc()

    try:
        input("Нажмите Enter для закрытия терминала...")
    except EOFError:
        pass
