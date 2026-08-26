#!/usr/bin/env python3
"""
Generate generated_<edition>.sgml Core improvements sections from conf.json,
order.json, and patch_descriptions.json for target editions
(be, certified, certified_2, se, se1c). Editions missing from conf.json are
skipped; free and persey are ignored.

Use description_en (or variants for multi-line items) for output text. Plain
text is XML-escaped; if the string looks like SGML (contains <...>), it is
emitted raw. Groups may use sgml_listitem for nested listitem blocks.

Order patch keys must match conf.json for the target edition exactly; unknown
or absent keys are skipped (no aliasing).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from xml.sax.saxutils import escape

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONF = Path("conf.json")
DEFAULT_ORDER = Path("order.json")
DEFAULT_DESCRIPTIONS = Path("patch_descriptions.json")
DEFAULT_SECTION_ID = "differences-core-improvements"

# free и persey не обрабатываем, даже если они есть в conf.json.
TARGET_EDITIONS = ("be", "certified", "certified_2", "se", "se1c")


# Group key: both patches in edition → groups.sgml_listitem; else standalone patch text.
QUERY_MASKING_PGSS_GROUP = "func/query_masking perf/pgss_sampling"

BACKTRACE_GROUP = "func/backtrace func/log_version func/controlfile"
BACKTRACE_GROUP_PATCHES = frozenset(
    {"func/backtrace", "func/log_version", "func/controlfile"}
)


def order_includes_backtrace_group(order_items: list[dict]) -> bool:
    return any(
        item.get("type") == "group" and item.get("key") == BACKTRACE_GROUP
        for item in order_items
    )


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def covered_patches_by_groups(edition_patches: set[str], groups: dict) -> set[str]:
    covered: set[str] = set()
    for group_key, group_entry in groups.items():
        if not isinstance(group_key, str):
            continue
        group_patches = set(group_key.split())
        if not group_patches.issubset(edition_patches):
            continue
        if (group_entry.get("description_en") is None) and not group_entry.get(
            "sgml_listitem"
        ):
            continue
        if group_entry.get("keep_individual_patches"):
            continue
        covered.update(group_patches)
    return covered


def warn_missing_descriptions(
    edition: str, edition_patches: set[str], patches: dict, groups: dict
) -> None:
    """Print patch keys that exist in conf.json but are missing in patch_descriptions.json."""
    covered_by_groups = covered_patches_by_groups(edition_patches, groups)

    missing = sorted(
        p for p in edition_patches if p not in patches and p not in covered_by_groups
    )
    if not missing:
        return
    print(
        f"[WARN] Missing patch descriptions for edition '{edition}': {len(missing)}"
    )
    for key in missing:
        print(f"  - {key}")


def warn_empty_descriptions(
    edition: str, edition_patches: set[str], patches: dict, groups: dict
) -> None:
    """Print patch keys that exist but currently have empty descriptions."""
    covered_by_groups = covered_patches_by_groups(edition_patches, groups)
    empty: list[str] = []
    for key in sorted(edition_patches):
        if key in covered_by_groups:
            continue
        entry = patches.get(key)
        if not isinstance(entry, dict):
            continue
        desc = entry.get("description_en")
        if desc != "":
            continue
        variants = entry.get("variants") or {}
        has_any_variant_text = any(v not in (None, "") for v in variants.values())
        if not has_any_variant_text:
            empty.append(key)

    if not empty:
        return
    print(
        f"[WARN] Empty descriptions in patch_descriptions for edition '{edition}': {len(empty)}"
    )
    for key in empty:
        print(f"  - {key}")


def patches_referenced_in_order(order_items: list[dict]) -> set[str]:
    referenced: set[str] = set()
    for item in order_items:
        itype = item.get("type")
        key = item.get("key")
        if not isinstance(key, str):
            continue
        if itype == "patch":
            referenced.add(key)
            continue
        if itype == "group":
            referenced.update(group_patch_ids(key))
    return referenced


def warn_patches_missing_in_order(edition: str, edition_patches: set[str], order_items: list[dict]) -> None:
    """Print edition patch keys that won't be emitted because they are absent in order.json."""
    referenced = patches_referenced_in_order(order_items)
    missing_in_order = sorted(p for p in edition_patches if p not in referenced)
    if not missing_in_order:
        return
    print(
        f"[WARN] Patches from conf not mentioned in order.json for edition '{edition}': {len(missing_in_order)}"
    )
    for key in missing_in_order:
        print(f"  - {key}")


