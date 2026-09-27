# Meyers Gazetteer Hierarchical Place Extraction

## Overview

This project extracts, resolves, structures, and verifies historical place data from the **Meyers Gazetteer**.

Starting from an initial list of places from any source — for example AGO-Ost, a manually curated list, or another historical dataset — the workflow identifies the corresponding Meyers entries, extracts their place metadata and dependent-place relationships, resolves those dependent places against their own Meyers entries, and builds a hierarchical dataset that preserves both the original source observations and the canonical Meyers data.

The project is not only an extraction pipeline. It also acts as a **verification and discrepancy-detection workflow**. OCR errors, transcription mistakes, ambiguous names, source-print conventions, Meyers printing errors, and inconsistent classifications are surfaced explicitly rather than silently normalized away.

---

## Goals

The main goals are:

1. Resolve an initial list of historical places against Meyers Gazetteer.
2. Extract structured metadata from each Meyers place page.
3. Extract hierarchical relationships from the corresponding Meyers entry scans/PDFs.
4. Resolve dependent places recursively against Meyers.
5. Preserve source-bound observations separately from normalized or canonical values.
6. Verify extracted names and place types against the resolved Meyers place pages.
7. Detect and classify discrepancies such as OCR errors, transcription errors, print errors, ambiguous matches, or genuinely inconsistent data.
8. Produce a reusable hierarchical representation of the historical place network.

---

## Problem

Meyers Gazetteer data is not available as a clean hierarchical dataset.

A place entry may contain:

- one or more place types such as `D.`, `Rg.`, `Gut`, `St.`, or `Fl.`
- dependent places listed under headings such as `Zum D.`, `Zum Rg.`, `Dazu`, or parenthetical `(mit ...)` structures
- abbreviated member types such as `Kol.`, `H.`, `Hr.`, `Hrgr.`, `Vw.`, `Bw.`, `Forsth.`, and others
- multiple dependent places of the same type where the type abbreviation is printed only once and implicitly applies to the following names
- multiple same-named dependent places with different types
- multiple `Type` rows on a single Meyers place page

The source also contains OCR/transcription problems and occasional print errors. Therefore, a simple "extract one name and one type per place" model is insufficient.

The workflow must distinguish between:

- what was printed or transcribed in a parent entry
- what was inferred from Meyers' formatting conventions
- what the resolved Meyers place page reports
- what has been normalized for the project data model

---

## Core Principle: Preserve Source and Interpretation Separately

The project treats Meyers information as **source-bound observations**, not as timeless or automatically authoritative facts.

Raw source values should be preserved wherever practical, while normalized values are stored separately.

For example:

```json
{
  "raw": "Koln. Bendschine",
  "name": "Bendschine",
  "kind_raw": "Koln.",
  "kind": "Kol."
}
```

For a type inherited from a previous entry in the same printed run:

```json
{
  "raw": "Grabek",
  "name": "Grabek",
  "kind_raw": null,
  "kind": "Kol."
}
```

This makes it possible to distinguish:

- literal source transcription
- normalization
- carry-forward interpretation
- canonical data from the resolved Meyers page

---

## High-Level Workflow

### 1. Start with an Initial Place List

The pipeline begins with a list of historical places from an external or internal source.

Possible sources include:

- AGO-related datasets
- archival or historical lists
- manually curated place lists
- migration data from an existing application

The initial list is treated as a set of search targets, not as canonical Meyers data.

### 2. Resolve Main Places Against Meyers

Each initial place is matched to a Meyers Gazetteer place page.

Matching may require more than exact name equality because historical spelling, OCR errors, and Meyers print errors occur.

Disambiguation may use:

- name similarity
- Kreis / district information
- known geographic context
- parent/dependent relationships
- surrounding Meyers entry information

The resolved Meyers URL becomes the stable reference for later extraction.

### 3. Extract Main-Place Metadata

For every resolved main place, structured values are extracted from the Meyers place page.

Typical fields include:

- canonical Meyers place name
- Meyers place type(s)
- volume
- page
- Meyers URL

A Meyers page may contain **multiple `Type` rows**. The extractor must preserve all of them.

Example:

```text
Breschine
Types: D.; Vw.
```

The page must therefore be modeled as:

