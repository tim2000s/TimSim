"""Each mechanism ablated from the shipped configuration, regressed against every signature.

Three mechanisms were added to this model on the reasoning that a real person's glucose is less
predictable than a simulated one: meal-to-meal variation in absorption, a multi-day component in
insulin sensitivity, and physical activity. Two of them ship on and one ships off, and the table
recording what each is worth survives only as a comment in `patient/varying.py`. That is the
condition that produced the wrong refutation in study 07, the wrong design argument in study 12,
and the two inverted conclusions in studies 03 and 05.

The regression runs from the shipped configuration outwards rather than from a bare model inwards,
because the shipped configuration is what a benchmark uses, and a mechanism's worth is what
removing it costs rather than what adding it to a stripped model buys. The two are not the same
number when mechanisms interact, and the recorded table says these do.

    shipped        meal absorption CV 0.9, multi-day CV 0.15, activity off
    no_absorption  absorption variation removed
    no_slow        the multi-day sensitivity component removed
    slow_030       the multi-day component at twice its shipped size
    activity       activity switched on, everything else as shipped
    neither        absorption variation and the multi-day component both removed

`neither` is what makes an interaction visible: if the two mechanisms were independent, removing
both would cost the sum of removing each. Study 06 recorded that they do not, so the arm is run
rather than assumed.

Every arm keeps the physiology layer, since both coefficients are applied inside it and a run
given them without it accepts the arguments and ignores them. `--probe` checks that each ablation
reaches the simulation before the full run starts.

    python examples/mechanism_regression.py --probe
    python examples/mechanism_regression.py --subjects 40 --workers 7
"""
import argparse
import concurrent.futures as futures
import json
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

DAYS = 28
SEED = seeds.BENCH
BASE_LAYERS = ("physiology", "behaviour", "sensor", "site")
DRIVER = "trend"
OUT = os.path.join(MEASUREMENTS, "mechanism_regression.json")

# (name, meal_absorption_cv, si_slow_cv, activity). None keeps the shipped value.
ARMS = (
    ("shipped", None, None, False),
    ("no_absorption", 0.0, None, False),
    ("no_slow", None, 0.0, False),
    ("slow_030", None, 0.30, False),
    ("activity", None, None, True),
    ("neither", 0.0, 0.0, False),
)


