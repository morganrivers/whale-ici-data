"""Concatenate all per-source intermediate CSVs into the unified corpus.

Re-runs each loader so the pipeline is reproducible end-to-end with one entry point:
    python -m src.pipeline.D_merge_unified
"""
from pathlib import Path
import pandas as pd

from .schema import UNIFIED_COLUMNS
from . import A_load_dswp, B_load_birth, F_load_hersh_pacific, E_classify

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "unified" / "codas_unified.csv"


def main():
    loaders = [
        (A_load_dswp, "A_dswp.csv"),
        (B_load_birth, "B_birth.csv"),
        (F_load_hersh_pacific, "F_hersh_pacific.csv"),
    ]
    intermediate_dir = REPO / "data" / "intermediate"
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    parts = []
    for module, fname in loaders:
        sub = module.load()
        sub.to_csv(intermediate_dir / fname, index=False)
        parts.append(sub)

    df = pd.concat(parts, ignore_index=True)

    # Stage E: fill in rhythm + extra_click using the Sharma 2024 reconstruction.
    df = E_classify.classify(df)
    df = df[UNIFIED_COLUMNS]  # enforce column order

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    summary = (
        df.groupby("source")
          .agg(codas=("source_coda_id", "size"),
               with_whale_id=("whale_photo_id", lambda s: s.notna().sum()),
               with_clan=("clan", lambda s: s.notna().sum()),
               with_rhythm=("rhythm", lambda s: s.notna().sum()),
               with_extra_click=("extra_click", lambda s: s.notna().sum()))
    )
    print(f"D_merge_unified: wrote {len(df):,} rows -> {OUT.relative_to(REPO)}")
    print(summary.to_string())


if __name__ == "__main__":
    main()
