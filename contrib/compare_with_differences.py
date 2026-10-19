#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_DIFFERENCES = [
    ('be', '/home/kot/repo/tantor-db-14_23/tantor/doc/new_pages/differences_be_14_24.sgml'),
    ('se', '/home/kot/repo/tantor-db-14_23/tantor/doc/new_pages/differences_se_14_24.sgml'),
    ('se-1c', '/home/kot/repo/tantor-db-14_23/tantor/doc/new_pages/differences_se1c_14_24.sgml'),
    ('certified', '/home/kot/repo/tantor-db-14_23/tantor/doc/new_pages/differences_certified_14_24.sgml'),
    ('certified-2', '/home/kot/repo/tantor-db-14_23/tantor/doc/new_pages/differences_certified_2_14_24.sgml'),
]

CONTRIB_SECTION_RE = re.compile(
    r'<sect2\s+id="differences-contrib">\s*(.*?)\s*</sect2>',
    re.DOTALL,
)
LINKEND_RE = re.compile(r'<link\b[^>]*\blinkend="([^"]+)"[^>]*>', re.DOTALL)
VERSION_LABEL_RE = re.compile(r'tantor-db-([^/]+)')

# Имена в differences.sgml, которые соответствуют другому name в contrib.json.
NAME_ALIASES = {
    'oauth-validator': 'oauth_base_validator',
}


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def canonical_name(name: str) -> str:
    return NAME_ALIASES.get(name, name)


def version_label_from_path(path: str) -> str:
    """Из .../tantor-db-18_6/... получает метку 18_6 для имён файлов."""
    match = VERSION_LABEL_RE.search(path.replace('\\', '/'))
    if match:
        return match.group(1)
    return os.path.basename(os.path.dirname(path)) or 'unknown'


def extract_contrib_names(sgml_text: str) -> list[str]:
    section_match = CONTRIB_SECTION_RE.search(sgml_text)
    if not section_match:
        raise ValueError('Раздел <sect2 id="differences-contrib"> не найден.')

    section_body = section_match.group(1)
    names: list[str] = []
    seen: set[str] = set()

    for match in LINKEND_RE.finditer(section_body):
        name = normalize_text(match.group(1))
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)

    return names


def load_sgml(path: str) -> str:
    print(f"Источник: локальный файл {os.path.abspath(path)}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def load_json_contrib_names(filename: str) -> list[str]:
    """Имена расширений из первой секции файла contrib.py (до пустой строки)."""
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"Файл не найден: {filename}")

    names: list[str] = []
    seen: set[str] = set()
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                break
            name = line.split()[0]
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
    return names


def write_output_file(
    filename: str,
    diff_names: list[str],
    json_names: list[str],
) -> None:
    json_canon = {canonical_name(name) for name in json_names}
    diff_canon = {canonical_name(name) for name in diff_names}
    only_json = [
        name for name in json_names if canonical_name(name) not in diff_canon
    ]
    only_diff = [
        name for name in diff_names if canonical_name(name) not in json_canon
    ]

    with open(filename, 'w', encoding='utf-8') as f:
        for name in diff_names:
            f.write(f"{name}\n")

        f.write('\n')
        f.write("Расширения есть в contrib.json, но нет differences:\n")
        for name in only_json:
            f.write(f"{name}\n")

        f.write('\n')
        f.write("Расширения есть в differences, но нет contrib.json:\n")
        for name in only_diff:
            f.write(f"{name}\n")


def process_edition(edition: str, sgml_path: str) -> None:
    label = version_label_from_path(sgml_path)
    print(f"\n=== {label} {edition} ===")
    if not os.path.isfile(sgml_path):
        raise FileNotFoundError(f"Файл не найден: {sgml_path}")

    sgml_text = load_sgml(sgml_path)
    diff_names = extract_contrib_names(sgml_text)

    json_list_file = f"{label}_{edition}.txt"
    json_names = load_json_contrib_names(json_list_file)
    print(f"Список из contrib.json: {json_list_file} ({len(json_names)} расширений)")

    output_file = f"contrib_{label}_{edition}.txt"
    write_output_file(output_file, diff_names, json_names)
    print(
        f"Создан файл: {output_file} с {len(diff_names)} "
        f"расширениями из differences"
    )


def main() -> None:
    for edition, sgml_path in DEFAULT_DIFFERENCES:
        process_edition(edition, sgml_path)

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