```json
{
  "canonical_name": "Breschine",
  "meyers_types": ["D.", "Vw."],
  "volume": "1",
  "page": "238"
}
```

not as a single `type` field.

### 4. Extract Hierarchical Structure from the Meyers Entry

The hierarchy is not fully represented by the structured HTML metadata.

Dependent places must be extracted from the linked entry scan/PDF or image.

Relevant source structures include:

- `Zum D.`
- `Zum Rg.`
- `Dazu`
- `(mit ...)`
- other printed member lists or dependent-place groupings

These entries are captured as source-bound structure rather than immediately flattened into a canonical hierarchy.

A main place may have multiple structural contexts, for example:

```text
Parent: Lassisken

D.:
  Koln. Bendschine
  Frischfeuer
  Grabek
  Jeziore
  Poremben

Rg.:
  Forsthr. Bendschine
  Grabek
```

The same member name may occur more than once under different type-heading lists. These occurrences remain separate records.

---

## Member-Type Carry-Forward

Meyers often prints a type abbreviation only on the first place in a run.

Example:

```text
Koln. Bendschine, Frischfeuer, Grabek, Jeziore, Poremben
```

This means all following entries belong to the same type until a new explicit type marker appears.

The postprocessing step therefore applies carry-forward **only within the same `(parent, type-heading)` member list**.

It never carries a type:

- between different type headings
- between different parents
- across unrelated lists

Example normalized output:

```json
[
  {
    "raw": "Koln. Bendschine",
    "name": "Bendschine",
    "kind_raw": "Koln.",
    "kind": "Kol."
  },
  {
    "raw": "Frischfeuer",
    "name": "Frischfeuer",
    "kind_raw": null,
    "kind": "Kol."
  },
  {
    "raw": "Grabek",
    "name": "Grabek",
    "kind_raw": null,
    "kind": "Kol."
  }
]
```

---

## Kind Normalization

Only confirmed transformations are normalized.

Currently confirmed mappings include:

```text
Koln.    -> Kol.
Forsthr. -> Forsth.
Bw.      -> Vw.
Hr.      -> H.
```

The reasons differ:

- `Koln.` → `Kol.`: source/list abbreviation convention
- `Forsthr.` → `Forsth.`: source/list abbreviation convention
- `Bw.` → `Vw.`: confirmed OCR/transcription confusion
- `Hr.` → `H.`: plural/list convention for Häuser versus Meyers' canonical house type code

No broader fuzzy normalization should be applied automatically.

Unconfirmed differences such as `Hrgr.` vs. `Hr.` or `Hof` vs. `Hrgr.` must remain visible until individually understood.

---

## 5. Resolve Every Member Against Meyers

Each extracted member is searched against Meyers and matched to its own place entry.

This produces a `meyers_url` for the member.

Matching may require disambiguation using:

- canonical or approximate name
- Kreis Groß Wartenberg
- parent context
- member type
- known hierarchical relationship

Duplicate names are normal and must not be collapsed.

A single Meyers place page may legitimately contain multiple types and may correspond to more than one parent/member relationship.

For example, Breschine can occur in two contexts:

```text
Dobrzetz (D.)  -> Breschine -> expected kind D.
Dobrzetz (Rg.) -> Breschine -> expected kind Vw.
```

while the resolved Meyers page reports:

```text
Types: D.; Vw.
```

Both relationships are therefore valid against the same resolved Meyers page.

---

## 6. Recursive Resolution

Dependent places are not terminal strings.

Once a member has been resolved to its own Meyers entry, it becomes another Meyers place that can itself provide:

- canonical name
- place type(s)
- volume/page
- further dependent places
- additional hierarchy information

The extraction process can therefore continue recursively.

Conceptually:

```text
initial place
  -> Meyers place
     -> dependent place
        -> Meyers place
           -> dependent place
              -> ...
```

Recursion must preserve provenance and avoid accidental merging solely by name.

Stable Meyers identifiers/URLs should be used to track already-resolved entities and avoid unnecessary repeated work.

---

## Suggested Data Model

The project benefits from separating **relationships** from **Meyers place entities**.

### MeyersPlace

Represents the canonical information obtained from a Meyers place page.

