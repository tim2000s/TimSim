"""Does each layer do the same thing to the person whatever is driving?\n\n`layer_ablation.py` adds one mechanism at a time and reports where the eleven fidelity\nsignatures land. It has one weakness, which is that it changes the driving algorithm partway\nup the ladder: the first three rungs run open loop and the last three run the built-in\ncorrection loop. A reader is entitled to ask whether the sensor and site layers move those\nstatistics because of what they do to the person or because of what the loop does in response\nto them.\n\nThis runs the same ladder four times, once per driver, holding the layers constant within\neach run. Two of the four drivers are other people's shipped code called across a pipe and\nknow nothing about this package, so agreement between them is not something the package can\narrange.\n\nThe question is not which driver produces the better glucose. It is whether adding a layer\nmoves a signature in the same direction by a similar amount regardless of what is dosing. A\nlayer that does is a property of the simulated person. A layer that does not is an\ninteraction with the controller, and the package should not claim it as physiology.\n\npython examples/layer_ladder_by_controller.py --subjects 10 --days 28\npython examples/layer_ladder_by_controller.py --table\n"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timsim import signatures, simulate                          # noqa: E402
from timsim import seeds
from timsim.population import names                              # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "docs", "ladder")

# Cumulative, one mechanism per rung. Behaviour comes before physiology, which is not the
# order `layer_ablation.py` uses. The first walk of this ladder used that order and lost half
# the cohort at the physiology rung under two of the four drivers: sensitivity that moves
# through the day and week to week, with nobody yet able to treat a low, produces subjects who
# die. Adding the mechanism before its antidote made every rung above it measurable on a
# different and smaller set of people, and left only four of ten subjects completing all
# twenty arms. In this order every rung has someone to treat the lows it causes.
RUNGS = [
    ("stock", "stock 2008", ()),
    ("behav", "+behaviour", ("behaviour",)),
    ("phys", "+physiology", ("behaviour", "physiology")),
    ("sens", "+sensor", ("behaviour", "physiology", "sensor")),
    ("site", "+site", ("behaviour", "physiology", "sensor", "site")),
]

# Two of this package's own and two shipped elsewhere. `basal-bolus` is open loop, which is
# the control: whatever a layer does there, it does without any algorithm reacting to it.
DRIVERS = ["basal-bolus", "trend", "boost", "oref"]

KEYS = ["cv", "tail", "acf30", "acf60", "outcome", "diurnal", "hypo_rec", "hypo_reb",
        "compress", "noise", "insulin_cv", "drift"]
LABELS = {
    "cv": "Glucose variability (CV%)", "tail": "Rise tail P(dBG>10/5min) %",
    "acf30": "Autocorrelation @30min", "acf60": "Autocorrelation @60min",
    "outcome": "Outcome SD @stuck-high (mg/dL)", "diurnal": "Diurnal amplitude (mg/dL)",
    "hypo_rec": "Hypo recovery to 100 (min)", "hypo_reb": "Hypo rebound >180 %",
    "compress": "Compression lows /30d", "noise": "Sensor jitter (mg/dL)",
    "insulin_cv": "Insulin week-to-week (%CV)",
    # Kept in the table and out of any conclusion: it reads the built-in controller's own
    # learned correction factor, so it is undefined for anything else driving and does not
    # respond to the person. `insulin_cv` above is the statistic it was meant to be.
    "drift": "ISF drift (weekly %CV), not evidence",
}


def driver_for(name, driver):
    """A fresh controller for one subject.\n\nThe two bridged algorithms hold a subprocess each and per-subject state, so they cannot\nbe shared. The two built-in ones are strings the runner resolves itself.\n"""
    if driver == "boost":
        from timsim.controller import boost_bridge
        return boost_bridge.BoostBridgeController(name)
    if driver == "oref":
        from timsim.controller import oref
        return oref.OrefController(name)
    return driver


def one(job):
    """One subject. Returns its own signature values, not a cohort summary.\n\nPer-subject values are what makes a paired comparison possible, and a paired comparison\nis the only honest one here: the same virtual people are run under every rung and every\ndriver, so treating the arms as independent cohorts throws away most of the power and\nsilently compares different sets of people whenever an arm loses a subject.\n"""
    name, layers, driver, days, seed = job
    ctrl = driver_for(name, driver)
    try:
        r = simulate(name, days=days, seed=seed, layers=layers, controller=ctrl)
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    packed = signatures.from_result(r)
    values = {key: float(fn(packed)) for key, _, fn in signatures.SIGS}
    values["drift"] = float(getattr(r, "isf_weekly_cv", float("nan")))
    values["insulin_cv"] = float(signatures.insulin_weekly_cv(
        getattr(r, "insulin_series", []), getattr(r, "sample_time", 5.0)))
    return {"name": name, "completed": bool(r.completed), "values": values}


def run(subjects, days, seed, workers):
    os.makedirs(OUT, exist_ok=True)
    for driver in DRIVERS:
        for key, label, layers in RUNGS:
            path = os.path.join(OUT, f"{driver}__{key}.json")
            if os.path.exists(path):
                print(f"  {driver} {label}: already done", flush=True)
                continue
            # One seed for the whole rung. The subject name is folded into the random
            # stream inside `simulate`, so offsetting by position would only make a
            # subject's month depend on where it sat in `subjects`.
            jobs = [(n, layers, driver, days, seed) for n in subjects]
            with ProcessPoolExecutor(max_workers=workers) as pool:
                rows = list(pool.map(one, jobs))
            json.dump({"driver": driver, "rung": key, "label": label,
                       "layers": list(layers), "subjects": rows,
                       "completed": int(sum(r["completed"] for r in rows)),
                       "n": len(rows)}, open(path, "w"), indent=1)
            print(f"  {driver} {label}: done, "
                  f"{sum(r['completed'] for r in rows)}/{len(rows)} completed", flush=True)


def load():
    data = {}
    for driver in DRIVERS:
        for key, _, _ in RUNGS:
            path = os.path.join(OUT, f"{driver}__{key}.json")
            if os.path.exists(path):
                data[(driver, key)] = json.load(open(path))
    return data


def paired(data, driver, rung_a, rung_b, key, subjects=None):
    """Per-subject movement between two rungs, over the people who survived both.

    Pairing per comparison rather than over the whole ladder. Requiring a subject to
    complete all twenty arms leaves four of ten, because the `+physiology` rung kills half
    the cohort on its own; but a comparison between two rungs only needs the people who
    completed those two, and using them costs nothing in like-for-likeness while roughly
    doubling the number of subjects behind most cells.
    """
    a = {r["name"]: r["values"][key] for r in data[(driver, rung_a)]["subjects"]
         if r["completed"]}
    b = {r["name"]: r["values"][key] for r in data[(driver, rung_b)]["subjects"]
         if r["completed"]}
    pool = subjects if subjects is not None else sorted(set(a) & set(b))
    d = np.array([b[n] - a[n] for n in pool
                  if n in a and n in b
                  and np.isfinite(a[n]) and np.isfinite(b[n])], float)
    if d.size < 3:
        return None
    se = d.std(ddof=1) / np.sqrt(d.size)
    return d.mean(), 1.96 * se, d.size


def survivors(data, drivers):
    """Subjects that completed 28 days in every arm.\n\nComparing arms that lost different subjects compares different populations. The rung\nthat costs the most is `+physiology`, which without the behaviour layer's rescue\ncarbohydrate loses half the cohort, so the ladder cannot be walked one layer at a time\nwithout saying who is left.\n"""
    sets = []
    for d in drivers:
        for k, _, _ in RUNGS:
            sets.append({r["name"] for r in data[(d, k)]["subjects"] if r["completed"]})
    return sorted(set.intersection(*sets)) if sets else []


