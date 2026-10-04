"""Whether the width of the target range is why autosens cannot see the simulated person's resistance.

Three arrangements have now failed to show a known change in the simulated person's sensitivity
in the deviations autosens reads: removing the day-to-day and multi-day terms
(`sim_autosens.py`, 25 September 2026), and night sensitivity at 0.7 read on carbohydrate-chosen
windows (`night_sensitivity.py`) and on a fixed clock-chosen set (`night_exclusion.py`, +0.26
mg/dL per hour, -0.66 to 2.84, with mean night glucose 12 mg/dL higher).

The arithmetic suggests why. A deviation is the glucose change plus what the profile says net
insulin should have done. With insulin held at schedule, a person who turns resistant rises to a
new level and stays there, and the deviations return to zero whatever the sensitivity. Resistance
persists in the deviations only when the loop holds glucose at target by delivering extra
insulin, because then glucose is flat while net insulin is positive. oref0 does that only when
its predicted glucose leaves the target range: between `min_bg` and `max_bg` it runs the
scheduled basal. The panel runs 100 to 120 mg/dL for every subject (`therapy/profile.py`), so a
person drifting from 113 to 125 overnight is mostly left alone.

Real users mostly run a single target. `target_widths()` below reads the latest Nightscout
profile of each user in the OpenAPS Data Commons sample: of 169 users with a readable profile,
57 per cent set the two ends equal, the median width is 0 mg/dL, and 24 per cent run 20 or more.

Arms, forty titrated adults, 28 days on the bench seed under oref0 SMB with the shipped layers,
paired per subject:

    band             100 to 120, as shipped
    band_night       the same, with insulin sensitivity times 0.7 from 23:00 to 04:59
    point            a single target of 110, the band's centre, so oref's dosing target is unchanged
    point_night      the same, with the night change

All four are read on one fixed set of cycles per subject, built as in `night_exclusion.py`:
01:00 to 04:59, from day two, at least 180 minutes after any meal and 120 after any rescue eaten
in any arm. Per subject on that set: the median deviation autosens computed (per hour), net
insulin activity, mean glucose. Over every cycle from day two: the share reading resistant.

Reproduction. band and band_night repeat the shipped and night_resistant arms of
`night_exclusion.py` on the same seed, so their time in range must match it exactly.

Registered before the run, 4 October 2026.

A four-day run of adult#005 in all four arms was made first to check the wiring, and is part of
the registration. The single target reached oref and changed little on that subject: time in
range 86.4 against 86.5, night glucose 117.7 against 117.0. Under the night change glucose rose
to 135 mg/dL, above the band, with net activity moving from 1.25 to 1.27 U/h. oref's reasons on
those nights show it alternating between microboluses of 0.75 to 0.8 U and 60-minute zero temps
at a profile correction factor of 8 mg/dL per unit, so its response is a swing rather than a
held rate. That is one subject over three nights and is not used to revise the expectation, but
it makes a null result here likely, in which case the width hypothesis closes.

Expectation. Under the point target the night change raises the deviation by 2 to 6 mg/dL per
hour with an interval clear of zero, and raises net night activity; under the band it does not,
as already measured. The single target raises the share reading resistant on the shipped person
but leaves it below the real 10.7 to 70.2.

Rule.
  Control under a point target. point_night minus point in the night deviation must have a
  paired 95 per cent interval above zero. If it does not, the range width is not why autosens
  misses the change and that is the finding; the line closes.
  Width hides resistance. The interaction (point_night minus point) minus (band_night minus
  band) on the night deviation has an interval above zero.
  Width explains 25 September. point minus band in the share reading resistant has an interval
  above zero; full when the point cohort median is inside the real 10th to 90th percentile,
  partial otherwise.
  A positive result does not by itself change the shipped profile. Moving the panel to a single
  target is a settings change that would need its own titration and the full statistic table,
  and is put to Tim rather than made here.

    python examples/night_target.py
"""
import argparse
import glob
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "night_target.json")
REAL = os.path.join(MEASUREMENTS, "real_autosens.json")
PREVIOUS = os.path.join(MEASUREMENTS, "night_exclusion.json")
NS = os.path.expanduser("~/oref-investigations/240 NS samples")
WORKERS = 7
POINT = 110.0
ARMS = {"band": {}, "band_night": {"night_si": 0.7},
        "point": {"target_bg": POINT}, "point_night": {"night_si": 0.7, "target_bg": POINT}}
