  # whale-ici-data

A unified collection of publicly released sperm whale (*Physeter macrocephalus*)
coda inter-click interval (ICI) datasets, packaged in a single consistent
schema for downstream analysis.

This repository **only** stores raw ICI sequences plus provenance and
identification metadata (whale photo-ID, social unit, clan, location). It does
**not** include post-processed features such as rhythm/tempo categories,
ornamentation flags, or rubato measurements — those are speculative
classifications and should be computed downstream from the ICIs by each
consumer (e.g. in [whale-grammar](https://github.com/morganrivers/whale-grammar)).
This split is deliberate: Sharma 2024's rhythm templates and ornament rule
were derived from the Eastern Caribbean (EC) clans on Dominica and may not
generalise to the Pacific clans, so any classifier needs the freedom to
expand or replace those definitions per dataset.

## Contents

| Source | Codas | Region | Distinct whales (with ID) | Period |
|---|---:|---|---:|---|
| `sharma2024_dswp` — Sharma et al. 2024 ([Nat Comm 15:3617](https://doi.org/10.1038/s41467-024-47221-8)) | 8,872 | Dominica, EC clans | 35 (3,014 codas attributed) | 2005-2018 |
| `sharma2025_birth` — Sharma et al. 2025 ([Sci Rep](https://doi.org/10.1038/s41598-025-27438-3)) | 5,731 | Dominica, single live-birth event | 0 (within-recording speaker tags only) | 2023 |
| `hersh2022_pacific` — Hersh et al. 2022 ([PNAS](https://doi.org/10.1073/pnas.2201692119), [OSF](https://osf.io/ae6pd/)) | 24,237 | Pacific (23 regions, 7 clans: FP, PALI, PO, REG, RI, SH, SI) | 0 (no persistent IDs in this release) | 1978-2017 |
| `hersh2021_idcallr` — Hersh et al. 2021 ([MEE](https://doi.org/10.1111/2041-210X.13524)) | 4,269 | Eastern Caribbean + Watkins archive | 0 | 1978-2019 |
| `begus2026_vowel` — Beguš et al. 2026 ([OSF 9t6qu](https://osf.io/9t6qu/)) | 1,375 | Dominica, Eastern Caribbean | 13 (1,267 codas attributed) | 2014-2016 |
| `bermant2019_etp` — Bermant et al. 2019 ([Sci Rep 9:12588](https://doi.org/10.1038/s41598-019-48909-4)) | 3,450 | Eastern Tropical Pacific (6 clan types: Regular, Short, FourPlus, PlusOne, Caribbean, Tonga) | 0 | 1985-2014 |
| **Unified** | **47,934** | | | |

## Layout

```
whale-ici-data/
├── data/
│   ├── raw/                          # original published files, unmodified
│   │   ├── dswp_dominica_codas.csv
│   │   ├── sw_combinatoriality_dialogues.csv
│   │   ├── sharma2025_birth.csv
│   │   ├── hersh2022_pacific_codas.csv
│   │   ├── hersh2022_pacific_README.txt
│   │   ├── IDcallR_SpermWhaleCodas.csv
│   │   ├── ETP.xlsx                  # Bermant 2019 ETP suppl. (MOESM3)
│   │   └── gero_vowel_phonology/     # Beguš et al. 2026 (OSF 9t6qu)
│   │       ├── codamd.csv
│   │       └── focal-coarticulation-metadata.csv
│   ├── intermediate/                 # per-source unified-schema CSVs
│   └── unified/
│       └── codas_unified.csv         # final concatenated corpus (47,934 rows)
├── src/pipeline/
│   ├── schema.py                     # shared column definitions
│   ├── A_load_dswp.py
│   ├── B_load_birth.py
│   ├── D_merge_unified.py            # entry point — produces codas_unified.csv
│   ├── F_load_hersh_pacific.py
│   ├── G_load_gero_vowel.py
│   ├── H_load_idcallr.py
│   └── I_load_bermant_etp.py
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
| `source` | str | Short paper key (`sharma2024_dswp`, `sharma2025_birth`, `hersh2022_pacific`, `hersh2021_idcallr`, `begus2026_vowel`, `bermant2019_etp`) |
| `source_doi` | str | DOI of the source publication or data release |
| `source_coda_id` | str | Original coda identifier within the source file |
| `recording_id` | str | Recording session identifier (raw, source-specific). DSWP uses date as proxy. |
| `date` | str | Raw date string from source — **not** normalized; mixed formats (`DD/MM/YYYY`, `YYYY-MM-DD`, ISO datetime `YYYY-MM-DDTHH:MM:SS`). Hersh 2022 Pacific rows matched to the Bermant 2019 ETP supplement carry a precise ISO datetime; unmatched rows carry only a date. |
| `time_in_recording_s` | float | Seconds from recording start; populated for `sharma2025_birth` and the DSWP/dialogues-joined subset of `sharma2024_dswp` |
| `n_clicks` | int | Number of clicks in the coda |
| `coda_duration_s` | float | Sum of ICIs (= time from first to last click) |
| `whale_photo_id` | str | Persistent Caribbean photo-ID (e.g. `"5151"`); `NaN` if unattributed |
| `local_speaker_id` | str | Within-recording speaker tag (birth dataset only); **not** comparable across recordings |
| `social_unit` | str | Original social-unit identifier (study-specific; not cross-source comparable) |
| `clan` | str | Vocal clan label (`EC1`, `EC2`, `FP`, `PALI`, `PO`, `REG`, `RI`, `SH`, `SI`, `Regular`, `Short`, …); `NaN` if unknown |
| `coda_type` | str | Coda type label from the source paper's classification system. **Notation is source-specific and not cross-source comparable**: DSWP uses alphanumeric labels (`5R3`, `1+1+3`, `4D`); Hersh 2022 uses numeric codes (`510`, `59`); Bermant 2019 ETP uses numeric codes (`599`, `899`). `NaN` if the source did not include a coda type. |
| `location` | str | Geographic region (free text). Hersh Pacific rows include the original abbreviation, e.g. `"Galapagos Islands (GAL)"`. |
| `latitude` | float | Decimal degrees of recording location. Currently populated only for Hersh 2022 Pacific rows; `NaN` for other sources. |
| `longitude` | float | Decimal degrees of recording location. Same coverage caveat as `latitude`. |
| `ICI1` … `ICI40` | float | Inter-click intervals in seconds. `NaN` past `n_clicks - 1`. Max observed length is 40 clicks (birth dataset). |

For Sharma 2024's labelled DSWP subset (rhythm cluster ids and ornament
flags), see `data/raw/sw_combinatoriality_dialogues.csv` together with
`sw_combinatoriality_rhythms.p` and `sw_combinatoriality_ornaments.p`.
These are not joined into `codas_unified.csv` — downstream consumers can
align them on the DSWP rows (or train their own classifier).

## Important caveats

- **`begus2026_vowel` ICIs are reconstructed, not measured.** The source OSF
  deposit (`codamd.csv`) records only the total coda duration and the
  traditional codatype label (e.g. `"1+1+3"`, `"5R1"`) — per-click onset
  times were not released. ICIs for these 1,375 codas are therefore
  reconstructed by computing the median ICI proportion (ICI_i / Duration)
  for each codatype across all matching rows in the `sharma2024_dswp` corpus
  (which uses the same codatype vocabulary), then scaling those proportions
  by each coda's actual duration. The reconstructed ICIs reproduce the
  correct duration and the typical within-type rhythm, but not the click-by-
  click variance of the individual recording. NOISE-labelled codatypes (e.g.
  `"5-NOISE"`) are reconstructed the same way; they have higher inter-coda
  variance in the DSWP reference and should be treated with additional
  caution. Two 1-click codas (`"1-NOISE"`) have zero ICIs and carry `NaN`
  for all ICI columns.

- **The birth dataset has no persistent whale IDs.** `SegmentWhale` from the
   source file is preserved as `local_speaker_id` in the form
   `"<recording>_seg<n>"`, which is unique within the file but tells you
   nothing about whether segment 1 in CETI23-277 is the same animal as
   segment 1 in CETI23-278.
- **`hersh2022_pacific` has no individual IDs; timestamps are partial.**
   The OSF release exposes only repertoire-day group codes (kept as
   `recording_id`); `whale_photo_id`, `local_speaker_id`, `social_unit`, and
   `time_in_recording_s` are all `NaN` for these rows. 13,520 of the 24,237
   rows were matched to the Bermant 2019 ETP supplement by date + ICI
   fingerprint and have their `date` upgraded to a precise ISO datetime
   (`YYYY-MM-DDTHH:MM:SS`); the remaining 10,717 rows retain date-only
   resolution. Downstream classifiers that need temporal neighbours (e.g.
   Sharma 2024's ornament rule) cannot run on this subset; classifiers that
   work on ICIs alone (rhythm templates, tempo buckets) can. Note also that
   the Sharma rhythm/ornament definitions were derived from EC clans and may
   not transfer cleanly to the Pacific clans.
- **Hersh Pacific clan abbreviations are not the EC1/EC2 vocabulary.** The
   seven Pacific clans use the labels from Hersh et al. 2022: FP (Four-Plus),
   PALI (Palindrome), PO (Plus-One), REG (Regular), RI (Rapid Increasing),
   SH (Short), SI (Slow-Increasing). 682 codas are unassigned (`clan = NaN`)
   because their parent repertoires fell below the within-clan correlation
   threshold in the source paper.
- **`bermant2019_etp` contains only codas not already in `hersh2022_pacific`.**
   The Bermant 2019 ETP supplement (MOESM3 / `ETP.xlsx`) has 16,995 codas;
   ~13,545 share an ICI fingerprint with `hersh2022_pacific` rows and are
   excluded to avoid duplication. The 3,450 remaining rows are mostly
   Short, PlusOne, FourPlus, and Caribbean-clan codas from the 1985-2014
   ETP recording series. Clan labels use the ETP file's own names (Regular,
   Short, FourPlus, PlusOne, Caribbean, Tonga) rather than the Hersh
   abbreviations; the Caribbean-clan rows (476) represent Caribbean-dialect
   whales encountered in the Pacific, not Dominica whales. No per-coda
   coordinates were released; `latitude`, `longitude` are `NaN`.
- **`coda_type` notation is not cross-source comparable.** Each source uses
   its own classification vocabulary. Do not compare numeric codes between
   `hersh2022_pacific` (e.g. `510`) and `bermant2019_etp` (e.g. `599`); they
   are from different systems. The DSWP alphanumeric codes (`5R3`, `1+1+3`)
   are yet another vocabulary.
- **Hersh `source_coda_id` is mostly numeric, with two prefixed exceptions.**
   3,113 Galápagos codas (`WatGal###`) are Watkins-archive recordings
   re-annotated by Hersh, and three Southern New Zealand codas (`NZ0071`–
   `NZ0073`) have `latitude`/`longitude = NaN` because the source CSV had
   the literal string `"Unk"` for those coordinates.
- **`social_unit` semantics are study-specific.** DSWP uses letter codes
   (`A`, `D`, `F`, …) for persistent matrilines; Hersh leaves it `NaN` (the
   `grpvar` repertoire-day code goes to `recording_id` instead, since it is
   not a persistent unit).

## Adding another source

1. Drop the raw file under `data/raw/`.
2. Add `src/pipeline/<L>_load_<name>.py` mirroring the existing loaders — it
   must expose `load() -> pd.DataFrame` returning a frame with exactly
   `schema.UNIFIED_COLUMNS`. (Letter `D` is taken by the merge step; pick
   the next free letter.)
3. Add the new module to the `loaders` list in `D_merge_unified.py`.
4. Re-run `python -m src.pipeline.D_merge_unified` and update the table at
   the top of this README.

## Datasets considered but not included

| Dataset | Reason |
|---|---|
| Cantor et al. 2016 Galápagos cultural turnover (Dryad doi:10.5061/dryad.8jj26) | Only figure-source summary tables, no raw ICIs |
| Project CETI WhAM corpus (Paradise et al. NeurIPS 2025) | The new 7,653-coda CETI portion is not yet publicly released |
| HuggingFace `orrp/DSWP` | Audio only, no ICI annotations; subset of DSWP |
| `Project-CETI/coda-vowel-phonology` (Beguš et al. 2026, [OSF 9t6qu](https://osf.io/9t6qu/)) | Now included as `begus2026_vowel`. ICIs are reconstructed from DSWP median proportions per codatype (see caveats above). |
| Watkins Marine Mammal Sound Database | Audio clips only, no coda-level ICI annotations |

## License

CC BY 4.0 — see `LICENSE`. Cite the original source publications when using
this data; their citations are listed in `LICENSE`.
