"""Load the Beguš et al. coda-vowel-phonology dataset.

Source: "The phonology of sperm whale coda vowels"
OSF deposit: https://osf.io/9t6qu
Data files (in data/raw/gero_vowel_phonology/):
  codamd.csv                       — coda metadata (codatype, duration, whale)
  focal-coarticulation-metadata.csv — timestamps for 1,139 of the 1,375 codas

The dataset does not include per-click onset times, so ICIs cannot be read
directly. Instead, we reconstruct ICIs by:
  1. Computing the median ICI proportions (ICI_i / sum_of_ICIs) for each
     codatype across all matching rows in the DSWP corpus (Sharma 2024),
     which uses the same traditional codatype vocabulary.
  2. Scaling those proportions by the actual coda Duration from codamd.csv.

The reconstructed ICIs honour each coda's real duration while embedding the
typical within-codatype rhythm from the much larger DSWP reference set.
NOISE-labelled codatypes (e.g. "5-NOISE") are reconstructed the same way but
with higher inter-coda variance in the reference; treat them with caution.

n_clicks is taken from the DSWP mode of nClicks per CodaType, which matches
the actual per-click counts in the original audio (verified against the
clickspec feather file in the source OSF deposit).

time_in_recording_s is computed as (codadt − tagondt) in seconds, where both
are absolute datetimes stored in focal-coarticulation-metadata.csv. 236 codas
that never appear in a consecutive-pair record have NaN for this field.

Whale names (ATWOOD, FORK, …) are persistent Dominica photo-IDs used across
the DSWP study and stored as both whale_photo_id and local_speaker_id.
"""
from pathlib import Path
import numpy as np
import pandas as pd

from .schema import UNIFIED_COLUMNS, ICI_COLUMNS, normalize_icis

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw" / "gero_vowel_phonology"
DSWP_RAW = REPO / "data" / "raw" / "dswp_dominica_codas.csv"
OUT = REPO / "data" / "intermediate" / "G_gero_vowel.csv"

SOURCE = "begus2026_vowel"
SOURCE_DOI = "https://osf.io/9t6qu"
LOCATION = "Dominica, Eastern Caribbean"
DSWP_ICI_COLS = [f"ICI{i}" for i in range(1, 10)]


def _build_ici_fractions() -> tuple[dict, dict]:
    """Return (fractions, n_clicks_map) computed from DSWP per codatype.

    fractions[codatype]  → list of length n_clicks-1, summing to 1.0
    n_clicks_map[codatype] → int
    """
    dswp = pd.read_csv(DSWP_RAW, encoding="utf-8-sig")
    fractions: dict = {}
    n_clicks_map: dict = {}

    for ct, group in dswp.groupby("CodaType"):
        n_clicks = int(group["nClicks"].mode().iloc[0])
        n_ici = n_clicks - 1
        n_clicks_map[ct] = n_clicks

        if n_ici <= 0:
            fractions[ct] = []
            continue

        real_icis = group[DSWP_ICI_COLS[:n_ici]].values.astype(float)
        row_sums = real_icis.sum(axis=1, keepdims=True)
        frac_matrix = real_icis / row_sums
        med_fracs = np.nanmedian(frac_matrix, axis=0)
        # Column-wise medians of row-normalised data don't sum to exactly 1;
        # renormalise so reconstructed ICIs sum exactly to Duration.
        med_fracs /= med_fracs.sum()
        fractions[ct] = med_fracs.tolist()

    return fractions, n_clicks_map


def _load_timestamps() -> pd.DataFrame:
    """Build codanum → (tagondt, codadt) from focal-coarticulation-metadata.

    Covers both the focal codanum and prevcodanum in each consecutive pair,
    yielding timestamps for 1,139 of the 1,375 codas.
    """
    focal = pd.read_csv(RAW / "focal-coarticulation-metadata.csv", low_memory=False)

    focal_side = focal[["codanum", "tagondt", "codadt"]].copy()
    focal_side["tagondt"] = pd.to_datetime(focal_side["tagondt"])
    focal_side["codadt"] = pd.to_datetime(focal_side["codadt"])

    prev_side = focal[["prevcodanum", "prevtagondt", "prevcodadt"]].rename(columns={
        "prevcodanum": "codanum",
        "prevtagondt": "tagondt",
        "prevcodadt": "codadt",
    }).copy()
    prev_side["tagondt"] = pd.to_datetime(prev_side["tagondt"])
    prev_side["codadt"] = pd.to_datetime(prev_side["codadt"])

    combined = pd.concat([focal_side, prev_side], ignore_index=True)
    combined = combined.drop_duplicates("codanum", keep="first")
    return combined.set_index("codanum")


def load() -> pd.DataFrame:
    codamd = pd.read_csv(RAW / "codamd.csv", low_memory=False)
    ici_fractions, n_clicks_map = _build_ici_fractions()
    ts = _load_timestamps()

    codamd = codamd.join(ts, on="codanum")

    rows = []
    n_no_ts = 0
    n_unknown_ct = 0

    for _, r in codamd.iterrows():
        codatype = str(r["codatype"])
        duration = float(r["Duration"])
        tagondt = r.get("tagondt")
        codadt = r.get("codadt")

        if pd.notna(tagondt) and pd.notna(codadt):
            recording_id = pd.Timestamp(tagondt).strftime("%Y-%m-%d %H:%M:%S")
            date_str = pd.Timestamp(codadt).strftime("%Y-%m-%d")
            time_s = (pd.Timestamp(codadt) - pd.Timestamp(tagondt)).total_seconds()
        else:
            recording_id = np.nan
            date_str = np.nan
            time_s = np.nan
            n_no_ts += 1

        fracs = ici_fractions.get(codatype)
        n_clicks = n_clicks_map.get(codatype)

        if fracs is None:
            n_unknown_ct += 1
            ici_vals = []
            n_clicks = n_clicks if n_clicks is not None else np.nan
        else:
            ici_vals = [f * duration for f in fracs]

        row = {
            "source": SOURCE,
            "source_doi": SOURCE_DOI,
            "source_coda_id": str(int(r["codanum"])),
            "recording_id": recording_id,
            "date": date_str,
            "time_in_recording_s": time_s,
            "n_clicks": n_clicks,
            "coda_duration_s": duration,
            "whale_photo_id": str(r["whale"]) if pd.notna(r["whale"]) else np.nan,
            "local_speaker_id": str(r["whale"]) if pd.notna(r["whale"]) else np.nan,
            "coda_type": codatype if codatype not in ("nan", "", "None") else np.nan,
            "social_unit": np.nan,
            "clan": np.nan,
            "location": LOCATION,
            "latitude": np.nan,
            "longitude": np.nan,
        }
        for col, v in zip(ICI_COLUMNS, normalize_icis(ici_vals, n_clicks or 0)):
            row[col] = v

        rows.append(row)

    print(
        f"G_load_gero_vowel: {len(rows)} codas; "
        f"{len(rows) - n_no_ts} with timestamps, "
        f"{n_no_ts} without; "
        f"{n_unknown_ct} unknown codatypes (ICIs left NaN)."
    )
    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def main():
    df = load()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"G_load_gero_vowel: wrote {len(df)} rows -> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
