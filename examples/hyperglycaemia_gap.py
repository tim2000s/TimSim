"""Where TimSim's time above 180 mg/dL differs from DCLP3's, and what accounts for it.

This is the measurement that produced the infusion site layer, kept runnable so the layer's
parameters can be rechecked rather than taken on trust. It needs a copy of the DCLP3 trial
data; `docs/VALIDATION.md` covers where to get it and how to point `DCLP3_DIR` at it.

The question it answers is not whether TimSim spends the right amount of time above 180 but
which excursions the difference lives in. Running it against the closed-loop arm showed that
TimSim already had the number of excursions about right and their peaks about right, and was
short only on how long they lasted, almost entirely in the tail past three hours. That is a
different problem from the one a headline percentage suggests, and it pointed at insulin not
being absorbed rather than at meals or at the controller.

Three things it prints.

The episode decomposition: count, duration and peak of every excursion above 180, in both
the trial and the simulator, and the share of the total difference sitting in each duration
band. This is the part that localises the problem.

The by-hour profile, because a difference concentrated overnight and a difference spread
across the day have different causes. TimSim's was concentrated overnight, which is what
put detection-while-asleep into `therapy/site.py`.

The signature table against both references, since the site layer trades a better match on
hyperglycaemia for a worse one on variability and autocorrelation, and the size of that
trade is the thing worth watching when its parameters change.

    python examples/hyperglycaemia_gap.py --arm nosite     # writes docs/gap_nosite.json
    python examples/hyperglycaemia_gap.py --arm site       # writes docs/gap_site.json
    python examples/hyperglycaemia_gap.py --table          # collect and print

Each arm is a full cohort run and takes roughly half an hour for 34 subjects over 28 days,
so run the two in parallel processes if you have the cores.
"""
import argparse, json, os

import numpy as np

from timsim import simulate_cohort
from timsim import seeds
from timsim.analysis import signatures
from timsim.population import names
from timsim.validation import dclp3

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "docs")

BASE = ("physiology", "behaviour", "sensor")

# `isf_scale` 2.4 puts the median correction factor at 35.3 mg/dL per unit, which is what
# DCLP3 participants ran, in place of the 14.7 measured from the subjects' own physiology.
# It is the "real people do not have optimal settings" arm.
ARMS = {
    "nosite": (BASE, {}),
    "site": (BASE + ("site",), {}),
    "settings": (BASE, {"isf_scale": 2.4}),
    "both": (BASE + ("site",), {"isf_scale": 2.4}),
}

# Duration bands. The interesting boundary is three hours: below it TimSim already matched,
# above it the whole of the difference sat.
BANDS = [(0, 60, "under 1h"), (60, 120, "1-2h"), (120, 180, "2-3h"),
         (180, 360, "3-6h"), (360, None, "over 6h")]


def episodes(glucose, threshold=180.0, step=5.0):
    """Every run of consecutive samples at or above a threshold, as (minutes, peak).

    The peak is the highest reading within the episode, not every reading above the
    threshold pooled together. Pooling gives a different and much less useful number: a
    single long excursion contributes hundreds of samples and drowns out the short ones,
    so the pooled median describes where glucose sits during a high rather than how high
    the highs get.
    """
    g = np.asarray(glucose, float)
    above, out, start = g >= threshold, [], None
    for i, a in enumerate(np.append(above, False)):
        if a and start is None:
            start = i
        elif not a and start is not None:
            out.append(((i - start) * step, float(g[start:i].max())))
            start = None
    return out


def _summarise(episode_list, days, by_hour):
    d = np.asarray([e[0] for e in episode_list], float)
    peaks = np.asarray([e[1] for e in episode_list], float)
    total = days * 1440.0
    out = {"episodes_per_day": len(d) / days,
           "median_dur": float(np.median(d)), "p90_dur": float(np.percentile(d, 90)),
           "max_dur": float(d.max()),
           "median_peak": float(np.median(peaks)), "p90_peak": float(np.percentile(peaks, 90)),
           "above180": float(d.sum() / total * 100), "by_hour": list(by_hour)}
    for lo, hi, label in BANDS:
        m = (d >= lo) & (d < (hi if hi is not None else np.inf))
        out[f"band_{label}"] = float(d[m].sum() / total * 100)
    return out


