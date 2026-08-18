#!/usr/bin/env python3
import csv
import json
import os
import re
import sys
import traceback
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

TARGETS = [
    ("18", Path("/home/kot/repo/tantor-db-18_3/tantor/conf.json")),
    ("17", Path("/home/kot/repo/tantor-db-17_10/tantor/conf.json")),
    ("16", Path("/home/kot/repo/tantor-db-16_14/tantor/conf.json")),
    ("15", Path("/home/kot/repo/tantor-db-15_18/tantor/conf.json")),
    ("14", Path("/home/kot/repo/tantor-db-14_23/tantor/conf.json")),
]

# Колонки JSON-изданий в итоговом CSV. После каждого, кроме free, идёт <edition>_sgml.
CSV_EDITIONS = ["be", "se", "se1c", "certified", "certified_2", "free"]

# Какой sgml-файл даёт список ОС для каких изданий.
SGML_SOURCES = (
    ("install-binaries.sgml", ("be", "se", "se1c")),
    ("install-binaries-certified.sgml", ("certified",)),
    ("install-binaries-certified-2.sgml", ("certified_2",)),
)

OS_LIST_RE = re.compile(
    r"The list of supported operating systems:\s*</para>\s*"
    r"<itemizedlist[^>]*>(.*?)</itemizedlist>",
    re.DOTALL | re.IGNORECASE,
)
PARA_RE = re.compile(r"<para>\s*(.*?)\s*</para>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

# Явные соответствия «текст из sgml → ключ platform из conf.json».
SGML_ALIASES = {
    "alt 8 sp, release 9 (c9f2)": "altlinux_c9f2",
    "alt 8 sp, release 10 (c10f2)": "altlinux_c10f2",
    "alt platform 10": "altlinux_p10",
    "alt platform 11": "altlinux_p11",
    "alt sp release 10": "altlinux_c10f2",
    "altlinux c10f2": "altlinux_c10f2",
    "astra linux common edition 2.12": "astralinux_2_12",
    "astra linux special edition 1.7": "astralinux_1_7",
    "astra linux special edition 1.8": "astralinux_1_8",
    "astra linux special edition 4.7": "astralinux_4_7",
    "centos 7": "centos_7",
    "debian 10 (buster)": "debian_10",
    "debian 11 (bullseye)": "debian_11",
    "debian 12 (bookworm)": "debian_12",
    "debian 13 (trixie)": "debian_13",
    "oracle linux 8": "oracle_8",
    "red os 7.3": "redos_7_3",
    "red os 8": "redos_8",
    "red os 8 certified edition": "redos_8",
    "redos 7.3": "redos_7_3",
    "rocky linux 8": "rocky_8",
    "rocky linux 9": "rocky_9",
    "rocky linux 10": "rocky_10",
    "ubuntu 18.04": "ubuntu_18_04",
    "ubuntu 20.04": "ubuntu_20_04",
    "ubuntu 22.04": "ubuntu_22_04",
    "ubuntu 24.04": "ubuntu_24_04",
    "ubuntu 26.04": "ubuntu_26_04",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Root JSON object must be a dictionary.")
    return data


def collect_os_matrix(data: dict) -> dict:
    """Матрица platform → set(edition) из run_build_all."""
    builds = data.get("run_build_all")
    if not isinstance(builds, list):
        raise ValueError('Key "run_build_all" must contain a list.')

    matrix = {}
    for item in builds:
        if not isinstance(item, dict):
            continue
        platform = str(item.get("platform") or "").strip()
        edition = str(item.get("edition") or "").strip()
        if not platform or not edition:
            continue
        matrix.setdefault(platform, set()).add(edition)
    return matrix


def normalize_os_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def sgml_label_to_platform(label: str) -> tuple:
    """Преобразует строку из sgml в ключ platform. Второй элемент — True, если сработал slug-fallback."""
    key = normalize_os_label(label)
    alias = SGML_ALIASES.get(key)
    if alias:
        return alias, False

    m = re.fullmatch(r"ubuntu (\d+)\.(\d+)", key)
    if m:
        return f"ubuntu_{m.group(1)}_{m.group(2)}", False

    m = re.fullmatch(r"debian (\d+)(?: \([^)]+\))?", key)
    if m:
        return f"debian_{m.group(1)}", False

    m = re.fullmatch(r"rocky linux (\d+)", key)
    if m:
        return f"rocky_{m.group(1)}", False

    m = re.fullmatch(r"oracle linux (\d+)", key)
    if m:
        return f"oracle_{m.group(1)}", False

    m = re.fullmatch(r"centos (\d+)", key)
    if m:
        return f"centos_{m.group(1)}", False

    m = re.fullmatch(r"(?:red os|redos) (\d+(?:\.\d+)?)(?:\s+.*)?", key)
    if m:
        return "redos_" + m.group(1).replace(".", "_"), False

    m = re.fullmatch(r"astra linux (?:special|common) edition (\d+)\.(\d+)", key)
    if m:
        return f"astralinux_{m.group(1)}_{m.group(2)}", False

    m = re.fullmatch(r"alt platform (\d+)", key)
    if m:
        return f"altlinux_p{m.group(1)}", False

    m = re.search(r"\((c\d+f\d+)\)", key)
    if m:
        return f"altlinux_{m.group(1)}", False

    m = re.fullmatch(r"altlinux (c\d+f\d+)", key)
    if m:
        return f"altlinux_{m.group(1)}", False

    m = re.fullmatch(r"alt sp release (\d+)", key)
    if m:
        return f"altlinux_c{m.group(1)}f2", False

    return re.sub(r"[^a-z0-9]+", "_", key).strip("_"), True


def extract_sgml_os_labels(text: str) -> list:
    match = OS_LIST_RE.search(text)
    if not match:
        return []
    labels = []
    for para in PARA_RE.finditer(match.group(1)):
        raw = TAG_RE.sub("", para.group(1))
        raw = re.sub(r"\s+", " ", raw).strip()
        if raw:
            labels.append(raw)
    return labels


def collect_sgml_matrix(sgml_dir: Path) -> tuple:
    """Матрица platform → set(edition) из install-binaries*.sgml.

    Возвращает (matrix, stats) — stats для печати: имя файла, найден/нет, число ОС.
    """
    matrix = {}
    stats = []
    unmapped = []
    for filename, editions in SGML_SOURCES:
        path = sgml_dir / filename
        if not path.is_file():
            stats.append((filename, False, 0))
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        labels = extract_sgml_os_labels(text)
        platforms = []
        for label in labels:
            platform, fallback = sgml_label_to_platform(label)
            if fallback:
                unmapped.append((filename, label, platform))
            platforms.append(platform)
            for edition in editions:
                matrix.setdefault(platform, set()).add(edition)
        stats.append((filename, True, len(platforms)))
    return matrix, stats, unmapped


def csv_header() -> list:
    header = ["os"]
    for edition in CSV_EDITIONS:
        header.append(edition)
        if edition != "free":
            header.append(f"{edition}_sgml")
    return header


def write_csv(path: Path, platforms: list, json_matrix: dict, sgml_matrix: dict) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header())
        for platform in platforms:
            json_eds = json_matrix.get(platform, set())
            sgml_eds = sgml_matrix.get(platform, set())
            row = [platform]
            for edition in CSV_EDITIONS:
                row.append("y" if edition in json_eds else "")
                if edition != "free":
                    row.append("y" if edition in sgml_eds else "")
            writer.writerow(row)


def process_one(version: str, conf_path: Path) -> None:
    print(f"\n=== Версия {version}: {conf_path} ===")
    if not conf_path.is_file():
        raise FileNotFoundError(f"Файл не найден: {conf_path}")

    json_matrix = collect_os_matrix(load_json(conf_path))
    sgml_dir = conf_path.parent / "doc" / "replace_whole_sgml"
    sgml_matrix, sgml_stats, unmapped = collect_sgml_matrix(sgml_dir)

    platforms = sorted(set(json_matrix) | set(sgml_matrix))
    target = Path(f"{version}.csv").resolve()
    write_csv(target, platforms, json_matrix, sgml_matrix)

    print(f"Сохранено: {target}")
    print(f"  Операционных систем (json ∪ sgml): {len(platforms)}")
    print(f"  Из conf.json: {len(json_matrix)}")
    for filename, found, count in sgml_stats:
        if found:
            print(f"  {filename}: {count} ОС")
        else:
            print(f"  {filename}: файл не найден")
    if unmapped:
        print("  Не удалось однозначно сопоставить имена из sgml:")
        for filename, label, platform in unmapped:
            print(f"    {filename}: {label!r} → {platform}")


def main() -> None:
    print("Старт генерации <version>.csv из conf.json и install-binaries*.sgml")
    for version, conf_path in TARGETS:
        process_one(version, conf_path)
    print("\nГотово. Все версии обработаны.")


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
