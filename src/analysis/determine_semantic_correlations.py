#!/usr/bin/env python3
"""Rank contextual-feature correlations for coda types and morphemes.

This script reads the unified coda CSV, normalizes location names, and computes
Pearson correlations between binary explanatory units and contextual features.

It supports two explanatory-unit modes:
  1. coda_type      -> one-hot encoded coda labels
  2. morpheme_seq   -> tokenized morphemes from the morpheme sequence

For categorical contextual columns, the script one-hot encodes each level and
computes a Pearson correlation for each level separately.

Outputs:
  - one combined CSV of all results
  - per-split CSV files for overall / by-clan / by-social-unit

Usage example:
  python determine_semantic_correlations.py \
      --input ../data/unified/codas_unified.csv \
      --output-dir ../data/unified/correlation_outputs
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import numpy as np
import pandas as pd


CONTEXTUAL_COLUMNS = [
    "whale_photo_id",
    "location",
    "derived_lat",
    "derived_lon",
    "recording_method",
    "timeofday",
    "is_clan_coda",
    "is_in_other_clan_territory",
    "codas_per_10min",
    "likely_solitary_male",
    "n_unique_whales_in_sequence",
    "year_normalized",
]

COLUMN_EXPLANATIONS = {
    "split": "The subset of data analyzed (e.g., a specific clan, social unit, or the overall dataset).",
    "is_clan_coda_prop": "The proportion (0.0 to 1.0) of times this coda type is categorized as a 'clan coda' in this split.",
    "unit_kind": "Whether the unit analyzed is a full coda label or a tokenized morpheme.",
    "unit_name": "The specific coda type or morpheme being tested for correlation.",
    "context_column": "The original category of the contextual feature (e.g., location, latitude).",
    "context_name": "The specific contextual level or numeric feature being correlated.",
    "n": "The total sample size: the number of rows where both the unit and context have valid data.",
    "unit_count": "Frequency of X: The sum of the unit occurrences (how many times the coda/morpheme appeared).",
    "context_sum": "Magnitude of Y: The total sum of the context values (count for categories, sum for numeric).",
    "pearson_r": "The Pearson correlation coefficient ranging from -1 to 1.",
    "abs_pearson_r": "The absolute value of the Pearson correlation coefficient, used for ranking significance."
}


@dataclass(frozen=True)
class SplitSpec:
    name: str
    column: str | None = None


def normalize_location(value: object) -> object:
    if pd.isna(value):
        return np.nan
    s = str(value).strip()
    if not s:
        return np.nan
    if "eastern caribbean" in s.lower():
        return "Eastern Caribbean"
    return s



def coerce_bool_series(series: pd.Series) -> pd.Series:
    def _coerce(v: object) -> float | np.nan:
        # missing values allowed
        if pd.isna(v):
            return np.nan

        if isinstance(v, str) and v.strip() == "":
            return np.nan

        # actual bools
        if v is True:
            return 1.0

        if v is False:
            return 0.0

        # pandas/parsers often convert bool CSV cols to 1.0 / 0.0
        if isinstance(v, (int, float, np.integer, np.floating)):
            if v == 1 or v == 1.0:
                return 1.0

            if v == 0 or v == 0.0:
                return 0.0

        raise ValueError(
            f"Invalid boolean value encountered: {repr(v)} "
            f"(only True/False, 1/0, or blank allowed)"
        )

    return series.map(_coerce).astype("float64")

def tokenise_morpheme_seq(value: object, mode: str = "auto") -> list[str]:
    if pd.isna(value):
        return []
    s = str(value).strip()
    if not s:
        return []

    if mode == "whitespace":
        return [tok for tok in s.split() if tok]
    if mode == "char":
        return list(s.replace(" ", ""))

    # auto: whitespace-tokenized if spaces exist,
    # otherwise treat entire sequence as one morpheme
    if any(ch.isspace() for ch in s):
        return [tok for tok in s.split() if tok]

    return [s]


def sanitize_name(value: object) -> str:
    s = "NA" if pd.isna(value) else str(value)
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")
    return s or "NA"


def pearson_corr(x: pd.Series, y: pd.Series) -> float:
    valid = x.notna() & y.notna()
    if valid.sum() < 3:
        return np.nan
    xv = x.loc[valid].astype(float)
    yv = y.loc[valid].astype(float)
    if xv.nunique(dropna=True) < 2 or yv.nunique(dropna=True) < 2:
        return np.nan
    return float(xv.corr(yv))



def build_explanatory_matrix(
    df: pd.DataFrame,
    unit_kind: str,
    morpheme_mode: str = "auto",
    min_unit_count: int = 5,
) -> pd.DataFrame:
    if unit_kind == "coda_type":
        series = df["coda_type"].astype("string")
        counts = series.value_counts(dropna=True)
        keep = counts[counts >= min_unit_count].index
        series = series.where(series.isin(keep))
        matrix = pd.get_dummies(series, prefix="coda_type", prefix_sep="=")
        # if include_is_clan_coda(unit_kind, morpheme_mode, df):
        #     matrix["is_clan_coda"] = df["is_clan_coda"].astype(float)
        return matrix.astype(float)

    if unit_kind == "morpheme_seq":
        token_lists = df["morpheme_seq"].map(lambda v: tokenise_morpheme_seq(v, mode=morpheme_mode))
        token_counts: dict[str, int] = {}
        for toks in token_lists:
            for tok in set(toks):
                token_counts[tok] = token_counts.get(tok, 0) + 1
        keep = {tok for tok, count in token_counts.items() if count >= min_unit_count}
        if not keep:
            return pd.DataFrame(index=df.index)

        rows = []
        for toks in token_lists:
            rows.append({tok: 1.0 for tok in set(toks) if tok in keep})
        matrix = pd.DataFrame.from_records(rows, index=df.index).fillna(0.0)
        matrix = matrix.reindex(sorted(matrix.columns), axis=1)


        matrix = matrix.astype(float)

        # if include_is_clan_coda(unit_kind, morpheme_mode, df):
        #     matrix["is_clan_coda"] = df["is_clan_coda"].astype(float)

        return matrix

    raise ValueError(f"Unsupported unit_kind: {unit_kind}")


def build_context_matrix(
    df: pd.DataFrame,
    column: str,
    min_category_count: int = 5,
) -> pd.DataFrame:
    series = df[column]

    if column in {"is_clan_coda", "is_in_other_clan_territory", "likely_solitary_male"}:
        numeric = coerce_bool_series(series)
        return pd.DataFrame({column: numeric}, index=df.index)

    if pd.api.types.is_numeric_dtype(series):
        return pd.DataFrame({column: pd.to_numeric(series, errors="coerce")}, index=df.index)

    if column == "location":
        series = series.map(normalize_location)

    counts = series.astype("string").value_counts(dropna=True)
    keep = counts[counts >= min_category_count].index
    series = series.where(series.astype("string").isin(keep))
    dummies = pd.get_dummies(series.astype("string"), prefix=column, prefix_sep="=")
    return dummies.astype(float)


def iter_splits(df: pd.DataFrame) -> Iterator[tuple[str, pd.DataFrame]]:
    yield "overall", df

    if "clan" in df.columns:
        for value, group in df.groupby("clan", dropna=False, sort=True):
            yield f"clan={sanitize_name(value)}", group

    if "social_unit" in df.columns:
        for value, group in df.groupby("social_unit", dropna=False, sort=True):
            yield f"social_unit={sanitize_name(value)}", group

def compute_correlations_for_split(
    split_name: str,
    split_df: pd.DataFrame,
    unit_kind: str,
    morpheme_mode: str,
    min_unit_count: int,
    min_category_count: int,
    mapped_clans: set,
) -> pd.DataFrame:
    unit_matrix = build_explanatory_matrix(
        split_df,
        unit_kind=unit_kind,
        morpheme_mode=morpheme_mode,
        min_unit_count=min_unit_count,
    )
    if unit_matrix.empty:
        return pd.DataFrame()

    current_clan = None
    if split_name.startswith("clan="):
        current_clan = split_name.split("=")[1]

    results = []

    for context_col in CONTEXTUAL_COLUMNS:
        if context_col not in split_df.columns:
            continue

        context_matrix = build_context_matrix(split_df, context_col, min_category_count=min_category_count)
        if context_matrix.empty:
            continue

        for unit_name in unit_matrix.columns:
            # Calculate the proportion once per unit
            is_clan_coda_val = "" 
            if current_clan in mapped_clans and unit_kind == "coda_type":
                raw_coda_name = unit_name.replace("coda_type=", "")
                sample = split_df[split_df["coda_type"] == raw_coda_name]
                if not sample.empty and "is_clan_coda" in sample.columns:
                    is_clan_coda_val = float(sample["is_clan_coda"].mean())

            # Inner loop for context names
            for ctx_name in context_matrix.columns:
                x = unit_matrix[unit_name]
                y = context_matrix[ctx_name]
                
                r = pearson_corr(x, y)
                if pd.isna(r):
                    continue
                
                valid = x.notna() & y.notna()
                
                results.append({
                    "split": split_name,
                    "is_clan_coda_prop": is_clan_coda_val, # Now assigned correctly to every context result
                    "unit_kind": unit_kind,
                    "unit_name": unit_name,
                    "context_column": context_col,
                    "context_name": ctx_name,
                    "n": int(valid.sum()),
                    "unit_count": float(x.loc[valid].sum()),
                    "context_sum": float(y.loc[valid & (x == 1)].sum()),
                    "pearson_r": r,
                    "abs_pearson_r": abs(r),
                })

    if not results:
        return pd.DataFrame()

    out = pd.DataFrame(results)
    out = out.sort_values(["abs_pearson_r", "pearson_r"], ascending=[False, False]).reset_index(drop=True)
    return out

def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "location" in df.columns:
        df["location"] = df["location"].map(normalize_location)

    for col in [
        "derived_lat",
        "derived_lon",
        "codas_per_10min",
        "n_unique_whales_in_sequence",
        "year_normalized",
    ]:
        if col in df.columns:
            raw = df[col]

            # allow blanks only
            blank_mask = raw.isna() | (raw.astype(str).str.strip() == "")

            try:
                converted = pd.to_numeric(raw.where(~blank_mask, np.nan), errors="raise")
            except Exception:
                bad_mask = ~blank_mask & pd.to_numeric(
                    raw.where(~blank_mask, np.nan),
                    errors="coerce",
                ).isna()

                bad_values = raw[bad_mask].unique().tolist()[:10]

                raise ValueError(
                    f"Column '{col}' contains invalid numeric values: {bad_values}"
                )

            df[col] = converted
    for col in ["is_clan_coda", "is_in_other_clan_territory", "likely_solitary_male"]:
        if col in df.columns:
            df[col] = coerce_bool_series(df[col])

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "unified" / "codas_unified.csv",
        help="Path to the unified coda CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "unified" / "correlation_outputs",
        help="Directory where correlation CSVs will be written.",
    )
    parser.add_argument(
        "--morpheme-mode",
        choices=["auto", "whitespace", "char"],
        default="auto",
        help="How to split morpheme_seq into morpheme units.",
    )
    parser.add_argument(
        "--min-unit-count",
        type=int,
        default=5,
        help="Minimum number of rows a coda type / morpheme must appear in to be included.",
    )
    parser.add_argument(
        "--min-category-count",
        type=int,
        default=5,
        help="Minimum number of rows a categorical context level must appear in to be included.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Write a small top-N CSV for each split in addition to the full results.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input, low_memory=False)

    # Load the mapping
    map_path = Path("/home/dmrivers/Code/whale-ici-data/data/unified/social_unit_clan_map.csv")
    mapping_df = pd.read_csv(map_path)
    # Get a list of unique clans we actually have mapping data for
    mapped_clans = set(mapping_df['clan'].dropna().unique())

    df = prepare_dataframe(df)

    all_frames: list[pd.DataFrame] = []

    for split_name, split_df in iter_splits(df):
        # split_dir = args.output_dir / sanitize_name(split_name)
        # split_dir.mkdir(parents=True, exist_ok=True)

        for unit_kind in ["coda_type", "morpheme_seq"]:
            corr = compute_correlations_for_split(
                split_name=split_name,
                split_df=split_df,
                unit_kind=unit_kind,
                morpheme_mode=args.morpheme_mode,
                min_unit_count=args.min_unit_count,
                min_category_count=args.min_category_count,
                mapped_clans=mapped_clans  # <--- Add this line here
            )
            if corr.empty:
                continue

            # full_path = split_dir / f"{unit_kind}_correlations_full.csv"
            # top_path = split_dir / f"{unit_kind}_correlations_top{args.top_n}.csv"
            # corr.to_csv(full_path, index=False)
            # corr.head(args.top_n).to_csv(top_path, index=False)
            all_frames.append(corr)
            # print(f"Wrote {full_path} ({len(corr):,} rows)")

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        combined = combined.sort_values(["abs_pearson_r", "pearson_r"], ascending=[False, False])
        
        # Create the explanation row
        # Ensure the row has the same columns as the dataframe
        explanation_row = pd.DataFrame([COLUMN_EXPLANATIONS], columns=combined.columns)
        
        # Concatenate: Explanation row first, then the data
        final_output = pd.concat([explanation_row, combined], ignore_index=True)
        
        combined_path = args.output_dir / "all_correlations_combined.csv"
        final_output.to_csv(combined_path, index=False)
        print(f"Wrote combined results with explanations to {combined_path}")
    else:
        print("No correlations were produced. Check thresholds and input columns.")


if __name__ == "__main__":
    main()
