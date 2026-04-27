#!/usr/bin/env python3
import csv
import json
import os
import sys
import traceback
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOCAL = 'conf.json'
OUTPUT_FILE = 'pathes.csv'

EDITION_ORDER = ["be", "se", "se1c", "certified", "certified_2", "free"]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Root JSON object must be a dictionary.")
    return data


def collect_patch_names(edition_sets: dict) -> list:
    all_from_editions = set()
    for values in edition_sets.values():
        all_from_editions.update(values)
    return sorted(all_from_editions)


def build_edition_sets(editions_obj) -> dict:
    if not isinstance(editions_obj, dict):
        raise ValueError('Key "editions" must contain a dictionary.')

    result = {}
    for edition in EDITION_ORDER:
        edition_obj = editions_obj.get(edition)
        if not isinstance(edition_obj, dict):
            raise ValueError(f'Edition "{edition}" must be an object.')
        values = edition_obj.get("patches")
        if not isinstance(values, list):
            raise ValueError(f'Edition "{edition}" must contain a list in key "patches".')
        result[edition] = {str(item) for item in values}
    return result


def write_csv(output_path: Path, patch_names: list, edition_sets: dict) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["patch", *EDITION_ORDER])
        for patch in patch_names:
            row = [patch]
            for edition in EDITION_ORDER:
                row.append("y" if patch in edition_sets[edition] else "")
            writer.writerow(row)


def load_conf(source: str):
    """source: пустая строка → ./conf.json, иначе путь к локальному JSON-файлу."""
    source = (source or '').strip().strip('"').strip("'")
    path = Path(source).expanduser() if source else Path(DEFAULT_LOCAL)
    print(f"Источник: локальный файл {path.resolve()}")
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path.resolve()}")
    return load_json(path)


def resolve_source():
    """Берём источник из argv[1], иначе спрашиваем интерактивно."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        return input(
            f"Путь до conf.json (Enter — использовать ./{DEFAULT_LOCAL}): "
        )
    except EOFError:
        return ''


def main() -> None:
    data = load_conf(resolve_source())
    edition_sets = build_edition_sets(data.get("editions"))
    patch_names = collect_patch_names(edition_sets)

    output_path = Path(OUTPUT_FILE).resolve()
    write_csv(output_path, patch_names, edition_sets)
    print(f"Создан CSV: {output_path}")
    print(f"  Уникальных патчей: {len(patch_names)}")
    print(f"  Колонок-изданий: {len(EDITION_ORDER)} ({', '.join(EDITION_ORDER)})")
    print("Обработка завершена.")


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
