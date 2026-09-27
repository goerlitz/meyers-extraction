"""
Beschaffung (nicht Auswertung!) der Meyers-Rohdateien je Ort.

Lädt für jeden Ort mit gesetztem link_meyersgaz drei Dateien aus
meyersgaz.org in migration/meyers_cache/ herunter:

  {place_id}.html  - die Ortsseite (enthält die Fundstellenangabe, z.B.
                      "Volume 1, Page 38")
  {place_id}.png   - der enge Bildausschnitt des Eintrags
  {place_id}.pdf   - die volle gescannte Lexikonseite (mehrere Einträge,
                      der gesuchte ist farbig hervorgehoben)

Dieses Skript extrahiert nichts. Die drei Dateien sind reine Rasterbilder /
HTML ohne nutzbare Textebene; die eigentliche Transkription erfordert
Bild-/PDF-Lesefähigkeit (Vision) und ist ein separater, von Claude direkt
ausgeführter Durchlauf (siehe migration/meyers_raw_compare.txt).

Verarbeitet alle Orte mit gesetztem link_meyersgaz.

Wiederholt aufrufbar: bereits gecachte Dateien werden nicht neu geladen.

Run with: python3 scripts/fetch_meyers_entries.py
"""

import gzip
import http.client
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "migration" / "meyers_cache"

USER_AGENT = "wartenberg-verzeichnis-meyers-fetch/1.0 (Kontakt: siehe Projekt-README)"
REQUEST_DELAY_SECONDS = 1.0

MEYERS_ID_RE = re.compile(r"/place/(\d+)$")


def load_places():
    with open(DATA_DIR / "places.json", encoding="utf-8") as f:
        return json.load(f)["places"]


def meyers_id(link):
    match = MEYERS_ID_RE.search(link)
    if not match:
        return None
    return match.group(1)


def fetch(url, retries=3):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except (urllib.error.URLError, OSError, http.client.HTTPException):
            if attempt == retries:
                raise
            time.sleep(REQUEST_DELAY_SECONDS * attempt)


def fetch_if_missing(url, target_path):
    if target_path.exists():
        return "cached"
    data = fetch(url)
    target_path.write_bytes(data)
    time.sleep(REQUEST_DELAY_SECONDS)
    return "downloaded"


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    places = [p for p in load_places() if p.get("link_meyersgaz")]

    errors = []
    for place in places:
        place_id = place["id"]
        gaz_id = meyers_id(place["link_meyersgaz"])
        if gaz_id is None:
            errors.append(f"{place_id}: konnte keine Meyers-ID aus {place['link_meyersgaz']!r} lesen")
            continue

        targets = {
            f"https://www.meyersgaz.org/place/{gaz_id}": CACHE_DIR / f"{place_id}.html",
            f"https://www.meyersgaz.org/entryimages/{gaz_id}.png": CACHE_DIR / f"{place_id}.png",
            f"https://www.meyersgaz.org/entrypdf/{gaz_id}": CACHE_DIR / f"{place_id}.pdf",
        }
        for url, target_path in targets.items():
            try:
                status = fetch_if_missing(url, target_path)
                print(f"{place_id}: {status} {url}")
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                errors.append(f"{place_id}: {url} - {exc}")

    if errors:
        (CACHE_DIR / "fehler.txt").write_text("\n".join(errors) + "\n", encoding="utf-8")
        print(f"\n{len(errors)} Fehler, siehe migration/meyers_cache/fehler.txt")
    else:
        error_file = CACHE_DIR / "fehler.txt"
        if error_file.exists():
            error_file.unlink()
        print("\nKeine Fehler.")


if __name__ == "__main__":
    main()
