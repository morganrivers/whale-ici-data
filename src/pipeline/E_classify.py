"""Fill in `rhythm` and `extra_click` columns on the unified corpus.

Approach (reconstructed from Sharma et al. 2024; the paper's classifier code is
not in the Project-CETI release):

  Rhythm  - Build per-(rhythm, n_clicks) centroids from the labelled dialogues
            subset (sperm-whale-dialogues.csv + rhythms.p) by averaging the
            standardised cumulative-ICI vectors. Classify each unified coda by
            nearest centroid of matching length. Validate accuracy on the
            labelled set and report.

  Ornament - Apply the paper's rule (Sharma 2024, Methods D / glossary): a coda
             is ornamented if the temporally nearest neighbour from the same
             whale within +/-WINDOW seconds has exactly n_clicks - 1 clicks.
             Sweep (mode, window, same_whale) on the labelled set, pick the
             max-F1 config, then run on every unified row that has both a
             recording_id and a time_in_recording_s. Rows without timing are
             left as <NA>.

Run:
    python -m src.pipeline.E_classify
"""
from collections import defaultdict
from pathlib import Path
import pickle

import numpy as np
import pandas as pd

from .schema import ICI_COLUMNS, UNIFIED_COLUMNS

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
LABELED_CSV = RAW / "sw_combinatoriality_dialogues.csv"
LABELED_RHYTHMS = RAW / "sw_combinatoriality_rhythms.p"
LABELED_ORNAMENTS = RAW / "sw_combinatoriality_ornaments.p"
UNIFIED_CSV = REPO / "data" / "unified" / "codas_unified.csv"

MIN_CLUSTER_SIZE = 5  # minimum codas to form a (rhythm, n_clicks) centroid


# ---------- helpers ----------

def _icis_from_row(row, ici_cols):
    """Return non-zero, non-NaN ICIs for one coda row."""
    vals = pd.to_numeric(row[ici_cols], errors="coerce").to_numpy()
    return vals[np.isfinite(vals) & (vals > 0)]


def _normalised_cumulative(icis):
    """[0, ICI1, ICI1+ICI2, ...] / total. Length = n_clicks."""
    icis = np.asarray(icis, dtype=float)
    cum = np.concatenate([[0.0], np.cumsum(icis)])
    total = cum[-1]
    if total <= 0:
        return None
    return cum / total


def _best_match(vec, centroids_by_len):
    """Closest centroid of the same length. Returns (rhythm_id, mse)."""
    candidates = centroids_by_len.get(len(vec))
    if not candidates:
        return None, np.inf
    best_r, best_mse = None, np.inf
    for r, c in candidates:
        mse = float(np.mean((vec - c) ** 2))
        if mse < best_mse:
            best_mse, best_r = mse, r
    return best_r, best_mse


# ---------- training ----------

def build_centroids():
    """Group labelled codas by (rhythm, n_clicks) and average them."""
    labelled = pd.read_csv(LABELED_CSV)
    rhythms = pickle.load(open(LABELED_RHYTHMS, "rb"))
    ici_cols = [c for c in labelled.columns if c.startswith("ICI")]
    assert len(rhythms) == len(labelled), "rhythms.p and dialogues.csv length mismatch"

    groups = defaultdict(list)
    for i, row in labelled.iterrows():
        icis = _icis_from_row(row, ici_cols)
        if len(icis) < 2:
            continue
        vec = _normalised_cumulative(icis)
        if vec is None:
            continue
        groups[(rhythms[i], len(vec))].append(vec)

    centroids_by_len = defaultdict(list)
    for (r, length), vecs in groups.items():
        if r < 0 or len(vecs) < MIN_CLUSTER_SIZE:
            continue
        centroids_by_len[length].append((r, np.mean(np.stack(vecs), axis=0)))
    return labelled, ici_cols, list(rhythms), centroids_by_len


# ---------- ornament rule ----------

