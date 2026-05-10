"""Load ETP-exclusive codas from Bermant et al. 2019.

Source: Bermant, Bronstein, Wood, Gero & Gruber 2019, "Deep Machine Learning
Techniques for the Detection and Classification of Sperm Whale Bioacoustics",
Scientific Reports 9:12588.
DOI:  10.1038/s41598-019-48909-4
Data: Supplementary Data 3 (ETP.xlsx / MOESM3) — 16,995 ETP codas with
      precise timestamps and numeric coda-type labels.

Only the ~3,317 rows whose ICI fingerprint does NOT appear in the Hersh 2022
Pacific dataset are loaded here; the remainder are already represented in
hersh2022_pacific and are enriched in F_load_hersh_pacific.py.

Clan labels are kept as-is from the ETP file (Regular, Short, FourPlus,
PlusOne, Caribbean, Tonga) since the exact correspondence to Hersh clan codes
(REG, SH, FP, PO, PALI, …) is uncertain.

The ETP file does not carry per-coda location coordinates, so latitude and
longitude are NaN. Location is set to "Eastern Tropical Pacific" for all
rows (the Caribbean and Tonga clans were recorded in the ETP field area).
"""
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np

from .schema import UNIFIED_COLUMNS, ICI_COLUMNS, normalize_icis

REPO = Path(__file__).resolve().parents[2]
ETP_RAW = REPO / "data" / "raw" / "ETP.xlsx"
HERSH_RAW = REPO / "data" / "raw" / "hersh2022_pacific_codas.csv"
OUT = REPO / "data" / "intermediate" / "I_bermant_etp.csv"

ETP_ICI_COLS = [f"ICI{i}" for i in range(1, 12)]
HERSH_ICI_COLS = [f"ICI{i}" for i in range(1, 31)]


def _fingerprint(n_clicks, row, ici_cols):
    """(n_clicks, tuple of non-zero ICIs rounded to 3 dp)."""
    vals = []
    for c in ici_cols:
        v = row[c]
        if pd.isna(v) or float(v) == 0.0:
            break
        vals.append(round(float(v), 3))
    return (int(n_clicks), tuple(vals))


def _build_hersh_fingerprint_set():
    hersh = pd.read_csv(HERSH_RAW, na_values=["#N/A"], low_memory=False)
    fps = set()
    for _, r in hersh.iterrows():
        fps.add(_fingerprint(r["nclicks"], r, HERSH_ICI_COLS))
    return fps


def load() -> pd.DataFrame:
    hersh_fps = _build_hersh_fingerprint_set()

    etp = pd.read_excel(ETP_RAW)
    etp["FullDateTime"] = pd.to_datetime(etp["FullDateTime"])

    rows = []
    for _, r in etp.iterrows():
        fp = _fingerprint(r["NumClicks"], r, ETP_ICI_COLS)
        if fp in hersh_fps:
            continue  # already covered by hersh2022_pacific

        n_clicks = int(r["NumClicks"])
        ici_vals = [r[c] for c in ETP_ICI_COLS]

        ct_raw = r["Coda Type"]
        coda_type = str(int(ct_raw)) if pd.notna(ct_raw) else np.nan

        unified = {
            "source": "bermant2019_etp",
            "source_doi": "10.1038/s41598-019-48909-4",
            "source_coda_id": str(int(r["CodaNum"])),
            "recording_id": np.nan,
            "date": r["FullDateTime"].strftime("%Y-%m-%dT%H:%M:%S"),
            "time_in_recording_s": np.nan,
            "n_clicks": n_clicks,
            "coda_duration_s": float(r["TotalDur"]),
            "whale_photo_id": np.nan,
            "local_speaker_id": np.nan,
            "social_unit": np.nan,
            "clan": str(r["ClanName"]),
            "coda_type": coda_type,
            "location": "Eastern Tropical Pacific",
            "latitude": np.nan,
            "longitude": np.nan,
        }
        for col, v in zip(ICI_COLUMNS, normalize_icis(ici_vals, n_clicks)):
            unified[col] = v
        rows.append(unified)

    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def main():
    df = load()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"I_load_bermant_etp: wrote {len(df)} rows "
          f"({df['clan'].value_counts().to_dict()}) "
          f"-> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