PREVIOUS_ARM = {"band": "shipped", "band_night": "night_resistant"}


def target_widths():
    """The target range of each user's latest Nightscout profile, in mg/dL."""
    per = {}
    for f in sorted(glob.glob(os.path.join(NS, "*", "direct-sharing-31", "*profile*.json*"))):
        user = os.path.relpath(f, NS).split(os.sep)[0]
        try:
            d = json.load(open(f))
        except (ValueError, OSError):
            continue
        d = d if isinstance(d, list) else [d]
        for rec in sorted(d, key=lambda r: str(r.get("startDate", r.get("created_at", ""))))[-1:]:
            store = rec.get("store") or {}
            p = store.get(rec.get("defaultProfile")) or (next(iter(store.values())) if store else None)
            try:
                lo = float(p["target_low"][0]["value"])
                hi = float(p["target_high"][0]["value"])
            except (TypeError, KeyError, IndexError, ValueError):
                continue
            if str(p.get("units", "mg/dl")).lower().startswith("mmol") or lo < 20:
                lo, hi = lo * 18.018, hi * 18.018
            per[user] = (lo, hi)
    w = np.array([h - l for l, h in per.values()], float)
    return {"users": len(per), "median_width": float(np.median(w)),
            "p10": float(np.percentile(w, 10)), "p90": float(np.percentile(w, 90)),
            "share_single": float(np.mean(w < 1.0)), "share_20_or_more": float(np.mean(w >= 19.9)),
            "median_low": float(np.median([l for l, _ in per.values()])),
            "median_high": float(np.median([h for _, h in per.values()]))}


def job(args):
    name, arm, seed, days = args
    from examples import night_sensitivity as ns
    from timsim.patient import varying
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    opts = dict(ARMS[arm])
    restore = ns.night_si(opts.pop("night_si")) if "night_si" in opts else None
    target = opts.pop("target_bg", None)
    prof = titrate.profile_for(name)
    ctrl = ns.recorder()(name, profile=prof, target_bg=target)
    t0 = time.time()
    try:
        r = simulate(name, days=days, seed=seed, layers=DEFAULT_LAYERS, controller=ctrl,
                     profile=prof, **opts)
        tr = np.array(ctrl.trace, float)
        ratios = np.array([np.nan if x is None else x for x in ctrl.ratios], float)
    finally:
        ctrl.close()
        if restore is not None:
            varying.VaryingPatient.sensitivity = restore
    cgm = np.asarray(r.cgm, float)
    return {"subject": name, "arm": arm, "completed": bool(r.completed),
            "seconds": float(time.time() - t0),
            "tir": float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
            "tbr70": float(100.0 * np.mean(cgm < 70)),
            "meals": [[float(m), float(g)] for m, g in r.meal_log],
            "rescues": sorted(float(e[1]) for e in r.rescue_log),
            # minute, deviation, counted, iob, basal, ratio, cgm, activity
            "trace": np.column_stack([tr[:, 0], tr[:, 5], tr[:, 6], tr[:, 7], tr[:, 8],
                                      ratios[:len(tr)], tr[:, 1], tr[:, 2]])}


