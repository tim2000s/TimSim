"""How a low ends without treatment: the generated adults against the Commons users, by one rule.

Written 5 September 2026. The rescue rate (2.0 helpings a day under oref0 SMB, 0.7 to 0.8 under
the built-in loop and Boost) was on the list as a lead and is an outcome of the loop, since the
person treats what the controller lets happen. What belongs to the person, and so to the
population this package generates, is how their glucose recovers from a low once nothing more
is eaten: how long it takes to climb back to 100 mg/dL and how often it overshoots 180 within
the two hours after. `person/behaviour.py` records that the model took 80 minutes and rebounded
38.5 per cent of the time on untreated lows, against 62.4 minutes and 25.3 per cent across 13
real users, and that the two were measured under different controllers: the built-in loop on
the simulated side, oref and AndroidAPS on the real side. That confound is what this settles.

The real side is `docs/measurements/real_rescues.json`, the 28-day window of the OpenAPS Data
Commons export, whose untreated stratum is a crossing below 70 mg/dL with no carbohydrate entry
from 15 minutes before to 30 minutes after. `--whole-record` output of the same script is read
too when it exists, since the window keeps about a fortieth of the crossings. Both sides are
reduced per person: the median recovery and the rebound share of a person's untreated lows,
on people with at least five of them, and the spread across people is what the simulated
figure is placed against.

The simulated side runs forty titrated adults for 28 days with every layer on, under the
built-in correction loop and under oref0 SMB, each twice: as it ships, where the person treats
every low it notices, and with the probability of treating set to zero, so every low ends the
way an untreated real one does. The arm with no treatment is the like-for-like one. The
shipped arm is reduced by the same crossing rule as the real record, so its untreated stratum
means what the real one means (a low the person did not eat for inside the window) and is
reported beside it. The treat probability is a module constant (`P_TREAT_LOW`) read when the
person is built, and it is set in the worker; the arm checks that no rescue was logged, which
is the option-did-not-arrive signature from `docs/ISSUES.md`.

Registered before the run. Under the built-in loop the untreated recovery is expected near 80
minutes and the rebound near 38 per cent, as previously measured; the real per-user medians
on the window are 72.5 minutes (10th to 90th percentile 43 to 124) and 28.2 per cent (0 to
53). The rule: with the simulated median of per-subject medians inside the real 10th to 90th
percentile on both quantities under oref0 SMB, the confound was the controller and the lead
closes; outside on either, the difference is the person's, and the candidates are the
counterregulation in `patient/glucagon.py` and the production floor during a low, which
`examples/production_during_a_low.py` already measures at 0.49 mg/kg/min against a reported
0.14. Runs that end by leaving the model's range from below are counted per arm, because a
person whose untreated low does not turn is the other way this measurement can come out.

Result, 5 September 2026. Per-person medians of the untreated stratum, with the 10th to 90th
percentile across people; the real side is the whole record (43 users, 28,731 lows) with the
28-day window in brackets (24 users, 758 lows).

    arm                                 people   recovery, min          rebound, per cent
    Commons, untreated                    43     65 (41 to 119)         26 (10 to 49)
      28-day window                       24     72 (43 to 124)         28 (0 to 53)
    built-in loop, treatment off          40    105 (72 to 133)         27 (10 to 63)
    oref0 SMB, treatment off              40    114 (85 to 138)         22 (8 to 39)
    built-in loop, shipped, treated       40     65 (45 to 85)          34 (17 to 65)
    oref0 SMB, shipped, treated           40     76 (60 to 96)          34 (17 to 54)

By the registered rule the oref0 SMB arm is inside on both quantities and the lead closes as
registered. It is inside at the edge: the simulated median sits at the real 90th percentile,
the 95 per cent intervals on the medians are [104, 120] against [65, 75], and the simulated
10th percentile (85) is above the real median. The controller is not the reason. Swapping the
built-in loop for oref0 SMB moves the untreated recovery by 8.75 minutes paired on 40
subjects, and both arms are about 40 to 50 minutes slower than the real users, who were on
oref and AndroidAPS. The rebound rate is inside and central in every arm.

The registration also named the other way the measurement could come out, and it did. With
treatment off under oref0 SMB, 8 of 40 subjects left the model's range from below inside 28
days, every one reaching about 10 mg/dL, against 0 of 40 under the built-in loop and 1 of 40
under oref0 SMB as shipped. A real person on the same algorithm who does not eat for a low
recovers in 65 minutes at the median; a fifth of these subjects do not turn at all. The real
untreated stratum is untreated by the logged record, and treatment people do not log makes it
recover faster than a truly untreated low would, which widens the gap rather than closing it.

So the recovery from a low without eating is the person's and it is slow, which is the
property the shipped person hides by treating every low. Both hypoglycaemia mechanisms in
`patient/varying.py` were judged on outcomes read under that person and neither was adopted;
the treatment-off arm is a statistic that can see them, so they are measured on it next, as
arms passed explicitly (`--mechanisms floor defence --treat none`). Registered: an arm that
moves the oref0 SMB untreated recovery median below 90 minutes, or the fall-throughs below 4
of 40, is worth carrying to the outcome table; one that does neither leaves the gap where it
is, in the published production parameters that the clamp already showed cannot be reached by
a gain.

    python examples/low_recovery.py
    python examples/low_recovery.py --treat none --mechanisms floor --out low_recovery_floor.json
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds
from timsim.person.behaviour import P_TREAT_LOW as DEFAULT_P_TREAT

OUT = os.path.join(MEASUREMENTS, "low_recovery.json")
REAL = os.path.join(MEASUREMENTS, "real_rescues.json")
REAL_WHOLE = os.path.join(MEASUREMENTS, "real_rescues_whole.json")
WORKERS = 7
DRIVERS = ("trend", "oref")
TREAT = ("shipped", "none")
# The two hypoglycaemia mechanisms held at their stock values, each measured on its own clamp
# in `patient/varying.py` and neither adopted, because the outcome they were judged on was
# read under a person who treats every low. Passed to `simulate` explicitly, so the stock arm
# and a mechanism arm cannot inherit each other's value.
MECHANISMS = {"stock": {}, "floor": {"hypo_egp_floor": 0.55},
              "defence": {"hypo_egp_defence": 0.25}}
MIN_LOWS = 5

# The rule the real strata are cut on, copied from examples/real_rescues.py.
CROSS = 70.0
RECOVER_TO = 100.0
REBOUND_ABOVE = 180.0
REBOUND_WINDOW_MIN = 120.0
TREAT_BEFORE_MIN = 15.0
TREAT_WINDOW_MIN = 30.0


def strata(minutes, cgm, rescue_minutes):
    """Every crossing below 70 mg/dL: treated or not, minutes to 100, and whether it rebounded."""
    ts, gs = np.asarray(minutes, float), np.asarray(cgm, float)
    rt = np.asarray(rescue_minutes, float)
    below = gs < CROSS
    crossings = np.flatnonzero(below[1:] & ~below[:-1]) + 1
    out = []
    for i in crossings:
        tc = ts[i]
        treated = bool(np.any((rt >= tc - TREAT_BEFORE_MIN) & (rt <= tc + TREAT_WINDOW_MIN)))
        after = np.flatnonzero((ts > tc) & (gs >= RECOVER_TO))
        if not len(after):
            continue
        j = after[0]
        rec = float(ts[j] - tc)
        if rec > 24 * 60:
            continue
        w = gs[(ts >= ts[j]) & (ts <= ts[j] + REBOUND_WINDOW_MIN)]
        if not len(w):
            continue
        out.append({"treated": treated, "recovery_min": rec,
                    "rebound": bool(np.max(w) > REBOUND_ABOVE)})
    return out


def per_person(rows, treated=False):
    """Median recovery and rebound share of one person's lows in a stratum, or None."""
    s = [r for r in rows if r["treated"] == treated]
    if len(s) < MIN_LOWS:
        return None
    return {"n": len(s), "recovery_min": float(np.median([r["recovery_min"] for r in s])),
            "rebound_pct": 100.0 * float(np.mean([r["rebound"] for r in s]))}


