#!/usr/bin/env python3
import json
import os
import re
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOCAL = 'contrib.json'


def extract_version(url):
    if not url or url == "....":
        return None

    patterns = [
        r'/releases/tag/v?(\d+\.\d+\.\d+)',
        r'/releases/tag/v?(\d+\.\d+)',
        r'/tag/v?(\d+\.\d+\.\d+)',
        r'/tag/v?(\d+\.\d+)',
        r'/tree/v?(\d+\.\d+\.\d+)',
        r'/tree/ver_(\d+\.\d+\.\d+)',
        r'/tree/v(\d+\.\d+\.\d+)',
        r'/tag/VERSION_(\d+_\d+_\d+)',
        r'/tag/REL(\d+_\d+_\d+)',
        r'/tag/wal2json_(\d+_\d+)',
        r'/tag/refs/tags/v(\d+\.\d+\.\d+)',
        r'/tree/(\d+\.\d+\.\d+)',
        r'/tree/ver_(\d+\.\d+\.\d+)',
        r'/(\d+\.\d+\.\d+)/',
        r'/(\d+\.\d+)/'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1).replace('_', '.')

    return None


def load_contrib(source):
    """source: пустая строка → ./contrib.json, иначе путь к локальному файлу."""
    source = (source or '').strip().strip('"').strip("'")
    path = source or DEFAULT_LOCAL
    print(f"Источник: локальный файл {os.path.abspath(path)}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_source():
    """Берём источник из argv[1], иначе спрашиваем интерактивно."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        return input(
            "Путь до contrib.json (Enter — использовать ./contrib.json): "
        )
    except EOFError:
        return ''


def main():
    data = load_contrib(resolve_source())

    editions = ['be', 'se', 'se-1c', 'certified', 'certified-2', 'free']
    edition_components = {edition: [] for edition in editions}
    all_components = {}  # Для хранения всех уникальных компонентов (name -> entry)

    for component in data['contrib']:
        name = component['name']
        version_url = component['current_version']
        version = extract_version(version_url)

        if version:
            entry = f"{name} {version} {version_url}"
        else:
            entry = f"{name} {version_url}"

        all_components[name] = entry

        for edition in component['editions']:
            if edition in edition_components:
                edition_components[edition].append(entry)

    for edition, components in edition_components.items():
        filename = f"{edition}.txt"
        with open(filename, 'w', encoding='utf-8') as file:
            for entry in sorted(components):
                file.write(f"{entry}\n")
        print(f"Создан файл: {filename} с {len(components)} компонентами")

    with open('all.txt', 'w', encoding='utf-8') as file:
        for entry in sorted(all_components.values()):
            file.write(f"{entry}\n")
    print(f"Создан файл: all.txt с {len(all_components)} уникальными компонентами")

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
