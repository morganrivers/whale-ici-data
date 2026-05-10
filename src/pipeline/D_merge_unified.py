"""Concatenate all per-source intermediate CSVs into the unified corpus.

Re-runs each loader so the pipeline is reproducible end-to-end with one entry point:
    python -m src.pipeline.D_merge_unified
"""
import datetime as _dt
from pathlib import Path
import pandas as pd

from .schema import UNIFIED_COLUMNS
from . import A_load_dswp, B_load_birth, F_load_hersh_pacific, G_load_gero_vowel, H_load_idcallr, I_load_bermant_etp

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "unified" / "codas_unified.csv"

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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    summary = (
        df.groupby("source")
          .agg(codas=("source_coda_id", "size"),
               with_whale_id=("whale_photo_id", lambda s: s.notna().sum()),
               with_clan=("clan", lambda s: s.notna().sum()),
               with_coda_type=("coda_type", lambda s: s.notna().sum()),
               with_time=("time_in_recording_s", lambda s: s.notna().sum()),
               with_timeofday=("timeofday", lambda s: s.notna().sum()))
    )
    print(f"D_merge_unified: wrote {len(df):,} rows -> {OUT.relative_to(REPO)}")
    print(summary.to_string())


if __name__ == "__main__":
    main()
