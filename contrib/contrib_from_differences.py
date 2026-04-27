#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOCAL = 'differences.sgml'
OUTPUT_FILE = 'contrib.txt'

CONTRIB_SECTION_RE = re.compile(
    r'<sect2\s+id="differences-contrib">\s*(.*?)\s*</sect2>',
    re.DOTALL,
)
LINKEND_RE = re.compile(r'<link\b[^>]*\blinkend="([^"]+)"[^>]*>', re.DOTALL)


def normalize_text(text: str) -> str:
    return " ".join(text.split())


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


def load_sgml(source: str) -> str:
    """source: пустая строка → ./differences.sgml, иначе путь к локальному файлу."""
    source = (source or '').strip().strip('"').strip("'")
    path = source or DEFAULT_LOCAL
    print(f"Источник: локальный файл {os.path.abspath(path)}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def resolve_source() -> str:
    """Берём источник из argv[1], иначе спрашиваем интерактивно."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        return input(
            "Путь до differences.sgml (Enter — использовать ./differences.sgml): "
        )
    except EOFError:
        return ''


def main() -> None:
    sgml_text = load_sgml(resolve_source())
    names = extract_contrib_names(sgml_text)

    payload = "\n".join(names) + ("\n" if names else "")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(payload)

    print(f"Файл {OUTPUT_FILE} успешно создан. Записано {len(names)} расширений.")
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
