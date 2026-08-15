"""Outcomes for the OpenAPS Data Commons users, on one 28-day window each.

Written so the Commons column of the validation paper is reproducible and so the pairing
against the simulated runs is stated rather than implied. Every statistic here is computed
per user over that user's own window and summarised across users only afterwards, which is
the same order the simulated side uses.

Filenames in the export carry a user-id prefix for some users and not others, so the glob is
`*entries*.json` rather than `entries_*.json`. Matching the narrower pattern silently drops
most of the sample.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")
import json
import re
import glob
import numpy as np

ROOT = os.path.expanduser("~/oref-investigations/240 NS samples")
OUT = os.path.join(MEASUREMENTS, "commons_cohort.json")

WINDOW_DAYS = 28
EXPECTED = WINDOW_DAYS * 288                 # a 5-minute sensor over 28 days
MIN_COVERAGE = 0.70                          # share of expected readings a window must carry
SGV_LO, SGV_HI = 39, 401                     # Nightscout clamps at these; keep them as read

_OBJ = re.compile(rb'"(sgv|date)"\s*:\s*(-?\d+)')


def readings(path):
    """(epoch_ms, sgv) pairs from a Nightscout entries export, streamed."""
    out = []
    carry = b""
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 22)
            if not chunk:
                break
            buf = carry + chunk
            cut = buf.rfind(b"{")               # keep the last, possibly incomplete, object
            if cut < 0:
                carry = buf[-64:]
                continue
            carry, buf = buf[cut:], buf[:cut]
            for frag in buf.split(b"{"):
                d = s = None
                for key, val in _OBJ.findall(frag):
                    if key == b"date":
                        d = int(val)
                    elif key == b"sgv":
                        s = int(val)
                if d is not None and s is not None:
                    out.append((d, s))
    d = s = None                                      # the final object, left in the carry
    for key, val in _OBJ.findall(carry):
        if key == b"date":
            d = int(val)
        elif key == b"sgv":
            s = int(val)
    if d is not None and s is not None:
        out.append((d, s))
    return out


def user_series(user_dir):
    """One user's deduplicated glucose series, ascending, as (minutes, sgv)."""
    pairs = []
    for path in sorted(glob.glob(os.path.join(user_dir, "**", "*entries*.json"),
                                 recursive=True)):
        try:
            pairs += readings(path)
        except Exception as exc:                      # a truncated export is not fatal
            print(f"  skip {os.path.basename(path)}: {exc}", file=sys.stderr)
    if not pairs:
        return None
    a = np.asarray(pairs, dtype=np.int64)
    ok = (a[:, 1] >= SGV_LO) & (a[:, 1] <= SGV_HI) & (a[:, 0] > 1_000_000_000_000)
    a = a[ok]
    if not len(a):
        return None
    minutes = a[:, 0] // 60000                        # to the minute, which dedupes rewrites
    _, first = np.unique(minutes, return_index=True)
    a = a[np.sort(first)]
    order = np.argsort(a[:, 0])
    return a[order]


def window(a, mode="middle"):
    """A 28-day slice of one user's series, and its coverage."""
    span = WINDOW_DAYS * 86400_000
    t0, t1 = int(a[0, 0]), int(a[-1, 0])
    if t1 - t0 < span:
        return None, 0.0
    if mode == "middle":
        start = (t0 + t1) // 2 - span // 2
    else:                                             # densest window, as a sensitivity check
        starts = np.linspace(t0, t1 - span, 40).astype(np.int64)
        counts = [np.sum((a[:, 0] >= s) & (a[:, 0] < s + span)) for s in starts]
        start = int(starts[int(np.argmax(counts))])
    sel = a[(a[:, 0] >= start) & (a[:, 0] < start + span)]
    return sel, len(sel) / EXPECTED


def outcomes(sel):
    g = sel[:, 1].astype(float)
    return {"n_readings": int(len(g)),
            "tir": float(100.0 * np.mean((g >= 70) & (g <= 180))),
            "tbr70": float(100.0 * np.mean(g < 70)),
            "tbr54": float(100.0 * np.mean(g < 54)),
            "tar180": float(100.0 * np.mean(g > 180)),
            "tar250": float(100.0 * np.mean(g > 250)),
            "mean": float(np.mean(g)),
            "cv": float(100.0 * np.std(g, ddof=1) / np.mean(g))}


def main(mode="middle"):
    users = sorted(d for d in glob.glob(os.path.join(ROOT, "*")) if os.path.isdir(d))
    print(f"{len(users)} user directories in the export")
    rows, skipped = [], {"no_cgm": 0, "short_record": 0, "sparse_window": 0}
    for i, d in enumerate(users, 1):
        uid = os.path.basename(d)
        a = user_series(d)
        if a is None:
            skipped["no_cgm"] += 1
            continue
        sel, cov = window(a, mode)
        if sel is None:
            skipped["short_record"] += 1
            continue
        if cov < MIN_COVERAGE:
            skipped["sparse_window"] += 1
            continue
        row = {"user": uid, "coverage": round(cov, 3),
               "record_days": round((int(a[-1, 0]) - int(a[0, 0])) / 86400_000, 1)}
        row.update(outcomes(sel))
        rows.append(row)
        if i % 20 == 0:
            print(f"  {i}/{len(users)} scanned, {len(rows)} usable", flush=True)

    print(f"\nusable users: {len(rows)}   skipped: {skipped}")
    summary = {}
    for k in ("tir", "tbr70", "tbr54", "tar180", "tar250", "mean", "cv"):
        v = np.array([r[k] for r in rows])
        summary[k] = {"median": float(np.median(v)),
                      "p10": float(np.percentile(v, 10)),
                      "p90": float(np.percentile(v, 90)),
                      "iqr": [float(np.percentile(v, 25)), float(np.percentile(v, 75))],
                      "sd_between_users": float(np.std(v, ddof=1))}
        s = summary[k]
        print(f"  {k:7} median {s['median']:8.2f}   IQR {s['iqr'][0]:7.2f} to {s['iqr'][1]:7.2f}"
              f"   p10-p90 {s['p10']:7.2f} to {s['p90']:7.2f}")
    cov = np.array([r["coverage"] for r in rows])
    days = np.array([r["record_days"] for r in rows])
    print(f"  coverage median {np.median(cov):.3f}; record length median {np.median(days):.0f} d")
    json.dump({"mode": mode, "window_days": WINDOW_DAYS, "min_coverage": MIN_COVERAGE,
               "n_users_scanned": len(users), "n_usable": len(rows), "skipped": skipped,
               "summary": summary, "users": rows}, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "middle")