```json
{
  "meyers_url": "https://www.meyersgaz.org/place/10238002",
  "canonical_name": "Breschine",
  "meyers_types": ["D.", "Vw."],
  "volume": "1",
  "page": "238"
}
```

### MemberRelation

Represents one specific relationship observed in a parent entry.

```json
{
  "parent_name": "Dobrzetz",
  "parent_kind": "Rg.",
  "source_name": "Breschine",
  "kind_raw": "Bw.",
  "kind": "Vw.",
  "meyers_url": "https://www.meyersgaz.org/place/10238002"
}
```

A second relationship may point to the same Meyers place:

```json
{
  "parent_name": "Dobrzetz",
  "parent_kind": "D.",
  "source_name": "Breschine",
  "kind_raw": "D.",
  "kind": "D.",
  "meyers_url": "https://www.meyersgaz.org/place/10238002"
}
```

This prevents the model from incorrectly assuming:

```text
one relationship == one Meyers page
```

or:

```text
one Meyers page == one type
```

---

## Main-Place Structure

For main places, the project may maintain source-specific `PlaceStructure` assertions.

Example normalized mappings:

```text
D.     -> dorf
Rg.    -> rittergut
Gut    -> gut
Fl.    -> flecken
St.    -> stadt
KrSt.  -> stadt
```

The original Meyers wording should remain available in the source/citation layer.

`Gut` and `Rittergut` remain distinct because Meyers distinguishes them. The project should not infer legal equivalence or non-equivalence beyond what the source establishes.

---

## Citations and Provenance

Every extracted structural assertion should retain enough information to trace it back to Meyers.

Useful provenance fields include:

- Meyers URL
- volume
- page
- parent entry
- original member string
- raw type prefix
- normalized type
- extraction source (HTML / PDF / image)
- optional extraction notes

The goal is that every normalized relationship can be reconstructed from the source evidence.

---

## Validation

Validation is a separate stage from extraction.

For each resolved member:

### Name Validation

Compare:

```text
source/transcribed name
vs.
canonical name from the resolved Meyers page
```

Differences are retained for review rather than automatically overwritten.

Typical causes include:

- OCR errors
- transcription errors
- spelling variants
- additional explanatory text in the parent entry
- genuine Meyers print errors

Examples encountered during development include cases such as:

```text
Drossenschin -> Drosdenschin
Frischeuer   -> Frischfeuer
Smolof       -> Smolok
```

A mismatch does not automatically mean the Meyers page is correct; the discrepancy itself is the useful result.

### Kind Validation

Compare the normalized relationship kind against **all types reported by the resolved Meyers page**.

Correct logic:

```text
expected_kind in meyers_types
```

not:

```text
expected_kind == last_type_on_page
```

This distinction is essential because some Meyers pages contain multiple `Type` rows.

---

## Discrepancy Classification

Remaining discrepancies should be reviewed and classified rather than automatically normalized.

Useful categories include:

### OCR / Transcription Error

The source transcription misread the printed value.

Example pattern:

```text
Bw. -> Vw.
```

### Source-List Convention

The printed parent list uses a plural or run-level abbreviation that maps to a canonical Meyers type.

Example:

```text
Hr. -> H.
```

### Meyers Print Error

The Meyers printed entry itself appears to contain an error.

Such cases should be documented explicitly rather than "corrected" without provenance.

### Wrong Meyers Match

The correct historical place exists, but the resolver selected another same-named or similar Meyers entry.

This is especially important for names that occur multiple times with different types.

### Ambiguous / Unresolved

The available evidence is insufficient to decide confidently.

These cases remain unresolved and should not be normalized by guesswork.

### Genuine Data Discrepancy

The source relationship and resolved Meyers place appear to disagree even after extraction errors, list conventions, and matching errors have been ruled out.

---

## Known Challenges

### Historical Name Ambiguity

Many places share generic names such as:

- Neue Welt
- Dreihäuser
- Jeziore
- Poremben

Name equality alone is therefore not a reliable identifier.

### OCR and Transcription Errors

Single-character errors can materially affect matching.

The resolver must tolerate spelling differences without silently rewriting source data.

### Meyers Print Errors

Meyers itself is not error-free.

Canonical website data must therefore be treated as another source observation, not as an unquestionable truth.

### Multiple Types on One Page

A single Meyers place page can contain several type rows.