def measure_trial(arm=dclp3.CLOSED_LOOP, source="pump"):
    """The same decomposition on the trial's calibration half.

    The held-out half is deliberately not touched. It is sealed behind the fingerprint in
    `dclp3.split` and is worth one scoring, at the end.
    """
    split = dclp3.split()
    ids = set(dclp3.roster().query(f"trtGroup == '{arm}'").PtID) & set(split["calibration"])
    found, days = [], 0.0
    hits, seen = np.zeros(24), np.zeros(24)
    for _, segs in dclp3.traces(participants=ids, source=source).items():
        for t, g in segs:
            g = np.asarray(g, float)
            found += episodes(g)
            days += len(g) * 5 / 1440
            hour = ((np.asarray(t, np.int64) // 3600) % 24).astype(int)
            for h in range(24):
                m = hour == h
                hits[h] += np.sum(g[m] >= 180)
                seen[h] += m.sum()
    return _summarise(found, days,
                      np.where(seen > 0, hits / np.maximum(seen, 1) * 100, np.nan))


def _scaled_profile(name, isf_scale):
    """A titrated profile with its correction factor weakened further.

    Module-level and composed with `functools.partial` so it survives pickling to a worker,
    which a closure would not.
    """
    from dataclasses import replace
    from timsim.therapy import titrate
    p = titrate.profile_for(name)
    return replace(p, isf=p.isf * float(isf_scale))


def run_arm(key, subjects, days, seed=seeds.BENCH):
    import functools
    from timsim.therapy import titrate
    layers, kwargs = ARMS[key]
    # `isf_scale` cannot ride through simulate's kwargs any more: an explicit profile wins
    # over the arguments `for_subject` would have taken, so the settings arms would silently
    # have become copies of their partners. It is applied to the titrated profile instead.
    kwargs = dict(kwargs)
    scale = kwargs.pop("isf_scale", None)
    factory = (functools.partial(_scaled_profile, isf_scale=scale) if scale
               else titrate.profile_for)
    results = simulate_cohort(subjects, days=days, seed=seed, layers=layers,
                              profile_factory=factory,
                              progress=False, **kwargs)
    found, total = [], 0.0
    hits, seen = np.zeros(24), np.zeros(24)
    for r in results:
        g = np.asarray(r.cgm, float)
        found += episodes(g, step=r.sample_time)
        total += len(g) * r.sample_time / 1440
        # From the run's own clock, not from the sample index. The run is primed with one
        # step before its loop, so sample `i` sits at minute `(i + 1) * step`, and rebuilding
        # the axis from the index put every reading in the hour bin one step early. This
        # comparison is against the trial's own hour-by-hour profile, where the deepest part
        # of the gap sits between midnight and 04:00, so the binning has to be right.
        hour = ((np.asarray(r.minutes, float) // 60) % 24).astype(int)
        for h in range(24):
            m = hour == h
            hits[h] += np.sum(g[m] >= 180)
            seen[h] += m.sum()
    payload = _summarise(found, total,
                         np.where(seen > 0, hits / np.maximum(seen, 1) * 100, np.nan))
    payload.update({
        "arm": key, "layers": list(layers), "settings": kwargs,
        "n": len(results), "days": days,
        "tir": float(np.mean([r.time_in_range for r in results])),
        "tbr": float(np.mean([r.time_below_70 for r in results])),
        "site_failures_per_30d": float(np.mean(
            [r.meta.get("site_failures", 0) for r in results]) * 30 / days),
        "stats": {k: list(v) for k, v in signatures.evaluate(results).items()},
    })
    os.makedirs(OUT, exist_ok=True)
    json.dump(payload, open(os.path.join(OUT, f"gap_{key}.json"), "w"), indent=1)
    return payload


def table(arms=None):
    arms = arms or [k for k in ARMS
                    if os.path.exists(os.path.join(OUT, f"gap_{k}.json"))]
    data = {k: json.load(open(os.path.join(OUT, f"gap_{k}.json"))) for k in arms}
    trial = measure_trial()

    rows = [("excursions above 180 per day", "episodes_per_day", 2),
            ("median duration, min", "median_dur", 0),
            ("p90 duration, min", "p90_dur", 0),
            ("median peak, mg/dL", "median_peak", 0),
            ("p90 peak, mg/dL", "p90_peak", 0),
            ("total time above 180, %", "above180", 2)]
    head = " | ".join(arms)
    bar = "|---" * (len(arms) + 2) + "|"
    print(f"| | DCLP3 | {head} |")
    print(bar)
    for label, key, dp in rows:
        cells = " | ".join(f"{data[a][key]:.{dp}f}" for a in arms)
        print(f"| {label} | {trial[key]:.{dp}f} | {cells} |")
    print()

    print("Time above 180 by episode length, as a percentage of all time.")
    print(f"| Episode length | DCLP3 | {head} |")
    print(bar)
    for _, _, label in BANDS:
        k = f"band_{label}"
        cells = " | ".join(f"{data[a][k]:.2f}" for a in arms)
        print(f"| {label} | {trial[k]:.2f} | {cells} |")
    print()

    print("Time above 180 by hour of day, %.")
    hours = range(0, 24, 2)
    print("     hour " + " ".join(f"{h:4d}" for h in hours))
    for name, d in [("DCLP3", trial)] + [(a, data[a]) for a in arms]:
        print(f"{name:>9} " + " ".join(f"{d['by_hour'][h]:4.0f}" for h in hours))
    print()

    ref = dclp3.REFERENCE["CLC"]
    print(f"| Signature | DCLP3 IQR | Nightscout range | {head} |")
    print("|---" * (len(arms) + 3) + "|")
    counts = {a: [0, 0] for a in arms}
    for key, (lo_n, hi_n) in signatures.REAL_RANGE.items():
        if key not in ref or key not in data["site"]["stats"]:
            continue
        _, lo_d, hi_d = ref[key]
        cells = []
        for arm in arms:
            v = data[arm]["stats"][key][0]
            counts[arm][0] += lo_d <= v <= hi_d
            counts[arm][1] += lo_n <= v <= hi_n
            marks = ("d" if lo_d <= v <= hi_d else "") + ("n" if lo_n <= v <= hi_n else "")
            cells.append(f"{v:.2f}{' ' + marks if marks else ''}")
        print(f"| {key} | {lo_d:.2f}-{hi_d:.2f} | {lo_n:.2f}-{hi_n:.2f} | "
              + " | ".join(cells) + " |")
    print("\nd = inside the DCLP3 interquartile range, n = inside the Nightscout range.")
    for arm in arms:
        print(f"{arm:>9}: {counts[arm][0]} inside DCLP3, {counts[arm][1]} inside Nightscout"
              f", site failures {data[arm]['site_failures_per_30d']:.2f} per 30 days"
              f", time in range {data[arm]['tir']:.1f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", choices=sorted(ARMS))
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--subjects", type=int, default=34)
    ap.add_argument("--days", type=int, default=28)
    a = ap.parse_args()

    if not dclp3.available():
        raise SystemExit(f"DCLP3 not found at {dclp3.DCLP3_DIR}. "
                         "See docs/VALIDATION.md and set DCLP3_DIR.")
    if a.table:
        return table()
    subjects = names("adult")[:a.subjects]
    for key in ([a.arm] if a.arm else sorted(ARMS)):
        print(f"running {key} ...", flush=True)
        run_arm(key, subjects, a.days)
    if a.arm is None:
        print()
        table()


if __name__ == "__main__":
    main()
