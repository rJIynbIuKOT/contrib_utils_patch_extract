#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
import traceback
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_FILE = 'patches_and_gucs.csv'

# Поведение по умолчанию для интерактивного режима и при отсутствии флагов в CLI:
# из CSV исключаются патчи, у которых не удалось найти GUC.
DEFAULT_EXCLUDE_EMPTY = True

CONF_RELPATH = Path('tantor') / 'conf.json'
PATCHES_RELDIR = Path('tantor') / 'patches'
DOC_RELDIR = Path('tantor') / 'doc' / 'insert_part_sgml'
DOC_HTML_RELDIR = Path('tantor') / 'doc' / 'output' / 'sphinx_html' / 'ru'

# Издания внутри собранной HTML-документации, в которых ищем якорь GUC. Порядок
# важен: при совпадении в нескольких редакциях побеждает первая (по требованию —
# сначала se, затем se1c; be не просматривается).
DOC_HTML_EDITIONS = ("se", "se1c", "certified")

# Базовый URL внутреннего портала, на который заменяется локальный путь
# tantor/doc/output/sphinx_html/ru/<версия>/.
DOC_PUBLIC_URL_BASE = "https://docs-internal.tantorlabs.ru/tdb/ru"

# Файлы внутри каталога патча, в которых может быть описание GUC. Все они имеют
# один и тот же формат (yaml с modifications/insert_text), просто бьют в разные C-файлы:
#   * guc.yaml         — единый файл, формат вне привязки к конкретному target_file;
#   * guc_tables.yaml  — правки src/backend/utils/misc/guc_tables.c (PG 16+);
#   * guc_c.yaml       — правки src/backend/utils/misc/guc.c (PG 14/15, старый формат).
# Если у патча есть несколько таких файлов — их GUC объединяются (с дедупликацией).
GUC_FILENAMES = ("guc.yaml", "guc_tables.yaml", "guc_c.yaml")

# Где и в каких файлах ищем документацию по GUC. По требованию: только эти каталоги
# (рекурсивно) и только эти расширения, всё остальное игнорируется. Каждой записи —
# короткая метка для CSV (источник, в котором найдено упоминание).
DOC_SEARCH_SOURCES = (
    (DOC_RELDIR, "doc"),
    (PATCHES_RELDIR, "patch"),
)
DOC_FILE_EXTS = (".sgml", ".patch")

# Известные издания и их «предпочтительный» порядок — используется и для отображения,
# и при разрешении приоритетов. В conf.json конкретного репозитория одних может не быть
# (старые ветки PG 14/15 знают не обо всех изданиях), и это не считается ошибкой:
# просматриваются только реально присутствующие в conf.json. Если встретится новое
# издание, не из этого списка, оно тоже будет учтено (и допишется в хвост).
EDITION_ORDER = ["be", "se", "se1c", "certified", "certified_2", "free"]

# Имя GUC в PostgreSQL объявляется в таблицах ConfigureNamesBool/Int/Real/String/Enum
# первой строкой записи: `{"имя_guc", PGC_<категория>, ...}`. По этому шаблону и
# вытаскиваем имена прямо из текста yaml — без yaml-парсера, чтобы остаться на
# чистой стандартной библиотеке (как и export_patches_csv.py).
GUC_NAME_RE = re.compile(
    r'\{\s*"(?P<name>[A-Za-z_][A-Za-z0-9_.]*)"\s*,\s*PGC_'
)

# В документации (.sgml/.patch) имена GUC оформляются как <varname>имя_guc</varname>.
VARNAME_RE = re.compile(r'<varname>([^<\s]+)</varname>')

