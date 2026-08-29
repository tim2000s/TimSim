"""What people actually eat when they go low, from the records rather than from a comment.

The rescue behaviour in `person/behaviour.py` is calibrated against real carbohydrate entries
made at low readings: how big one helping is, how it varies with how low the reading was, how
often an episode is treated at all, and how much arrives per episode once re-treatment is
counted. Those figures are quoted throughout the documentation and no script regenerated any of
them, which is the condition that has produced three wrong results in this package already.

This produces them. For each user with a usable 28-day window it pairs every carbohydrate entry
with the sensor reading the person could see when they made it, keeps the entries made below 75
mg/dL, and reports them per entry and per episode.

Two definitions carry the result and both are stated rather than chosen quietly.

An entry is matched to a reading within ten minutes of it. A carbohydrate entry with no reading
near it cannot be attributed to a low and is dropped rather than assumed.

An episode is a run of entries separated by less than the refractory window, so a person who eats
15 g, waits, and eats another 15 g counts once at 30 g. Summing every entry near an excursion
instead counts re-treatment as one large dose, which is how an earlier version of this
measurement found dose depending on depth three times as strongly as it does.

The untreated share is computed the other way round, from excursions rather than from entries: a
crossing below 70 mg/dL is treated when any carbohydrate entry falls inside the window after it.

    python examples/real_rescues.py --workers 2
"""
import argparse
import concurrent.futures as futures
import glob
import json
import os
import re
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance

OUT = os.path.join(MEASUREMENTS, "real_rescues.json")

LOW = 75.0                 # entries at or below this reading count as a rescue
MATCH_MIN = 10.0           # how near a reading has to be to attribute an entry to it
EPISODE_GAP_MIN = 45.0     # matches RESCUE_REFRACTORY_MIN, so an episode means the same thing
TREAT_WINDOW_MIN = 30.0    # after a crossing below 70, how long counts as treating it
CROSS = 70.0
BANDS = ((65.0, 75.0), (55.0, 65.0), (45.0, 55.0), (0.0, 45.0))

_CARB = re.compile(rb'"(carbs|date)"\s*:\s*(-?\d+(?:\.\d+)?)')


def carb_entries(path):
    """(epoch_ms, grams) for every treatment carrying carbohydrate, streamed.

    Read with a regular expression rather than a JSON parse for the same reason the entries
    reader is: several exports are truncated mid-array and a parse of the whole file returns
    nothing at all, where this returns everything before the truncation.
    """
    out, date, carbs = [], None, None
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            for m in _CARB.finditer(chunk):
                key, val = m.group(1), float(m.group(2))
                if key == b"date":
                    if date is not None and carbs:
                        out.append((date, carbs))
                    date, carbs = val, None
                else:
                    carbs = val
    if date is not None and carbs:
        out.append((date, carbs))
    return np.array(out, float).reshape(-1, 2)