def resolve_patch_key(order_key: str, edition_patches: set[str]) -> str | None:
    """Return order_key if it is listed for this edition in conf; no alias resolution."""
    return order_key if order_key in edition_patches else None


def group_patch_ids(group_key: str) -> list[str]:
    return group_key.split()


def group_applicable(group_key: str, edition_patches: set[str]) -> bool:
    return all(p in edition_patches for p in group_patch_ids(group_key))


def get_patch_entry(patches: dict, key: str) -> dict | None:
    return patches.get(key)


def looks_like_sgml(text: str) -> bool:
    """Heuristic: DocBook/SGML fragment vs plain English for escaping."""
    return "<" in text and ">" in text


def resolve_description(
    entry: dict | None,
    variant: str | None,
) -> str | None:
    """Return text to emit; only None means skip item."""
    if entry is None:
        return None
    if variant:
        return (entry.get("variants") or {}).get(variant)
    return entry.get("description_en")


def format_comment(patch_keys: str) -> str:
    return f"            <!-- {patch_keys} -->"


def emit_listitem_simple(comment_keys: str, body: str, escape_body: bool) -> list[str]:
    inner = escape(body) if escape_body else body
    return [
        "        <listitem>",
        "          <para>",
        format_comment(comment_keys),
        f"            {inner}",
        "          </para>",
        "        </listitem>",
    ]


def emit_query_masking_pgss_group(
    edition_patches: set[str],
    patches: dict,
    groups: dict,
) -> tuple[list[str], str | None]:
    """
    Returns (lines to append, state token) or ([], None) if this group item yields nothing.
    state: 'both' | 'pgss_only' | 'qm_only' when something was emitted.
    """
    has_qm = "func/query_masking" in edition_patches
    has_pgss = "perf/pgss_sampling" in edition_patches
    gentry = groups.get(QUERY_MASKING_PGSS_GROUP) or {}

    if has_qm and has_pgss:
        listitem_raw = gentry.get("sgml_listitem")
        if not listitem_raw:
            return [], None
        lines = listitem_raw.rstrip("\n").split("\n")
        return lines, "both"

    if has_pgss and not has_qm:
        entry = get_patch_entry(patches, "perf/pgss_sampling")
        text = resolve_description(entry, None)
        if text is None:
            return [], None
        use_escape = not looks_like_sgml(text)
        return emit_listitem_simple("perf/pgss_sampling", text, use_escape), "pgss_only"

    if has_qm and not has_pgss:
        entry = get_patch_entry(patches, "func/query_masking")
        text = resolve_description(entry, None)
        if text is None:
            return [], None
        use_escape = not looks_like_sgml(text)
        return emit_listitem_simple("func/query_masking", text, use_escape), "qm_only"

    return [], None


def build_sgml(
    edition_patches: set[str],
    order_items: list[dict],
    patches: dict,
    groups: dict,
    section_id: str,
) -> str:
    lines: list[str] = [
        f'  <sect2 id="{escape(section_id)}">',
        "    <title>Core improvements</title>",
        "      <itemizedlist spacing=\"compact\">",
    ]

    qm_pgss_handled: str | None = None
    skip_backtrace_individual_patches = (
        order_includes_backtrace_group(order_items)
        and group_applicable(BACKTRACE_GROUP, edition_patches)
    )

    for item in order_items:
        itype = item.get("type")
        if itype == "group":
            gkey = item["key"]
            if gkey == QUERY_MASKING_PGSS_GROUP:
                extra, state = emit_query_masking_pgss_group(
                    edition_patches, patches, groups
                )
                if state is not None:
                    qm_pgss_handled = state
                    lines.extend(extra)
                continue

            if not group_applicable(gkey, edition_patches):
                continue
            gentry = groups.get(gkey) or {}
            listitem_raw = gentry.get("sgml_listitem")
            if listitem_raw:
                for line in listitem_raw.rstrip("\n").split("\n"):
                    lines.append(line)
                continue
            desc = gentry.get("description_en")
            if desc is None or (isinstance(desc, str) and desc.strip() == ""):
                continue
            body = desc if looks_like_sgml(desc) else escape(desc)
            lines.extend(
                [
                    "        <listitem>",
                    "          <para>",
                    format_comment(gkey),
                    f"            {body}",
                    "          </para>",
                    "        </listitem>",
                ]
            )
            continue

        if itype != "patch":
            continue

        order_key = item["key"]
        variant = item.get("variant")
        resolved = resolve_patch_key(order_key, edition_patches)
        if resolved is None:
            continue

        if resolved in ("func/query_masking", "perf/pgss_sampling") and qm_pgss_handled:
            if qm_pgss_handled == "both":
                continue
            if qm_pgss_handled == "pgss_only" and resolved == "perf/pgss_sampling":
                continue
            if qm_pgss_handled == "qm_only" and resolved == "func/query_masking":
                continue

        if resolved in BACKTRACE_GROUP_PATCHES and skip_backtrace_individual_patches:
            continue

        entry = get_patch_entry(patches, resolved)
        text = resolve_description(entry, variant)
        if text is None:
            continue

        use_escape = not looks_like_sgml(text)
        lines.extend(emit_listitem_simple(resolved, text, use_escape))

    lines.extend(
        [
            "      </itemizedlist>",
            "  </sect2>",
        ]
    )
    return "\n".join(lines) + "\n"


