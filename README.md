# whale-ici-data

A unified collection of publicly released sperm whale (*Physeter macrocephalus*)
coda inter-click interval (ICI) datasets, packaged in a single consistent
schema for downstream analysis.

This repository **only** stores raw ICI sequences plus provenance and
identification metadata (whale photo-ID, social unit, clan, location). It does
**not** include post-processed features such as rhythm/tempo categories,
ornamentation flags, or rubato measurements — those should be computed
downstream from the ICIs.

## Contents

| Source | Codas | Region | Distinct whales (with ID) | Period |
|---|---:|---|---:|---|
| `sharma2024_dswp` — Sharma et al. 2024 ([Nat Comm 15:3617](https://doi.org/10.1038/s41467-024-47221-8)) | 8,872 | Dominica, EC clans | 35 (3,014 codas attributed) | 2005-2018 |
| `sharma2025_birth` — Sharma et al. 2025 ([Sci Rep](https://doi.org/10.1038/s41598-025-27438-3)) | 5,731 | Dominica, single live-birth event | 0 (within-recording speaker tags only) | 2023 |
| `hersh2022_pacific` — Hersh et al. 2022 ([PNAS](https://doi.org/10.1073/pnas.2201692119), [OSF](https://osf.io/ae6pd/)) | 24,237 | Pacific (23 regions, 7 clans: FP, PALI, PO, REG, RI, SH, SI) | 0 (no persistent IDs in this release) | 1978-2017 |
| **Unified** | **38,840** | | | |

## Layout

```
whale-ici-data/
├── data/
│   ├── raw/                          # original published files, unmodified
│   │   ├── dswp_dominica_codas.csv
│   │   ├── sharma2025_birth.csv
│   │   ├── hersh2022_pacific_codas.csv
│   │   └── hersh2022_pacific_README.txt
│   ├── intermediate/                 # per-source unified-schema CSVs
│   └── unified/
│       └── codas_unified.csv         # final concatenated corpus (38,840 rows)
├── src/pipeline/
│   ├── schema.py                     # shared column definitions
│   ├── A_load_dswp.py
│   ├── B_load_birth.py
│   ├── D_merge_unified.py            # entry point — produces codas_unified.csv
│   ├── E_classify.py                 # fills in rhythm + extra_click columns
│   └── F_load_hersh_pacific.py
├── requirements.txt
├── LICENSE                           # CC BY 4.0
└── README.md
```

## Reproduce

```bash
pip install -r requirements.txt
python -m src.pipeline.D_merge_unified
```

That single command re-runs every loader and rewrites `data/unified/codas_unified.csv`.

## Schema

Every row in `codas_unified.csv` represents one coda.

| Column | Type | Description |
|---|---|---|
| `source` | str | Short paper key (`sharma2024_dswp`, `sharma2025_birth`, `hersh2022_pacific`) |
| `source_doi` | str | DOI of the source publication or data release |
| `source_coda_id` | str | Original coda identifier within the source file |
| `recording_id` | str | Recording session identifier (raw, source-specific). DSWP uses date as proxy. |
| `date` | str | Raw date string from source — **not** normalized; mixed formats (`DD/MM/YYYY`, `DD-MM-YYYY`, `2023`) |
| `time_in_recording_s` | float | Seconds from recording start; only populated for the birth dataset |
| `n_clicks` | int | Number of clicks in the coda |
| `coda_duration_s` | float | Sum of ICIs (= time from first to last click) |
| `whale_photo_id` | str | Persistent Caribbean photo-ID (e.g. `"5151"`); `NaN` if unattributed |
| `local_speaker_id` | str | Within-recording speaker tag (birth dataset only); **not** comparable across recordings |
| `social_unit` | str | Original social-unit identifier (study-specific; not cross-source comparable) |
| `clan` | str | Vocal clan label (`EC1`, `EC2`, `FP`, `PALI`, `PO`, `REG`, `RI`, `SH`, `SI`, …); `NaN` if unknown |
| `location` | str | Geographic region (free text). Hersh Pacific rows include the original abbreviation, e.g. `"Galapagos Islands (GAL)"`. |
| `latitude` | float | Decimal degrees of recording location. Currently populated only for Hersh 2022 Pacific rows; `NaN` for Caribbean sources, which did not release per-coda coordinates. |
| `longitude` | float | Decimal degrees of recording location. Same coverage caveat as `latitude`. |
| `rhythm` | int | 0–17 rhythm cluster id (Sharma 2024 numbering). Filled in by `E_classify` via nearest-centroid match against the labelled DSWP dialogues subset. `NaN` for codas with fewer than 2 ICIs. |
| `extra_click` | int | 0/1 ornament flag. Filled in by `E_classify` from temporally adjacent same-whale codas. `NaN` for any row without `recording_id` + `time_in_recording_s` (so all of `hersh2022_pacific`). |
| `ICI1` … `ICI40` | float | Inter-click intervals in seconds. `NaN` past `n_clicks - 1`. Max observed length is 40 clicks (birth dataset). |

## Important caveats

1. **Gero et al. 2016 Atlantic was excluded after measurement.** Fingerprinting
   on `(n_clicks, ICIs)` showed that all 4,930 Gero codas appear verbatim in
   the Sharma 2024 DSWP release across every social unit (1-11). The Gero
   companion file's WhaleID join attached ambiguous (`6070/6068`) IDs to 146
   DSWP rows that were otherwise un-attributed, but no codas were unique to
   Gero. The dataset is preserved in git history but is no longer in the
   pipeline.
2. **The birth dataset has no persistent whale IDs.** `SegmentWhale` from the
   source file is preserved as `local_speaker_id` in the form
   `"<recording>_seg<n>"`, which is unique within the file but tells you
   nothing about whether segment 1 in CETI23-277 is the same animal as
   segment 1 in CETI23-278.
3. **`hersh2022_pacific` has no per-coda timestamps and no individual IDs.**
   The OSF release exposes only repertoire-day group codes (kept as
   `recording_id`); `whale_photo_id`, `local_speaker_id`, `social_unit`, and
   `time_in_recording_s` are all `NaN` for these rows. Consequently the
   `extra_click` ornament classifier (which needs same-whale temporal
   neighbours) is skipped for the entire Pacific subset. `rhythm` is still
   assigned because that classifier needs only the ICIs.
4. **Hersh Pacific clan abbreviations are not the EC1/EC2 vocabulary.** The
   seven Pacific clans use the labels from Hersh et al. 2022: FP (Four-Plus),
   PALI (Palindrome), PO (Plus-One), REG (Regular), RI (Rapid Increasing),
   SH (Short), SI (Slow-Increasing). 682 codas are unassigned (`clan = NaN`)
   because their parent repertoires fell below the within-clan correlation
   threshold in the source paper.
5. **Hersh `source_coda_id` is mostly numeric, with two prefixed exceptions.**
   3,113 Galápagos codas (`WatGal###`) are Watkins-archive recordings
   re-annotated by Hersh, and three Southern New Zealand codas (`NZ0071`–
   `NZ0073`) have `latitude`/`longitude = NaN` because the source CSV had
   the literal string `"Unk"` for those coordinates.
6. **`social_unit` semantics are study-specific.** DSWP uses letter codes
   (`A`, `D`, `F`, …) for persistent matrilines; Hersh leaves it `NaN` (the
   `grpvar` repertoire-day code goes to `recording_id` instead, since it is
   not a persistent unit).

## Adding another source

1. Drop the raw file under `data/raw/`.
2. Add `src/pipeline/<L>_load_<name>.py` mirroring the existing loaders — it
   must expose `load() -> pd.DataFrame` returning a frame with exactly
   `schema.UNIFIED_COLUMNS`. (Letters `D` and `E` are taken by the merge step
   and the rhythm/ornament classifier; pick the next free letter.)
3. Add the new module to the `loaders` list in `D_merge_unified.py`.
4. Re-run `python -m src.pipeline.D_merge_unified` and update the table at
   the top of this README.

## Datasets considered but not included

| Dataset | Reason |
|---|---|
| Cantor et al. 2016 Galápagos cultural turnover (Dryad doi:10.5061/dryad.8jj26) | Only figure-source summary tables, no raw ICIs |
| Project CETI WhAM corpus (Paradise et al. NeurIPS 2025) | The new 7,653-coda CETI portion is not yet publicly released |
| HuggingFace `orrp/DSWP` | Audio only, no ICI annotations; subset of DSWP |
| `Project-CETI/coda-vowel-phonology` (Beguš et al. 2026, [OSF 9t6qu](https://osf.io/9t6qu/)) | Spectral/vowel features only — `codamd.csv` carries coda duration and vowel labels, `codasp.csv` carries spectral peak measurements. No per-click ICIs. |
| Watkins Marine Mammal Sound Database | Audio clips only, no coda-level ICI annotations |

## License

CC BY 4.0 — see `LICENSE`. Cite the original source publications when using
this data; their citations are listed in `LICENSE`.