def per_subject(run, minutes):
    from examples import night_exclusion as ne
    out = ne.per_subject(run, minutes)
    tr = run["trace"]
    on = np.isin(tr[:, 0], list(minutes))
    out.update(night_act_u_per_h=float(np.median(tr[on, 7]) * 60.0),
               night_mean_cgm=float(np.mean(tr[on, 6])), tbr70=run["tbr70"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=WORKERS)
    a = ap.parse_args()
    from examples import night_exclusion as ne
    from examples.panel import dosable

    widths = target_widths()
    print(f"real target widths: {json.dumps(widths)}", flush=True)

    subs = dosable(a.subjects)
    jobs = [(n, arm, seeds.BENCH, a.days) for n in subs for arm in ARMS]
    print(f"{len(subs)} subjects, arms {list(ARMS)}, {a.days} days, {len(jobs)} runs", flush=True)
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        runs = pool.map(job, jobs, chunksize=1)
    print(f"{len(runs)} runs in {(time.time() - t0) / 60:.1f} min", flush=True)
    by = {(r["subject"], r["arm"]): r for r in runs}
    same_meals = all(by[(n, arm)]["meals"] == by[(n, "band")]["meals"]
                     for n in subs for arm in ARMS)

    rows = {}
    for n in subs:
        minutes = ne.fixed_set([by[(n, arm)] for arm in ARMS])
        for arm in ARMS:
            rows[(n, arm)] = per_subject(by[(n, arm)], minutes)

    prev = {(x["subject"], x["arm"]): x for x in json.load(open(PREVIOUS))["per_subject"]}
    d = [abs(rows[(n, arm)]["tir"] - prev[(n, old)]["tir"])
         for n in subs for arm, old in PREVIOUS_ARM.items() if (n, old) in prev]
    repro = {"compared": len(d), "max_abs_tir_diff": float(max(d)) if d else None}
    print(f"meals identical: {same_meals}; reproduction against night_exclusion.json: {repro}",
          flush=True)

    rng = np.random.default_rng(20261004)

    def ci(v):
        v = np.asarray(v, float)
        b = [np.median(rng.choice(v, v.size)) for _ in range(10000)]
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    keys = ("cycles", "night_dev_per_h", "night_act_u_per_h", "night_mean_cgm",
            "night_counted_share", "night_iob_rule_share", "night_ratio", "resistant_pct",
            "at_one_pct", "tir", "tbr70")
    stats = {arm: {k: {"median": float(np.median([rows[(n, arm)][k] for n in subs])),
                       "p10": float(np.percentile([rows[(n, arm)][k] for n in subs], 10)),
                       "p90": float(np.percentile([rows[(n, arm)][k] for n in subs], 90))}
                   for k in keys} for arm in ARMS}

    def paired(a1, a0, k):
        v = [rows[(n, a1)][k] - rows[(n, a0)][k] for n in subs]
        return {"paired_median": float(np.median(v)), "ci95": ci(v)}

    effects = {f"{a1}-{a0}": {k: paired(a1, a0, k) for k in keys if k != "cycles"}
               for a1, a0 in (("band_night", "band"), ("point_night", "point"), ("point", "band"))}
    inter = [(rows[(n, "point_night")]["night_dev_per_h"] - rows[(n, "point")]["night_dev_per_h"])
             - (rows[(n, "band_night")]["night_dev_per_h"] - rows[(n, "band")]["night_dev_per_h"])
             for n in subs]
    interaction = {"paired_median": float(np.median(inter)), "ci95": ci(inter)}

    real = json.load(open(REAL))["stats"]["resistant_pct"]
    band = (real["p10"], real["p90"])
    width = effects["point-band"]["resistant_pct"]
    pm = stats["point"]["resistant_pct"]["median"]
    verdicts = {
        "control_under_point": bool(effects["point_night-point"]["night_dev_per_h"]["ci95"][0] > 0),
        "width_hides_resistance": bool(interaction["ci95"][0] > 0),
        "width_explains": ("full" if width["ci95"][0] > 0 and band[0] <= pm <= band[1]
                           else "partial" if width["ci95"][0] > 0 else "none"),
        "real_resistant_pct_p10_p90": list(band), "point_resistant_pct_median": pm}

    print(f"\n{'per subject, median':>24}" + "".join(f"{arm:>14}" for arm in ARMS))
    for k in keys:
        print(f"{k:>24}" + "".join(f"{stats[arm][k]['median']:>14.3f}" for arm in ARMS))
    for name, e in effects.items():
        print(name, json.dumps({k: [round(v["paired_median"], 3)] + [round(x, 3) for x in v["ci95"]]
                                for k, v in e.items()}))
    print("interaction on night deviation", json.dumps(interaction))
    print("verdicts", json.dumps(verdicts))

    json.dump({"provenance": provenance.stamp(), "subjects": subs, "days": a.days,
               "seed": seeds.BENCH, "arms": ARMS, "point_target": POINT,
               "real_target_widths": widths, "same_meals": same_meals, "reproduction": repro,
               "stats": stats, "effects": effects, "interaction": interaction,
               "verdicts": verdicts,
               "per_subject": [{"subject": n, "arm": arm, **rows[(n, arm)]}
                               for n in subs for arm in ARMS]},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
