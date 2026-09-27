"""
Extracts a focused name/kind diff report from migration/meyers_members_verified.txt:
every place where the JSON name disagrees with the website, and every place
where the expected (normalized) kind disagrees with the website, listed
separately for direct review. Diffs are recomputed from the parsed
expected/web values, not trusted from the source file's own trailing status,
which is instead used as a consistency cross-check on that file. The website
can legitimately list more than one kind per page (web values are ";"-joined
in meyers_members_verified.txt); a row's kind counts as matching if the
expected kind is any one of them.

Rows whose meyersgaz.org url is shared by more than one member entry (see
scripts/audit_duplicate_meyers_urls.py) are marked [DUPLICATE_URL]. This is a
neutral flag, not an assertion that the row is wrong.

Read-only against its inputs; writes only migration/meyers_members_diffs.txt.

Run with: python3 scripts/report_meyers_diffs.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION_DIR = ROOT / "migration"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_duplicate_meyers_urls import find_duplicate_urls, load  # noqa: E402

NORMAL_RE = re.compile(
    r"^(?P<place>.*?) \| url=(?P<url>.*?) \| "
    r"name: json=(?P<json_name>.*?) web=(?P<web_name>.*?) \| "
    r"kind: expected=(?P<expected_kind>.*?) web=(?P<web_kind>.*?) \| "
    r"volume=(?P<volume>.*?) page=(?P<page>.*?) \| "
    r"(?P<tail>OK|DIFF:.*)$"
)
NO_URL_RE = re.compile(r"^ \| parent=(?P<parent>.*?) \| url= \| NO_URL$")
ERROR_RE = re.compile(r"^(?P<place>.*?) \| url=(?P<url>.*?) \| (?P<tail>ERROR:.*)$")


def escape(value):
    return value.replace('"', '\\"')


def parse_lines(text):
    normal, no_url, error = [], [], []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = NORMAL_RE.match(line)
        if match:
            normal.append((line_no, match.groupdict()))
            continue
        match = NO_URL_RE.match(line)
        if match:
            no_url.append(line_no)
            continue
        match = ERROR_RE.match(line)
        if match:
            error.append(line_no)
            continue
        raise ValueError(f"Unrecognized line {line_no} in meyers_members_verified.txt: {line!r}")
    return normal, no_url, error


def tail_fields(tail, line_no):
    if tail == "OK":
        return set()
    if tail.startswith("DIFF:"):
        return {field.strip() for field in tail[len("DIFF:"):].split(",")}
    raise ValueError(f"Unexpected tail on line {line_no}: {tail!r}")


def main():
    verified_text = (MIGRATION_DIR / "meyers_members_verified.txt").read_text(encoding="utf-8")
    normal, no_url, error = parse_lines(verified_text)

    source_entries = load(MIGRATION_DIR / "meyers_members_with_urls.json")
    duplicate_urls = set(find_duplicate_urls(source_entries).keys())

    name_diffs = []
    kind_diffs = []
    inconsistent = False

    for line_no, fields in normal:
        place = fields["place"]
        url = fields["url"]
        json_name, web_name = fields["json_name"], fields["web_name"]
        expected_kind, web_kind = fields["expected_kind"], fields["web_kind"]
        web_kinds = web_kind.split(";") if web_kind else []

        name_differs = json_name != web_name
        kind_differs = expected_kind not in web_kinds

        computed = set()
        if name_differs:
            computed.add("name")
        if kind_differs:
            computed.add("kind")

        if computed != tail_fields(fields["tail"], line_no):
            print(
                f"INCONSISTENT line {line_no} ({place}): tail says {fields['tail']!r}, "
                f"recomputed diffs are {sorted(computed) or ['none']}"
            )
            inconsistent = True

        marker = " [DUPLICATE_URL]" if url in duplicate_urls else ""

        if name_differs:
            name_diffs.append(
                f'{place} [line {line_no}]: json="{escape(json_name)}" web="{escape(web_name)}"{marker}'
            )
        if kind_differs:
            kind_diffs.append(
                f'{place} [line {line_no}]: expected="{escape(expected_kind)}" web="{escape(web_kind)}"{marker}'
            )

    report_lines = [f"=== Name differences ({len(name_diffs)}) ==="]
    report_lines.extend(name_diffs)
    report_lines.append("")
    report_lines.append(f"=== Kind differences ({len(kind_diffs)}) ===")
    report_lines.extend(kind_diffs)

    out_path = MIGRATION_DIR / "meyers_members_diffs.txt"
    out_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    duplicate_marked = sum(1 for line in name_diffs + kind_diffs if "[DUPLICATE_URL]" in line)
    total = len(normal) + len(no_url) + len(error)

    print(f"Name differences: {len(name_diffs)}")
    print(f"Kind differences: {len(kind_diffs)}")
    print(f"DUPLICATE_URL-marked rows: {duplicate_marked}")
    print(f"Parsed: {len(normal)} normal, {len(no_url)} NO_URL, {len(error)} ERROR (total {total})")
    print(f"Wrote {out_path}")

    return 1 if inconsistent else 0


if __name__ == "__main__":
    raise SystemExit(main())
