"""Load the Dominica Sperm Whale Project dataset (Sharma et al. 2024).

Source: https://www.nature.com/articles/s41467-024-47221-8
Data:   https://github.com/Project-CETI/sw-combinatoriality
DOI:    10.1038/s41467-024-47221-8

The Sharma 2024 release ships two views of the same DSWP corpus:

  DominicaCodas.csv          (8,719 codas)  - every Dominica coda Sharma 2024
                                              analysed; includes Clan, Unit,
                                              IDN (persistent whale photo-ID)
                                              and the manual CodaType label,
                                              but the schema caps at 9 ICIs and
                                              has no per-coda timestamps.
  sperm-whale-dialogues.csv  (3,840 codas)  - chorus/dialogue subset; carries
                                              REC (recording id), Whale
                                              (within-recording speaker tag)
                                              and TsTo (seconds from recording
                                              start), and goes up to 29 clicks.

We load DominicaCodas as the primary table, then join the dialogues file on
the fingerprint (nClicks, Duration, ICI1..ICI9) to attach REC/Whale/TsTo where
possible. Dialogue codas with >10 clicks (which DominicaCodas can't represent)
are appended as additional rows so the unified corpus retains long codas.
"""
from collections import defaultdict
from pathlib import Path
import pandas as pd
import numpy as np

from .schema import UNIFIED_COLUMNS, ICI_COLUMNS, normalize_icis

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw" / "dswp_dominica_codas.csv"
DIALOGUES = REPO / "data" / "raw" / "sw_combinatoriality_dialogues.csv"
OUT = REPO / "data" / "intermediate" / "A_dswp.csv"

FP_NDIG = 4  # rounding precision for fingerprint join


def _fingerprint(n_clicks, duration, icis):
    """Stable (nClicks, Duration, ICI1..ICI9) key for joining the two files."""
    rounded = []
    for i in range(9):
        v = icis[i] if i < len(icis) else 0
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0.0
        if not np.isfinite(v):
            v = 0.0
        rounded.append(round(v, FP_NDIG))
    return (int(n_clicks), round(float(duration), FP_NDIG), tuple(rounded))


def _build_dialogue_lookup(dom_df):
    """Walk dialogues in document order, claim a DominicaCodas index per row.

    Returns:
      dom_idx_to_meta: {dominica_row_index: (REC, TsTo, Whale)}
      long_dialogue_rows: list of dialogue rows with nClicks > 10 (no DSWP twin)
      stats: dict with match counts for diagnostics
    """
    dia = pd.read_csv(DIALOGUES)
    dia_ici_cols = [c for c in dia.columns if c.startswith("ICI")]

    # Index DominicaCodas rows by fingerprint, preserving order.
    dom_index = defaultdict(list)
    for i, r in dom_df.iterrows():
        key = _fingerprint(r["nClicks"], r["Duration"],
                           [r[f"ICI{j}"] for j in range(1, 10)])
        dom_index[key].append(i)
    consumed = defaultdict(int)  # next un-claimed slot per fingerprint

    dom_idx_to_meta = {}
    long_dialogue_rows = []
    n_unique = n_ambig = n_long = n_unmatched_short = 0

    for _, r in dia.iterrows():
        n_clicks = int(r["nClicks"])
        if n_clicks > 10:
            long_dialogue_rows.append(r)
            n_long += 1
            continue

        key = _fingerprint(r["nClicks"], r["Duration"],
                           [r[c] for c in dia_ici_cols[:9]])
        candidates = dom_index.get(key, [])
        slot = consumed[key]
        if slot < len(candidates):
            dom_idx = candidates[slot]
            consumed[key] += 1
            dom_idx_to_meta[dom_idx] = (
                str(r["REC"]),
                float(r["TsTo"]) if pd.notna(r["TsTo"]) else np.nan,
                str(int(r["Whale"])) if pd.notna(r["Whale"]) else None,
            )
            if len(candidates) == 1:
                n_unique += 1
            else:
                n_ambig += 1
        else:
            n_unmatched_short += 1

    stats = {
        "dialogue_rows": len(dia),
        "matched_unique": n_unique,
        "matched_ambiguous_resolved_by_order": n_ambig,
        "long_dialogue_rows_appended": n_long,
        "unmatched_short": n_unmatched_short,
    }
    return dom_idx_to_meta, long_dialogue_rows, stats


