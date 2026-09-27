"""
Verifies migration/meyers_members_with_urls.json against the live meyersgaz.org
pages: fetches each member's own place page, reads its name/volume/page/type,
and flags entries where the name or expected kind disagrees with the website.

The expected kind comes from migration/meyers_member_kinds_normalized.json, not
from meyers_members_with_urls.json's own (partly null, partly un-normalized)
kind field: the normalized file already resolves the print-convention
carry-forward and the Koln./Forsthr. abbreviation variants. The two files are
matched up positionally (both are derived from meyers_place_structure.json in
the same order); a name/parent mismatch at any position aborts the run rather
than silently comparing the wrong pair.

Read-only against both input JSON files; writes only
migration/meyers_members_verified.txt.

Run with: python3 scripts/fetch_meyers_members.py [--limit N]

--limit N processes only the first N entries that have a meyers_url. Entries
with meyers_url: null are not counted against the limit and may not appear at
all in a limited run.
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION_DIR = ROOT / "migration"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_meyers_entries import fetch, REQUEST_DELAY_SECONDS  # noqa: E402

NAME_RE = re.compile(r'var placeName = "(.*?)";')
FIELD_RE = re.compile(r"<td class='type entry'>(Volume|Page|Type)</td><td class='entry'>(.*?)</td>")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def flatten_normalized(structure):
    """Flattens meyers_member_kinds_normalized.json in the same (parent, then
    type-heading, then list order) traversal used to build it, so position i
    here corresponds to position i in meyers_members_with_urls.json."""
    flat = []
    for slug, place in structure.items():
        for type_heading, parsed_members in place["members"].items():
            for member in parsed_members:
                flat.append({"parent_name": place["name"], "name": member["name"], "kind": member["kind"]})
    return flat


def pair_with_expected_kind(entries, normalized_flat):
    """Zips each entry with its expected kind by position, verifying name and
    parent agree rather than assuming the two files stay aligned."""
    if len(entries) != len(normalized_flat):
        raise AssertionError(
            f"meyers_members_with_urls.json has {len(entries)} entries but "
            f"meyers_member_kinds_normalized.json has {len(normalized_flat)}"
        )

    pairs = []
    for i, (entry, norm) in enumerate(zip(entries, normalized_flat)):
        entry_parent_name = (entry.get("parent") or {}).get("name")
        if entry.get("name") != norm["name"] or entry_parent_name != norm["parent_name"]:
            raise AssertionError(
                f"position {i} misaligned: meyers_members_with_urls.json has "
                f"{entry.get('name')!r} (parent {entry_parent_name!r}), "
                f"meyers_member_kinds_normalized.json has {norm['name']!r} (parent {norm['parent_name']!r})"
            )
        pairs.append((entry, norm["kind"]))
    return pairs


def extract(html_text):
    """Purely structural: returns the raw findings, with no error decisions.
    `Type` is genuinely multi-valued (a page can list more than one), so
    `kinds` keeps every match; `volume_matches`/`page_matches` keep every
    match too, so callers can detect an unexpected repeat instead of a
    match dict silently discarding it."""
    name_match = NAME_RE.search(html_text)
    rows = FIELD_RE.findall(html_text)

    def values(field):
        return [html.unescape(v).strip() for k, v in rows if k == field]

    return {
        "name": html.unescape(name_match.group(1)).strip() if name_match else None,
        "volume_matches": values("Volume"),
        "page_matches": values("Page"),
        "kinds": values("Type"),
    }


def validate_extracted(raw):
    """Decides what's wrong with a raw extract() result, separately from
    parsing it. Returns (normalized_fields_or_None, error_or_None)."""
    if raw["name"] is None or not raw["volume_matches"] or not raw["page_matches"] or not raw["kinds"]:
        missing = [
            field
            for field, values in (
                ("name", [raw["name"]] if raw["name"] is not None else []),
                ("volume", raw["volume_matches"]),
                ("page", raw["page_matches"]),
                ("kind", raw["kinds"]),
            )
            if not values
        ]
        return None, f"missing {','.join(missing)}"

    for field, values in (("volume", raw["volume_matches"]), ("page", raw["page_matches"])):
        if len(values) > 1:
            return None, f"unexpected multiple {field} matches ({len(values)})"

    return {
        "name": raw["name"],
        "volume": raw["volume_matches"][0],
        "page": raw["page_matches"][0],
        "kinds": raw["kinds"],
    }, None


def format_line(entry, expected_kind, fields=None, diffs=None, status=None):
    json_name = entry.get("name") or ""
    expected_kind = expected_kind or ""
    url = entry.get("meyers_url") or ""

    if status == "NO_URL":
        parent_name = (entry.get("parent") or {}).get("name") or ""
        return f"{json_name} | parent={parent_name} | url= | NO_URL"

    if status is not None and status.startswith("ERROR"):
        return f"{json_name} | url={url} | {status}"

    web_name = fields["name"] or ""
    web_kinds = ";".join(fields["kinds"])
    tail = "OK" if not diffs else f"DIFF: {','.join(diffs)}"
    return (
        f"{json_name} | url={url} | name: json={json_name} web={web_name} "
        f"| kind: expected={expected_kind} web={web_kinds} | volume={fields['volume']} page={fields['page']} | {tail}"
    )


def process_entry(entry, expected_kind):
    if not entry.get("meyers_url"):
        return format_line(entry, expected_kind, status="NO_URL"), "NO_URL"

    try:
        body = fetch(entry["meyers_url"])
    except (urllib.error.URLError, OSError) as exc:
        return format_line(entry, expected_kind, status=f"ERROR: {exc}"), "ERROR"

    html_text = body.decode("utf-8", errors="replace")
    fields, error = validate_extracted(extract(html_text))
    if error:
        return format_line(entry, expected_kind, status=f"ERROR: {error}"), "ERROR"

    diffs = []
    json_name = entry.get("name") or ""
    if json_name != fields["name"]:
        diffs.append("name")
    if (expected_kind or "") not in fields["kinds"]:
        diffs.append("kind")

    status = "OK" if not diffs else "DIFF"
    return format_line(entry, expected_kind, fields=fields, diffs=diffs), status


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="process only the first N entries that have a meyers_url "
        "(entries with meyers_url: null are not counted and may be excluded entirely)",
    )
    args = parser.parse_args()

    entries = load(MIGRATION_DIR / "meyers_members_with_urls.json")
    normalized_structure = load(MIGRATION_DIR / "meyers_member_kinds_normalized.json")
    pairs = pair_with_expected_kind(entries, flatten_normalized(normalized_structure))

    total = len(pairs)
    with_url = [pair for pair in pairs if pair[0].get("meyers_url")]

    if args.limit:
        # Limited run: only the first N url-bearing entries, in their
        # original relative order. NO_URL entries are deliberately excluded,
        # even if they would have appeared earlier in the full list.
        run_pairs = with_url[: args.limit]
        limited = args.limit < len(with_url)
    else:
        run_pairs = pairs
        limited = False

    fetch_positions = [i for i, (entry, _) in enumerate(run_pairs) if entry.get("meyers_url")]
    last_fetch_position = fetch_positions[-1] if fetch_positions else None

    lines = []
    counts = {"OK": 0, "DIFF": 0, "NO_URL": 0, "ERROR": 0}

    for i, (entry, expected_kind) in enumerate(run_pairs):
        line, status = process_entry(entry, expected_kind)
        lines.append(line)
        counts[status] += 1

        if entry.get("meyers_url") and i != last_fetch_position:
            time.sleep(REQUEST_DELAY_SECONDS)

    out_path = MIGRATION_DIR / "meyers_members_verified.txt"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if limited:
        print(f"Processed {len(run_pairs)} of {total} entries (LIMITED RUN)")
    else:
        assert sum(counts.values()) == total, f"expected {total} rows, got {sum(counts.values())}"

    print(f"OK={counts['OK']} DIFF={counts['DIFF']} NO_URL={counts['NO_URL']} ERROR={counts['ERROR']}")
    print(f"Wrote {out_path}")

    return 1 if counts["ERROR"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
