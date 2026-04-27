#!/usr/bin/env python3
import json
import os
import sys
import traceback
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOCAL = 'ppk.json'


def load_ppk(source):
    """source: пустая строка → ./ppk.json, иначе путь к локальному JSON-файлу."""
    source = (source or '').strip().strip('"').strip("'")
    path = Path(source) if source else Path(DEFAULT_LOCAL)
    print(f"Источник: локальный файл {path.resolve()}")
    with open(path, 'r', encoding='utf-8') as f:
        return path, json.load(f)


def resolve_source():
    """Берём источник из argv[1], иначе спрашиваем интерактивно."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        return input(
            f"Путь до JSON-файла ППК (Enter — использовать ./{DEFAULT_LOCAL}): "
        )
    except EOFError:
        return ''


def extract_vcs_url(component):
    for ref in component.get("externalReferences") or []:
        if ref.get("type") == "vcs":
            return (ref.get("url") or "").strip()
    return ""


def main():
    src_path, data = load_ppk(resolve_source())

    components = data.get("components") or []
    if not components:
        raise RuntimeError(
            "В файле не найден массив 'components' или он пуст. "
            "Ожидается CycloneDX-совместимый JSON с ключом 'components'."
        )

    lines = []
    for component in components:
        name = (component.get("name") or "").strip()
        version = (component.get("version") or "").strip()
        url = extract_vcs_url(component)
        lines.append(f"{name} {version} {url}".rstrip())

    out_path = src_path.with_suffix('.txt')
    with open(out_path, 'w', encoding='utf-8') as f_out:
        for line in lines:
            f_out.write(line + '\n')

    print(f"Создан файл: {out_path} с {len(lines)} компонентами")
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
