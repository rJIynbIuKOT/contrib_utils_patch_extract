#!/usr/bin/env python3
import csv
import os
import sys
import traceback
from collections import OrderedDict
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_FILE = "summ_patches_and_gucs_all_versions.csv"

# Порядок важен:
# - агрегируем от более новой версии к более старой;
# - в колонке version показываем версии в таком же порядке;
# - url сохраняем от самой новой версии, где он непустой.
VERSION_FILES = [
    ("18", "patches_and_gucs_18.csv"),
    ("17", "patches_and_gucs_17.csv"),
    ("16", "patches_and_gucs_16.csv"),
    ("15", "patches_and_gucs_15.csv"),
    ("14", "patches_and_gucs_14.csv"),
]

# Строка-заголовок секции «описано, но нет в коде» во входных файлах. Её пишет
# patches_and_gucs_csv.py (константа MISSING_SECTION_TITLE), и этим же заголовком
# отделяется вторая таблица в итоговой сводке. Менять надо в обоих скриптах сразу.
MISSING_SECTION_TITLE = "GUC с описанием, но отсутствующие в коде"


def normalize(value: str) -> str:
    return (value or "").strip()


def documented_versions(doc_values: OrderedDict) -> list:
    """Версии, в которых найден <varname> (порядок как в VERSION_FILES)."""
    versions = []
    for status, vers in doc_values.items():
        if not status or status == "no":
            continue
        for version in vers:
            if version not in versions:
                versions.append(version)
    return versions


def format_doc_groups(doc_values: OrderedDict) -> str:
    """«<версии> <статус>», через «; » — если статус документации различается по версиям."""
    documented = [(status, versions) for status, versions in doc_values.items() if status and status != "no"]
    if not documented:
        return "no"
    return "; ".join(f"{' '.join(versions)} {status}" for status, versions in documented)


def format_aggregated_doc(guc_versions: list, doc_values: OrderedDict) -> str:
    """Собирает doc для сводки: «<версии> yes (...); …» по группам статуса документации.

    Если набор версий GUC не совпадает с набором версий, где найден <varname>,
    в начало ставится «! » (в обе стороны: GUC без описания или описание без GUC).
    """
    text = format_doc_groups(doc_values)
    if set(guc_versions) != set(documented_versions(doc_values)):
        return f"! {text}"
    return text


def read_version_file(path: Path) -> tuple:
    """Разбирает файл версии на две части.

    Возвращает (main_rows, missing_rows), где main_rows — список (patch, guc, doc, url)
    основной таблицы с раскрытыми продолжениями строк, а missing_rows — список
    (patch, guc, doc, url) из секции MISSING_SECTION_TITLE в конце файла. В секции в
    колонке `patch` может стоять несколько имён через пробел — описание GUC встречается
    в файлах сразу нескольких патчей.

    Секция отделяется строкой, у которой в колонке `patch` стоит MISSING_SECTION_TITLE;
    всё после неё в основную таблицу не попадает. Файлы, сделанные старой версией
    patches_and_gucs_csv.py, просто не содержат такой строки — тогда missing_rows пуст.
    """
    main_rows = []
    missing_rows = []

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"patch", "guc", "doc", "url"}
        if not required.issubset(reader.fieldnames or set()):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"{path.name}: отсутствуют колонки: {', '.join(missing)}")

        current_patch = ""
        in_missing_section = False
        for row in reader:
            patch = normalize(row.get("patch", ""))
            guc = normalize(row.get("guc", ""))
            doc = normalize(row.get("doc", ""))
            url = normalize(row.get("url", ""))

            if patch == MISSING_SECTION_TITLE:
                in_missing_section = True
                continue

            if in_missing_section:
                if guc:
                    missing_rows.append((patch, guc, doc, url))
                continue

            if patch:
                current_patch = patch
            else:
                patch = current_patch

            # Пустые строки или битые continuation-строки без guc игнорируем.
            if not patch or not guc:
                continue

            main_rows.append((patch, guc, doc, url))

    return main_rows, missing_rows


