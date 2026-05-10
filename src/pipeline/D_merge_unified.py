"""Concatenate all per-source intermediate CSVs into the unified corpus.

Re-runs each loader so the pipeline is reproducible end-to-end with one entry point:
    python -m src.pipeline.D_merge_unified
"""
from pathlib import Path
import pandas as pd

from .schema import UNIFIED_COLUMNS
from . import A_load_dswp, B_load_birth, F_load_hersh_pacific, G_load_gero_vowel, H_load_idcallr, I_load_bermant_etp

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "unified" / "codas_unified.csv"


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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    summary = (
        df.groupby("source")
          .agg(codas=("source_coda_id", "size"),
               with_whale_id=("whale_photo_id", lambda s: s.notna().sum()),
               with_clan=("clan", lambda s: s.notna().sum()),
               with_coda_type=("coda_type", lambda s: s.notna().sum()),
               with_time=("time_in_recording_s", lambda s: s.notna().sum()))
    )
    print(f"D_merge_unified: wrote {len(df):,} rows -> {OUT.relative_to(REPO)}")
    print(summary.to_string())


if __name__ == "__main__":
    main()