def _row_from_dominica(r, dialogue_meta):
    n_clicks = int(r["nClicks"])
    ici_vals = [r[f"ICI{i}"] for i in range(1, 10)]
    idn = str(r["IDN"]).strip()
    whale_photo_id = idn if idn not in ("0", "", "nan") else np.nan

    if dialogue_meta is not None:
        rec, t_in_rec, whale_local = dialogue_meta
    else:
        rec, t_in_rec, whale_local = np.nan, np.nan, None

    unified = {
        "source": "sharma2024_dswp",
        "source_doi": "10.1038/s41467-024-47221-8",
        "source_coda_id": str(r["codaNUM2018"]),
        "recording_id": rec,  # REC from dialogues join, else NaN (Date is in `date`)
        "date": str(r["Date"]),
        "time_in_recording_s": t_in_rec,
        "n_clicks": n_clicks,
        "coda_duration_s": float(r["Duration"]),
        "whale_photo_id": whale_photo_id,
        "local_speaker_id": whale_local if whale_local is not None else np.nan,
        "social_unit": str(r["Unit"]),
        "clan": str(r["Clan"]),
        "location": "Dominica, Eastern Caribbean",
        "latitude": np.nan,
        "longitude": np.nan,
    }
    for col, v in zip(ICI_COLUMNS, normalize_icis(ici_vals, n_clicks)):
        unified[col] = v
    return unified


def _row_from_long_dialogue(r):
    """Dialogue codas with >10 clicks - no DominicaCodas counterpart, so we
    emit them with full timing but no Clan/Unit/IDN labels."""
    n_clicks = int(r["nClicks"])
    ici_cols = [c for c in r.index if c.startswith("ICI")]
    ici_vals = [r[c] for c in ici_cols]

    unified = {
        "source": "sharma2024_dswp",
        "source_doi": "10.1038/s41467-024-47221-8",
        "source_coda_id": f"dialogues_{r['REC']}_{r['TsTo']:.4f}",
        "recording_id": str(r["REC"]),
        "date": np.nan,  # dialogues file does not carry a calendar date
        "time_in_recording_s": float(r["TsTo"]) if pd.notna(r["TsTo"]) else np.nan,
        "n_clicks": n_clicks,
        "coda_duration_s": float(r["Duration"]) if pd.notna(r["Duration"]) else float(sum(v for v in ici_vals if pd.notna(v))),
        "whale_photo_id": np.nan,
        "local_speaker_id": str(int(r["Whale"])) if pd.notna(r["Whale"]) else np.nan,
        "social_unit": np.nan,
        "clan": np.nan,
        "location": "Dominica, Eastern Caribbean",
        "latitude": np.nan,
        "longitude": np.nan,
    }
    for col, v in zip(ICI_COLUMNS, normalize_icis(ici_vals, n_clicks)):
        unified[col] = v
    return unified


def load() -> pd.DataFrame:
    dom = pd.read_csv(RAW, encoding="utf-8-sig")
    dom_idx_to_meta, long_rows, stats = _build_dialogue_lookup(dom)

    rows = []
    for i, r in dom.iterrows():
        rows.append(_row_from_dominica(r, dom_idx_to_meta.get(i)))
    for r in long_rows:
        rows.append(_row_from_long_dialogue(r))

    print(f"A_load_dswp: dialogues join: "
          f"{stats['matched_unique']} unique + "
          f"{stats['matched_ambiguous_resolved_by_order']} ambiguous (resolved by order) + "
          f"{stats['long_dialogue_rows_appended']} long dialogue codas appended; "
          f"{stats['unmatched_short']} dialogue rows had no DominicaCodas twin.")

    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def main():
    df = load()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    n_with_time = df["time_in_recording_s"].notna().sum()
    print(f"A_load_dswp: wrote {len(df)} rows ({n_with_time} with timing) "
          f"-> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
