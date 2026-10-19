#!/usr/bin/env python3
import json
import os
import re
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOCAL = 'config.json'
OUTPUT_FILE = 'ext.txt'
TANTOR_DB_ROOT = '/home/kot/repo/tantor-db-18_6/'
DOC_DIRS = [
    os.path.join(TANTOR_DB_ROOT, 'tantor', 'doc', 'contrib_ext'),
    os.path.join(TANTOR_DB_ROOT, 'tantor', 'doc', 'programs'),
]

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

DOC_VERSION_RE = re.compile(
    r'<emphasis\s+role="strong">\s*Version\s*:?\s*</emphasis>\s*:?\s*'
    r'([0-9]+(?:\.[0-9]+)*)',
    re.IGNORECASE,
)


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


def extract_doc_version(sgml_path):
    """Достаёт версию из строки Version в начале sgml-файла."""
    try:
        with open(sgml_path, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(4096)
    except OSError:
        return ''

    match = DOC_VERSION_RE.search(head)
    return match.group(1) if match else ''


def collect_sgml_versions(doc_dirs):
    """Читает *.sgml в каталогах документации и возвращает {имя: версия}."""
    versions = {}
    for doc_dir in doc_dirs:
        if not os.path.isdir(doc_dir):
            print(f"Каталог документации не найден: {doc_dir}")
            continue

        print(f"Каталог документации: {os.path.abspath(doc_dir)}")
        found = 0
        for fname in sorted(os.listdir(doc_dir)):
            if not fname.endswith('.sgml'):
                continue
            path = os.path.join(doc_dir, fname)
            if not os.path.isfile(path):
                continue
            name = fname[:-5]
            versions[name] = extract_doc_version(path)
            found += 1
        print(f"Найдено sgml-файлов: {found}")
    return versions


def format_aligned_rows(rows):
    """Выравнивает колонки по ширине и склеивает табами."""
    if not rows:
        return []

    col_count = max(len(row) for row in rows)
    col_widths = [0] * col_count
    for row in rows:
        for i, value in enumerate(row):
            col_widths[i] = max(col_widths[i], len(value))

    lines = []
    for row in rows:
        parts = []
        for i, value in enumerate(row):
            if i == len(row) - 1:
                parts.append(value)
            else:
                parts.append(value.ljust(col_widths[i]))
        lines.append('\t'.join(parts))
    return lines


def collect_json_rows(data):
    rows = []
    versions = {}
    for entity in ENTITIES:
        if entity not in data:
            continue
        general = data[entity].get('general', {})
        version = general.get('version', '')
        git_info = general.get('git', {})
        git_url = git_info.get('url', '')
        git_tag = git_info.get('tag', '')
        rows.append([entity, version, git_url, git_tag])
        versions[entity] = version
    return rows, versions


def collect_mismatches(json_versions, sgml_versions):
    names = []
    seen = set()
    for name in ENTITIES:
        if name in json_versions and name in sgml_versions:
            names.append(name)
            seen.add(name)
    for name in sgml_versions:
        if name not in seen and name in json_versions:
            names.append(name)

    lines = []
    for name in names:
        json_ver = json_versions.get(name) or ''
        sgml_ver = sgml_versions.get(name) or ''
        if json_ver and sgml_ver and json_ver != sgml_ver:
            lines.append(f"{name} json={json_ver} sgml={sgml_ver}")
    return lines


def main():
    data = load_config(resolve_source())
    json_rows, json_versions = collect_json_rows(data)
    sgml_versions = collect_sgml_versions(DOC_DIRS)
    sgml_rows = [[name, version] for name, version in sgml_versions.items()]
    mismatches = collect_mismatches(json_versions, sgml_versions)

    sections = [
        'config.json:',
        *format_aligned_rows(json_rows),
        '',
        'tantor doc:',
        *format_aligned_rows(sgml_rows),
        '',
        'Версии отличаются в:',
        *mismatches,
    ]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sections))
        if sections:
            f.write('\n')

    print(f"Информация успешно сохранена в {OUTPUT_FILE}")
    print(f"Обработано сущностей config.json: {len(json_rows)}")
    print(f"Обработано sgml: {len(sgml_rows)}")
    print(f"Несовпадений версий: {len(mismatches)}")
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