def prompt_path(prompt_text: str, default_path: Path) -> Path:
    """Спрашиваем путь у пользователя; пустой ввод/EOF → default_path."""
    try:
        raw = input(prompt_text).strip().strip('"').strip("'")
    except EOFError:
        raw = ''
    return Path(raw) if raw else default_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Core improvements SGML for editions "
            f"{', '.join(TARGET_EDITIONS)}."
        ),
    )
    parser.add_argument(
        "--conf",
        type=Path,
        default=None,
        help=f"Path to conf.json (default: ./{DEFAULT_CONF}; "
             f"в интерактивном режиме предложен ввод вручную)",
    )
    parser.add_argument(
        "--order",
        type=Path,
        default=None,
        help=f"Path to order.json (default: ./{DEFAULT_ORDER} рядом со скриптом)",
    )
    parser.add_argument(
        "--descriptions",
        type=Path,
        default=None,
        help=f"Path to patch_descriptions.json (default: ./{DEFAULT_DESCRIPTIONS} рядом со скриптом)",
    )
    parser.add_argument(
        "--section-id",
        default=DEFAULT_SECTION_ID,
        help=f'sect2 id attribute (default: {DEFAULT_SECTION_ID})',
    )
    args = parser.parse_args()

    if args.conf is not None:
        conf_path = args.conf
    else:
        conf_path = prompt_path(
            f"Путь до conf.json (Enter — использовать ./{DEFAULT_CONF}): ",
            DEFAULT_CONF,
        )

    # order.json и patch_descriptions.json всегда рядом со скриптом,
    # даже если --conf указывает на файл в другой папке.
    order_path = args.order if args.order is not None else DEFAULT_ORDER
    descriptions_path = (
        args.descriptions if args.descriptions is not None
        else DEFAULT_DESCRIPTIONS
    )

    print(f"Источник: локальный файл {conf_path.resolve()}")
    conf = load_json(conf_path)
    editions = conf.get("editions") or {}

    order_data = load_json(order_path)
    order_items = order_data.get("items_order") or []
    section_id = order_data.get("section_id") or args.section_id

    desc_data = load_json(descriptions_path)
    patches = desc_data.get("patches") or {}
    groups = desc_data.get("groups") or {}

    for edition in TARGET_EDITIONS:
        if edition not in editions:
            print(f"Издание {edition!r} отсутствует в conf.json, пропускаю.")
            continue

        edition_patches = set(editions[edition].get("patches") or [])
        warn_missing_descriptions(edition, edition_patches, patches, groups)
        warn_empty_descriptions(edition, edition_patches, patches, groups)
        warn_patches_missing_in_order(edition, edition_patches, order_items)

        out_path = Path(f"generated_{edition}.sgml")
        sgml = build_sgml(
            edition_patches,
            order_items,
            patches,
            groups,
            section_id,
        )
        out_path.write_text(sgml, encoding="utf-8")
        print(f"Файл {out_path.resolve()} успешно создан.")

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
