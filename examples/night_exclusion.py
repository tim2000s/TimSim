"""Whether oref's insulin-on-board meal rule hides the simulated person's resistance from autosens.

`examples/night_sensitivity.py` (4 October 2026) was void because its positive control was read
on windows chosen by the carbohydrate estimate, which the control itself changed. It left a lead
recorded outside its rule: the simulated loop sits over twice the scheduled basal in net insulin
on board on 24 per cent of night cycles against 10 for 115 real users, which is the rule by which
oref sets a cycle aside as an unannounced meal, and added night resistance raised that share by
0.10 and cut the share autosens counted by the same. If the rule is where the resistance goes, it
would explain `examples/sim_autosens.py`, where autosens read resistant on 0.43 per cent of
cycles against a real median of 42.2 (10.7 to 70.2 across 54 users).

This tests the lead with the selection removed. Forty titrated adults, 28 days on the bench seed
under oref0 SMB with the shipped layers, in four arms paired per subject:

    shipped             the person as shipped
    night_resistant     insulin sensitivity times 0.7 from 23:00 to 04:59 (the control)
    no_iob_rule         autosens classifies without the insulin-on-board clause
    night_no_iob_rule   both

The clause removed is `iob > 2 x current basal` in `Autosens._classify`; the carbohydrate
tracking, the 45 minutes after an entry and the carry-over of a rising unannounced meal are all
kept. Removing it changes the ratio oref receives and so the dosing, which is intended: the arm
asks what the bench's autosens would read and do if its high-insulin cycles were counted.

The cycle set is fixed per subject before any arm is compared: cycles stamped 01:00 to 04:59,
from day two onward (autosens starts empty), at least 180 minutes after any meal and 120 after
any rescue carbohydrate eaten in any of the four arms. Meals are scheduled from the seed and are
the same in every arm, which the script checks; rescues are not, and taking the union over arms
is what keeps the set identical. A first draft cleared 240 minutes after either and was changed
before registration, on availability alone: an eight-day check of adult#001 left 34 of 336
eligible cycles, because the panel eats as late as 23:20 and the four arms between them ate 106
rescues in eight days. The values chosen left 129 for adult#001 and 226 for adult#005 over the
same eight days; no statistic was computed on that check. The hour from 23:00 is left out because the control steps
in then and the hour from 05:00 because it steps out.

Per subject on the fixed set: the median deviation autosens computed (glucose change minus the
profile's prediction from insulin activity, per five minutes, reported per hour), the share of
cycles autosens counted as non-meal, the share over the insulin-on-board clause, and the mean
ratio oref received. Over every cycle from day two: the share of cycles reading resistant, as in
`sim_autosens.py`.

Registered before the run, 4 October 2026.

Expectation. The control raises the night deviation by 3 to 8 mg/dL per hour and lowers the
share counted. With the clause in place the night ratio barely moves; with it removed it rises,
so the interaction is positive. Removing the clause from the shipped person raises the share
reading resistant to inside the real 10.7 to 70.2.

Rule.
  Control. night_resistant minus shipped in the night deviation, paired median, must have a
  95 per cent interval above zero. Otherwise the fixed set cannot see a known night
  resistance and nothing below is read.
  Hiding. The meal rule hides night resistance when the control lowers the share counted
  (interval below zero) and the interaction on the night ratio, (night_no_iob_rule minus
  no_iob_rule) minus (night_resistant minus shipped), has an interval above zero.
  Explanation. The rule explains the 25 September result when no_iob_rule minus shipped in the
  share reading resistant has an interval above zero and the no_iob_rule cohort median lies
  inside the real 10th to 90th percentile. A rise that stays below the band is a partial
  explanation and is reported at its size. No rise says the rule is not the reason, and the
  lead closes.
  Either way the clause stays in the shipped controller, since real oref has it. A positive
  result moves the question to why the simulated loop carries about three times the real net
  insulin overnight.

Result, 4 October 2026 (`docs/measurements/night_exclusion.json`, 160 runs in 69.6 minutes).
The shipped arm reproduced `sim_autosens.json` exactly over 40 runs, the meal schedule was the
same in every arm, and each subject kept a median 603.5 cycles in the fixed set.

The control failed and nothing past it is read as a verdict. On the fixed set the deviation
autosens computed moved +0.26 mg/dL per hour (-0.66 to 2.84) under night sensitivity at 0.7,
where 3 to 8 was expected. The control did reach the runs: time in range fell 1.19 points
(-2.23 to -0.06) and the share of night cycles over the insulin-on-board clause rose 0.12 (0.08
to 0.16). This is the third arrangement in which a known change in the simulated person's
sensitivity has failed to show in autosens's deviations, after the drift ablation of 25
September and the windowed control of `night_sensitivity.py`. Why the deviations do not follow
was not established.

    per subject, median                 shipped   night 0.7   clause off   both
    night deviation, mg/dL per h          -4.9       -4.1        -3.2      -5.5
    night share counted                   0.78       0.65        1.00      1.00
    night share over the clause           0.21       0.33        0.21      0.29
    night ratio received                  0.96       0.97        0.93      0.94
    resistant, per cent of cycles         0.43       0.71        6.41      5.01
    ratio exactly 1.0, per cent           69.8       72.6        49.9      52.2

As description only, two readings bear on the lead. On cycles chosen by the clock, the shipped
person's night deviation is negative, at -4.9 mg/dL per hour: glucose falls faster than the
settings predict, which is sensitivity rather than hidden resistance. The +5.3 of
`night_sensitivity.py` was a different quantity, over windows chosen by carbohydrate on board
and with unclamped activity. Counting the clause's cycles moved the night ratio towards
sensitive, -0.033 (-0.058 to -0.018). Removing the clause raised the share reading resistant
from 0.43 to 6.41 per cent, +5.4 (2.3 to 6.6) paired, below the real 10.7 to 70.2. The clause
therefore accounts for a few points of the 25 September gap at most, and on these figures not
by hiding night resistance. The lead from `night_sensitivity.py` is closed.

    python examples/night_exclusion.py
"""
import argparse
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