def job(args):
    name, driver, treat, days, mech = args
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    from timsim.person import behaviour
    from examples.capability_table import driver_for
    # Set for both arms, because a pool worker runs many jobs and a value left at zero by one
    # would carry into the next subject's shipped arm.
    behaviour.P_TREAT_LOW = 0.0 if treat == "none" else DEFAULT_P_TREAT
    prof = titrate.profile_for(name)
    ctrl = driver_for(name, driver, prof)
    try:
        r = simulate(name, days=days, seed=seeds.BENCH, layers=DEFAULT_LAYERS,
                     controller=ctrl, profile=prof, **MECHANISMS[mech])
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    if treat == "none" and r.rescue_events:
        raise RuntimeError(f"{name} {driver}: {r.rescue_events} rescues with treatment off")
    rescue_minutes = [e[0] for e in r.rescue_log]
    rows = strata(r.minutes, r.cgm, rescue_minutes)
    return {"subject": name, "driver": driver, "treat": treat, "mechanism": mech,
            "termination": r.termination, "days": r.days_requested,
            "rescues_per_day": r.rescue_events / r.days_requested,
            "crossings": len(rows), "treated": int(sum(x["treated"] for x in rows)),
            "untreated": per_person(rows, False), "treated_stratum": per_person(rows, True),
            "tbr": r.time_below_70}


