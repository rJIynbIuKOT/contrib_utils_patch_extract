#!/usr/bin/env python3
import argparse
import csv
import os
import sys
import traceback
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_INPUT = "summ_patches_and_gucs_all_versions.csv"


def make_html_link(guc: str, url: str) -> str:
    """
    HTML link used for Confluence when Wiki Markup isn't parsed.

    Confluence usually sanitizes content, but HTML <table> often works better
    than wiki tables in "rich text" mode.
    """

    def esc(s: str) -> str:
        s = "" if s is None else str(s)
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    url_esc = (url or "").strip()
    guc_esc = esc(guc)
    if not url_esc:
        return guc_esc
    url_esc = url_esc.replace("&", "&amp;").replace('"', "&quot;")
    return f'<a href="{url_esc}">{guc_esc}</a>'


def csv_to_html_table(input_csv: Path) -> str:
    with input_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"patch", "guc", "version", "doc", "url"}
        if not (required.issubset(set(reader.fieldnames or []))):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"{input_csv.name}: missing columns: {', '.join(missing)}")

        def esc(s: str) -> str:
            s = "" if s is None else str(s)
            return (
                s.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        lines = []
        lines.append("<table>")
        lines.append("  <thead>")
        lines.append("    <tr>")
        lines.append("      <th>patch</th>")
        lines.append("      <th>guc</th>")
        lines.append("      <th>version</th>")
        lines.append("      <th>doc</th>")
        lines.append("    </tr>")
        lines.append("  </thead>")
        lines.append("  <tbody>")

        for row in reader:
            patch = esc(row.get("patch", ""))
            guc = row.get("guc", "")
            version = esc(row.get("version", ""))
            doc = esc(row.get("doc", ""))
            url = row.get("url", "")

            lines.append("    <tr>")
            lines.append(f"      <td>{patch}</td>")
            lines.append(f"      <td>{make_html_link(guc, url)}</td>")
            lines.append(f"      <td>{version}</td>")
            lines.append(f"      <td>{doc}</td>")
            lines.append("    </tr>")

        lines.append("  </tbody>")
        lines.append("</table>")
        return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert CSV summary with GUC links to an HTML table for Confluence."
    )
    p.add_argument(
        "input_csv",
        nargs="?",
        default=DEFAULT_INPUT,
        help=f"Input CSV. Defaults to {DEFAULT_INPUT}",
    )
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output file. Defaults to <input_csv>.confluence.html.txt",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    input_csv = Path(args.input_csv).expanduser().resolve()
    if not input_csv.is_file():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = Path(str(input_csv) + ".confluence.html.txt")

    out_text = csv_to_html_table(input_csv)
    output_path.write_text(out_text, encoding="utf-8")
    print(f"Создан HTML table for Confluence: {output_path}")


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