The parser must preserve all of them.

### Implicit Type Runs

Dependent-place types can be inherited from an earlier explicit type marker in the same printed sequence.

### Same Name, Different Member Types

A parent can contain multiple same-named dependent places distinguished by type.

They must not be merged merely because their names match.

### Source Hierarchy vs. Entity Identity

The hierarchy belongs to a particular source entry and context.

A member relationship is not identical to the canonical Meyers place entity it resolves to.

---

## Pipeline Structure

A clean implementation keeps the following stages separate:

```text
Initial place list
        |
        v
Main-place resolution
        |
        v
Meyers HTML extraction
        |
        v
PDF/image hierarchy extraction
        |
        v
Raw member structure
        |
        v
Member-kind postprocessing
  - prefix parsing
  - carry-forward
  - confirmed normalization
        |
        v
Member Meyers resolution
        |
        v
Canonical member-page extraction
  - name
  - all types
  - volume/page
        |
        v
Verification
  - name comparison
  - expected kind in Meyers types
        |
        v
Discrepancy classification
        |
        v
Recursive expansion
```

Each stage should have explicit inputs and outputs and should avoid silently modifying the source representation from earlier stages.

---

## Current Workflow Artifacts

The exact filenames may evolve, but the current workflow uses files such as:

```text
migration/meyers_place_structure.json
migration/meyers_member_kinds_normalized.json
migration/meyers_members_with_urls.json
migration/meyers_members_verified.txt
migration/meyers_members_diffs.txt
```

### `meyers_place_structure.json`

Raw hierarchical member structure extracted from the parent Meyers entries.

### `meyers_member_kinds_normalized.json`

Postprocessed representation of the member structure with:

- parsed member names
- raw type prefixes
- carry-forward type resolution
- confirmed kind normalization

### `meyers_members_with_urls.json`

Resolved member records with Meyers URLs and parent context.

### `meyers_members_verified.txt`

Merged verification output comparing expected values against data extracted from each resolved Meyers page.

### `meyers_members_diffs.txt`

Focused review report containing only remaining name and kind differences.

---

## Design Rules

The project follows several rules that are important for historical-data reliability:

1. **Do not discard raw source values.**
2. **Do not normalize a discrepancy until its meaning is understood.**
3. **Do not assume one place page has only one type.**
4. **Do not merge places solely because their names match.**
5. **Do not treat repeated Meyers URLs as automatically erroneous.**
6. **Do not carry member types across parent/type-heading boundaries.**
7. **Keep extraction, normalization, resolution, and validation separate.**
8. **Fail loudly on unexpected source shapes rather than silently selecting one value.**
9. **Preserve provenance for every interpreted field.**
10. **Treat discrepancies as research output, not merely as errors to suppress.**

---

## Current Status

The workflow currently supports:

- extraction of the main Meyers place structure
- extraction of dependent/member places
- member-type carry-forward
- confirmed abbreviation/OCR normalization
- member resolution to Meyers URLs
- extraction of canonical names, volume/page, and multiple Meyers types
- comparison of normalized expected kinds against all web-reported types
- name discrepancy reporting
- kind discrepancy reporting
- detection of cases requiring manual historical review

The remaining discrepancies are now small enough to inspect individually rather than being dominated by parser or normalization errors.

---

## Future Work

Potential next steps include:

- formalizing the recursive crawler/resolver
- storing Meyers entities and parent/member relationships as separate normalized records
- adding explicit discrepancy categories
- preserving both source spelling and canonical Meyers spelling in the final model
- adding automated regression tests for known multi-Type pages and carry-forward cases
- building a manual-review queue for ambiguous matches and source-print anomalies
- documenting every accepted normalization rule with examples and source reasoning
- extending the workflow to additional districts or initial place datasets

---

## Summary

This project turns Meyers Gazetteer from a collection of individual historical place entries into a verifiable hierarchical dataset.

The key methodological principle is to keep **source observation**, **normalization**, **entity resolution**, and **verification** separate.

That separation allows the workflow to handle the difficult cases that occur frequently in historical gazetteers: OCR mistakes, abbreviated list conventions, repeated names, multiple place types, hierarchy embedded in prose or scans, ambiguous matches, and even errors in the original printed source itself.
