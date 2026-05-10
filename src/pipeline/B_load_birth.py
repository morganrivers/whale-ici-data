"""Load the sperm whale live birth dataset (Sharma et al. 2025).

Source: https://www.nature.com/articles/s41598-025-27438-3
DOI:    10.1038/s41598-025-27438-3

Recordings (CETI23-XXX) come from CETI hydrophone tags on 2023-07-08 off Dominica.
The `SegmentWhale` column distinguishes overlapping callers WITHIN a recording but
is NOT a persistent photo-ID — we expose it as `local_speaker_id`.

Recording timestamps are derived by chaining recordings consecutively starting from
CETI23-277 at 10:53:00 Dominica local time (14:53:00 UTC) — the "First Acoustic
Recording" landmark from the supplementary event table.  Because per-recording start
times are not in the supplement, later recordings may be shifted by up to ~66 min
relative to the known 15:29 anchor of the last recording (CETI23-294).
"""
import datetime as dt
from pathlib import Path
import pandas as pd
import numpy as np

from .schema import UNIFIED_COLUMNS, ICI_COLUMNS, normalize_icis

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw" / "sharma2025_birth.csv"
OUT = REPO / "data" / "intermediate" / "B_birth.csv"

# 10:53:00 Dominica local (AST = UTC-4) → 14:53:00 UTC
_FIRST_RECORDING_START_UTC = dt.datetime(2023, 7, 8, 14, 53, 0, tzinfo=dt.timezone.utc)


def _chain_recording_starts(df_raw: pd.DataFrame) -> dict:
    """Return {recording_id: start_datetime_utc} by chaining recordings back-to-back."""
    recordings = sorted(df_raw["Recording"].unique(), key=lambda r: int(r.split("-")[1]))
    max_tfs = df_raw.groupby("Recording")["TfS"].max()

    starts: dict = {}
    t = _FIRST_RECORDING_START_UTC
    for rec in recordings:
        starts[rec] = t
        t = t + dt.timedelta(seconds=float(max_tfs[rec]))
    return starts


def load() -> pd.DataFrame:
    # File has a banner row "Whale Birth Audio_annotations" before the real header
    df_raw = pd.read_csv(RAW, skiprows=1)

    rec_starts = _chain_recording_starts(df_raw)

    ici_cols_in = [c for c in df_raw.columns if c.startswith("ICI")]
    rows = []
    for idx, r in df_raw.iterrows():
        ici_vals = [r[c] for c in ici_cols_in]
        # n_clicks = number of non-zero ICIs + 1 (each ICI is between two clicks)
        n_real_icis = sum(1 for v in ici_vals if v and v != 0 and not pd.isna(v))
        n_clicks = n_real_icis + 1 if n_real_icis > 0 else 0
        coda_duration = sum(v for v in ici_vals if v and not pd.isna(v))

        recording_id = str(r["Recording"]).strip()
        seg = r["SegmentWhale"]
        local_speaker = f"{recording_id}_seg{int(seg)}" if not pd.isna(seg) else np.nan

        tfs = float(r["TfS"]) if not pd.isna(r["TfS"]) else None
        if tfs is not None and recording_id in rec_starts:
            coda_utc = rec_starts[recording_id] + dt.timedelta(seconds=tfs)
            date_str = coda_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        else:
            date_str = "2023-07-08"

        unified = {
            "source": "sharma2025_birth",
            "source_doi": "10.1038/s41598-025-27438-3",
            "source_coda_id": f"row{idx}",
            "recording_id": recording_id,
            "date": date_str,
            "time_in_recording_s": tfs if tfs is not None else np.nan,
            "n_clicks": n_clicks,
            "coda_duration_s": coda_duration,
            "whale_photo_id": np.nan,  # birth dataset does not provide persistent photo-IDs
            "local_speaker_id": local_speaker,
            "social_unit": np.nan,
            "clan": "EC1",  # Dominica CETI work is on the Eastern Caribbean clan
            "location": "Dominica, Eastern Caribbean (live birth event)",
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
    print(f"B_load_birth: wrote {len(df)} rows -> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