def pct(v):
    v = np.asarray(v, float)
    return [float(np.percentile(v, q)) for q in (10, 50, 90)] if v.size else [np.nan] * 3


def ci(v, rng):
    v = np.asarray(v, float)
    if v.size < 2:
        return [np.nan, np.nan]
    b = np.array([np.median(rng.choice(v, size=v.size, replace=True)) for _ in range(10000)])
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def real_side(path):
    j = json.load(open(path))
    users = [per_person(u["strata"]) for u in j["users"] if not u.get("skipped")]
    users = [u for u in users if u]
    pooled = [r for u in j["users"] if not u.get("skipped") for r in u["strata"]
              if not r["treated"]]
    return j["span"], users, pooled


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--treat", nargs="+", default=list(TREAT), choices=TREAT)
    ap.add_argument("--mechanisms", nargs="+", default=["stock"], choices=list(MECHANISMS))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    rng = np.random.default_rng(20260905)

    from examples.panel import dosable
    subs = dosable(a.subjects)
    jobs = [(n, d, t, a.days, m) for m in a.mechanisms for d in DRIVERS for t in a.treat
            for n in subs]
    print(f"{len(subs)} subjects, {len(jobs)} runs on {a.workers} workers", flush=True)
    with mp.Pool(a.workers) as pool:
        runs = pool.map(job, jobs, chunksize=1)

    rows = []

    def add(side, label, people, pooled=None):
        rec = [p["recovery_min"] for p in people]
        reb = [p["rebound_pct"] for p in people]
        row = {"side": side, "label": label, "people": len(people),
               "lows": int(sum(p["n"] for p in people)),
               "recovery_min": {"p10_50_90": pct(rec), "ci95_median": ci(rec, rng)},
               "rebound_pct": {"p10_50_90": pct(reb), "ci95_median": ci(reb, rng)}}
        if pooled is not None:
            row["pooled"] = {"n": len(pooled),
                             "recovery_min": float(np.median([r["recovery_min"] for r in pooled])),
                             "rebound_pct": 100.0 * float(np.mean([r["rebound"] for r in pooled]))}
        rows.append(row)
        return row

    for path in (REAL, REAL_WHOLE):
        if os.path.exists(path):
            span, users, pooled = real_side(path)
            add("real", f"Commons, {span}, untreated", users, pooled)
    reference = rows[0]

    terminations = []
    for m in a.mechanisms:
      for d in DRIVERS:
        for t in a.treat:
            cell = [r for r in runs if r["driver"] == d and r["treat"] == t
                    and r["mechanism"] == m]
            ended = [r for r in cell if r["termination"]]
            tag = f"{d}, {m}, treatment {t}" if m != "stock" else f"{d}, treatment {t}"
            terminations.append({"driver": d, "treat": t, "mechanism": m,
                                 "runs": len(cell), "ended": len(ended),
                                 "from_below": sum(1 for r in ended
                                                   if r["termination"]["direction"] == "hypoglycaemic"),
                                 "rescues_per_day": float(np.median([r["rescues_per_day"] for r in cell])),
                                 "tbr": float(np.median([r["tbr"] for r in cell])),
                                 "crossings": int(sum(r["crossings"] for r in cell)),
                                 "treated": int(sum(r["treated"] for r in cell))})
            people = [r["untreated"] for r in cell if r["untreated"]]
            add("sim", f"{tag}, untreated", people)
            if t == "shipped":
                people = [r["treated_stratum"] for r in cell if r["treated_stratum"]]
                add("sim", f"{tag}, treated", people)

    verdicts = {}
    print(f"\n{'side':>5} {'people':>6} {'lows':>6}  {'recovery p10/50/90':>22}  {'95% on p50':>14}"
          f"  {'rebound p10/50/90':>20}  {'95% on p50':>14}  label")
    for r in rows:
        rec, reb = r["recovery_min"], r["rebound_pct"]
        v = ""
        if r["side"] == "sim":
            lo, hi = reference["recovery_min"]["p10_50_90"][0], reference["recovery_min"]["p10_50_90"][2]
            lo2, hi2 = reference["rebound_pct"]["p10_50_90"][0], reference["rebound_pct"]["p10_50_90"][2]
            inside = lo <= rec["p10_50_90"][1] <= hi and lo2 <= reb["p10_50_90"][1] <= hi2
            v = "inside" if inside else "outside"
            verdicts[r["label"]] = v
        f = lambda x: "/".join(f"{y:.0f}" for y in x)
        g = lambda x: f"[{x[0]:.0f}, {x[1]:.0f}]"
        print(f"{r['side']:>5} {r['people']:>6} {r['lows']:>6}  {f(rec['p10_50_90']):>22}  "
              f"{g(rec['ci95_median']):>14}  {f(reb['p10_50_90']):>20}  {g(reb['ci95_median']):>14}"
              f"  {r['label']}  {v}")
        if "pooled" in r:
            p = r["pooled"]
            print(f"{'':>5} pooled {p['n']:>6}  {p['recovery_min']:>22.1f}  {'':>14}  "
                  f"{p['rebound_pct']:>20.1f}")
    print("\nterminations and rescues per arm")
    for t in terminations:
        print(f"  {t['driver']:>6} {t['mechanism']:>8} {t['treat']:>8}  ended {t['ended']}/{t['runs']} "
              f"({t['from_below']} from below)  rescues/day {t['rescues_per_day']:.2f}  "
              f"TBR {t['tbr']:.2f}  crossings {t['crossings']} of which treated {t['treated']}")

    json.dump({"provenance": provenance.stamp(), "days": a.days, "seed": seeds.BENCH,
               "subjects": subs, "drivers": DRIVERS, "treat": a.treat,
               "mechanisms": {m: MECHANISMS[m] for m in a.mechanisms}, "min_lows": MIN_LOWS,
               "rows": rows, "verdicts": verdicts, "terminations": terminations,
               "per_subject": [{k: v for k, v in r.items()} for r in runs]},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
