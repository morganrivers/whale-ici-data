"""Load the Hersh et al. 2022 Pacific multi-clan ICI corpus.

Source: Hersh, Gero, Rendell, Cantor, Weilgart, Amano, Dawson, Slooten, Johnson,
Kerr & Whitehead 2022, "Evidence from sperm whale clans of symbolic marking in
non-human cultures", PNAS 119(37):e2201692119.
DOI:  10.1073/pnas.2201692119
Data: https://osf.io/ae6pd/  (RawCodaInterClickIntervals/pacific_coda_data.csv)

Covers 24,237 codas from 23 Pacific regions (1978-2017) attributed to seven
vocal clans (FP, PALI, PO, REG, RI, SH, SI) plus codas in repertoires that did
not pass the within-clan correlation threshold (clan = NaN). 3,113 of the
Galapagos codas are Watkins-archive recordings re-annotated by Hersh and carry
string IDs of the form WatGal### in the source `coda_number` column.

Caveats:
- No persistent whale photo-ID or per-recording timestamp: every coda has
  NaN for `whale_photo_id`, `local_speaker_id`, and `time_in_recording_s`,
  which means Hersh codas will not get an `extra_click` label from
  E_classify (they will get a rhythm assignment, since that needs only ICIs).
- `grpvar` is a repertoire-day code, not a persistent social unit, so it goes
  to `recording_id` and `social_unit` stays NaN.
- The CSV uses the literal string "#N/A" for missing values; we read them as
  NaN. Trailing zeros past `nclicks - 1` are zero-padding (not real ICIs)
  and `normalize_icis` converts them to NaN.
- `duration` in the CSV is post-Nov-2022-fix sum-of-ICIs (per the upstream
  README), so it is consistent with our `coda_duration_s` definition.

ETP enrichment (Bermant et al. 2019, DOI 10.1038/s41598-019-48909-4):
- The ETP.xlsx supplementary contains precise timestamps (FullDateTime) for
  codas that overlap with this dataset. Where a hersh coda matches ETP by
  date + n_clicks + ICI fingerprint, its `date` is updated to the full ETP
  datetime string (ISO 8601 format).
"""
from collections import defaultdict
from pathlib import Path
import pandas as pd
import numpy as np

from .schema import UNIFIED_COLUMNS, ICI_COLUMNS, normalize_icis

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw" / "hersh2022_pacific_codas.csv"
ETP_RAW = REPO / "data" / "raw" / "ETP.xlsx"
OUT = REPO / "data" / "intermediate" / "F_hersh_pacific.csv"

ETP_ICI_COLS = [f"ICI{i}" for i in range(1, 12)]


def _etp_fingerprint(n_clicks, ici_row, ici_cols):
    """(n_clicks, tuple of non-zero ICIs rounded to 3 dp) for ETP rows."""
    vals = []
    for c in ici_cols:
        v = ici_row[c]
        if pd.isna(v) or v == 0.0:
            break
        vals.append(round(float(v), 3))
    return (int(n_clicks), tuple(vals))


def _build_etp_datetime_lookup():
    """Return dict keyed by (n_clicks, date_str, ici_tuple) -> ISO datetime str.

    Consumed with a counter so duplicate fingerprints on the same date are
    matched in document order (first ETP row to first hersh row with that key).
    """
    if not ETP_RAW.exists():
        return {}, {}

    etp = pd.read_excel(ETP_RAW)
    etp["FullDateTime"] = pd.to_datetime(etp["FullDateTime"])

    # keyed by (n_clicks, date_YYYYMMDD, ici_tuple) -> list of ISO datetime strings
    by_date = defaultdict(list)
    # fallback keyed by (n_clicks, ici_tuple) -> list of ISO datetime strings
    by_fp = defaultdict(list)

    for _, r in etp.iterrows():
        fp = _etp_fingerprint(r["NumClicks"], r, ETP_ICI_COLS)
        date_str = r["FullDateTime"].strftime("%Y-%m-%d")
        iso_dt = r["FullDateTime"].strftime("%Y-%m-%dT%H:%M:%S")
        by_date[(fp, date_str)].append(iso_dt)
        by_fp[fp].append(iso_dt)

    return by_date, by_fp

