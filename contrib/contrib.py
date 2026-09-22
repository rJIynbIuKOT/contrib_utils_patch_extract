#!/usr/bin/env python3
import json
import os
import re
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONTRIB_JSON = [
    '/home/kot/repo/tantor-db-18_6/tantor/contrib/contrib.json',
    '/home/kot/repo/tantor-db-17_11/tantor/contrib/contrib.json',
    '/home/kot/repo/tantor-db-16_15/tantor/contrib/contrib.json',
    '/home/kot/repo/tantor-db-15_19/tantor/contrib/contrib.json',
    '/home/kot/repo/tantor-db-14_23/tantor/contrib/contrib.json',
]

EDITIONS = ['be', 'se', 'se-1c', 'certified', 'certified-2', 'free']

DOC_VERSION_RE = re.compile(
    r'<emphasis\s+role="strong">\s*Version\s*:?\s*</emphasis>\s*:?\s*'
    r'([0-9]+(?:\.[0-9]+)*)',
    re.IGNORECASE,
)

CONTROL_VERSION_RE = re.compile(
    r"^\s*default_version\s*=\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE | re.IGNORECASE,
)

VERSION_LABEL_RE = re.compile(r'tantor-db-([^/]+)')


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
        r'/tree/v?(\d+(?:\.\d+)*)/?$',
        r'/tree/ver_(\d+(?:\.\d+)*)',
        r'/tag/VERSION_(\d+(?:_\d+)+)',
        r'/tag/REL(\d+(?:_\d+)+)',
        r'/tag/wal2json_(\d+(?:_\d+)+)',
        r'/tag/refs/tags/v(\d+\.\d+\.\d+)',
        r'/(\d+\.\d+\.\d+)/',
        r'/(\d+\.\d+)/',
        r'/(\d+(?:\.\d+)*)/?$',
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


def extract_control_version(control_path):
    """Достаёт default_version из .control файла расширения."""
    try:
        with open(control_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError:
        return None

    match = CONTROL_VERSION_RE.search(content)
    return match.group(1).strip() if match else None


def find_control_file(ext_dir, name):
    """Ищет <name>.control, иначе любой *.control в корне каталога расширения."""
    exact = os.path.join(ext_dir, f"{name}.control")
    if os.path.isfile(exact):
        return exact
    try:
        for fname in sorted(os.listdir(ext_dir)):
            if fname.endswith('.control'):
                path = os.path.join(ext_dir, fname)
                if os.path.isfile(path):
                    return path
    except OSError:
        pass
    return None


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


def collect_control_versions(contrib_dir):
    """Обходит каталоги расширений и собирает default_version из .control."""
    versions = {}
    if not contrib_dir or not os.path.isdir(contrib_dir):
        return versions

    for entry in sorted(os.listdir(contrib_dir)):
        ext_dir = os.path.join(contrib_dir, entry)
        if not os.path.isdir(ext_dir):
            continue
        control_path = find_control_file(ext_dir, entry)
        if not control_path:
            continue
        control_version = extract_control_version(control_path)
        if control_version:
            versions[entry] = control_version

    print(f"Найдено версий в control: {len(versions)}")
    return versions


def version_label_from_path(json_path):
    """Из .../tantor-db-18_3/... получает метку 18_3 для имён выходных файлов."""
    match = VERSION_LABEL_RE.search(json_path.replace('\\', '/'))
    if match:
        return match.group(1)
    # запасной вариант — имя родительского каталога contrib.json
    return os.path.basename(os.path.dirname(json_path)) or 'unknown'


def load_contrib(path):
    print(f"Источник: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


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


def format_entry(
    name,
    version,
    version_url,
    doc_version=None,
    control_version=None,
    include_url=False,
):
    parts = [name]
    if version:
        parts.append(f"json={version}")
    if include_url:
        parts.append(version_url)
    if doc_version:
        parts.append(f"sgml={doc_version}")
    if control_version:
        parts.append(f"control={control_version}")
    return ' '.join(parts)


def versions_mismatch(json_ver, sgml_ver, control_ver):
    """True, если json/sgml/control не все заданы и равны друг другу.

    Пример: только control=1.0 при пустых json и sgml — тоже несовпадение.
    Если ни одной версии нет — не считаем несовпадением.
    """
    versions = (json_ver, sgml_ver, control_ver)
    present = [v for v in versions if v is not None]
    if not present:
        return False
    if len(present) < 3:
        return True
    return len(set(present)) > 1


def write_output_file(filename, records):
    """Пишет список расширений и сводку по несовпадениям / отсутствию control/sgml."""
    records = sorted(records, key=lambda r: r['entry'])
    with open(filename, 'w', encoding='utf-8') as file:
        for record in records:
            file.write(f"{record['entry']}\n")

        file.write('\n')
        mismatches = [r['entry'] for r in records if r['mismatch']]
        if mismatches:
            file.write("Не совпадают версии:\n")
            for entry in mismatches:
                file.write(f"{entry}\n")
        else:
            file.write("Все версии совпадают\n")

        file.write('\n')
        no_control = [r['entry'] for r in records if r['no_control']]
        if no_control:
            file.write("Расширения без .control:\n")
            for entry in no_control:
                file.write(f"{entry}\n")
        else:
            file.write("Все расширения с .control\n")

        file.write('\n')
        no_sgml = [r['entry'] for r in records if r['no_sgml']]
        if no_sgml:
            file.write("Расширения без версии в sgml:\n")
            for entry in no_sgml:
                file.write(f"{entry}\n")
        else:
            file.write("Все расширения с версиями в sgml\n")


def process_contrib_json(json_path, include_url):
    label = version_label_from_path(json_path)
    contrib_dir = os.path.dirname(json_path)

    print(f"\n=== {label} ===")
    if not os.path.isfile(json_path):
        raise FileNotFoundError(f"Файл не найден: {json_path}")

    data = load_contrib(json_path)
    doc_versions = collect_doc_versions(contrib_dir)
    control_versions = collect_control_versions(contrib_dir)

    edition_records = {edition: [] for edition in EDITIONS}
    all_records = {}

    for component in data['contrib']:
        name = component['name']
        version_url = component['current_version']
        version = extract_version(version_url)
        doc_version = doc_versions.get(name)
        control_version = control_versions.get(name)
        entry = format_entry(
            name,
            version,
            version_url,
            doc_version=doc_version,
            control_version=control_version,
            include_url=include_url,
        )
        record = {
            'entry': entry,
            'mismatch': versions_mismatch(version, doc_version, control_version),
            'no_control': control_version is None,
            'no_sgml': doc_version is None,
        }

        all_records[name] = record

        for edition in component['editions']:
            if edition in edition_records:
                edition_records[edition].append(record)

    for edition, records in edition_records.items():
        filename = f"{label}_{edition}.txt"
        write_output_file(filename, records)
        print(f"Создан файл: {filename} с {len(records)} компонентами")

    all_filename = f"{label}_all.txt"
    write_output_file(all_filename, list(all_records.values()))
    print(
        f"Создан файл: {all_filename} с {len(all_records)} "
        f"уникальными компонентами"
    )


def main():
    include_url = resolve_include_url()

    for json_path in DEFAULT_CONTRIB_JSON:
        process_contrib_json(json_path, include_url)

    print("\nОбработка завершена.")


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
