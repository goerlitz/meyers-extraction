"""
Fetches a single AGOFF district page (e.g. https://agoff.de/?p=102289) and
writes the deduplicated place names found in its "Ort" tables to
data/agoff_<id>.txt, one name per line.
"""

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parent / "data"

POPULATION_SUFFIX_RE = re.compile(r"\s*\([\d.\s]+\)\s*$")


def fetch_page(url):
    try:
        with urllib.request.urlopen(url) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except (urllib.error.URLError, OSError) as exc:
        raise SystemExit(f"Failed to fetch {url}: {exc}")


def page_id(url):
    values = parse_qs(urlparse(url).query).get("p", [])
    if len(values) != 1:
        raise SystemExit(f"URL must contain exactly one 'p' parameter, found: {values!r}")
    return values[0]


def clean_name(text):
    return POPULATION_SUFFIX_RE.sub("", text).strip()


def first_cell_text(row):
    cell = row.find(["td", "th"])
    return cell.get_text(separator=" ", strip=True) if cell else ""


def extract_place_names(html):
    soup = BeautifulSoup(html, "html.parser")
    names = []
    for table in soup.find_all("table"):
        # AGOFF marks header rows with plain <td><b>...</b></td>, not <th>, and a
        # <thead> caption row (e.g. "Stadtgemeinden") precedes the real "Ort" header
        # row inside <tbody> - so the header is identified by its text, not by tag
        # or row position.
        in_relevant_section = False
        for row in table.find_all("tr"):
            text = first_cell_text(row)
            if text == "Ort":
                in_relevant_section = True
            elif in_relevant_section and text:
                names.append(clean_name(text))
    return list(dict.fromkeys(name for name in names if name))


def main():
    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument("url", help="AGOFF page URL, e.g. https://agoff.de/?p=102289")
    args = arg_parser.parse_args()

    pid = page_id(args.url)
    html = fetch_page(args.url)
    names = extract_place_names(html)
    if not names:
        raise SystemExit("No place names found.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target_path = DATA_DIR / f"agoff_{pid}.txt"
    target_path.write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"{len(names)} place names written to {target_path}")


if __name__ == "__main__":
    sys.exit(main())