# В сгенерированном HTML каждое описание GUC оформлено как:
#   <dt id="GUC-…"><span class="term">…<code class="varname">имя_guc</code>…
# Якорь (id) бывает любой (с дефисами/подчёркиваниями, иногда с артефактами sphinx —
# например GUC-AUTONOMOUS-SAFE_ENCODINGESSION-LIFETIME), поэтому полагаться на его
# вычисление по имени GUC нельзя — надо забирать пару (anchor, имя) прямо из HTML.
DT_GUC_RE = re.compile(
    r'<dt\s+id="(?P<anchor>GUC-[^"]+)"[^>]*>'  # открывающий тег с id
    r'.*?'                                       # промежуточная разметка (DOTALL)
    r'<code\s+class="varname">(?P<name>[A-Za-z_][A-Za-z0-9_]*)</code>',
    re.DOTALL,
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Root JSON object must be a dictionary.")
    return data


def determine_present_editions(editions_obj) -> list:
    """Возвращает упорядоченный список изданий, реально присутствующих в conf.json.

    Сначала идут известные издания в порядке EDITION_ORDER (только те, что нашлись),
    затем — любые неизвестные, отсортированные по алфавиту, чтобы вывод был стабильным.
    Если editions_obj не словарь — список пустой; ошибка про это будет выкинута выше.
    """
    if not isinstance(editions_obj, dict):
        return []
    available = set(editions_obj.keys())
    known_in_order = [e for e in EDITION_ORDER if e in available]
    extras = sorted(available - set(EDITION_ORDER))
    return known_in_order + extras


def collect_all_patches(editions_obj, present_editions: list) -> list:
    if not isinstance(editions_obj, dict):
        raise ValueError('Key "editions" must contain a dictionary.')

    all_patches = set()
    for edition in present_editions:
        edition_obj = editions_obj.get(edition)
        if not isinstance(edition_obj, dict):
            raise ValueError(f'Edition "{edition}" must be an object.')
        values = edition_obj.get("patches")
        if not isinstance(values, list):
            raise ValueError(f'Edition "{edition}" must contain a list in key "patches".')
        all_patches.update(str(item) for item in values)
    return sorted(all_patches)


def extract_guc_names_from_text(text: str, seen: set, accumulator: list) -> None:
    """Дописывает в accumulator имена GUC, найденные в text, минуя уже виденные.

    Ищем характерный для GUC-таблиц PostgreSQL шаблон `{"name", PGC_*`. Он встречается
    только внутри C-кода в `txt:`-блоках yaml, поэтому достаточно регулярки по
    сырому тексту файла — yaml-парсер не нужен.
    """
    for match in GUC_NAME_RE.finditer(text):
        name = match.group("name")
        if name in seen:
            continue
        seen.add(name)
        accumulator.append(name)


def collect_patch_gucs(patches_dir: Path, patch_names: list) -> tuple:
    """Для каждого патча находит его GUC по файлам tantor/patches/<patch>/<имя>.yaml.

    Просматриваются все файлы из GUC_FILENAMES (guc.yaml, guc_tables.yaml). Если ни
    одного нет — список пустой; это нормальная ситуация для патчей без GUC. Если есть
    оба файла — GUC из них объединяются с дедупликацией (порядок: сначала guc.yaml).

    Возвращает кортеж (patch_to_gucs, patches_with_guc_files), где второй элемент —
    число патчей, у которых нашёлся хотя бы один из GUC_FILENAMES (для статистики).
    """
    patch_to_gucs = {}
    patches_with_guc_files = 0
    for patch in patch_names:
        seen = set()
        gucs = []
        had_file = False
        for filename in GUC_FILENAMES:
            guc_path = patches_dir / patch / filename
            if not guc_path.is_file():
                continue
            had_file = True
            text = guc_path.read_text(encoding="utf-8")
            extract_guc_names_from_text(text, seen, gucs)
        patch_to_gucs[patch] = gucs
        if had_file:
            patches_with_guc_files += 1
    return patch_to_gucs, patches_with_guc_files


def collect_documented_gucs(repo_path: Path) -> tuple:
    """Возвращает (документированные_по_источникам, кол-во просмотренных файлов).

    Первый элемент — dict[имя_GUC -> list[метки источников]] (порядок меток совпадает
    с порядком в DOC_SEARCH_SOURCES, так что в CSV они выводятся стабильно). Имя GUC
    распознаётся как содержимое тега <varname>...</varname> в файлах с расширениями
    DOC_FILE_EXTS из указанных каталогов (рекурсивно).
    """
    documented = {}
    files_scanned = 0
    for rel, label in DOC_SEARCH_SOURCES:
        base = repo_path / rel
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in DOC_FILE_EXTS:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files_scanned += 1
            for m in VARNAME_RE.finditer(text):
                name = m.group(1)
                sources = documented.setdefault(name, [])
                if label not in sources:
                    sources.append(label)
    return documented, files_scanned


def format_doc_cell(guc_name: str, documented_gucs: dict) -> str:
    """Формирует значение колонки `doc`: `no` / `yes (doc)` / `yes (patch)` / `yes (doc, patch)`."""
    sources = documented_gucs.get(guc_name)
    if not sources:
        return "no"
    return f"yes ({', '.join(sources)})"


def derive_doc_version(tantor_version: str) -> str:
    """Преобразует tantor_version вида '18.3.0' в имя каталога документации '18_3'.

    Берём первые две компоненты major.minor (как использует sphinx), отбрасываем patch.
    Если на входе пусто или не хватает компонент — возвращаем как есть.
    """
    if not tantor_version:
        return ""
    parts = tantor_version.split(".")
    if len(parts) < 2:
        return tantor_version
    return f"{parts[0]}_{parts[1]}"


def collect_html_guc_urls(repo_path: Path, doc_version: str) -> tuple:
    """Возвращает (dict[имя_guc -> url], кол-во просмотренных html файлов).

    Просматриваются только html-файлы верхнего уровня в редакциях DOC_HTML_EDITIONS.
    Для каждого вхождения <dt id="GUC-…">…<code class="varname">имя</code> строится
    публичная ссылка через DOC_PUBLIC_URL_BASE. Если имя GUC встречается в нескольких
    редакциях, побеждает первая по порядку (по требованию — se → se1c).
    """
    name_to_url = {}
    files_scanned = 0
    if not doc_version:
        return name_to_url, files_scanned

    base = repo_path / DOC_HTML_RELDIR / doc_version
    if not base.is_dir():
        return name_to_url, files_scanned

    for edition in DOC_HTML_EDITIONS:
        edition_dir = base / edition
        if not edition_dir.is_dir():
            continue
        for html_path in sorted(edition_dir.glob("*.html")):
            try:
                text = html_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files_scanned += 1
            for m in DT_GUC_RE.finditer(text):
                name = m.group("name")
                if name in name_to_url:
                    continue
                anchor = m.group("anchor")
                name_to_url[name] = (
                    f"{DOC_PUBLIC_URL_BASE}/{doc_version}/{edition}/"
                    f"{html_path.name}#{anchor}"
                )
    return name_to_url, files_scanned


def write_csv(
    output_path: Path,
    patch_names: list,
    patch_to_gucs: dict,
    documented_gucs: dict,
    guc_urls: dict,
    exclude_empty: bool,
) -> int:
    """Возвращает число записанных в CSV патчей (без шапки).

    Если exclude_empty=True — патчи без GUC в CSV не попадают вообще (одна строка с
    пустыми колонками для них тоже не пишется). При exclude_empty=False сохраняется
    прежнее поведение: для патчей без GUC выводится одна строка с пустыми колонками.
    """
    written = 0
    with output_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["patch", "guc", "doc", "url"])
        for patch in patch_names:
            gucs = patch_to_gucs.get(patch) or []
            if not gucs:
                if exclude_empty:
                    continue
                writer.writerow([patch, "", "", ""])
                written += 1
                continue
            first, *rest = gucs
            writer.writerow([
                patch,
                first,
                format_doc_cell(first, documented_gucs),
                guc_urls.get(first, ""),
            ])
            for guc in rest:
                writer.writerow([
                    "",
                    guc,
                    format_doc_cell(guc, documented_gucs),
                    guc_urls.get(guc, ""),
                ])
            written += 1
    return written


