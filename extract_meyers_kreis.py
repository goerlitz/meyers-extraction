"""
Extracts every Meyers Gazetteer entry belonging to one Kreis (district) from
data/all.json, the bulk place index the meyersgaz.org search page itself
loads and filters client-side.

Read-only against data/all.json (must already exist; this script does not
fetch or cache anything). Writes only data/meyers_<kreis_slug>.json.

Run with: python3 extract_meyers_kreis.py "Gross Wartenberg"
"""

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


def load_all_json(path):
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Download it from https://www.meyersgaz.org/all.json "
            "and save it there before running this script."
        )
    body = path.read_bytes()
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return json.loads(body)


def matching_endings(all_json, kreis):
    prefix = f", {kreis},".casefold()
    return [(idx, text) for idx, text in all_json["Endings"] if text.casefold().startswith(prefix)]


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def extract_records(all_json, kreis):
    matches = matching_endings(all_json, kreis)
    ending_ids = {idx for idx, _ in matches}

    print(f"Matching Endings for {kreis!r}:")
    for idx, text in matches:
        print(f"  {idx}: {text}")

    place_desc = dict(all_json["PlaceDescList"])
    target_kreis = kreis.casefold()

    records = []
    for row in all_json["data"]:
        if row[4] not in ending_ids and row[2].casefold() != target_kreis:
            continue
        records.append({
            "id": row[0],
            "display_name": row[1],
            "name": row[2],
            "place_type": place_desc.get(row[6]) if row[6] else None,
        })
    return records


def main():
    arg_parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    arg_parser.add_argument("kreis", help='Kreis to extract, e.g. "Gross Wartenberg"')
    args = arg_parser.parse_args()

    all_json = load_all_json(DATA_DIR / "all.json")
    records = extract_records(all_json, args.kreis)

    target_path = DATA_DIR / f"meyers_{slugify(args.kreis)}.json"
    target_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(records)} entries found for Kreis {args.kreis!r}; wrote {target_path}")


if __name__ == "__main__":
    sys.exit(main())
