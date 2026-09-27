# TODO: Meyers scripts pipeline refactor

Refactor the four existing Meyers scripts into `scripts/meyers/`, remove duplicated path/import
plumbing, and extract only the shared HTTP/page-parsing utilities that are already used by more
than one current script.

## Why

All 4 top-level scripts duplicate the same `ROOT`/`MIGRATION_DIR` path constants, and two of them
reach into a sibling script via a manual `sys.path.insert` hack instead of a real import:

- `fetch_meyers_members.py` imports `fetch`/`REQUEST_DELAY_SECONDS` from `fetch_meyers_entries.py`
  this way.
- `report_meyers_diffs.py` imports `find_duplicate_urls`/`load` from `audit_duplicate_meyers_urls.py`
  — a module that does not exist anywhere in this repo, so `report_meyers_diffs.py` cannot run at
  all today.

## Target structure

Only what's evidenced as actually shared today — not a speculative full pipeline architecture:

```text
scripts/meyers/
  fetch_places.py          # was fetch_meyers_entries.py
  normalize_members.py     # was normalize_meyers_member_kinds.py
  verify_members.py        # was fetch_meyers_members.py
  report_diffs.py          # was report_meyers_diffs.py
  common.py
  meyers_page.py
```

- **`common.py`** — only provably shared things: `ROOT`/`DATA_DIR`/`MIGRATION_DIR`/`CACHE_DIR`
  path constants (currently duplicated across the scripts), the JSON-load helper (currently
  duplicated in two scripts, missing in the third), and the HTTP fetch (`fetch()`, `USER_AGENT`,
  `REQUEST_DELAY_SECONDS`) already shared today between `fetch_meyers_entries.py` and
  `fetch_meyers_members.py` via the `sys.path.insert` hack.
- **`meyers_page.py`** — only the already-relevant Meyers page logic: extracting HTML fields
  (name/volume/page/all types) and validating the extracted structure, moved out of
  `fetch_meyers_members.py`.

### Explicitly not in scope right now

Not wrong ideas, just not evidenced as necessary refactor steps yet: `resolve_places.py`,
`extract_structure.py`, `resolve_members.py`, `models.py`, `matching.py`,
`kind_normalization.py`, `io_json.py`, `run_pipeline.py`.

### Known open issue (note, don't resolve here)

`report_meyers_diffs.py` currently fails to import because `audit_duplicate_meyers_urls.py`
doesn't exist. Decide separately whether/how duplicate-URL flagging is still wanted, rather than
presetting a `find_duplicate_urls()` as core matching logic — the earlier assumption that
duplicate Meyers URLs are inherently problematic already turned out to be wrong once.

## Steps

1. `git mv` the 4 existing files into `scripts/meyers/` under the new names above.
2. Add `scripts/meyers/common.py` with the path constants, the JSON-load helper, and `fetch()`/
   `USER_AGENT`/`REQUEST_DELAY_SECONDS` (moved out of `fetch_meyers_entries.py`).
3. Add `scripts/meyers/meyers_page.py` with the HTML field-extraction and validation functions
   (moved out of `fetch_meyers_members.py`).
4. Update `fetch_places.py` to import path constants from `common.py`; keep `load_places()`,
   `meyers_id()`, `fetch_if_missing()`, and `main()` as its own (place-specific, not shared).
5. Update `verify_members.py` to drop its `sys.path.insert` hack and import `fetch`/
   `REQUEST_DELAY_SECONDS` from `common.py` and the extraction/validation functions from
   `meyers_page.py`; behavior otherwise unchanged.
6. Update `normalize_members.py` to import path constants and the JSON-load helper from
   `common.py`; keep `KNOWN_KIND_PREFIXES`, `NORMALIZE`, `match_prefix()`, `parse_member_list()`
   in this script (not shared with any other script today).
7. Update `report_diffs.py` to drop its `sys.path.insert` hack and import the JSON-load helper
   from `common.py`; resolve the duplicate-URL-flagging question separately (see open issue
   above) before deciding what replaces the missing import.
8. Update each moved script's `Run with: python3 scripts/...` docstring line to its new
   `scripts/meyers/...` path.
