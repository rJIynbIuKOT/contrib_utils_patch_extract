#!/usr/bin/env python3
import json
import os
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOCAL = 'config.json'
OUTPUT_FILE = 'ext.txt'

ENTITIES = [
    "pipelinedb",
    "pg_anon",
    "pg_configurator",
    "ldap2pg",
    "mysql_fdw",
    "oracle_fdw",
    "pg_timetable",
    "pgbouncer",
    "tds_fdw",
    "wal-g",
]


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

    rows = []
    for entity in ENTITIES:
        if entity in data:
            general = data[entity].get('general', {})
            version = general.get('version', '')
            git_info = general.get('git', {})
            git_url = git_info.get('url', '')
            git_tag = git_info.get('tag', '')

            rows.append([entity, version, git_url, git_tag])

    col_widths = [0, 0, 0, 0]
    for row in rows:
        for i, value in enumerate(row):
            col_widths[i] = max(col_widths[i], len(value))

    results = []
    for row in rows:
        line = (
            f"{row[0].ljust(col_widths[0])}\t"
            f"{row[1].ljust(col_widths[1])}\t"
            f"{row[2].ljust(col_widths[2])}\t"
            f"{row[3]}"
        )
        results.append(line)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))

    print(f"Информация успешно сохранена в {OUTPUT_FILE}")
    print(f"Обработано сущностей: {len(results)}")
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
