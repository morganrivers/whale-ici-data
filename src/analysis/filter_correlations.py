#!/usr/bin/env python3
"""Filter correlation results into a smaller, higher-confidence CSV."""

from pathlib import Path

import pandas as pd


INPUT_CSV = Path("data/unified/correlation_outputs/all_correlations_combined.csv")
OUTPUT_CSV = Path("data/unified/correlation_outputs/all_correlations_filtered.csv")

MIN_N = 1000
MIN_ABS_PEARSON = 0.1
EXCLUDED_CONTEXT_COLUMNS = {"whale_photo_id", "location","is_clan_coda"}
def main() -> None:
    df = pd.read_csv(INPUT_CSV)

    # 1. Identify your "pinned" row (assuming it's the very first row of the CSV)
    # We pull it out into its own tiny dataframe
    pinned_row = df.iloc[[0]].copy()
    
    # 2. Grab the rest of the data for processing
    other_rows = df.iloc[1:].copy()

    # 3. Clean and convert only the data rows
    # Using 'coerce' ensures that if there are any other header-strings, they won't crash it
    other_rows["pearson_r"] = pd.to_numeric(other_rows["pearson_r"], errors='coerce')
    other_rows["abs_pearson_r"] = pd.to_numeric(other_rows["abs_pearson_r"], errors='coerce')
    other_rows["n"] = pd.to_numeric(other_rows["n"], errors='coerce')

    # 4. Compute R^2 and Filter the data rows
    other_rows["r_squared"] = other_rows["pearson_r"] ** 2
    
    # Add your new exclusion here
    EXCLUDED_CONTEXT_COLUMNS.add("is_clan_coda")

    filtered_data = other_rows[
        (other_rows["n"] >= MIN_N)
        & (other_rows["abs_pearson_r"] >= MIN_ABS_PEARSON)
        # & (~other_rows["context_column"].isin(EXCLUDED_CONTEXT_COLUMNS))
        & (other_rows["context_column"].isin({"timeofday"}))
    ].copy()

    # 5. Sort only the filtered data
    filtered_data = filtered_data.sort_values(
        ["r_squared", "abs_pearson_r"],
        ascending=False,
    )

    # 6. Stitch the pinned row back to the top
    final_df = pd.concat([pinned_row, filtered_data], ignore_index=True)

    # 7. Save
    final_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {OUTPUT_CSV} ({len(final_df):,} rows)")

if __name__ == "__main__":
    main()