def one(job):
    """One user. `whole` reads the entire record rather than the 28-day window.

    Both are reported because the choice moves the sample by an order of magnitude, and the
    figure this producer exists to check was made on a sample whose definition was not recorded.
    The window keeps every Commons figure here on one basis; the whole record is the larger
    sample and the fairer test of a dependence measured across thousands of entries.
    """
    from examples.commons_cohort import user_series, window, MIN_COVERAGE
    user_dir, whole = job
    name = os.path.basename(user_dir)
    a = user_series(user_dir)
    if a is None or not len(a):
        return {"user": name, "skipped": "no_cgm"}
    if whole:
        sel, cov = a, 1.0
    else:
        sel, cov = window(a)
        if sel is None:
            return {"user": name, "skipped": "short_record"}
        if cov < MIN_COVERAGE:
            return {"user": name, "skipped": "sparse_window"}

    paths = glob.glob(os.path.join(user_dir, "**", "*treatments*.json"), recursive=True)
    if not paths:
        return {"user": name, "skipped": "no_treatments"}
    rows = [carb_entries(p) for p in paths]
    rows = [r for r in rows if len(r)]
    if not rows:
        return {"user": name, "skipped": "no_carbs"}
    carbs = np.concatenate(rows)
    t0, t1 = float(sel[0, 0]), float(sel[-1, 0])
    carbs = carbs[(carbs[:, 0] >= t0) & (carbs[:, 0] <= t1)]
    if not len(carbs):
        return {"user": name, "skipped": "no_carbs_in_window"}
    carbs = carbs[np.argsort(carbs[:, 0])]

    # The reading the person could see when they ate.
    ts, gs = sel[:, 0].astype(float), sel[:, 1].astype(float)
    idx = np.searchsorted(ts, carbs[:, 0])
    idx = np.clip(idx, 1, len(ts) - 1)
    left = np.abs(carbs[:, 0] - ts[idx - 1])
    right = np.abs(ts[np.minimum(idx, len(ts) - 1)] - carbs[:, 0])
    near = np.where(left <= right, idx - 1, np.minimum(idx, len(ts) - 1))
    gap_min = np.minimum(left, right) / 60000.0
    ok = gap_min <= MATCH_MIN
    at = gs[near]

    low = ok & (at <= LOW)
    entries = [{"t": float(carbs[i, 0]), "grams": float(carbs[i, 1]), "reading": float(at[i])}
               for i in np.flatnonzero(low)]

    # Episodes, so re-treatment is one event rather than one large dose.
    episodes = []
    for e in entries:
        if episodes and (e["t"] - episodes[-1]["end"]) / 60000.0 < EPISODE_GAP_MIN:
            episodes[-1]["grams"] += e["grams"]
            episodes[-1]["end"] = e["t"]
            episodes[-1]["helpings"] += 1
        else:
            episodes.append({"grams": e["grams"], "reading": e["reading"],
                             "end": e["t"], "helpings": 1})

    # Excursions, to say how many go untreated. A crossing is a reading below 70 whose
    # predecessor was not, so a single long low counts once.
    below = gs < CROSS
    crossings = np.flatnonzero(below[1:] & ~below[:-1]) + 1
    treated = 0
    ct = carbs[:, 0]
    for i in crossings:
        t = ts[i]
        if np.any((ct >= t) & (ct <= t + TREAT_WINDOW_MIN * 60000.0)):
            treated += 1

    days = (t1 - t0) / 86400_000.0
    return {"user": name, "coverage": float(cov), "days": float(days),
            "n_entries_low": len(entries), "entries": entries,
            "n_episodes": len(episodes),
            "episode_grams": [e["grams"] for e in episodes],
            "episode_reading": [e["reading"] for e in episodes],
            "episode_helpings": [e["helpings"] for e in episodes],
            "crossings": int(len(crossings)), "crossings_treated": int(treated),
            "episodes_per_day": len(episodes) / days if days > 0 else float("nan")}


