"""Load new-location codas from the Hersh et al. 2021 IDcallR sperm whale dataset.

Source: Hersh, T.A. et al. (2021). Using identity calls to detect structure in
acoustic datasets. Methods in Ecology and Evolution 12(7).
DOI: 10.1111/2041-210X.13524
Data: IDcallR_SpermWhaleCodas.csv (companion to the IDcallR R package)

We include only locations NOT already covered by hersh2022_pacific (which is
more complete and carries clan labels and coordinates). The inclusions are:

  BAL     Balearic Islands              1,749 codas  (Rendell et al. 2014)
  CAR*    Eastern Caribbean, pre-2005   1,551 codas  (* Watkins archive 1981–1995 only)
  AtPAN   Atlantic Panama                 313 codas  (Weilgart & Whitehead 1997)
  JAR     Jarvis Island, C. Pacific       510 codas
  GOM     Gulf of Mexico                  102 codas  (Weilgart & Whitehead 1997)
  NEW      44 codas  (location unresolved — possibly N. Atlantic or Pacific)

CAR 2005+ is excluded: those codas come from the Dominica Sperm Whale Project
and are already in sharma2024_dswp with photo-IDs, clan labels, and timestamps.
The Watkins archive portion (years ≤ 2004) is unique to this source.

All other IDcallR locations (GAL, ECU, PER, BAK, EAS, CHI, PacPAN, TON, etc.)
are covered by hersh2022_pacific with better annotation.

Caveats:
- No clan labels in IDcallR: `clan` is NaN for all rows.
- No per-coda coordinates: `latitude` / `longitude` are NaN.
- No per-coda timestamps: `time_in_recording_s` is NaN.
- `grpvar` is a repertoire-day code used for `recording_id` (same as hersh2022).
- `totdur` (post-Nov-2022 corrected sum of ICIs) → `coda_duration_s`.
"""
from pathlib import Path
import pandas as pd
import numpy as np

from .schema import UNIFIED_COLUMNS, ICI_COLUMNS, normalize_icis

REPO = Path(__file__).resolve().parents[2]
RAW  = REPO / "data" / "raw" / "IDcallR_SpermWhaleCodas.csv"
OUT  = REPO / "data" / "intermediate" / "H_idcallr.csv"

# Locations not covered by hersh2022_pacific
INCLUDE_LOCS = {"BAL", "AtPAN", "GOM", "JAR", "NEW"}
# CAR pre-DSWP era only (sharma2024_dswp covers 2005+)
CAR_WATKINS_MAX_YEAR = 2004

LOC_TO_REGION = {
    "BAL":   "Balearic Islands",
    "AtPAN": "Atlantic Panama",
    "GOM":   "Gulf of Mexico",
    "JAR":   "Jarvis Island",
    "NEW":   "NEW (location unresolved)",
    "CAR":   "Eastern Caribbean, Watkins archive",
}

ICI_IN = [f"ICI{i}" for i in range(1, 31)]


def load() -> pd.DataFrame:
    df = pd.read_csv(RAW, na_values=["#N/A"], low_memory=False)

    mask = (
        df["recloc"].isin(INCLUDE_LOCS)
        | ((df["recloc"] == "CAR") & (df["year"] <= CAR_WATKINS_MAX_YEAR))
    )
    df = df[mask].copy()

    rows = []
    for _, r in df.iterrows():
        n_clicks = int(r["nclicks"])
        ici_vals  = [r[c] for c in ICI_IN]

        loc_abbr = r["recloc"]
        region   = LOC_TO_REGION.get(loc_abbr, loc_abbr)
        location = f"{region} ({loc_abbr})"

        unified = {
            "source":             "hersh2021_idcallr",
            "source_doi":         "10.1111/2041-210X.13524",
            "source_coda_id":     str(r["codanum"]),
            "recording_id":       str(int(r["grpvar"])),
            "date":               str(r["date"]),
            "time_in_recording_s": np.nan,
            "n_clicks":           n_clicks,
            "coda_duration_s":    float(r["totdur"]) if pd.notna(r["totdur"]) else np.nan,
            "whale_photo_id":     np.nan,
            "local_speaker_id":   np.nan,
            "social_unit":        str(int(r["grpvar"])),
            "clan":               np.nan,
            "location":           location,
            "latitude":           np.nan,
            "longitude":          np.nan,
        }
        for col, v in zip(ICI_COLUMNS, normalize_icis(ici_vals, n_clicks)):
            unified[col] = v
        rows.append(unified)

    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def main():
    df = load()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"H_load_idcallr: wrote {len(df)} rows -> {OUT.relative_to(REPO)}")
    for loc, count in df["location"].value_counts().items():
        print(f"  {loc}: {count}")


if __name__ == "__main__":
    main()