def add_occurrence(bucket: OrderedDict, key, version: str, doc: str, url: str, patch: str = "") -> None:
    """Накапливает версии, статусы doc, первый непустой url и имена патчей для ключа.

    `patch` заполняется только для секции «описано, но нет в коде»: там ключ — сам GUC,
    а патчи в разных версиях могут отличаться, поэтому их надо объединять. В основной
    таблице патч входит в ключ, и аргумент не используется.
    """
    item = bucket.get(key)
    if item is None:
        item = {
            "versions": [],
            "url": "",
            "doc_values": OrderedDict(),
            "patches": [],
        }
        bucket[key] = item

    for name in patch.split():
        if name not in item["patches"]:
            item["patches"].append(name)

    if version not in item["versions"]:
        item["versions"].append(version)

    if doc not in item["doc_values"]:
        item["doc_values"][doc] = []
    item["doc_values"][doc].append(version)

    # Сохраняем первый непустой url в порядке от новых к старым.
    if item["url"] == "" and url:
        item["url"] = url


def aggregate_rows(base_dir: Path):
    merged = OrderedDict()
    missing = OrderedDict()
    doc_conflicts = []

    for version, filename in VERSION_FILES:
        path = base_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Не найден входной файл: {path}")

        main_rows, missing_rows = read_version_file(path)

        for patch, guc, doc, url in main_rows:
            add_occurrence(merged, (patch, guc), version, doc, url)

        for patch, guc, doc, url in missing_rows:
            add_occurrence(missing, guc, version, doc, url, patch)

    # Предупреждаем, если статус doc (yes/no и источник) различается между версиями.
    for (patch, guc), item in merged.items():
        distinct_docs = [d for d in item["doc_values"] if d and d != "no"]
        if len(distinct_docs) <= 1:
            continue
        details = []
        for doc_value, versions in item["doc_values"].items():
            if not doc_value or doc_value == "no":
                continue
            details.append(f'"{doc_value}" в версиях: {" ".join(versions)}')
        doc_conflicts.append((patch, guc, "; ".join(details)))

    return merged, missing, doc_conflicts


def write_output(path: Path, merged: OrderedDict, missing: OrderedDict):
    """Пишет основную таблицу и, следом, отдельную таблицу «описано, но нет в коде».

    Вторая таблица использует те же колонки: имя GUC в `guc`, версии, где оно описано
    и при этом отсутствует в коде, — в `version`, статус документации — в `doc`,
    а в `patch` — патчи, в файлах которых лежит лишнее описание (не те, что определяют
    GUC: определения как раз и нет).
    """
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["patch", "guc", "version", "doc", "url"])
        for (patch, guc), item in merged.items():
            writer.writerow([
                patch,
                guc,
                " ".join(item["versions"]),
                format_aggregated_doc(item["versions"], item["doc_values"]),
                item["url"],
            ])

        writer.writerow(["", "", "", "", ""])
        writer.writerow([MISSING_SECTION_TITLE, "", "", "", ""])
        for guc, item in sorted(missing.items()):
            writer.writerow([
                " ".join(sorted(item["patches"])),
                guc,
                " ".join(item["versions"]),
                format_doc_groups(item["doc_values"]),
                item["url"],
            ])


def main() -> None:
    base_dir = Path(".").resolve()
    merged, missing, doc_conflicts = aggregate_rows(base_dir)

    output_path = (base_dir / OUTPUT_FILE).resolve()
    write_output(output_path, merged, missing)

    print(f"Создан CSV: {output_path}")
    print(f"  Уникальных пар patch+guc: {len(merged)}")
    print(f"  Обработано версий: {len(VERSION_FILES)} ({', '.join(v for v, _ in VERSION_FILES)})")
    print(f"  {MISSING_SECTION_TITLE}: {len(missing)}")
    for guc, item in sorted(missing.items()):
        where = " ".join(sorted(item["patches"])) or "патч не определён"
        print(f"  - {guc}: {' '.join(item['versions'])} <- {where}")

    if doc_conflicts:
        print("\nПРЕДУПРЕЖДЕНИЕ: найдено расхождение значений колонки doc между версиями.")
        print(f"  Количество конфликтов: {len(doc_conflicts)}")
        for patch, guc, details in doc_conflicts:
            print(f"  - {patch} | {guc}: {details}")
    else:
        print("  Расхождений doc между версиями не найдено.")

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