def parse_cli_args() -> argparse.Namespace:
    """Разбирает аргументы командной строки.

    Поддерживает позиционный путь к репозиторию tantor-db и взаимоисключающую пару
    флагов для управления попаданием в CSV патчей без GUC. Если флаг не указан —
    значение остаётся None и решение принимается интерактивно (см. resolve_exclude_empty).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Экспортирует список патчей и их GUC из conf.json в CSV "
            "с пометкой о наличии документации и публичной ссылкой."
        ),
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=None,
        help="Путь до репозитория tantor-db (например, ~/repo/tantor-db-18_1).",
    )
    empty_group = parser.add_mutually_exclusive_group()
    empty_group.add_argument(
        "--exclude-empty",
        dest="exclude_empty",
        action="store_true",
        default=None,
        help="Не выводить в CSV патчи без GUC (без интерактивного запроса).",
    )
    empty_group.add_argument(
        "--include-empty",
        dest="exclude_empty",
        action="store_false",
        help="Оставлять в CSV патчи без GUC (без интерактивного запроса).",
    )
    return parser.parse_args()


def resolve_repo_path(cli_value) -> Path:
    """Берём путь к репозиторию tantor-db из CLI-аргумента или интерактивного ввода."""
    if cli_value is not None:
        raw = cli_value
    else:
        try:
            raw = input("Путь до репозитория tantor-db (например, ~/repo/tantor-db-18_1): ")
        except EOFError:
            raw = ''

    raw = (raw or '').strip().strip('"').strip("'")
    if not raw:
        raise ValueError("Не указан путь к репозиторию tantor-db.")

    repo_path = Path(raw).expanduser().resolve()
    if not repo_path.is_dir():
        raise NotADirectoryError(f"Каталог репозитория не найден: {repo_path}")

    conf_path = repo_path / CONF_RELPATH
    if not conf_path.is_file():
        raise FileNotFoundError(
            f"В указанном репозитории нет файла {CONF_RELPATH}: {conf_path}"
        )

    patches_dir = repo_path / PATCHES_RELDIR
    if not patches_dir.is_dir():
        raise NotADirectoryError(
            f"В указанном репозитории нет каталога {PATCHES_RELDIR}: {patches_dir}"
        )

    print(f"Репозиторий: {repo_path}")
    print(f"  conf.json:   {conf_path}")
    print(f"  patches dir: {patches_dir}")
    return repo_path


def resolve_exclude_empty(cli_value) -> bool:
    """Возвращает True, если из CSV нужно выкинуть патчи без GUC.

    Если CLI-флаг указан — берём его как есть. Иначе спрашиваем интерактивно: пустой
    ввод/Enter и EOFError → DEFAULT_EXCLUDE_EMPTY (True). 'no'/'n' → False. Любое
    другое значение трактуем как Enter и пишем подсказку.
    """
    if cli_value is not None:
        return bool(cli_value)

    default_label = "Y/n" if DEFAULT_EXCLUDE_EMPTY else "y/N"
    try:
        raw = input(f"Исключить патчи без гуков? [{default_label}] (Enter — да, 'no' — нет): ")
    except EOFError:
        return DEFAULT_EXCLUDE_EMPTY

    ans = (raw or '').strip().lower()
    if ans == "":
        return DEFAULT_EXCLUDE_EMPTY
    if ans in ("y", "yes", "да", "д"):
        return True
    if ans in ("n", "no", "нет", "н"):
        return False
    print(f"Не распознан ответ {raw!r}, использую значение по умолчанию ({'да' if DEFAULT_EXCLUDE_EMPTY else 'нет'}).")
    return DEFAULT_EXCLUDE_EMPTY


def main() -> None:
    args = parse_cli_args()

    repo_path = resolve_repo_path(args.repo_path)
    exclude_empty = resolve_exclude_empty(args.exclude_empty)
    print(
        f"  Патчи без GUC: "
        f"{'исключаются из CSV' if exclude_empty else 'остаются в CSV (одна пустая строка на патч)'}"
    )

    conf_path = repo_path / CONF_RELPATH
    patches_dir = repo_path / PATCHES_RELDIR

    data = load_json(conf_path)
    editions_obj = data.get("editions")
    present_editions = determine_present_editions(editions_obj)
    if not present_editions:
        raise ValueError('Key "editions" must contain a dictionary.')
    patch_names = collect_all_patches(editions_obj, present_editions)
    patch_to_gucs, patches_with_guc_files = collect_patch_gucs(patches_dir, patch_names)
    documented_gucs, doc_files_scanned = collect_documented_gucs(repo_path)

    tantor_version = (data.get("global") or {}).get("tantor_version", "")
    doc_version = derive_doc_version(tantor_version)
    guc_urls, html_files_scanned = collect_html_guc_urls(repo_path, doc_version)

    output_path = Path(OUTPUT_FILE).resolve()
    rows_patches = write_csv(
        output_path, patch_names, patch_to_gucs, documented_gucs, guc_urls, exclude_empty,
    )

    patches_with_gucs = sum(1 for v in patch_to_gucs.values() if v)
    total_gucs = sum(len(v) for v in patch_to_gucs.values())

    per_source_counts = {label: 0 for _, label in DOC_SEARCH_SOURCES}
    documented_total = 0
    for gucs in patch_to_gucs.values():
        for g in gucs:
            sources = documented_gucs.get(g)
            if not sources:
                continue
            documented_total += 1
            for s in sources:
                per_source_counts[s] = per_source_counts.get(s, 0) + 1

    urls_total = sum(
        1 for gucs in patch_to_gucs.values() for g in gucs if g in guc_urls
    )

    guc_files_label = " / ".join(GUC_FILENAMES)
    doc_dirs_label = ", ".join(str(rel) for rel, _ in DOC_SEARCH_SOURCES)
    doc_exts_label = "/".join(e.lstrip(".") for e in DOC_FILE_EXTS)
    per_source_str = ", ".join(f"{label}={per_source_counts[label]}" for _, label in DOC_SEARCH_SOURCES)
    html_dirs_label = "/".join(DOC_HTML_EDITIONS)
    print(f"Создан CSV: {output_path}")
    print(f"  Уникальных патчей:                  {len(patch_names)}")
    print(f"  Из них с {guc_files_label}:        {patches_with_guc_files}")
    print(f"  Из них с найденными GUC:            {patches_with_gucs}")
    print(f"  Всего извлечено GUC:                {total_gucs}")
    print(f"  Из них с документацией (yes):       {documented_total}  ({per_source_str})")
    print(f"  Файлов .{doc_exts_label} просмотрено в {doc_dirs_label}: {doc_files_scanned}")
    print(f"  Версия документации (sphinx_html):  {doc_version or '?'}  (из tantor_version={tantor_version!r})")
    print(f"  HTML-файлов просмотрено в {html_dirs_label}: {html_files_scanned}")
    print(f"  GUC с публичной ссылкой (url):      {urls_total}")
    print(f"  Записано в CSV патчей:              {rows_patches} (режим: {'без пустых' if exclude_empty else 'все'})")
    print(f"  Просмотрено изданий:                {len(present_editions)} ({', '.join(present_editions)})")
    missing_known = [e for e in EDITION_ORDER if e not in present_editions]
    if missing_known:
        print(f"  В conf.json отсутствуют (это нормально для старых веток): {', '.join(missing_known)}")
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
