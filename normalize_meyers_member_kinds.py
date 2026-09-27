"""
Applies the Meyers Gazetteer print convention to migration/meyers_place_structure.json:
within one parent's type-heading member list, only the first member in a run of
same-type entries carries an explicit type-abbreviation prefix; later entries in
that run carry the type forward implicitly. This resolves that carry-forward and applies four confirmed prefix
substitutions: two abbreviation variants (Koln. -> Kol., Forsthr. -> Forsth.),
a known OCR error (Bw. -> Vw.), and a known Haeuser-plural/canonical-type
substitution (Hr. -> H.).

Read-only against migration/meyers_place_structure.json; writes only
migration/meyers_member_kinds_normalized.json. Does not read or write
migration/meyers_members_with_urls.json.

Run with: python3 scripts/normalize_meyers_member_kinds.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION_DIR = ROOT / "migration"

# The 15 distinct non-null `kind` values used in meyers_members_with_urls.json,
# confirmed to cover every prefixed raw member string in meyers_place_structure.json.
# Sorted longest-first so "D. u. Rg." matches before the shorter "D." prefix.
KNOWN_KIND_PREFIXES = sorted(
    [
        "D. u. Rg.",
        "Etabl.",
        "Forsthr.",
        "Gsth.",
        "Gut",
        "Hof",
        "Hrgr.",
        "Hr.",
        "H.",
        "Kol.",
        "Koln.",
        "Ml.",
        "Vw.",
        "Bw.",
        "D.",
    ],
    key=len,
    reverse=True,
)

NORMALIZE = {"Koln.": "Kol.", "Forsthr.": "Forsth.", "Bw.": "Vw.", "Hr.": "H."}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def match_prefix(raw):
    for prefix in KNOWN_KIND_PREFIXES:
        if raw == prefix or raw.startswith(prefix + " "):
            return prefix
    return None


def parse_member_list(raw_members):
    current_kind = None
    parsed = []
    for raw in raw_members:
        prefix = match_prefix(raw)
        if prefix is not None:
            name = raw[len(prefix):].strip()
            kind_raw = prefix
            current_kind = NORMALIZE.get(prefix, prefix)
        else:
            name = raw
            kind_raw = None
        parsed.append({"raw": raw, "name": name, "kind_raw": kind_raw, "kind": current_kind})
    return parsed


def main():
    structure = load(MIGRATION_DIR / "meyers_place_structure.json")

    result = {}
    total = explicit = inherited = both_null = 0

    for slug, place in structure.items():
        members_out = {}
        for type_heading, raw_members in place.get("members", {}).items():
            parsed = parse_member_list(raw_members)
            members_out[type_heading] = parsed
            for entry in parsed:
                total += 1
                if entry["kind_raw"] is not None:
                    explicit += 1
                elif entry["kind"] is not None:
                    inherited += 1
                else:
                    both_null += 1
        result[slug] = {"name": place["name"], "members": members_out}

    out_path = MIGRATION_DIR / "meyers_member_kinds_normalized.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Total member rows: {total}")
    print(f"Explicit prefix: {explicit}")
    print(f"Carried forward: {inherited}")
    print(f"Unresolved (no prefix, nothing to inherit): {both_null}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