OUT = os.path.join(MEASUREMENTS, "night_exclusion.json")
REAL = os.path.join(MEASUREMENTS, "real_autosens.json")
SIM_AUTOSENS = os.path.join(MEASUREMENTS, "sim_autosens.json")
WORKERS = 7
ARMS = {"shipped": {}, "night_resistant": {"night_si": 0.7},
        "no_iob_rule": {"no_iob_rule": True},
        "night_no_iob_rule": {"night_si": 0.7, "no_iob_rule": True}}
HOURS = {1, 2, 3, 4}
CLEAR_AFTER_MEAL = 180
CLEAR_AFTER_RESCUE = 120
WARM = 1440.0


def job(args):
    name, arm, seed, days = args
    from examples import night_sensitivity as ns
    from timsim.patient import varying
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    opts = dict(ARMS[arm])
    restore = ns.night_si(opts.pop("night_si")) if "night_si" in opts else None
    no_rule = opts.pop("no_iob_rule", False)
    prof = titrate.profile_for(name)
    ctrl = ns.recorder()(name, profile=prof)
    if no_rule:
        a = ctrl.autosens
        original = a._classify
        # Handing the classifier no insulin on board removes that one clause and nothing else.
        a._classify = lambda deviation, iob, current_basal: original(deviation, 0.0, current_basal)
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
    rescues = sorted(float(e[1]) for e in r.rescue_log)
    return {"subject": name, "arm": arm, "completed": bool(r.completed),
            "seconds": float(time.time() - t0),
            "tir": float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
            "meals": [[float(m), float(g)] for m, g in r.meal_log], "rescues": rescues,
            # minute, deviation, counted, iob, basal, ratio
            "trace": np.column_stack([tr[:, 0], tr[:, 5], tr[:, 6], tr[:, 7], tr[:, 8],
                                      ratios[:len(tr)]])}