def one(job):
    arm, absorption, slow, activity, name, days, seed = job
    from timsim.simulation.run import simulate
    from timsim.analysis import signatures
    from timsim.therapy import titrate
    t0 = time.time()
    layers = BASE_LAYERS + (("activity",) if activity else ())
    try:
        r = simulate(name, days=days, seed=seed, layers=layers, controller=DRIVER,
                     profile=titrate.profile_for(name), announcement="some",
                     meal_absorption_cv=absorption, si_slow_cv=slow)
    except Exception as exc:
        return {"arm": arm, "name": name, "completed": False,
                "error": str(exc)[:200], "seconds": time.time() - t0}

    packed = signatures.from_result(r)
    values = {k: float(fn(packed)) for k, _, fn in signatures.SIGS}
    values["insulin_cv"] = float(signatures.insulin_weekly_cv(
        getattr(r, "insulin_series", [])))
    cgm = np.asarray(r.cgm, dtype=float)
    days_run = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    return {"arm": arm, "name": name, "completed": bool(r.completed),
            "seconds": time.time() - t0, "values": values,
            "tir_cgm": float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
            "tbr70_cgm": float(100.0 * np.mean(cgm < 70)),
            "tbr54_cgm": float(100.0 * np.mean(cgm < 54)),
            "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days_run)}


def probe(workers):
    """Check every ablation reaches the simulation before spending an hour on it."""
    from examples.panel import dosable
    names = dosable(2, quiet=True)
    jobs = [(a, ab, sl, ac, n, 14, SEED) for a, ab, sl, ac in ARMS for n in names]
    with futures.ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one, jobs))
    by = {}
    for r in rows:
        by.setdefault(r["name"], {})[r["arm"]] = r
    ok = True
    for name, arms in sorted(by.items()):
        base = arms.get("shipped")
        if not base or not base.get("completed"):
            print(f"  {name}: the shipped arm did not complete, cannot tell")
            ok = False
            continue
        for arm, _, _, _ in ARMS[1:]:
            other = arms.get(arm)
            if not other or not other.get("completed"):
                print(f"  {name} {arm}: did not complete")
                continue
            d = abs(base["insulin_per_day"] - other["insulin_per_day"])
            same = d < 1e-9
            print(f"  {name} {arm:14} insulin differs by {d:8.4f} U/day"
                  f"{'   IDENTICAL' if same else ''}")
            ok = ok and not same
    print("\nevery ablation reaches the simulation" if ok else
          "\nat least one arm is identical to the shipped one, so its ablation did not reach "
          "the simulation. The full run would measure nothing for that arm.")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 7)))
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    if a.probe:
        raise SystemExit(probe(a.workers))

    from timsim.analysis import signatures
    from examples.panel import dosable
    names = dosable(a.subjects)
    jobs = [(arm, ab, sl, ac, n, a.days, SEED)
            for arm, ab, sl, ac in ARMS for n in names]
    print(f"{len(names)} subjects x {len(ARMS)} arms = {len(jobs)} runs "
          f"on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            if i % 30 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    keys = [k for k, _, _ in signatures.SIGS] + ["insulin_cv"]
    labels = {k: lab for k, lab, _ in signatures.SIGS}
    labels["insulin_cv"] = "Insulin week-to-week (%CV)"

    by_arm = {}
    for arm, _, _, _ in ARMS:
        done = [r for r in rows if r["arm"] == arm and r.get("completed")]
        by_arm[arm] = done
        print(f"  {arm:14} {len(done)}/{sum(1 for r in rows if r['arm'] == arm)} completed")

    print(f"\n{'Signature':<30}{'reference':>14}" + "".join(f"{a_:>14}" for a_, _, _, _ in ARMS))
    counts = {a_: 0 for a_, _, _, _ in ARMS}
    table = {}
    for k in keys:
        band = signatures.REAL_RANGE.get(k)
        ref = f"{band[0]:g} to {band[1]:g}" if band else ""
        line = f"{labels.get(k, k):<30}{ref:>14}"
        table[k] = {"label": labels.get(k, k), "real_range": list(band) if band else None,
                    "arms": {}}
        for arm, _, _, _ in ARMS:
            v = np.array([r["values"][k] for r in by_arm[arm]
                          if k in r.get("values", {})], float)
            v = v[np.isfinite(v)]
            if not len(v):
                line += f"{'-':>14}"
                continue
            med = float(np.median(v))
            inside = bool(band and band[0] <= med <= band[1])
            counts[arm] += inside
            table[k]["arms"][arm] = {"median": med, "n": len(v), "inside": inside}
            line += f"{med:>12.2f}{'*' if inside else ' '} "
        print(line)
    print(f"{'signatures inside the range':<30}{'':>14}"
          + "".join(f"{counts[a_]:>13} " for a_, _, _, _ in ARMS))
    print("  a star marks a median inside the real range")

    # Paired against the shipped arm, since between-subject spread exceeds every effect here.
    rng = np.random.default_rng(SEED)
    idx = {}
    for r in rows:
        if r.get("completed"):
            idx.setdefault(r["name"], {})[r["arm"]] = r
    print(f"\npaired against the shipped configuration")
    paired = {}
    for arm, _, _, _ in ARMS[1:]:
        both = [v for v in idx.values() if "shipped" in v and arm in v]
        if len(both) < 10:
            print(f"  {arm}: {len(both)} pairs, too few")
            continue
        print(f"  {arm}, n={len(both)}")
        paired[arm] = {"n": len(both)}
        for k in keys + ["tir_cgm", "tbr70_cgm"]:
            get = (lambda r_, kk=k: r_["values"][kk] if kk in r_.get("values", {})
                   else r_.get(kk, float("nan")))
            d = np.array([get(v[arm]) - get(v["shipped"]) for v in both], float)
            d = d[np.isfinite(d)]
            if len(d) < 10:
                continue
            b = np.array([np.median(rng.choice(d, len(d), True)) for _ in range(4000)])
            lo, hi = np.percentile(b, [2.5, 97.5])
            paired[arm][k] = {"difference": float(np.median(d)),
                              "interval": [float(lo), float(hi)],
                              "excludes_zero": bool(lo > 0 or hi < 0)}
            if lo > 0 or hi < 0:
                print(f"    {labels.get(k, k):<30}{np.median(d):>+9.3f} "
                      f"[{lo:+.3f},{hi:+.3f}]")

    json.dump({"provenance": provenance.stamp(), "days": a.days, "seed": SEED,
               "driver": DRIVER, "base_layers": list(BASE_LAYERS),
               "arms": [{"name": n, "meal_absorption_cv": ab, "si_slow_cv": sl,
                         "activity": ac} for n, ab, sl, ac in ARMS],
               "subjects": names, "table": table, "counts": counts,
               "paired": paired, "runs": rows}, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
