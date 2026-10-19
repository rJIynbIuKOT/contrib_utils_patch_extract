#!/usr/bin/env python3
import csv
import os
import re
import sys
import traceback
from collections import OrderedDict
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Переиспользуем разбор документации и ссылок из соседнего скрипта, чтобы
# колонки doc/url совпадали с summ_patches_and_gucs_all_versions.csv.
import patches_and_gucs_csv as pg

OUTPUT_FILE = "hidden_gucs.csv"

# Те же репозитории, что в patches_and_gucs_csv_all_versions.py. Порядок важен:
# в колонке version сначала более новые. Пути при смене checkout надо править
# в обоих скриптах сразу.
TARGETS = [
    ("18", Path("/home/kot/repo/tantor-db-18_6/")),
    ("17", Path("/home/kot/repo/tantor-db-17_11/")),
    ("16", Path("/home/kot/repo/tantor-db-16_15/")),
    ("15", Path("/home/kot/repo/tantor-db-15_19/")),
    ("14", Path("/home/kot/repo/tantor-db-14_23/")),
]

# Кроме таблиц ConfigureNames* патч может регистрировать GUC расширений через
# DefineCustom*Variable("имя", ...) — это тоже определение, которого нет в yaml.
CUSTOM_GUC_RE = re.compile(
    r'DefineCustom(?:Bool|Int|Real|String|Enum)Variable\s*\(\s*'
    r'"(?P<name>[A-Za-z_][A-Za-z0-9_.]*)"'
)


def iter_guc_names(text: str):
    """Имена GUC из табличного `{"name", PGC_*` и из DefineCustom*Variable."""
    for match in pg.GUC_NAME_RE.finditer(text):
        yield match.group("name")
    for match in CUSTOM_GUC_RE.finditer(text):
        yield match.group("name")


def collect_yaml_gucs(patches_dir: Path) -> set:
    """Все GUC из guc.yaml / guc_tables.yaml / guc_c.yaml — их скрытыми не считаем."""
    names = set()
    if not patches_dir.is_dir():
        return names
    for filename in pg.GUC_FILENAMES:
        for path in patches_dir.rglob(filename):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            names.update(iter_guc_names(text))
    return names


def extract_added_gucs_from_patch(text: str) -> list:
    """GUC, которые патч добавляет, а не правит уже существующую запись.

    Смотрим только строки unified diff с префиксом «+» (новые). Имя, которое в том
    же файле есть и на «-», — правка ванильной/старой записи (как vacuum_* в xid64
    или wal_compression в 14), а не скрытый GUC Tantor.
    """
    added = []
    seen = set()
    removed = set()
    for line in text.splitlines():
        if line.startswith("+++") or line.startswith("---") or not line:
            continue
        prefix, body = line[0], line[1:]
        if prefix == "+":
            for name in iter_guc_names(body):
                if name in seen:
                    continue
                seen.add(name)
                added.append(name)
        elif prefix == "-":
            removed.update(iter_guc_names(body))
    return [name for name in added if name not in removed]


def patch_name_from_path(patch_path: Path, patches_dir: Path) -> str:
    """Имя патча — каталог относительно tantor/patches, в котором лежит .patch."""
    derived = patch_path.relative_to(patches_dir).parent.as_posix()
    return "" if derived == "." else derived


