#!/usr/bin/env python3
"""Generate utils.txt from utils.json and utils_conf.txt from conf.json."""

import json
import os
import sys
import traceback
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_UTILS = 'utils.json'
DEFAULT_CONF = 'conf.json'
VERSION_BASE_TEMPLATE = "/home/kot/repo/tantor-db-{version}/tantor"


def generate_from_utils_json(json_file, output_file):
    """Generate utils.txt from utils.json"""

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    edition_order_json = ['be', 'se', 'se-1c', 'certified', 'certified-2']
    edition_output_names = ['be', 'se', 'se1c', 'certified', 'certified_2']

    editions_dict = {edition: [] for edition in edition_order_json}
    utils_editions = {}

    for utility in data['utility_tools']:
        utility_name = utility['name']
        utils_editions[utility_name] = []
        for edition in utility['editions']:
            if edition in editions_dict:
                editions_dict[edition].append(utility_name)
                edition_idx = edition_order_json.index(edition)
                utils_editions[utility_name].append(edition_output_names[edition_idx])

    for edition in editions_dict:
        editions_dict[edition].sort()

    with open(output_file, 'w', encoding='utf-8') as f:
        for json_edition, output_edition in zip(edition_order_json, edition_output_names):
            f.write(f"{output_edition}\n")
            for utility in editions_dict[json_edition]:
                f.write(f"{utility}\n")
            if json_edition != edition_order_json[-1]:
                f.write("\n")

        f.write("\n")

        for utility_name in sorted(utils_editions.keys()):
            editions = utils_editions[utility_name]
            if len(editions) == len(edition_output_names):
                editions_str = "all"
            else:
                sorted_editions = [ed for ed in edition_output_names if ed in editions]
                editions_str = ",".join(sorted_editions)
            f.write(f"{utility_name} {editions_str}\n")

    print(f"Создан файл: {output_file}")
    print(f"  Обработано {len(data['utility_tools'])} утилит")
    print(f"  Сгенерированы списки для {len(edition_order_json)} изданий")


def generate_from_conf_json(json_file, output_file):
    """Generate utils_conf.txt from conf.json"""

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    edition_order_json = ['be', 'se', 'se1c', 'certified', 'certified_2']
    edition_output_names = ['be', 'se', 'se1c', 'certified', 'certified_2']

    editions_dict = {edition: [] for edition in edition_order_json}
    utils_editions = {}

    for json_key in edition_order_json:
        if json_key in data.get('editions', {}):
            edition_data = data['editions'][json_key]
            if 'utils' in edition_data:
                utilities = list(edition_data['utils'].keys())
                editions_dict[json_key] = sorted(utilities)

                edition_idx = edition_order_json.index(json_key)
                output_edition = edition_output_names[edition_idx]
                for utility in utilities:
                    if utility not in utils_editions:
                        utils_editions[utility] = []
                    utils_editions[utility].append(output_edition)

    with open(output_file, 'w', encoding='utf-8') as f:
        for json_edition, output_edition in zip(edition_order_json, edition_output_names):
            f.write(f"{output_edition}\n")
            for utility in editions_dict[json_edition]:
                f.write(f"{utility}\n")
            if json_edition != edition_order_json[-1]:
                f.write("\n")

        f.write("\n")

        for utility_name in sorted(utils_editions.keys()):
            editions = utils_editions[utility_name]
            if len(editions) == len(edition_output_names):
                editions_str = "all"
            else:
                sorted_editions = [ed for ed in edition_output_names if ed in editions]
                editions_str = ",".join(sorted_editions)
            f.write(f"{utility_name} {editions_str}\n")

    total_utils = sum(len(utils) for utils in editions_dict.values())
    print(f"Создан файл: {output_file}")
    print(f"  Обработано {total_utils} утилит")
    print(f"  Сгенерированы списки для {len(edition_order_json)} изданий")


