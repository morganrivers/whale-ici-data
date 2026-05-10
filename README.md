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
| **Unified** | **47,942** | | | |

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
│       └── codas_unified.csv         # final concatenated corpus (47,942 rows)
├── src/pipeline/
│   ├── schema.py                     # shared column definitions
│   ├── A_load_dswp.py
│   ├── B_load_birth.py
│   ├── F_load_hersh_pacific.py
│   ├── G_load_gero_vowel.py
│   ├── H_load_idcallr.py
│   ├── I_load_bermant_etp.py
│   └── merge_unified.py            # entry point — produces codas_unified.csv
├── requirements.txt
├── LICENSE                           # CC BY 4.0
└── README.md
```

## Reproduce

```bash
pip install -r requirements.txt
python -m src.pipeline.merge_unified
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
| `date` | str | Date or ISO datetime of the coda — **not** normalized across sources; mixed formats. `sharma2024_dswp`: `DD/MM/YYYY`. `hersh2022_pacific`: `YYYY-MM-DD` (unmatched rows) or `YYYY-MM-DDTHH:MM:SS+00:00` (rows matched to Bermant 2019 ETP). `bermant2019_etp`: `YYYY-MM-DDTHH:MM:SS+00:00`. `sharma2025_birth`: `YYYY-MM-DDTHH:MM:SS+00:00` UTC, derived from chained-recording estimation (see *Birth dataset timestamps* in caveats). `begus2026_vowel` and `hersh2021_idcallr`: `YYYY-MM-DD`. |
| `time_in_recording_s` | float | Seconds from recording start; populated for `sharma2025_birth` and the DSWP/dialogues-joined subset of `sharma2024_dswp` |
| `n_clicks` | int | Number of clicks in the coda |
| `coda_duration_s` | float | Sum of ICIs (= time from first to last click) |
| `whale_photo_id` | str | Persistent Caribbean photo-ID (e.g. `"5151"`); `NaN` if unattributed |
| `local_speaker_id` | str | Within-recording speaker tag (birth dataset only); **not** comparable across recordings |
| `social_unit` | str | Original social-unit identifier (study-specific; not cross-source comparable) |
| `clan` | str | Vocal clan label (`EC1`, `EC2`, `FP`, `PALI`, `PO`, `REG`, `RI`, `SH`, `SI`, `Regular`, `Short`, …); `NaN` if unknown |
| `coda_type` | str | Coda type label in DSWP alphanumeric notation (e.g. `5R3`, `1+1+3`, `4D`) where available. See *Coda type classification* below for coverage and sources. `NaN` if unclassified. |
| `coda_type_origin` | str | How the `coda_type` label was produced. `source-raw` = copied verbatim from the source publication; `pacific-matched` = assigned by kNN matching to a DSWP anchor in [whale-grammar](https://github.com/morganrivers/whale-grammar); `discovery-cluster` = OPTICSxi cluster discovered in [whale-grammar](https://github.com/morganrivers/whale-grammar); `discovery-noise` = rejected by OPTICSxi (treated as noise); `NaN` = no label assigned. |
| `location` | str | Geographic region (free text). Hersh Pacific rows include the original abbreviation, e.g. `"Galapagos Islands (GAL)"`. |
| `latitude` | float | Decimal degrees of recording location. Currently populated only for Hersh 2022 Pacific rows; `NaN` for other sources. |
| `longitude` | float | Decimal degrees of recording location. Same coverage caveat as `latitude`. |
| `derived_lat` | float | Best-guess latitude: copies `latitude` when the source provides per-row coordinates; otherwise looks up a representative centroid from the `location` string (see *Derived columns* below). `NaN` only for the 44 `"NEW (location unresolved)"` rows. |
| `derived_lon` | float | Best-guess longitude, same logic as `derived_lat`. |
| `recording_method` | str | Recording platform — see *Derived columns* below. |
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
- **Birth dataset timestamps are chained estimates, not measured recording start times.**
   The supplementary event table from Sharma et al. 2025 records only two acoustic
   anchors: the first recording started at 10:53:00 local time (14:53:00 UTC) and
   the last (CETI23-294) started at 15:29:00 local time on 2023-07-08. Per-recording
   start times were not released. `B_load_birth.py` assigns each coda an absolute UTC
   timestamp by sorting recordings numerically (CETI23-277 → CETI23-294, skipping the
   absent CETI23-284) and chaining them back-to-back from the first anchor.  The
   cumulative drift from chaining without gaps means that later recordings may be
   shifted up to ~66 minutes earlier than their true start time relative to the
   15:29 anchor.  All birth timestamps should be treated as approximate; they
   correctly preserve within-recording coda ordering and provide a plausible
   chronology for the birth event but are not suitable for analyses that require
   sub-minute inter-recording timing precision.
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
- **`bermant2019_etp` `coda_type` uses a different numeric vocabulary.** The
   3,448 labelled ETP rows carry numeric codes from the Bermant 2019 paper
   (e.g. `599`, `899`). These are **not** comparable to the DSWP alphanumeric
   labels used by every other labelled source; do not merge them as if they
   were the same system.
- **Hersh `source_coda_id` is mostly numeric, with two prefixed exceptions.**
   3,113 Galápagos codas (`WatGal###`) are Watkins-archive recordings
   re-annotated by Hersh, and three Southern New Zealand codas (`NZ0071`–
   `NZ0073`) have `latitude`/`longitude = NaN` because the source CSV had
   the literal string `"Unk"` for those coordinates.
- **`social_unit` semantics are study-specific.** DSWP uses letter codes
   (`A`, `D`, `F`, …) for persistent matrilines; Hersh leaves it `NaN` (the
   `grpvar` repertoire-day code goes to `recording_id` instead, since it is
   not a persistent unit).

## Derived columns

`codas_unified.csv` contains derived columns computed by `merge_unified.py`
after all sources are concatenated. They are not part of `UNIFIED_COLUMNS` and
are not emitted by individual loaders.

| Column | Values | Description |
|---|---|---|
| `recording_method` | `vessel` · `dtag` | Recording platform (see table below). |
| `coda_type_origin` | `source-raw` · `pacific-matched` · `discovery-cluster` · `discovery-noise` · `NaN` | How the `coda_type` label was produced. See *Coda type classification* below. |
| `timeofday` | `daytime` · `dawn` · `dusk` · `nighttime` · `NaN` | Broad time-of-day category based on civil twilight boundaries (astral, civil depression 6°). Populated only for sources that expose a clock-time datetime; `NaN` for sources with date-only or year-only timestamps. |
| `derived_lat` | float · `NaN` | Best-guess latitude for the recording. Copies `latitude` when the source provides per-row coordinates (Hersh 2022 Pacific); otherwise maps the `location` string to a representative centroid (see table below). `NaN` only for the 44 `"NEW (location unresolved)"` rows in `hersh2021_idcallr`. |
| `derived_lon` | float · `NaN` | Best-guess longitude, same logic as `derived_lat`. |
| `codas_per_10min` | float · `NaN` | Number of codas produced in a ±5-minute window centred on this coda, divided by 10, as a proxy for instantaneous calling rate. The coda itself is included in the count; division is always by 10 regardless of how much of the window falls within the recording. Computed within each sequence (see *Coverage* below); `NaN` for sources without any temporal information. |
| `likely_solitary_male` | `True` · `False` · `NaN` | Heuristic flag for likely solitary-male behaviour: `True` when `codas_per_10min ≤ 2` **and** `\|derived_lat\| > 25°` (high-latitude, low calling rate — the context in which lone males are typically encountered). `False` when both values are known but the conditions are not met. `NaN` when either `codas_per_10min` or `derived_lat` is unavailable. |
| `n_unique_whales_in_sequence` | int · `NaN` | Count of distinct whales identified within the same sequence. Uses `whale_photo_id` (persistent photo-ID) when available; falls back to `local_speaker_id` (within-recording tag) for rows without a photo-ID. `NaN` when fewer than 50 % of codas in the sequence carry any whale identifier. See *Coverage* below for sequence-boundary definition by source. |

**`recording_method` — platform by source:**

| Source | `recording_method` | Platform | Determination |
|---|---|---|---|
| `sharma2024_dswp` | `vessel` | Small research vessel + towed hydrophone array; Dominica fieldwork | Sharma et al. 2024, Nat Comm §Methods ("vessel-based monitoring") |
| `sharma2025_birth` | `dtag` | CETI hydrophone bio-logging tags (DTags) suction-cupped to whales | B_load_birth.py docstring: "CETI hydrophone tags"; Sharma et al. 2025, Sci Rep §Methods |
| `hersh2022_pacific` | `vessel` | Research vessels across multiple labs (Rendell, Whitehead) and the Watkins historical archive (also vessel-based) | Hersh et al. 2022, PNAS Table S1 lists all contributing research groups, all vessel-based |
| `hersh2021_idcallr` | `vessel` | Research vessels (Rendell BAL, Weilgart & Whitehead AtPAN/GOM) and Watkins archive | Hersh et al. 2021, MEE §Data; all contributing studies used vessel-deployed hydrophones |
| `begus2026_vowel` | `vessel` | DSWP Dominica vessel (same platform as `sharma2024_dswp`) | Beguš et al. 2026, OSF 9t6qu §Methods; G_load_gero_vowel.py docstring: "same traditional codatype vocabulary" as DSWP |
| `bermant2019_etp` | `vessel` | Research vessel in the Eastern Tropical Pacific | Bermant et al. 2019, Sci Rep 9:12588 §Methods |

No source in the current corpus uses a fixed (moored) hydrophone array. All `vessel` recordings were made with a towed hydrophone from a small research boat; the `dtag` recording was made with a tag physically attached to the whale.

**`timeofday` coverage by source:**

| Source | Rows with `timeofday` | How datetime is obtained |
|---|---:|---|
| `hersh2022_pacific` | 13,524 of 24,245 | ISO datetime in `date` column (matched rows only; unmatched rows are date-only) |
| `bermant2019_etp` | 3,450 of 3,450 | ISO datetime in `date` column; **fixed coordinates** (10 °N, 105 °W — ETP centre) used because no per-coda lat/lon was released |
| `sharma2025_birth` | 5,731 of 5,731 | ISO datetime in `date` column (chained-recording estimate); fixed Dominica coordinates (15.3 °N, 61.4 °W) |
| `begus2026_vowel` | 1,139 of 1,375 | Tag-on datetime from `recording_id` + `time_in_recording_s` offset; fixed Dominica coordinates (15.3 °N, 61.4 °W) |
| `sharma2024_dswp` | 0 | No clock time in source |
| `hersh2021_idcallr` | 0 | No clock time in source |

**`codas_per_10min` and `n_unique_whales_in_sequence` coverage by source:**

| Source | Rows with `codas_per_10min` | Rows with `n_unique_whales_in_sequence` | Sequence boundary |
|---|---:|---:|---|
| `sharma2025_birth` | 5,731 of 5,731 | 5,731 of 5,731 | Each CETI recording file (`recording_id`) |
| `hersh2022_pacific` | 13,524 of 24,245 | 0 (no whale IDs) | Repertoire-day group (`recording_id`), using ISO datetime in `date` |
| `bermant2019_etp` | 3,450 of 3,450 | 0 (no whale IDs) | Source + calendar day (no `recording_id` available) |
| `sharma2024_dswp` | 3,780 of 8,872 | 3,780 of 8,872 | Dialogue recording session (`recording_id`); only the dialogues-matched subset has timestamps |
| `begus2026_vowel` | 1,139 of 1,375 | 1,139 of 1,375 | Calendar day (`date`), not `recording_id`; each tag session covers one whale, so day-level grouping aggregates all whales recorded together that day |
| `hersh2021_idcallr` | 0 | 0 | No temporal or whale-ID information available |

For `codas_per_10min`, the computation uses `time_in_recording_s` where available (pass 1), then falls back to the absolute Unix timestamp derived from the ISO datetime in `date` (pass 2). For `n_unique_whales_in_sequence`, the 50 % threshold is evaluated per sequence: if fewer than half the codas in the sequence carry any whale identifier, the count is left as `NaN` for that entire sequence.

**Classification boundaries** (computed per coda using its local solar timezone, `lon/15` rounded to the nearest hour):

- **dawn** — civil twilight start to sunrise
- **daytime** — sunrise to sunset
- **dusk** — sunset to civil twilight end
- **nighttime** — outside civil twilight (before dawn or after dusk)

All timestamps are treated as UTC. The `bermant2019_etp` classification uses a single representative ETP coordinate and will be off by up to ~1 hour near the coast; treat it as approximate.

**`derived_lat` / `derived_lon` location centroids:**

| `location` value | `derived_lat` | `derived_lon` |
|---|---:|---:|
| Dominica, Eastern Caribbean | 15.30 | −61.40 |
| Dominica, Eastern Caribbean (live birth event) | 15.30 | −61.40 |
| Eastern Caribbean, Watkins archive (CAR) | 15.00 | −63.00 |
| Eastern Tropical Pacific | 10.00 | −105.00 |
| Galapagos Islands (GAL) | −0.95 | −90.96 |
| Northern Chile (CHL_N) | −20.00 | −70.00 |
| Southern Chile (CHL_S) | −45.00 | −73.00 |
| Ecuador (ECU) | −2.00 | −80.00 |
| Peru (PER) | −10.00 | −78.00 |
| Balearic Islands (BAL) | 39.50 | 2.80 |
| Tonga (TON) | −20.00 | −175.00 |
| Ogasawara Islands of Japan (JPN_Og) | 27.10 | 142.20 |
| Kumano coast of Japan (JPN_Ku) | 33.80 | 136.20 |
| Kiribati (KIR) | 1.87 | −157.36 |
| Jarvis Island (JAR) | −0.37 | −160.02 |
| Papua New Guinea (PNG) | −6.00 | 147.00 |
| Atlantic Panama (AtPAN) | 9.00 | −79.50 |
| Panama (PAN) | 8.50 | −79.50 |
| Mariana Islands (MNP) | 15.20 | 145.80 |
| Baker Island (BAK) | 0.19 | −176.47 |
| Equatorial South Pacific (ESP) | −5.00 | −140.00 |
| Midway Atoll (MID) | 28.20 | −177.40 |
| Sea of Cortez (SOC) | 27.00 | −110.00 |
| Southern New Zealand (NZL_S) | −46.00 | 168.00 |
| Northern New Zealand (NZL_N) | −36.00 | 175.00 |
| SGaan Kinghlas-Bowie Seamount (BOW) | 53.00 | −142.00 |
| Gulf of Mexico (GOM) | 24.00 | −90.00 |
| Easter Island (EAS) | −27.10 | −109.30 |
| Nauru (NRU) | −0.53 | 166.90 |
| Marquesas Islands (MRQ) | −9.00 | −139.50 |
| Palau (PAL) | 7.50 | 134.50 |
| NEW (location unresolved) (NEW) | NaN | NaN |

Rows in `hersh2022_pacific` with per-coda coordinates use those exact values instead of the centroid.

## Coda type classification

The `coda_type` column uses the DSWP alphanumeric notation (e.g. `5R3`, `1+1+3`, `4D`) as a common vocabulary wherever possible. Labels come from two sources: the original publication's own annotation, and the [whale-grammar](https://github.com/morganrivers/whale-grammar) classifier.

### Coverage

| Source | Rows with `coda_type` | Rows total | `coda_type_origin` |
|---|---:|---:|---|
| `sharma2024_dswp` | 8,719 | 8,872 | `source-raw` — DSWP alphanumeric labels copied from the source CSV |
| `hersh2022_pacific` | 23,437 | 24,245 | `pacific-matched` / `discovery-cluster` / `discovery-noise` — see below |
| `sharma2025_birth` | 5,551 | 5,731 | `pacific-matched` / `discovery-cluster` / `discovery-noise` — see below |
| `bermant2019_etp` | 3,448 | 3,450 | `source-raw` — Bermant 2019 numeric codes (**different vocabulary**, not DSWP-comparable) |
| `hersh2021_idcallr` | 0 | 4,269 | — (no coda-type annotations in the source release) |
| `begus2026_vowel` | 1,375 | 1,375 | `source-raw` — DSWP alphanumeric labels from `codamd.csv` |

### Hersh 2022 Pacific and Sharma 2025 birth: labels from whale-grammar

The `hersh2022_pacific` source was published with its own numeric coda-type system that is not compatible with the DSWP vocabulary. The `sharma2025_birth` source had no coda-type annotations at all. Both sets of labels were therefore generated by the [whale-grammar](https://github.com/morganrivers/whale-grammar) classifier and are stored here for convenience in `data/raw/whale_grammar_coda_types.csv`.

The whale-grammar classifier is a three-pass hybrid (documented in that repo):

1. **DSWP anchor lock** — every `sharma2024_dswp` row whose published label is a non-NOISE type is locked to that label (`origin = dswp-real`; not propagated to this corpus because the raw label already exists).
2. **kNN matching** — for each coda length 3–10, a k=5 nearest-neighbour classifier trained on DSWP anchors is applied to non-DSWP codas. A coda is accepted (`origin = pacific-matched`) if its distance to the predicted type's centroid is within a per-type tolerance τ (99th-percentile within-DSWP distance, floored at 0.10 s).
3. **OPTICSxi discovery** — DSWP NOISE rows and kNN rejects form a residual pool. ELKI 0.7.1 OPTICSxi (ξ = 0.04, minPts = 10) clusters this pool per length; clusters with ≥ 10 members become new Pacific-discovered types (`origin = discovery-cluster`); the rest are noise (`origin = discovery-noise`).

The lookup table (`whale_grammar_coda_types.csv`) was extracted from `whale-grammar/data/classified/codas_classified.csv` (column `coda_type_gero21`) and joined on `(source, source_coda_id)`. The `coda_type_origin` column records which pass produced each label.

| `coda_type_origin` | Count | Meaning |
|---|---:|---|
| `source-raw` | 13,542 | Copied verbatim from source publication |
| `pacific-matched` | 22,945 | kNN-matched to a DSWP anchor type |
| `discovery-cluster` | 4,029 | New type discovered by OPTICSxi |
| `discovery-noise` | 2,014 | Rejected by OPTICSxi; no stable cluster |
| `NaN` | 5,412 | No label assigned |

## Adding another source

1. Drop the raw file under `data/raw/`.
2. Add `src/pipeline/<L>_load_<name>.py` mirroring the existing loaders — it
   must expose `load() -> pd.DataFrame` returning a frame with exactly
   `schema.UNIFIED_COLUMNS`. (Letter `D` is taken by the merge step; pick
   the next free letter.)
3. Add the new module to the `loaders` list in `merge_unified.py`.
4. Re-run `python -m src.pipeline.merge_unified` and update the table at
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