def collect_hidden_gucs(repo_path: Path, core_gucs: set, yaml_gucs: set) -> tuple:
    """Возвращает (patch_to_gucs, files_scanned, skipped_yaml, skipped_core).

    patch_to_gucs: OrderedDict[patch -> list[guc]] в порядке обхода файлов.
    skipped_* — сколько имён отбросили как уже известные из yaml / ядра.
    """
    patches_dir = repo_path / pg.PATCHES_RELDIR
    patch_to_gucs = OrderedDict()
    files_scanned = 0
    skipped_yaml = 0
    skipped_core = 0
    if not patches_dir.is_dir():
        return patch_to_gucs, files_scanned, skipped_yaml, skipped_core

    for path in sorted(patches_dir.rglob("*.patch")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_scanned += 1
        patch = patch_name_from_path(path, patches_dir)
        if not patch:
            continue
        hidden = []
        seen_here = set(patch_to_gucs.get(patch, []))
        for name in extract_added_gucs_from_patch(text):
            if name in yaml_gucs:
                skipped_yaml += 1
                continue
            if name in core_gucs:
                skipped_core += 1
                continue
            if name in seen_here:
                continue
            seen_here.add(name)
            hidden.append(name)
        if not hidden:
            continue
        patch_to_gucs.setdefault(patch, []).extend(hidden)

    return patch_to_gucs, files_scanned, skipped_yaml, skipped_core


def documented_versions(doc_values: OrderedDict) -> list:
    versions = []
    for status, vers in doc_values.items():
        if not status or status == "no":
            continue
        for version in vers:
            if version not in versions:
                versions.append(version)
    return versions


def format_doc_groups(doc_values: OrderedDict) -> str:
    documented = [
        (status, versions)
        for status, versions in doc_values.items()
        if status and status != "no"
    ]
    if not documented:
        return "no"
    return "; ".join(f"{' '.join(versions)} {status}" for status, versions in documented)


def format_aggregated_doc(guc_versions: list, doc_values: OrderedDict) -> str:
    text = format_doc_groups(doc_values)
    if set(guc_versions) != set(documented_versions(doc_values)):
        return f"! {text}"
    return text


def add_occurrence(bucket: OrderedDict, key, version: str, doc: str, url: str) -> None:
    item = bucket.get(key)
    if item is None:
        item = {"versions": [], "url": "", "doc_values": OrderedDict()}
        bucket[key] = item
    if version not in item["versions"]:
        item["versions"].append(version)
    if doc not in item["doc_values"]:
        item["doc_values"][doc] = []
    item["doc_values"][doc].append(version)
    if item["url"] == "" and url:
        item["url"] = url


def process_repo(version: str, repo_path: Path) -> tuple:
    """Собирает скрытые GUC одной версии и связанные doc/url."""
    if not repo_path.is_dir():
        raise NotADirectoryError(f"Репозиторий не найден: {repo_path}")

    patches_dir = repo_path / pg.PATCHES_RELDIR
    if not patches_dir.is_dir():
        raise NotADirectoryError(
            f"В указанном репозитории нет каталога {pg.PATCHES_RELDIR}: {patches_dir}"
        )

    print(f"\n=== Версия {version}: {repo_path} ===")
    yaml_gucs = collect_yaml_gucs(patches_dir)
    core_gucs = pg.collect_core_gucs(repo_path)
    patch_to_gucs, files_scanned, skipped_yaml, skipped_core = collect_hidden_gucs(
        repo_path, core_gucs, yaml_gucs,
    )

    documented_gucs, _, doc_files_scanned = pg.collect_documented_gucs(repo_path)

    tantor_version = ""
    conf_path = repo_path / pg.CONF_RELPATH
    if conf_path.is_file():
        data = pg.load_json(conf_path)
        tantor_version = (data.get("global") or {}).get("tantor_version", "")
    doc_version = pg.derive_doc_version(tantor_version)
    guc_urls, html_files_scanned = pg.collect_html_guc_urls(repo_path, doc_version)

    total_gucs = sum(len(v) for v in patch_to_gucs.values())
    print(f"  .patch файлов просмотрено:          {files_scanned}")
    print(f"  GUC из { ' / '.join(pg.GUC_FILENAMES) }: {len(yaml_gucs)}")
    print(f"  GUC ядра из {pg.CONFIG_SGML_RELPATH}: {len(core_gucs) or 'файл не найден'}")
    print(f"  Отброшено как уже в yaml:           {skipped_yaml}")
    print(f"  Отброшено как GUC ядра:             {skipped_core}")
    print(f"  Патчей со скрытыми GUC:             {len(patch_to_gucs)}")
    print(f"  Скрытых GUC:                        {total_gucs}")
    print(f"  Файлов документации просмотрено:    {doc_files_scanned}")
    print(f"  HTML-файлов просмотрено:            {html_files_scanned}")
    for patch, gucs in patch_to_gucs.items():
        print(f"    - {patch}: {', '.join(gucs)}")

    return patch_to_gucs, documented_gucs, guc_urls


def write_output(path: Path, merged: OrderedDict) -> None:
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


def main() -> None:
    merged = OrderedDict()
    print("Старт поиска GUC, описанных в .patch, но не в guc.yaml / guc_tables.yaml / guc_c.yaml")
    for version, repo in TARGETS:
        patch_to_gucs, documented_gucs, guc_urls = process_repo(version, repo)
        for patch, gucs in patch_to_gucs.items():
            for guc in gucs:
                add_occurrence(
                    merged,
                    (patch, guc),
                    version,
                    pg.format_doc_cell(guc, documented_gucs),
                    guc_urls.get(guc, ""),
                )

    output_path = Path(OUTPUT_FILE).resolve()
    write_output(output_path, merged)

    print(f"\nСоздан CSV: {output_path}")
    print(f"  Уникальных пар patch+guc: {len(merged)}")
    print(f"  Обработано версий: {len(TARGETS)} ({', '.join(v for v, _ in TARGETS)})")
    for (patch, guc), item in merged.items():
        print(f"  - {patch} | {guc}: {' '.join(item['versions'])}")
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
