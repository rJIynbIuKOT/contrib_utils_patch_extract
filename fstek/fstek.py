#!/usr/bin/env python3
import json
import os
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOCAL = 'config.json'
OUTPUT_FILE = 'config.txt'


def load_config(source):
    """source: пустая строка → ./config.json, иначе путь к локальному файлу."""
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
            "Путь до config.json (Enter — использовать ./config.json): "
        )
    except EOFError:
        return ''


def main():
    data = load_config(resolve_source())

    output_lines = []
    for component_name, component_data in data.items():
        general_data = component_data.get('general', {})
        version = general_data.get('version', '')
        git_data = general_data.get('git', {})
        url = git_data.get('url', '')
        commit_sha = git_data.get('commit_sha', '')

        line = f"{component_name} {version} {url} {commit_sha}".strip()
        output_lines.append(line)

    output_lines.sort()

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print(f"Файл {OUTPUT_FILE} успешно создан. Записано {len(output_lines)} компонентов.")
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
