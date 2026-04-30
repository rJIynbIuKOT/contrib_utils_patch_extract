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


def normalize(value: str) -> str:
    return (value or "").strip()


def iter_rows(path: Path):
    """Итерирует пары (patch, guc, doc, url) с учётом продолжений строк."""
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"patch", "guc", "doc", "url"}
        if not required.issubset(reader.fieldnames or set()):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"{path.name}: отсутствуют колонки: {', '.join(missing)}")

        current_patch = ""
        for row in reader:
            patch = normalize(row.get("patch", ""))
            guc = normalize(row.get("guc", ""))
            doc = normalize(row.get("doc", ""))
            url = normalize(row.get("url", ""))

            if patch:
                current_patch = patch
            else:
                patch = current_patch

            # Пустые строки или битые continuation-строки без guc игнорируем.
            if not patch or not guc:
                continue

            yield patch, guc, doc, url


def aggregate_rows(base_dir: Path):
    merged = OrderedDict()
    doc_conflicts = []

    for version, filename in VERSION_FILES:
        path = base_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Не найден входной файл: {path}")

        for patch, guc, doc, url in iter_rows(path):
            key = (patch, guc)
            item = merged.get(key)
            if item is None:
                item = {
                    "versions": [],
                    "doc": doc,
                    "url": "",
                    "doc_values": OrderedDict(),
                }
                merged[key] = item

            if version not in item["versions"]:
                item["versions"].append(version)

            if doc not in item["doc_values"]:
                item["doc_values"][doc] = []
            item["doc_values"][doc].append(version)

            # Сохраняем doc от самой новой версии (первой в VERSION_FILES).
            if item["doc"] == "":
                item["doc"] = doc

            # Сохраняем первый непустой url в порядке от новых к старым.
            if item["url"] == "" and url:
                item["url"] = url

    # Формируем предупреждения по расхождениям doc.
    for (patch, guc), item in merged.items():
        distinct_docs = list(item["doc_values"].keys())
        if len(distinct_docs) <= 1:
            continue
        details = []
        for doc_value, versions in item["doc_values"].items():
            label = doc_value if doc_value else "<empty>"
            details.append(f'"{label}" в версиях: {" ".join(versions)}')
        doc_conflicts.append((patch, guc, "; ".join(details)))

    return merged, doc_conflicts


def write_output(path: Path, merged: OrderedDict):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["patch", "guc", "version", "doc", "url"])
        for (patch, guc), item in merged.items():
            writer.writerow([patch, guc, " ".join(item["versions"]), item["doc"], item["url"]])


def main() -> None:
    base_dir = Path(".").resolve()
    merged, doc_conflicts = aggregate_rows(base_dir)

    output_path = (base_dir / OUTPUT_FILE).resolve()
    write_output(output_path, merged)

    print(f"Создан CSV: {output_path}")
    print(f"  Уникальных пар patch+guc: {len(merged)}")
    print(f"  Обработано версий: {len(VERSION_FILES)} ({', '.join(v for v, _ in VERSION_FILES)})")

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
