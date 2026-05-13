"""Concatenate all per-source intermediate CSVs into the unified corpus.

Re-runs each loader so the pipeline is reproducible end-to-end with one entry point:
    python -m src.pipeline.merge_unified
"""
import datetime as _dt
from pathlib import Path
import pandas as pd

from .schema import UNIFIED_COLUMNS
from . import A_load_dswp, B_load_birth, F_load_hersh_pacific, G_load_gero_vowel, H_load_idcallr, I_load_bermant_etp

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "unified" / "codas_unified.csv"

# ── Morpheme constants (match whale-grammar morpheme_discovery.py) ─────────────
_N_BINS = 4
_LABELS = "ABCD"
_MIN_CLICKS = 3
_MAX_CLICKS = 40
_MORFESSOR_PATH = REPO / "data" / "morfessor_n4.bin"

# The seven Pacific vocal clans identified by Hersh et al. 2022.
_PACIFIC_CLANS   = frozenset({"REG", "SH", "FP", "PALI", "PO", "RI", "SI"})
# Eastern Caribbean clans from the Dominica Sperm Whale Project.
_CARIBBEAN_CLANS = frozenset({"EC1", "EC2"})

_SUN_CACHE: dict = {}


def _sun_at(lat, lon, local_date):
    """Return (dawn, sunrise, sunset, dusk) in local solar timezone for the given local date."""
    key = (lat, lon, local_date)
    if key not in _SUN_CACHE:
        from astral import LocationInfo
        from astral.sun import sun as astral_sun
        tz = _dt.timezone(_dt.timedelta(hours=round(lon / 15)))
        loc = LocationInfo(latitude=lat, longitude=lon)
        s = astral_sun(loc.observer, date=local_date, tzinfo=tz)
        _SUN_CACHE[key] = (s["dawn"], s["sunrise"], s["sunset"], s["dusk"])
    return _SUN_CACHE[key]


def _classify_tod(coda_dt_utc, lat, lon):
    """Classify a UTC datetime at (lat, lon) as nighttime/dawn/daytime/dusk."""
    local_tz = _dt.timezone(_dt.timedelta(hours=round(lon / 15)))
    local = coda_dt_utc.astimezone(local_tz)
    dawn, sunrise, sunset, dusk = _sun_at(lat, lon, local.date())
    if local < dawn or local > dusk:
        return "nighttime"
    elif local < sunrise:
        return "dawn"
    elif local < sunset:
        return "daytime"
    else:
        return "dusk"


def _derive_timeofday(df: pd.DataFrame) -> pd.Series:
    """Derive nighttime/dawn/daytime/dusk for rows that have a clock-time datetime.

    Sources covered:
      hersh2022_pacific  — ISO datetime in `date` col (UTC), per-row lat/lon
      bermant2019_etp    — ISO datetime in `date` col (UTC), fixed ETP centre (10°N, 105°W)
      begus2026_vowel    — tag-on UTC datetime in `recording_id` + time_in_recording_s offset,
                           fixed Dominica coords (15.3°N, 61.4°W)

    All other sources lack clock time and get NaN.
    """
    result = pd.Series(pd.NA, index=df.index, dtype="object")

    # ── hersh2022_pacific ─────────────────────────────────────────────────────
    # Only rows with a full ISO datetime (containing "T"); date-only rows lack time-of-day
    mask = (
        (df["source"] == "hersh2022_pacific")
        & df["date"].str.contains("T", na=False)
        & df["latitude"].notna()
    )
    hp = df.loc[mask].copy()
    if len(hp):
        hp["_dt"] = pd.to_datetime(hp["date"], format="ISO8601", utc=True)
        for idx, row in hp.iterrows():
            result[idx] = _classify_tod(row["_dt"], row["latitude"], row["longitude"])

    # ── bermant2019_etp ───────────────────────────────────────────────────────
    ETP_LAT, ETP_LON = 10.0, -105.0
    mask = (df["source"] == "bermant2019_etp") & df["date"].notna()
    bt = df.loc[mask].copy()
    if len(bt):
        bt["_dt"] = pd.to_datetime(bt["date"], format="ISO8601", utc=True)
        for idx, row in bt.iterrows():
            result[idx] = _classify_tod(row["_dt"], ETP_LAT, ETP_LON)

    # ── sharma2025_birth ──────────────────────────────────────────────────────
    DOM_LAT_B, DOM_LON_B = 15.3, -61.4
    mask = (df["source"] == "sharma2025_birth") & df["date"].str.contains("T", na=False)
    bi = df.loc[mask].copy()
    if len(bi):
        bi["_dt"] = pd.to_datetime(bi["date"], format="ISO8601", utc=True)
        for idx, row in bi.iterrows():
            result[idx] = _classify_tod(row["_dt"], DOM_LAT_B, DOM_LON_B)

    # ── begus2026_vowel ───────────────────────────────────────────────────────
    DOM_LAT, DOM_LON = 15.3, -61.4
    mask = (df["source"] == "begus2026_vowel") & df["recording_id"].notna()
    bv = df.loc[mask].copy()
    if len(bv):
        bv["_rec_dt"] = pd.to_datetime(bv["recording_id"], utc=True, errors="coerce")
        has_offset = bv["time_in_recording_s"].notna() & bv["_rec_dt"].notna()
        bv["_dt"] = bv["_rec_dt"]
        bv.loc[has_offset, "_dt"] = (
            bv.loc[has_offset, "_rec_dt"]
            + pd.to_timedelta(bv.loc[has_offset, "time_in_recording_s"], unit="s")
        )
        bv = bv[bv["_dt"].notna()].copy()
        for idx, row in bv.iterrows():
            result[idx] = _classify_tod(row["_dt"], DOM_LAT, DOM_LON)

    return result