def label_ornaments(df, *, window, mode, same_whale,
                    file_col, time_col, nclicks_col, whale_col=None):
    """Sharma-style ornament detector. See module docstring for `mode`."""
    out = np.zeros(len(df), dtype=int)
    files = df[file_col].astype(str).to_numpy()
    times = pd.to_numeric(df[time_col], errors="coerce").to_numpy()
    nclicks = df[nclicks_col].astype(int).to_numpy()
    whales = df[whale_col].astype(str).to_numpy() if (same_whale and whale_col) else None

    groups = defaultdict(list)
    for idx in range(len(df)):
        if not np.isfinite(times[idx]):
            continue
        key = (files[idx], whales[idx]) if whales is not None else files[idx]
        groups[key].append(idx)

    for key, idxs in groups.items():
        order = np.array(idxs)
        order = order[np.argsort(times[order])]
        t = times[order]
        n = nclicks[order]
        for k in range(len(order)):
            target = n[k] - 1
            prev_n, prev_dt = None, np.inf
            if k > 0 and t[k] - t[k - 1] <= window:
                prev_n, prev_dt = n[k - 1], t[k] - t[k - 1]
            next_n, next_dt = None, np.inf
            if k < len(order) - 1 and t[k + 1] - t[k] <= window:
                next_n, next_dt = n[k + 1], t[k + 1] - t[k]

            if mode == "nearest_either":
                if prev_dt < next_dt:
                    hit = prev_n == target
                elif next_dt < prev_dt:
                    hit = next_n == target
                else:  # tie or both missing
                    hit = prev_n == target or next_n == target
            elif mode == "any_either":
                hit = False
                j = k - 1
                while j >= 0 and t[k] - t[j] <= window:
                    if n[j] == target:
                        hit = True
                        break
                    j -= 1
                if not hit:
                    j = k + 1
                    while j < len(order) and t[j] - t[k] <= window:
                        if n[j] == target:
                            hit = True
                            break
                        j += 1
            elif mode == "nearest_both_sides":
                hit = (prev_n == target) and (next_n == target)
            elif mode == "both_sides_shorter":
                hit = (prev_n is not None and next_n is not None
                       and prev_n <= target and next_n <= target)
            else:
                raise ValueError(mode)
            out[order[k]] = int(hit)
    return out


def select_best_ornament_config(labelled, truth, *, file_col, time_col, nclicks_col, whale_col):
    """Sweep the rule variants on the labelled set, pick the highest-F1 config."""
    print("Ornament rule sweep on labelled set "
          f"(ground truth ornaments = {int(truth.sum())} of {len(truth)}):")
    best, best_f1 = None, -1.0
    for sw in (False, True):
        for window in (5.0, 8.0, 10.0, 15.0):
            for mode in ("any_either", "nearest_either",
                         "nearest_both_sides", "both_sides_shorter"):
                pred = label_ornaments(
                    labelled, window=window, mode=mode, same_whale=sw,
                    file_col=file_col, time_col=time_col,
                    nclicks_col=nclicks_col, whale_col=whale_col,
                )
                tp = int(((pred == 1) & (truth == 1)).sum())
                fp = int(((pred == 1) & (truth == 0)).sum())
                fn = int(((pred == 0) & (truth == 1)).sum())
                prec = tp / max(tp + fp, 1)
                rec = tp / max(tp + fn, 1)
                f1 = 2 * prec * rec / max(prec + rec, 1e-9)
                tag = f"sw={int(sw)} w={window:>4.1f}s {mode}"
                print(f"  {tag:<42s} pred={pred.sum():4d} "
                      f"prec={prec:.2f} rec={rec:.2f} F1={f1:.2f}")
                if f1 > best_f1:
                    best_f1, best = f1, (mode, window, sw)
    mode, window, sw = best
    print(f"  -> best: mode={mode} window={window}s same_whale={sw} (F1={best_f1:.2f})")
    return mode, window, sw, best_f1


# ---------- classification ----------

def classify_rhythms(df, ici_cols, centroids_by_len):
    """Per-row nearest-centroid rhythm assignment. Returns a list of int|<NA>."""
    out = []
    classified = 0
    for _, row in df.iterrows():
        icis = _icis_from_row(row, ici_cols)
        if len(icis) < 2:
            out.append(pd.NA)
            continue
        vec = _normalised_cumulative(icis)
        if vec is None:
            out.append(pd.NA)
            continue
        pred, _ = _best_match(vec, centroids_by_len)
        if pred is None:
            out.append(pd.NA)
        else:
            out.append(int(pred))
            classified += 1
    return out, classified


def validate_rhythm(labelled, ici_cols, rhythms_truth, centroids_by_len):
    correct = 0
    total = 0
    for i, row in labelled.iterrows():
        if rhythms_truth[i] < 0:
            continue
        icis = _icis_from_row(row, ici_cols)
        if len(icis) < 2:
            continue
        vec = _normalised_cumulative(icis)
        if vec is None:
            continue
        pred, _ = _best_match(vec, centroids_by_len)
        if pred is None:
            continue
        total += 1
        correct += int(pred == rhythms_truth[i])
    return correct, total


