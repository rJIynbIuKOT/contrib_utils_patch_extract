#!/usr/bin/env python3
import json
import os
import re
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOCAL = 'contrib.json'

DOC_VERSION_RE = re.compile(
    r'<emphasis\s+role="strong">\s*Version\s*</emphasis>\s*:\s*'
    r'([0-9]+(?:\.[0-9]+)*)',
    re.IGNORECASE,
)


def extract_version(url):
    if not url or url in ("....", "..."):
        return None

    # Голая версия в current_version (не URL), например "1.1"
    bare = re.fullmatch(r'v?(\d+(?:\.\d+)*)', url.strip())
    if bare:
        return bare.group(1)

    patterns = [
        r'/releases/tag/v?(\d+\.\d+\.\d+)',
        r'/releases/tag/v?(\d+\.\d+)',
        r'/releases/tag/ver_(\d+(?:\.\d+)*)',
        r'/tag/v?(\d+\.\d+\.\d+)',
        r'/tag/v?(\d+\.\d+)',
        r'/tag/ver_(\d+(?:\.\d+)*)',
        r'/tree/v?(\d+\.\d+\.\d+)',
        r'/tree/ver_(\d+(?:\.\d+)*)',
        r'/tree/v(\d+\.\d+\.\d+)',
        r'/tag/VERSION_(\d+(?:_\d+)+)',
        r'/tag/REL(\d+(?:_\d+)+)',
        r'/tag/wal2json_(\d+(?:_\d+)+)',
        r'/tag/refs/tags/v(\d+\.\d+\.\d+)',
        r'/tree/(\d+\.\d+\.\d+)',
        r'/(\d+\.\d+\.\d+)/',
        r'/(\d+\.\d+)/'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1).replace('_', '.')

    return None


def extract_doc_version(sgml_path):
    """Достаёт версию документации из строки Version в начале sgml-файла."""
    try:
        with open(sgml_path, 'r', encoding='utf-8', errors='replace') as f:
            # Версия почти всегда в первых строках файла
            head = f.read(4096)
    except OSError:
        return None

    match = DOC_VERSION_RE.search(head)
    return match.group(1) if match else None


def collect_doc_versions(contrib_dir):
    """Обходит каталоги расширений и собирает версии из <name>.sgml."""
    versions = {}
    if not contrib_dir:
        print("Каталог contrib не задан — версии из sgml не будут добавлены.")
        return versions
    if not os.path.isdir(contrib_dir):
        print(f"Каталог contrib не найден: {contrib_dir}")
        return versions

    print(f"Каталог contrib: {os.path.abspath(contrib_dir)}")
    for entry in sorted(os.listdir(contrib_dir)):
        ext_dir = os.path.join(contrib_dir, entry)
        if not os.path.isdir(ext_dir):
            continue
        sgml_path = os.path.join(ext_dir, f"{entry}.sgml")
        if not os.path.isfile(sgml_path):
            continue
        doc_version = extract_doc_version(sgml_path)
        if doc_version:
            versions[entry] = doc_version

    print(f"Найдено версий документации в sgml: {len(versions)}")
    return versions


def load_contrib(source):
    """source: пустая строка → ./contrib.json, иначе путь к локальному файлу."""
    source = (source or '').strip().strip('"').strip("'")
    path = source or DEFAULT_LOCAL
    abs_path = os.path.abspath(path)
    print(f"Источник: локальный файл {abs_path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f), abs_path


def resolve_source():
    """Берём источник из argv[1], иначе спрашиваем интерактивно.

    Возвращает (source, explicit): explicit=True, если путь задан явно.
    """
    if len(sys.argv) > 1:
        return sys.argv[1], True
    try:
        answer = input(
            "Путь до contrib.json (Enter — использовать ./contrib.json): "
        )
        answer = (answer or '').strip()
        return answer, bool(answer)
    except EOFError:
        return '', False


def resolve_contrib_dir(json_abs_path, explicit_json):
    """Путь к каталогу contrib: argv[2], dirname(json) или интерактивный ввод."""
    if len(sys.argv) > 2:
        return sys.argv[2].strip().strip('"').strip("'")

    default = ''
    if explicit_json and json_abs_path:
        default = os.path.dirname(json_abs_path)

    try:
        if default:
            prompt = f"Путь до каталога contrib (Enter — {default}): "
        else:
            prompt = "Путь до каталога contrib: "
        answer = input(prompt)
        answer = (answer or '').strip().strip('"').strip("'")
        return answer or default
    except EOFError:
        return default


def resolve_include_url():
    """Спрашивает, писать ли полную ссылку current_version. Enter/нет — не писать."""
    try:
        answer = input(
            "Писать полную ссылку current_version? (y/д — да, Enter — нет): "
        )
        answer = (answer or '').strip().lower()
    except EOFError:
        return False
    return answer in ('y', 'yes', 'д', 'да', '1')


def format_entry(name, version, version_url, doc_version=None, include_url=False):
    parts = [name]
    if version:
        parts.append(f"json={version}")
    if include_url:
        parts.append(version_url)
    if doc_version:
        parts.append(f"sgml={doc_version}")
    return ' '.join(parts)


def main():
    source, explicit_json = resolve_source()
    data, json_abs_path = load_contrib(source)
    contrib_dir = resolve_contrib_dir(json_abs_path, explicit_json)
    include_url = resolve_include_url()
    doc_versions = collect_doc_versions(contrib_dir)

    editions = ['be', 'se', 'se-1c', 'certified', 'certified-2', 'free']
    edition_components = {edition: [] for edition in editions}
    all_components = {}  # Для хранения всех уникальных компонентов (name -> entry)

    for component in data['contrib']:
        name = component['name']
        version_url = component['current_version']
        version = extract_version(version_url)
        doc_version = doc_versions.get(name)
        entry = format_entry(
            name, version, version_url, doc_version, include_url=include_url
        )

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