# Best-guess centre coordinates for each location string.
# Per-row lat/lon from the source always takes precedence.
_LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "Galapagos Islands (GAL)":                           (-0.95,  -90.96),
    "Dominica, Eastern Caribbean":                       (15.30,  -61.40),
    "Dominica, Eastern Caribbean (live birth event)":    (15.30,  -61.40),
    "Northern Chile (CHL_N)":                            (-20.0,  -70.00),
    "Eastern Tropical Pacific":                          (10.00, -105.00),
    "Balearic Islands (BAL)":                            (39.50,    2.80),
    "Eastern Caribbean, Watkins archive (CAR)":          (15.00,  -63.00),
    "Tonga (TON)":                                       (-20.0, -175.00),
    "Ogasawara Islands of Japan (JPN_Og)":               (27.10,  142.20),
    "Kumano coast of Japan (JPN_Ku)":                    (33.80,  136.20),
    "Ecuador (ECU)":                                     (-2.00,  -80.00),
    "Peru (PER)":                                        (-10.0,  -78.00),
    "Kiribati (KIR)":                                    (1.870, -157.36),
    "Jarvis Island (JAR)":                               (-0.37, -160.02),
    "Papua New Guinea (PNG)":                            (-6.00,  147.00),
    "Atlantic Panama (AtPAN)":                           (9.000,  -79.50),
    "Mariana Islands (MNP)":                             (15.20,  145.80),
    "Baker Island (BAK)":                                (0.190, -176.47),
    "Equatorial South Pacific (ESP)":                    (-5.00, -140.00),
    "Midway Atoll (MID)":                                (28.20, -177.40),
    "Sea of Cortez (SOC)":                               (27.00, -110.00),
    "Panama (PAN)":                                      (8.500,  -79.50),
    "Southern Chile (CHL_S)":                            (-45.0,  -73.00),
    "Southern New Zealand (NZL_S)":                      (-46.0,  168.00),
    "SGaan Kinghlas-Bowie Seamount (BOW)":               (53.00, -142.00),
    "Gulf of Mexico (GOM)":                              (24.00,  -90.00),
    "Easter Island (EAS)":                               (-27.1, -109.30),
    "Nauru (NRU)":                                       (-0.53,  166.90),
    "Marquesas Islands (MRQ)":                           (-9.00, -139.50),
    "Northern New Zealand (NZL_N)":                      (-36.0,  175.00),
    "Palau (PAL)":                                       (7.500,  134.50),
    # "NEW (location unresolved) (NEW)" intentionally omitted → NaN
}