# Region abbreviations from Hersh et al. 2022 supplementary Table S1.
# (The CSV uses JPN_Ku/JPN_Og while Table S1 prints JPN_K/JPN_O — we honour the
# CSV's spelling.)
LOC_TO_REGION = {
    "BAK":    "Baker Island",
    "BOW":    "SGaan Kinghlas-Bowie Seamount",
    "CHL_N":  "Northern Chile",
    "CHL_S":  "Southern Chile",
    "EAS":    "Easter Island",
    "ECU":    "Ecuador",
    "ESP":    "Equatorial South Pacific",
    "GAL":    "Galapagos Islands",
    "JPN_Ku": "Kumano coast of Japan",
    "JPN_Og": "Ogasawara Islands of Japan",
    "KIR":    "Kiribati",
    "MID":    "Midway Atoll",
    "MNP":    "Mariana Islands",
    "MRQ":    "Marquesas Islands",
    "NRU":    "Nauru",
    "NZL_N":  "Northern New Zealand",
    "NZL_S":  "Southern New Zealand",
    "PAL":    "Palau",
    "PAN":    "Panama",
    "PER":    "Peru",
    "PNG":    "Papua New Guinea",
    "SOC":    "Sea of Cortez",
    "TON":    "Tonga",
}

ICI_IN = [f"ICI{i}" for i in range(1, 31)]


def load() -> pd.DataFrame:
    df = pd.read_csv(RAW, na_values=["#N/A"], low_memory=False)

    # Latitude/longitude have stray non-numeric strings (e.g. "Unk") for some
    # Watkins-era rows. Coerce them to NaN.
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    unmapped = sorted(set(df["loc"].dropna().unique()) - LOC_TO_REGION.keys())
    if unmapped:
        print(f"F_load_hersh_pacific: warning - unmapped loc codes: {unmapped}")

    etp_by_date, _ = _build_etp_datetime_lookup()
    consumed = defaultdict(int)
    n_etp_enriched = 0

    rows = []
    for _, r in df.iterrows():
        n_clicks = int(r["nclicks"])
        ici_vals = [r[c] for c in ICI_IN]

        loc_abbr = r["loc"] if pd.notna(r["loc"]) else None
        region = LOC_TO_REGION.get(loc_abbr, loc_abbr)
        location = f"{region} ({loc_abbr})" if loc_abbr else np.nan

        clan = r["clan_name"] if pd.notna(r["clan_name"]) else np.nan
        coda_type_raw = r.get("coda_type", np.nan)
        coda_type = str(int(coda_type_raw)) if pd.notna(coda_type_raw) else np.nan

        # Try to enrich date with ETP precise timestamp.
        hersh_date = str(r["date"])
        fp = _etp_fingerprint(n_clicks, r, [f"ICI{i}" for i in range(1, 31)])
        lookup_key = (fp, hersh_date)
        candidates = etp_by_date.get(lookup_key, [])
        slot = consumed[lookup_key]
        if slot < len(candidates):
            date_out = candidates[slot]
            consumed[lookup_key] += 1
            n_etp_enriched += 1
        else:
            date_out = hersh_date

        unified = {
            "source": "hersh2022_pacific",
            "source_doi": "10.1073/pnas.2201692119",
            "source_coda_id": str(r["coda_number"]),  # mostly numeric, but Watkins archive uses "WatGal###"
            "recording_id": str(int(r["grpvar"])),    # repertoire-day code
            "date": date_out,
            "time_in_recording_s": np.nan,
            "n_clicks": n_clicks,
            "coda_duration_s": float(r["duration"]),
            "whale_photo_id": np.nan,
            "local_speaker_id": np.nan,
            "social_unit": np.nan,  # grpvar is a repertoire-day, not a persistent unit
            "clan": clan,
            "coda_type": coda_type,
            "location": location,
            "latitude": float(r["latitude"]) if pd.notna(r["latitude"]) else np.nan,
            "longitude": float(r["longitude"]) if pd.notna(r["longitude"]) else np.nan,
        }
        for col, v in zip(ICI_COLUMNS, normalize_icis(ici_vals, n_clicks)):
            unified[col] = v
        rows.append(unified)

    print(f"F_load_hersh_pacific: enriched {n_etp_enriched} rows with ETP precise datetime")
    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def main():
    df = load()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    n_with_clan = df["clan"].notna().sum()
    n_with_coda_type = df["coda_type"].notna().sum()
    print(f"F_load_hersh_pacific: wrote {len(df)} rows "
          f"({n_with_clan} with clan, {n_with_coda_type} with coda_type) "
          f"-> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