# ---------- ornament inference on unified ----------

def classify_ornaments(unified, *, window, mode, same_whale):
    """Apply the rule to every unified row that has recording_id + time. Other rows -> <NA>.

    Same-whale grouping uses local_speaker_id if available, else whale_photo_id.
    Codas without a recording grouping or without a timestamp are left as <NA>.
    """
    out = pd.array([pd.NA] * len(unified), dtype="Int64")

    has_time = unified["time_in_recording_s"].notna()
    has_rec = unified["recording_id"].notna()
    eligible = has_time & has_rec
    if not eligible.any():
        return out

    sub = unified.loc[eligible].copy()
    # Pick a same-whale column: prefer local_speaker_id, fall back to whale_photo_id.
    if same_whale:
        if sub["local_speaker_id"].notna().any():
            sub["_whale"] = sub["local_speaker_id"].fillna("__unknown__").astype(str)
        elif sub["whale_photo_id"].notna().any():
            sub["_whale"] = sub["whale_photo_id"].fillna("__unknown__").astype(str)
        else:
            sub["_whale"] = "__unknown__"
        whale_col = "_whale"
    else:
        whale_col = None

    pred = label_ornaments(
        sub, window=window, mode=mode, same_whale=same_whale,
        file_col="recording_id", time_col="time_in_recording_s",
        nclicks_col="n_clicks", whale_col=whale_col,
    )
    out_arr = out.copy()
    sub_idx = sub.index.to_numpy()
    for local_i, row_idx in enumerate(sub_idx):
        out_arr[row_idx] = int(pred[local_i])
    return out_arr


# ---------- entrypoint ----------

def classify(unified: pd.DataFrame) -> pd.DataFrame:
    """Augment a unified DataFrame in place with `rhythm` and `extra_click`."""
    print("E_classify: training rhythm centroids on labelled dialogues subset...")
    labelled, lab_ici_cols, rhythms_truth, centroids_by_len = build_centroids()
    n_cells = sum(len(v) for v in centroids_by_len.values())
    print(f"  built {n_cells} (rhythm, n_clicks) centroids covering "
          f"lengths {sorted(centroids_by_len.keys())}.")

    correct, total = validate_rhythm(labelled, lab_ici_cols, rhythms_truth, centroids_by_len)
    print(f"  rhythm validation: {correct}/{total} correct "
          f"({100 * correct / max(total, 1):.1f}%) on labelled set.")

    # Calibrate ornament rule on labelled set.
    orn_truth = np.array(pickle.load(open(LABELED_ORNAMENTS, "rb")))
    labelled_view = labelled.assign(File=labelled["REC"].astype(str))
    mode, window, same_whale, _f1 = select_best_ornament_config(
        labelled_view, orn_truth,
        file_col="File", time_col="TsTo", nclicks_col="nClicks", whale_col="Whale",
    )

    # Apply rhythm classifier.
    print("E_classify: applying rhythm classifier to unified corpus...")
    unified_ici_cols = [c for c in ICI_COLUMNS if c in unified.columns]
    rhythm_vals, n_classified = classify_rhythms(unified, unified_ici_cols, centroids_by_len)
    unified["rhythm"] = pd.array(rhythm_vals, dtype="Int64")
    print(f"  rhythm: {n_classified}/{len(unified)} codas classified "
          f"({100 * n_classified / len(unified):.1f}%).")

    # Apply ornament rule (only to rows with timing info).
    print("E_classify: applying ornament rule to rows with recording_id + time...")
    unified["extra_click"] = classify_ornaments(
        unified, window=window, mode=mode, same_whale=same_whale,
    )
    n_orn = (unified["extra_click"] == 1).sum()
    n_eligible = unified["extra_click"].notna().sum()
    print(f"  extra_click: {n_orn}/{n_eligible} flagged ornamented "
          f"({100 * n_orn / max(n_eligible, 1):.1f}% of timed rows; "
          f"{len(unified) - n_eligible} rows left <NA> for lack of timing).")

    return unified


def main():
    unified = pd.read_csv(UNIFIED_CSV)
    unified = classify(unified)
    unified = unified[UNIFIED_COLUMNS]
    unified.to_csv(UNIFIED_CSV, index=False)
    print(f"E_classify: wrote {len(unified):,} rows -> {UNIFIED_CSV.relative_to(REPO)}")


if __name__ == "__main__":
    main()