def _derive_coords(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return (derived_lat, derived_lon): per-row lat/lon when available, else location lookup."""
    lat = df["latitude"].copy().astype(float)
    lon = df["longitude"].copy().astype(float)
    missing = lat.isna() | lon.isna()
    if missing.any():
        mapped = df.loc[missing, "location"].map(_LOCATION_COORDS)
        lat.loc[missing] = mapped.map(lambda x: x[0] if isinstance(x, tuple) else float("nan"))
        lon.loc[missing] = mapped.map(lambda x: x[1] if isinstance(x, tuple) else float("nan"))
    return lat, lon


_WHALE_GRAMMAR_LOOKUP = REPO / "data" / "raw" / "whale_grammar_coda_types.csv"


def _apply_whale_grammar_coda_types(df: pd.DataFrame) -> pd.DataFrame:
    """Override coda_type for hersh2022_pacific and sharma2025_birth with
    DSWP-standard labels from the whale-grammar classifier, and populate
    coda_type_origin for all rows."""
    lookup = pd.read_csv(_WHALE_GRAMMAR_LOOKUP, dtype=str)
    lookup = lookup.rename(columns={
        "coda_type_gero21": "_wg_coda_type",
        "classifier_origin": "_wg_origin",
    })

    df = df.merge(
        lookup,
        on=["source", "source_coda_id"],
        how="left",
    )

    override_sources = {"hersh2022_pacific", "sharma2025_birth"}
    override_mask = df["source"].isin(override_sources) & df["_wg_coda_type"].notna()
    df.loc[override_mask, "coda_type"] = df.loc[override_mask, "_wg_coda_type"]

    # coda_type_origin: where the label came from
    df["coda_type_origin"] = pd.NA
    df.loc[override_mask, "coda_type_origin"] = df.loc[override_mask, "_wg_origin"]
    source_raw_mask = (
        df["coda_type"].notna()
        & ~override_mask
        & df["source"].isin({"sharma2024_dswp", "bermant2019_etp", "begus2026_vowel"})
    )
    df.loc[source_raw_mask, "coda_type_origin"] = "source-raw"

    df = df.drop(columns=["_wg_coda_type", "_wg_origin"])
    return df


def _identity_codas_for(sub_df: pd.DataFrame, repertoire_col: str,
                         critfact: float = 5, min_codas: int = 25) -> dict:
    """Return {coda_type: clan} for identity codas in sub_df.

    A coda type is an identity coda for clan X when its mean fractional usage
    across X's repertoires exceeds critfact × the mean across all other clans,
    mirroring the criterion in Hersh et al. 2022 (produceclades, critfact=5).
    Repertoires with fewer than min_codas codas are excluded.
    """
    sub = sub_df[
        sub_df["clan"].notna()
        & sub_df["coda_type"].notna()
        & sub_df[repertoire_col].notna()
    ].copy()
    rep_size = sub.groupby(repertoire_col).size()
    sub = sub[sub[repertoire_col].isin(rep_size[rep_size >= min_codas].index)]
    if sub.empty:
        return {}

    total = sub.groupby(repertoire_col).size().rename("total")
    counts = sub.groupby([repertoire_col, "clan", "coda_type"]).size().reset_index(name="n")
    counts = counts.join(total, on=repertoire_col)
    counts["frac"] = counts["n"] / counts["total"]

    clan_means = (
        counts.groupby(["coda_type", "clan"])["frac"]
        .mean()
        .unstack("clan", fill_value=0.0)
    )
    result: dict = {}
    for coda_type, row in clan_means.iterrows():
        best = row.idxmax()
        best_val = float(row[best])
        other_mean = float(row.drop(best).mean())
        if best_val > critfact * (other_mean + 1e-10):
            result[coda_type] = best
    return result


def _derive_symbolic_marking(df: pd.DataFrame) -> pd.DataFrame:
    """Add is_clan_coda and is_in_other_clan_territory derived columns."""

    # ── Identity codas ────────────────────────────────────────────────────────
    # Pacific: repertoire = recording_id (grpvar in raw hersh data)
    pacific_id = _identity_codas_for(
        df[df["source"] == "hersh2022_pacific"], "recording_id"
    )
    # Caribbean: repertoire = social_unit (family group in DSWP)
    carib_id = _identity_codas_for(
        df[df["source"] == "sharma2024_dswp"], "social_unit"
    )

    # is_clan_coda ────────────────────────────────────────────────────────────
    # True  = this coda type is an identity coda for this whale's clan.
    # False = coda type known but not an identity coda for this clan.
    # NaN   = clan or coda_type unknown, or clan not in a supported system.
    df["is_clan_coda"] = pd.NA

    pac_mask  = df["clan"].isin(_PACIFIC_CLANS)   & df["coda_type"].notna()
    carib_mask = df["clan"].isin(_CARIBBEAN_CLANS) & df["coda_type"].notna()

    # .map returns NaN for unmapped keys; NaN != clan string → False (correct)
    df.loc[pac_mask,   "is_clan_coda"] = (
        df.loc[pac_mask,   "coda_type"].map(pacific_id) == df.loc[pac_mask,   "clan"]
    )
    df.loc[carib_mask, "is_clan_coda"] = (
        df.loc[carib_mask, "coda_type"].map(carib_id)   == df.loc[carib_mask, "clan"]
    )

    # is_in_other_clan_territory ──────────────────────────────────────────────
    # Meaningful only where clans have distinct geographic ranges (Pacific).
    # True  = dominant clan at the recording location differs from this whale's.
    # False = whale's clan is dominant at that location.
    # NaN   = non-Pacific source, missing clan, or location without a loc code.
    hersh_mask = (
        (df["source"] == "hersh2022_pacific")
        & df["clan"].isin(_PACIFIC_CLANS)
        & df["location"].notna()
    )
    sub = df.loc[hersh_mask, ["location", "clan"]].copy()
    sub["loc_code"] = sub["location"].str.extract(r'\((\w+)\)$', expand=False)

    loc_counts = (
        sub[sub["loc_code"].notna()]
        .groupby(["loc_code", "clan"]).size()
        .reset_index(name="n")
    )
    dom_idx = loc_counts.groupby("loc_code")["n"].idxmax()
    dominant_by_loc = loc_counts.loc[dom_idx].set_index("loc_code")["clan"].to_dict()

    sub["dominant"] = sub["loc_code"].map(dominant_by_loc)
    has_dom = sub["dominant"].notna()

    df["is_in_other_clan_territory"] = pd.NA
    df.loc[sub.index[has_dom], "is_in_other_clan_territory"] = (
        (sub.loc[has_dom, "dominant"] != sub.loc[has_dom, "clan"]).values
    )

    # Print identity coda summary for transparency
    from collections import defaultdict
    for label, id_map in [("Pacific", pacific_id), ("Caribbean", carib_id)]:
        by_clan: dict = defaultdict(list)
        for ct, cl in sorted(id_map.items()):
            by_clan[cl].append(ct)
        print(f"\nIdentity codas — {label}:")
        for clan in sorted(by_clan):
            print(f"  {clan}: {sorted(by_clan[clan])}")

    return df


def _derive_coda_rate(df: pd.DataFrame) -> pd.Series:
    """Codas per 10 minutes: count codas within ±5 min in the same sequence, divided by 10.

    Two passes:
    1. Rows with time_in_recording_s: use that offset, grouped by recording_id.
    2. Remaining rows with a full ISO datetime in `date` (contains "T"): convert to
       Unix seconds and group by recording_id when available, else by source+day.

    The coda itself is included in the count.  Division is always by 10 regardless
    of how much of the window falls within the recording.
    """
    import numpy as np
    result = pd.Series(np.nan, index=df.index, dtype="float64")

    def _fill_group(t_arr, idx):
        lo = np.searchsorted(t_arr, t_arr - 300.0, side="left")
        hi = np.searchsorted(t_arr, t_arr + 300.0, side="right")
        result.loc[idx] = (hi - lo).astype(float) / 10.0

    # Pass 1: time_in_recording_s available
    mask1 = df["time_in_recording_s"].notna() & df["recording_id"].notna()
    sub1 = df.loc[mask1, ["recording_id", "time_in_recording_s"]]
    for _rec_id, grp in sub1.groupby("recording_id"):
        grp_s = grp.sort_values("time_in_recording_s")
        _fill_group(grp_s["time_in_recording_s"].values, grp_s.index)

    # Pass 2: full ISO datetime in `date`, not yet filled
    mask2 = result.isna() & df["date"].str.contains("T", na=False)
    sub2 = df.loc[mask2, ["source", "recording_id", "date"]].copy()
    sub2["_t"] = (
        pd.to_datetime(sub2["date"], format="ISO8601", utc=True, errors="coerce")
        .astype("int64") / 1e9
    )
    sub2 = sub2[sub2["_t"].notna()]
    # Group by recording_id when present; fall back to source+day
    sub2["_grp"] = sub2["recording_id"].where(
        sub2["recording_id"].notna(),
        sub2["source"] + "_" + sub2["date"].str[:10],
    )
    for _grp_key, grp in sub2.groupby("_grp"):
        grp_s = grp.sort_values("_t")
        _fill_group(grp_s["_t"].values, grp_s.index)

    return result


def _derive_likely_solitary_male(df: pd.DataFrame) -> pd.Series:
    """True when codas_per_10min <= 2 AND |derived_lat| > 25; NaN if either is unknown."""
    result = pd.Series(pd.NA, index=df.index, dtype="object")
    has_rate = df["codas_per_10min"].notna()
    has_lat = df["derived_lat"].notna()
    evaluable = has_rate & has_lat
    result.loc[evaluable] = (
        (df.loc[evaluable, "codas_per_10min"] <= 2.0)
        & (df.loc[evaluable, "derived_lat"].abs() > 25.0)
    )
    return result


def _derive_coda_duration(df: pd.DataFrame) -> pd.Series:
    """Coda duration in seconds: sum of ICI1..ICI(n_clicks-1).

    ICIs past n_clicks-1 are NaN in the source data, so summing all ICI columns
    with min_count=1 gives the correct total (NaN only when all ICIs are absent).
    """
    ici_cols = [f"ICI{i}" for i in range(1, _MAX_CLICKS + 1) if f"ICI{i}" in df.columns]
    return df[ici_cols].sum(axis=1, min_count=1)


def _ici_bin_edges(df: pd.DataFrame) -> dict:
    """Per-ICI-position quantile bin edges computed across all coda lengths."""
    import numpy as np
    edges: dict = {}
    for pos in range(1, _MAX_CLICKS):
        col = f"ICI{pos}"
        if col not in df.columns:
            break
        vals = df[col].dropna().values
        if len(vals) < _N_BINS * 10:
            continue
        e = np.unique(np.percentile(vals, np.linspace(0, 100, _N_BINS + 1)))
        if len(e) > 1:
            edges[col] = e
    return edges


def _ici_row_to_string(row, edges: dict) -> str | None:
    """Convert one coda row's ICI values to an ABCD symbol string."""
    import numpy as np
    n = row.get("n_clicks")
    if pd.isna(n) or not (_MIN_CLICKS <= int(n) <= _MAX_CLICKS):
        return None
    symbols = []
    for pos in range(1, int(n)):
        col = f"ICI{pos}"
        val = row.get(col, np.nan)
        if pd.isna(val):
            break
        if col not in edges:
            symbols.append("C")
            continue
        e = edges[col]
        idx = max(0, min(int(np.searchsorted(e[1:-1], val)), _N_BINS - 1))
        symbols.append(_LABELS[idx])
    return "".join(symbols) if symbols else None


def _derive_morpheme_seq(df: pd.DataFrame) -> pd.Series:
    """Morfessor morpheme segmentation of each coda's ICI symbol string.

    Each ICI is discretised to one of four symbols (A–D) using per-position
    quantile bin edges computed from the full unified corpus.  Morfessor
    Baseline then segments the resulting string into sub-units (morphemes).
    The column stores the morphemes space-joined, e.g. 'BCC AB'.

    The trained model is cached at data/morfessor_n4.bin; delete that file to
    force a full retrain (needed when the unified corpus changes substantially).

    NaN for codas outside the 3–40 click range or with missing ICI data.
    """
    import morfessor
    from collections import Counter

    valid_mask = df["n_clicks"].notna() & df["n_clicks"].between(_MIN_CLICKS, _MAX_CLICKS)
    edges = _ici_bin_edges(df[valid_mask].copy())

    # Build ICI string for every row
    ici_strings: list = []
    for _, row in df.iterrows():
        ici_strings.append(_ici_row_to_string(row, edges))

    corpus: Counter = Counter(s for s in ici_strings if s is not None)

    mio = morfessor.MorfessorIO()
    if _MORFESSOR_PATH.exists():
        model = mio.read_binary_model_file(str(_MORFESSOR_PATH))
        print(f"  Loaded Morfessor model from {_MORFESSOR_PATH.relative_to(REPO)}")
    else:
        print(f"  Training Morfessor on {len(corpus)} ICI string types …")
        model = morfessor.BaselineModel()
        model.load_data([(cnt, w) for w, cnt in corpus.items()])
        model.train_batch()
        _MORFESSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        mio.write_binary_model_file(str(_MORFESSOR_PATH), model)
        print(f"  Saved to {_MORFESSOR_PATH.relative_to(REPO)}")

    segs: dict = {}
    for s in corpus:
        morphs, _ = model.viterbi_segment(s)
        segs[s] = " ".join(morphs)

    n_types = len(segs)
    avg_len = sum(len(v.split()) for v in segs.values()) / n_types if n_types else 0
    print(f"  Morpheme vocab: {n_types} ICI string types, avg {avg_len:.2f} morphemes/coda")

    return pd.Series(
        [segs.get(s) if s is not None else None for s in ici_strings],
        index=df.index,
        dtype="object",
    )


def _derive_year_normalized(df: pd.DataFrame) -> pd.Series:
    """Year scaled to [0, 1] across the full corpus.

    Year is extracted from the `date` column as the first 4-digit sequence
    (handles all mixed formats: DD/MM/YYYY, YYYY-MM-DD, ISO datetimes).
    0 = oldest year in the corpus, 1 = newest.  NaN where `date` is absent.
    """
    yr = df["date"].str.extract(r"(\d{4})")[0].astype(float)
    yr_min, yr_max = yr.min(), yr.max()
    return (yr - yr_min) / (yr_max - yr_min)


def _derive_unique_whales(df: pd.DataFrame) -> pd.Series:
    """Count unique whales per sequence.

    Uses whale_photo_id first; falls back to local_speaker_id for rows without a
    photo-ID.  Returns NaN for a sequence where fewer than 50% of codas carry any
    whale identifier.

    Sequence key:
      begus2026_vowel — grouped by date (day), because each recording_id is a
                        single-whale tag session; multiple whales tagged the same
                        day are part of the same social encounter.
      all other sources — grouped by recording_id.
    """
    result = pd.Series(pd.NA, index=df.index, dtype="Int64")

    whale_id = df["whale_photo_id"].where(df["whale_photo_id"].notna(), df["local_speaker_id"])

    seq_key = df["recording_id"].copy().astype(object)
    begus_mask = df["source"] == "begus2026_vowel"
    seq_key.loc[begus_mask] = df.loc[begus_mask, "date"]

    for _key, grp_idx in df.groupby(seq_key).groups.items():
        group_whale = whale_id.loc[grp_idx]
        n_total = len(group_whale)
        n_identified = int(group_whale.notna().sum())
        if n_total > 0 and n_identified / n_total >= 0.5:
            result.loc[grp_idx] = int(group_whale.dropna().nunique())

    return result


def _merge_nearby_recordings(df: pd.DataFrame, gap_hours: float = 4.0) -> pd.DataFrame:
    """Merge recording IDs within the same source+location whose sessions are close in time.

    Two recordings are merged when the last coda of the earlier one is fewer than
    gap_hours before the first coda of the later one.  The canonical recording_id
    for the merged group is the ID of the earliest recording.

    After merging, time_in_recording_s is made continuous across the session:
      begus2026_vowel   — non-canonical codas' time_in_recording_s is shifted by
                          (nc_recording_start − canonical_recording_start) so the
                          inter-session gap is preserved on the time axis.
      hersh2022_pacific — time_in_recording_s is filled from per-coda abs datetime
      sharma2025_birth  — (same as above); previously NaN for these sources

    All other sources lack sub-day timestamps and are left unchanged.
    """
    gap_s = gap_hours * 3600.0

    # Compute UTC Unix seconds for each coda where possible.
    abs_time_s = pd.Series(pd.NA, index=df.index, dtype="Float64")

    for src in ("hersh2022_pacific", "sharma2025_birth"):
        mask = (df["source"] == src) & df["date"].str.contains("T", na=False)
        if mask.any():
            parsed = pd.to_datetime(df.loc[mask, "date"], format="ISO8601", utc=True, errors="coerce")
            abs_time_s.loc[mask] = parsed.astype("int64") / 1e9

    mask = (
        (df["source"] == "begus2026_vowel")
        & df["recording_id"].notna()
        & df["time_in_recording_s"].notna()
    )
    if mask.any():
        rec_dt = pd.to_datetime(df.loc[mask, "recording_id"], utc=True, errors="coerce")
        valid = rec_dt.notna()
        if valid.any():
            valid_idx = rec_dt.index[valid]
            abs_time_s.loc[valid_idx] = (
                rec_dt.loc[valid].astype("int64") / 1e9
                + df.loc[valid_idx, "time_in_recording_s"].astype(float)
            )

    df = df.copy()
    total_merged = 0

    for (source, location), grp_idx in df.groupby(
        ["source", "location"], dropna=False, sort=False
    ).groups.items():
        sub = df.loc[grp_idx]
        sub_time = abs_time_s.loc[grp_idx]

        has_data = sub["recording_id"].notna() & sub_time.notna()
        if not has_data.any():
            continue

        sub_data = sub.loc[has_data].copy()
        sub_data["_t"] = sub_time.loc[has_data].astype(float)

        rec_stats = sub_data.groupby("recording_id")["_t"].agg(["min", "max"])
        rec_stats = rec_stats.sort_values("min")

        if len(rec_stats) < 2:
            continue

        # Greedy forward merge.
        groups: list[list] = []
        current_group = [rec_stats.index[0]]
        current_max = float(rec_stats["max"].iloc[0])

        for i in range(1, len(rec_stats)):
            rec_id = rec_stats.index[i]
            rec_min = float(rec_stats["min"].iloc[i])
            rec_max = float(rec_stats["max"].iloc[i])
            if rec_min - current_max < gap_s:
                current_group.append(rec_id)
                current_max = max(current_max, rec_max)
            else:
                groups.append(current_group)
                current_group = [rec_id]
                current_max = rec_max
        groups.append(current_group)

        merge_map: dict = {}
        for g in groups:
            if len(g) > 1:
                canonical = g[0]
                for rec_id in g[1:]:
                    merge_map[rec_id] = canonical

        if merge_map:
            # Fix time_in_recording_s for begus before updating recording_id.
            # Each non-canonical recording's start is offset from the canonical
            # start by a known number of seconds; add that to time_in_recording_s
            # so the time axis is continuous across the merged session.
            if source == "begus2026_vowel":
                for nc_id, c_id in merge_map.items():
                    canonical_start_s = pd.to_datetime(c_id, utc=True).timestamp()
                    nc_start_s = pd.to_datetime(nc_id, utc=True).timestamp()
                    offset_s = nc_start_s - canonical_start_s
                    nc_mask = sub["recording_id"] == nc_id
                    nc_idx = grp_idx[nc_mask.values]
                    has_t = df.loc[nc_idx, "time_in_recording_s"].notna().values
                    if has_t.any():
                        df.loc[nc_idx[has_t], "time_in_recording_s"] = (
                            df.loc[nc_idx[has_t], "time_in_recording_s"] + offset_s
                        )

            update_mask = sub["recording_id"].isin(merge_map.keys()).values
            update_idx = grp_idx[update_mask]
            df.loc[update_idx, "recording_id"] = (
                df.loc[update_idx, "recording_id"].map(merge_map)
            )
            n_merged = len(merge_map)
            total_merged += n_merged
            print(
                f"  {source} / {location}: "
                f"merged {n_merged} recording IDs into {len(groups)} sessions"
            )

    # For hersh2022_pacific and sharma2025_birth, time_in_recording_s was NaN
    # because each recording had no explicit start-time anchor.  Now that
    # recording_ids are merged, fill it from the per-coda abs datetime so the
    # inter-session gap is properly represented on the time axis.
    for src in ("hersh2022_pacific", "sharma2025_birth"):
        src_mask = df["source"] == src
        if not src_mask.any():
            continue
        sub = df.loc[src_mask]
        sub_abs = abs_time_s.loc[src_mask]
        for rec_id, rec_idx in sub.groupby("recording_id").groups.items():
            rec_abs = sub_abs.loc[rec_idx]
            valid = rec_abs.notna()
            if not valid.any():
                continue
            session_start_s = float(rec_abs[valid].min())
            valid_idx = rec_idx[valid.values]
            df.loc[valid_idx, "time_in_recording_s"] = (
                rec_abs[valid].astype(float) - session_start_s
            )

    print(f"_merge_nearby_recordings: {total_merged} recording IDs merged total")
    return df


def main():
    loaders = [
        (A_load_dswp, "A_dswp.csv"),
        (B_load_birth, "B_birth.csv"),
        (F_load_hersh_pacific, "F_hersh_pacific.csv"),
        (G_load_gero_vowel, "G_gero_vowel.csv"),
        (H_load_idcallr, "H_idcallr.csv"),
        (I_load_bermant_etp, "I_bermant_etp.csv"),
    ]
    intermediate_dir = REPO / "data" / "intermediate"
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    parts = []
    for module, fname in loaders:
        sub = module.load()
        sub.to_csv(intermediate_dir / fname, index=False)
        parts.append(sub)

    df = pd.concat(parts, ignore_index=True)
    df = df[UNIFIED_COLUMNS]  # enforce column order

    df = _apply_whale_grammar_coda_types(df)
    df = _merge_nearby_recordings(df)

    _RECORDING_METHOD: dict[str, str] = {
        "sharma2024_dswp":   "vessel",
        "sharma2025_birth":  "dtag",
        "hersh2022_pacific": "vessel",
        "hersh2021_idcallr": "vessel",
        "begus2026_vowel":   "vessel",
        "bermant2019_etp":   "vessel",
    }
    df["recording_method"] = df["source"].map(_RECORDING_METHOD)

    df["timeofday"] = _derive_timeofday(df)
    df["derived_lat"], df["derived_lon"] = _derive_coords(df)
    df = _derive_symbolic_marking(df)

    df["codas_per_10min"] = _derive_coda_rate(df)
    df["likely_solitary_male"] = _derive_likely_solitary_male(df)
    df["n_unique_whales_in_sequence"] = _derive_unique_whales(df)
    df["year_normalized"] = _derive_year_normalized(df)
    df["coda_duration_s"] = _derive_coda_duration(df)
    df["morpheme_seq"] = _derive_morpheme_seq(df)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    summary = (
        df.groupby("source")
          .agg(codas=("source_coda_id", "size"),
               with_whale_id=("whale_photo_id", lambda s: s.notna().sum()),
               with_clan=("clan", lambda s: s.notna().sum()),
               with_coda_type=("coda_type", lambda s: s.notna().sum()),
               with_time=("time_in_recording_s", lambda s: s.notna().sum()),
               with_timeofday=("timeofday", lambda s: s.notna().sum()),
               is_clan_coda_n=("is_clan_coda", lambda s: s.notna().sum()),
               is_other_terr_n=("is_in_other_clan_territory", lambda s: s.notna().sum()),
               with_coda_rate=("codas_per_10min", lambda s: s.notna().sum()),
               likely_solitary_male_n=("likely_solitary_male", lambda s: s.notna().sum()),
               with_unique_whales=("n_unique_whales_in_sequence", lambda s: s.notna().sum()),
               with_year_normalized=("year_normalized", lambda s: s.notna().sum()),
               with_coda_duration=("coda_duration_s", lambda s: s.notna().sum()),
               with_morpheme_seq=("morpheme_seq", lambda s: s.notna().sum()))
    )
    print(f"merge_unified: wrote {len(df):,} rows -> {OUT.relative_to(REPO)}")
    print(summary.to_string())


if __name__ == "__main__":
    main()