def q(v, name, unit=""):
    v = np.asarray([x for x in v if np.isfinite(x)], float)
    if not len(v):
        return f"  {name:34} no data"
    return (f"  {name:34} median {np.median(v):7.2f}{unit}  mean {np.mean(v):7.2f}  "
            f"p25 {np.percentile(v, 25):6.2f}  p75 {np.percentile(v, 75):6.2f}  "
            f"p90 {np.percentile(v, 90):6.2f}  n={len(v)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--whole-record", dest="whole", action="store_true",
                    help="use each user's entire record instead of the 28-day window")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.commons_cohort import ROOT
    users = sorted(d for d in glob.glob(os.path.join(ROOT, "*")) if os.path.isdir(d))
    print(f"{len(users)} user directories, {a.workers} workers, "
          f"{'whole record' if a.whole else '28-day window'}", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, [(u, a.whole) for u in users]), 1):
            rows.append(r)
            if i % 40 == 0:
                print(f"  {i}/{len(users)}", flush=True)

    skipped = {}
    for r in rows:
        if r.get("skipped"):
            skipped[r["skipped"]] = skipped.get(r["skipped"], 0) + 1
    good = [r for r in rows if not r.get("skipped") and r["n_entries_low"]]
    print(f"\n{len(good)} users with carbohydrate entries below {LOW:.0f} mg/dL, "
          f"skipped {skipped}")

    entries = [e for r in good for e in r["entries"]]
    print(f"\n{len(entries)} entries from {len(good)} users\n")
    print(q([e["grams"] for e in entries], "grams per entry", " g"))
    print(q([e["reading"] for e in entries], "reading when eaten", " mg/dL"))

    print("\n  by the reading the person could see")
    print(f"  {'band, mg/dL':16}{'n':>7}{'median g':>11}{'mean g':>9}{'p90 g':>8}")
    band_rows = {}
    for lo, hi in BANDS:
        v = [e["grams"] for e in entries if lo <= e["reading"] < hi]
        if not v:
            continue
        band_rows[f"{lo:.0f}-{hi:.0f}"] = {"n": len(v), "median": float(np.median(v)),
                                           "mean": float(np.mean(v)),
                                           "p90": float(np.percentile(v, 90))}
        print(f"  {f'{lo:.0f} to {hi:.0f}':16}{len(v):>7}{np.median(v):>11.1f}"
              f"{np.mean(v):>9.1f}{np.percentile(v, 90):>8.1f}")

    x = np.array([e["reading"] for e in entries], float)
    y = np.array([e["grams"] for e in entries], float)
    slope, intercept = np.polyfit(x, y, 1)
    r = float(np.corrcoef(x, y)[0, 1])
    resid = float(np.std(y - (slope * x + intercept)))
    print(f"\n  dose against reading: {slope:+.3f} g per mg/dL, r = {r:+.3f}, "
          f"spread about the line {resid:.1f} g")

    eps = [g for r_ in good for g in r_["episode_grams"]]
    helps = [h for r_ in good for h in r_["episode_helpings"]]
    print(f"\n  per episode, entries within {EPISODE_GAP_MIN:.0f} min merged")
    print(q(eps, "grams per episode", " g"))
    print(q(helps, "helpings per episode"))
    print(q([r_["episodes_per_day"] for r_ in good], "episodes per day"))

    cr = sum(r_["crossings"] for r_ in good)
    tr = sum(r_["crossings_treated"] for r_ in good)
    per_user = [100.0 * r_["crossings_treated"] / r_["crossings"]
                for r_ in good if r_["crossings"]]
    print(f"\n  {cr} crossings below {CROSS:.0f} mg/dL, {tr} treated within "
          f"{TREAT_WINDOW_MIN:.0f} min ({100.0 * tr / cr:.1f}%)")
    print(q(per_user, "treated share per user", " %"))

    json.dump({"provenance": provenance.stamp(),
               "span": "whole_record" if a.whole else "window_28d",
               "definitions": {"low_mgdl": LOW, "match_min": MATCH_MIN,
                               "episode_gap_min": EPISODE_GAP_MIN,
                               "treat_window_min": TREAT_WINDOW_MIN, "crossing_mgdl": CROSS},
               "n_users": len(good), "skipped": skipped,
               "entries": {"n": len(entries),
                           "median_g": float(np.median([e["grams"] for e in entries])),
                           "mean_g": float(np.mean([e["grams"] for e in entries])),
                           "p90_g": float(np.percentile([e["grams"] for e in entries], 90)),
                           "by_band": band_rows,
                           "slope_g_per_mgdl": float(slope), "r": r,
                           "residual_sd_g": resid},
               "episodes": {"n": len(eps), "median_g": float(np.median(eps)),
                            "mean_g": float(np.mean(eps)),
                            "median_helpings": float(np.median(helps)),
                            "median_per_day": float(np.median(
                                [r_["episodes_per_day"] for r_ in good]))},
               "crossings": {"n": cr, "treated": tr,
                             "treated_pct": 100.0 * tr / cr if cr else float("nan"),
                             "treated_pct_per_user_median": float(np.median(per_user))
                             if per_user else float("nan")},
               "users": [{k: v for k, v in r_.items() if k != "entries"} for r_ in good]},
              open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
