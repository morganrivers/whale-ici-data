"""Unified schema for the whale-ici-data corpus.

All loader scripts must emit DataFrames conforming to UNIFIED_COLUMNS.
ICI columns past `n_clicks - 1` are NaN, not 0.
"""

MAX_ICI = 40

ICI_COLUMNS = [f"ICI{i}" for i in range(1, MAX_ICI + 1)]

UNIFIED_COLUMNS = [
    "source",              # short paper key, e.g. "sharma2024_dswp"
    "source_doi",          # DOI of the source publication
    "source_coda_id",      # original row identifier within source
    "recording_id",        # recording session identifier (raw)
    "date",                # raw date string from source (NOT normalized)
    "time_in_recording_s", # seconds from recording start, NaN if unknown
    "n_clicks",            # number of clicks in coda
    "coda_duration_s",     # total coda duration (sum of ICIs)
    "whale_photo_id",      # persistent Caribbean photo-ID (e.g. "5151"), NaN if unknown
    "local_speaker_id",    # within-recording speaker tag, NaN if unknown
    "social_unit",         # original social unit identifier (study-specific)
    "clan",                # vocal clan label (e.g. "EC1"), NaN if unknown
    "location",            # geographic region (text)
    "latitude",            # decimal degrees; NaN if source did not release per-coda coordinates
    "longitude",           # decimal degrees; NaN if source did not release per-coda coordinates
    "rhythm",              # 0..17 rhythm cluster id (Sharma 2024 numbering); NaN if not classifiable
    "extra_click",         # 0/1 ornament flag; NaN where neighbour timing isn't available
] + ICI_COLUMNS


def normalize_icis(ici_values, n_clicks):
    """Pad/truncate ICIs to MAX_ICI columns, replacing zero-padding past n_clicks-1 with NaN."""
    import math
    n_real = max(0, int(n_clicks) - 1) if n_clicks else 0
    out = []
    for i in range(MAX_ICI):
        if i < n_real and i < len(ici_values):
            v = ici_values[i]
            out.append(float(v) if v not in (None, "") else math.nan)
        else:
            out.append(math.nan)
    return out