def compare_files(utils_file, utils_conf_file):
    """Сравнить utils.txt и utils_conf.txt по содержимому."""
    with open(utils_file, 'r', encoding='utf-8') as f:
        utils_content = f.read()
    with open(utils_conf_file, 'r', encoding='utf-8') as f:
        utils_conf_content = f.read()

    print("\n" + "=" * 60)
    if utils_content == utils_conf_content:
        print("Файлы utils.txt и utils_conf.txt идентичны.")
    else:
        print("Обнаружены отличия между utils.txt и utils_conf.txt.")
    print("=" * 60)


def looks_like_version(value: str) -> bool:
    """Грубая эвристика: не содержит разделителей пути и не похоже на имя файла."""
    if not value:
        return False
    if '/' in value or '\\' in value or os.sep in value:
        return False
    if value.lower().endswith('.json'):
        return False
    return True


def resolve_paths(source: str):
    """source: пустая строка / путь к директории / путь к utils.json / строка-версия.

    Возвращает (utils_json_path, conf_json_path, source_label).
    """
    source = (source or '').strip().strip('"').strip("'")
    if not source:
        return Path(DEFAULT_UTILS), Path(DEFAULT_CONF), "локальные файлы рядом со скриптом"

    candidate = Path(source)
    if candidate.exists():
        if candidate.is_dir():
            return (
                candidate / DEFAULT_UTILS,
                candidate / DEFAULT_CONF,
                f"директория {candidate.resolve()}",
            )
        if candidate.is_file():
            parent = candidate.parent
            conf_above = parent.parent / DEFAULT_CONF
            if parent.name == 'contrib' and conf_above.exists():
                return candidate, conf_above, f"файл {candidate.resolve()}"
            return candidate, parent / DEFAULT_CONF, f"файл {candidate.resolve()}"

    if looks_like_version(source):
        base = Path(VERSION_BASE_TEMPLATE.format(version=source))
        return (
            base / "contrib" / DEFAULT_UTILS,
            base / DEFAULT_CONF,
            f"версия tantor-db-{source}",
        )

    raise RuntimeError(
        f"Не удалось интерпретировать {source!r} как путь или строку-версию "
        f"(например '17_7')."
    )


def resolve_source():
    """Берём источник из argv[1], иначе спрашиваем интерактивно."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        return input(
            "Путь до utils.json / папки с ним или строка-версия "
            "(Enter — локальные файлы рядом со скриптом): "
        )
    except EOFError:
        return ''


def prompt_path(prompt_text: str, default_path: Path) -> Path:
    """Спрашиваем путь у пользователя; пустой ввод/EOF → default_path."""
    try:
        raw = input(prompt_text).strip().strip('"').strip("'")
    except EOFError:
        raw = ''
    return Path(raw) if raw else default_path


def main():
    interactive = len(sys.argv) <= 1
    utils_json, conf_json, source_label = resolve_paths(resolve_source())

    output_dir = Path('.').resolve()

    print("=" * 60)
    print(f"Источник: {source_label}")
    print(f"  utils.json -> {utils_json}")
    print(f"  conf.json  -> {conf_json}")
    print(f"Выход в директорию: {output_dir}")
    print("=" * 60 + "\n")

    if not utils_json.exists() and interactive:
        print(f"Файл {utils_json} не найден.")
        utils_json = prompt_path(
            "Путь до utils.json (Enter — оставить как есть): ",
            utils_json,
        )
    if not utils_json.exists():
        raise RuntimeError(f"Файл {utils_json} не найден.")

    if not conf_json.exists() and interactive:
        print(f"Файл {conf_json} не найден.")
        conf_json = prompt_path(
            "Путь до conf.json (Enter — оставить как есть): ",
            conf_json,
        )
    if not conf_json.exists():
        raise RuntimeError(f"Файл {conf_json} не найден.")

    utils_txt = output_dir / "utils.txt"
    utils_conf_txt = output_dir / "utils_conf.txt"

    generate_from_utils_json(utils_json, utils_txt)
    generate_from_conf_json(conf_json, utils_conf_txt)
    compare_files(utils_txt, utils_conf_txt)

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