def fixed_set(runs):
    """Minutes eligible in every arm of one subject: clock hours, warm, clear of all carbohydrate."""
    common = None
    for r in runs:
        m = r["trace"][:, 0]
        common = set(m) if common is None else common & set(m)
    m = np.array(sorted(common), float)
    hour = ((m // 60) % 24).astype(int)
    keep = np.isin(hour, list(HOURS)) & (m >= WARM)
    meals = sorted(set(float(t) for r in runs for t, g in r["meals"] if g > 0))
    rescues = sorted(set(t for r in runs for t in r["rescues"]))
    keep &= since(meals, m) >= CLEAR_AFTER_MEAL
    keep &= since(rescues, m) >= CLEAR_AFTER_RESCUE
    return set(m[keep])


def since(events, m):
    """Minutes from the latest event at or before each of `m`, infinite where there is none."""
    ev = np.asarray(events, float)
    if ev.size == 0:
        return np.full(m.shape, np.inf)
    k = np.searchsorted(ev, m, side="right") - 1
    return np.where(k >= 0, m - ev[np.clip(k, 0, None)], np.inf)


def per_subject(run, minutes):
    tr = run["trace"]
    on = np.isin(tr[:, 0], list(minutes))
    t = tr[on]
    warm = tr[tr[:, 0] >= WARM]
    r = np.clip(warm[:, 5][np.isfinite(warm[:, 5])], 0.7, 1.2)
    return {"cycles": int(on.sum()),
            "night_dev_per_h": float(np.nanmedian(t[:, 1]) * 12.0),
            "night_counted_share": float(np.mean(t[:, 2] > 0)),
            "night_iob_rule_share": float(np.mean(t[:, 3] > 2.0 * t[:, 4])),
            "night_ratio": float(np.nanmean(t[:, 5])),
            "resistant_pct": float(100.0 * np.mean(r > 1.0)),
            "at_one_pct": float(100.0 * np.mean(r == 1.0)),
            "tir": run["tir"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=WORKERS)
    a = ap.parse_args()
    from examples.panel import dosable
    subs = dosable(a.subjects)
    jobs = [(n, arm, seeds.BENCH, a.days) for n in subs for arm in ARMS]
    print(f"{len(subs)} subjects, arms {list(ARMS)}, {a.days} days, {len(jobs)} runs", flush=True)
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        runs = pool.map(job, jobs, chunksize=1)
    print(f"{len(runs)} runs in {(time.time() - t0) / 60:.1f} min", flush=True)
    by = {(r["subject"], r["arm"]): r for r in runs}

    same_meals = all(by[(n, arm)]["meals"] == by[(n, "shipped")]["meals"]
                     for n in subs for arm in ARMS)
    print(f"meal schedule identical across arms: {same_meals}", flush=True)

    rows = {}
    for n in subs:
        minutes = fixed_set([by[(n, arm)] for arm in ARMS])
        for arm in ARMS:
            rows[(n, arm)] = per_subject(by[(n, arm)], minutes)

    repro = None
    if os.path.exists(SIM_AUTOSENS):
        prev = {x["subject"]: x for x in json.load(open(SIM_AUTOSENS))["per_run"]
                if x["arm"] == "shipped"}
        d = [abs(rows[(n, "shipped")]["tir"] - prev[n]["tir"]) for n in subs if n in prev]
        repro = {"compared": len(d), "max_abs_tir_diff": float(max(d)) if d else None}
        print(f"reproduction against sim_autosens.json: {repro}", flush=True)

    rng = np.random.default_rng(20261004)

    def ci(v):
        v = np.asarray(v, float)
        b = [np.median(rng.choice(v, v.size)) for _ in range(10000)]
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    def paired(a1, a0, k):
        v = [rows[(n, a1)][k] - rows[(n, a0)][k] for n in subs]
        return {"paired_median": float(np.median(v)), "ci95": ci(v)}

    keys = ("cycles", "night_dev_per_h", "night_counted_share", "night_iob_rule_share",
            "night_ratio", "resistant_pct", "at_one_pct", "tir")
    stats = {arm: {k: {"median": float(np.median([rows[(n, arm)][k] for n in subs])),
                       "p10": float(np.percentile([rows[(n, arm)][k] for n in subs], 10)),
                       "p90": float(np.percentile([rows[(n, arm)][k] for n in subs], 90))}
                   for k in keys} for arm in ARMS}
    effects = {f"{a1}-{a0}": {k: paired(a1, a0, k) for k in keys if k != "cycles"}
               for a1, a0 in (("night_resistant", "shipped"), ("no_iob_rule", "shipped"),
                              ("night_no_iob_rule", "no_iob_rule"))}
    inter = [(rows[(n, "night_no_iob_rule")]["night_ratio"] - rows[(n, "no_iob_rule")]["night_ratio"])
             - (rows[(n, "night_resistant")]["night_ratio"] - rows[(n, "shipped")]["night_ratio"])
             for n in subs]
    interaction = {"paired_median": float(np.median(inter)), "ci95": ci(inter)}

    real = json.load(open(REAL))["stats"]["resistant_pct"]
    band = (real["p10"], real["p90"])
    ctl = effects["night_resistant-shipped"]
    expl = effects["no_iob_rule-shipped"]["resistant_pct"]
    nr_median = stats["no_iob_rule"]["resistant_pct"]["median"]
    verdicts = {
        "control_sees": bool(ctl["night_dev_per_h"]["ci95"][0] > 0),
        "hiding": bool(ctl["night_counted_share"]["ci95"][1] < 0 and interaction["ci95"][0] > 0),
        "explanation": ("full" if expl["ci95"][0] > 0 and band[0] <= nr_median <= band[1]
                        else "partial" if expl["ci95"][0] > 0 else "none"),
        "real_resistant_pct_p10_p90": list(band),
        "no_iob_rule_resistant_pct_median": nr_median}

    print(f"\n{'per subject, median':>24}" + "".join(f"{arm:>20}" for arm in ARMS))
    for k in keys:
        print(f"{k:>24}" + "".join(f"{stats[arm][k]['median']:>20.3f}" for arm in ARMS))
    for name, e in effects.items():
        print(name, json.dumps({k: [round(v['paired_median'], 3)] + [round(x, 3) for x in v['ci95']]
                                for k, v in e.items()}))
    print("interaction on night ratio", json.dumps(interaction))
    print("verdicts", json.dumps(verdicts))

    json.dump({"provenance": provenance.stamp(), "subjects": subs, "days": a.days,
               "seed": seeds.BENCH, "arms": ARMS, "hours": sorted(HOURS),
               "clear_after_meal_min": CLEAR_AFTER_MEAL,
               "clear_after_rescue_min": CLEAR_AFTER_RESCUE, "same_meals": same_meals,
               "reproduction": repro, "stats": stats, "effects": effects,
               "interaction": interaction, "verdicts": verdicts,
               "per_subject": [{"subject": n, "arm": arm, **rows[(n, arm)]}
                               for n in subs for arm in ARMS]},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