def table(data):
    have = [d for d in DRIVERS if all((d, k) in data for k, _, _ in RUNGS)]
    if not have:
        raise SystemExit("no complete ladder yet")
    all_names = [r["name"] for r in data[(have[0], "stock")]["subjects"]]
    keep = survivors(data, have)

    print("## Who survives each rung\n")
    print("| Driver | " + " | ".join(l for _, l, _ in RUNGS) + " |")
    print("|---" * (len(RUNGS) + 1) + "|")
    for d in have:
        cells = [f"{data[(d, k)]['completed']}/{data[(d, k)]['n']}" for k, _, _ in RUNGS]
        print(f"| {d} | " + " | ".join(cells) + " |")
    print(f"\n{len(keep)} of {len(all_names)} subjects completed 28 days in all "
          f"{len(have) * len(RUNGS)} arms, and everything below is paired over those. "
          f"Comparing arms\nthat lost different subjects would compare different "
          f"populations.")

    print("\n## Where each rung lands, over the surviving subjects\n")
    print("| Signature | Real range | " + " | ".join(l for _, l, _ in RUNGS)
          + " | Driver spread |")
    print("|---" * (len(RUNGS) + 3) + "|")
    for key in KEYS:
        lo, hi = signatures.REAL_RANGE[key]
        dp = 2 if key.startswith("acf") else 1
        cells, spread = [], []
        for k, _, _ in RUNGS:
            per = []
            for d in have:
                v = {r["name"]: r["values"][key] for r in data[(d, k)]["subjects"]}
                vals = [v[n] for n in keep if n in v and np.isfinite(v[n])]
                if vals:
                    per.append(float(np.median(vals)))
            cells.append(f"{np.mean(per):.{dp}f}" if per else "-")
            spread.append(np.std(per) if per else np.nan)
        print(f"| {LABELS[key]} | {lo:.{dp}f}-{hi:.{dp}f} | " + " | ".join(cells)
              + f" | {np.nanmean(spread):.{dp}f} |")
    print("\nEach cell is the mean across drivers of that driver's median subject. The last "
          "column is the\nspread between drivers, which is how much of the number belongs to "
          "what is dosing rather than\nto the person.")

    print("\n## Does each rung move each signature the same way whatever is driving?\n")
    print("A rung is carried by the person when the paired movement is distinguishable from "
          "zero under\nevery driver and points the same way each time. `person` means all "
          f"{len(have)} agree; a number\nmeans only that many drivers show it; `-` means no "
          "driver does.\n")
    print("| Signature | " + " | ".join(l for _, l, _ in RUNGS[1:]) + " |")
    print("|---" * len(RUNGS) + "|")
    carried = tested = 0
    for key in KEYS:
        cells = []
        for i in range(1, len(RUNGS)):
            prev, this = RUNGS[i - 1][0], RUNGS[i][0]
            moves = [paired(data, d, prev, this, key) for d in have]
            moves = [m for m in moves if m is not None]
            if not moves:
                cells.append("-")
                continue
            real = [m for m in moves if abs(m[0]) > m[1]]
            tested += 1
            if len(real) == len(have) and len({np.sign(m[0]) for m in real}) == 1:
                carried += 1
                cells.append(f"person {np.mean([m[0] for m in real]):+.2f}")
            elif real:
                cells.append(f"{len(real)}/{len(have)} {np.mean([m[0] for m in real]):+.2f}")
            else:
                cells.append("-")
        print(f"| {LABELS[key]} | " + " | ".join(cells) + " |")
    print(f"\n{carried} of {tested} rung-signature movements are carried by the person: "
          f"distinguishable from zero\nunder every one of the {len(have)} drivers, and in "
          "the same direction.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=10)
    p.add_argument("--days", type=int, default=28)
    p.add_argument("--seed", type=int, default=seeds.BENCH)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--table", action="store_true")
    a = p.parse_args()
    if not a.table:
        run(names("adult")[:a.subjects], a.days, a.seed, a.workers)
    table(load())


if __name__ == "__main__":
    main()
