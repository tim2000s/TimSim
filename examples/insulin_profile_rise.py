"""The meal rise when the simulated person receives the real insulin profile and no controller.

Written 4 September 2026, after `insulin_by_peak.py` measured that the simulated oref0 SMB loop
has delivered 1.96 U per 10 entered grams by the peak of a covered meal against 1.77 for adult
Loop participants, as a smaller bolus (0.75 U per 10 g against 1.00) plus a larger addition after
the entry (1.31 against 0.71), on a rise of 11.5 mg/dL per 10 g against 15.1. Eleven per cent
more insulin, placed later, on a rise 24 per cent lower: the controller cannot be excluded from
the gap on that measurement and cannot be shown to own it either. This is the run that separates
the two.

Each subject is driven by the built-in correction loop between meals and by a profile inside
them. At every announced entry the driver delivers a bolus of `bolus_per_10g` per 10 entered
grams, and over the following `span_min` minutes it delivers, as boluses spread evenly across
the steps, whatever brings the total from 30 minutes before the entry to the end of the span
(scheduled basal included) to `total_per_10g` per 10 g. Inside that span the loop neither
corrects nor raises the basal; it keeps only its low-glucose suspension, as a real loop would.
Outside the span the correction loop runs as it does in every other measurement here, which
holds the glucose the meals start from where the loop holds it. A first version of this script
ran the profile with no loop at all, and the panel sat at a mean of 205 mg/dL with troughs above
200, so its meals were not comparable with anything. Four arms run on one panel, paired per
subject:

    arm         bolus U/10 g   total by peak U/10 g   span min   what it is
    loop        the correction loop alone             the reference driver, for the level check
    sim         0.75           1.96                   91         the simulated oref0 SMB loop's quantities
    real        1.00           1.77                   85         the adult Loop record
    real_bolus  1.00           none                   0          the real bolus, then the loop after 30 min

The `sim` arm is the check on the method. The loop places most of its addition early, as super
micro boluses in the first half hour, where the profile spreads it to the peak, so the arm reads
whether replaying the quantity reproduces the rise the loop produced. The comparison that answers
the question is `real` against `sim`, on the same subjects and the same meals, and the gap it is
read against is 3.6 mg/dL per 10 g.

Registered before the run. If the `sim` arm reads within 1.0 mg/dL per 10 g of the loop's own
11.5, the profile is a fair stand-in for the loop and `real` minus `sim` is the controller's share
of the gap directly. If `real` minus `sim` is under 1.0 mg/dL per 10 g with its interval clear of
1.8, the controller's dose is not where the gap is and the physiology is; the rise is then
recorded as a bound in `docs/VALIDATION.md` and not pursued further. If it is 1.8 or more, the
loop's dosing after the entry owns at least half of the gap and the investigation moves to why
oref0 SMB doses these subjects 1.7 times as much as a real loop over the day. Between the two the
answer is a fraction, and the fraction is reported. `real_bolus` hands the meal back to the
correction loop half an hour after the real bolus, and is there to size what the loop's own
addition does to the peak against a fixed one.

Delivered insulin is measured on every arm through the same definition as the two sides of the
original comparison (`timsim/analysis/meal_shape.py`), so an arm whose profile did not reach the
body shows it in the insulin column rather than in an unexplained rise. With no corrections the
panel may run high between meals, and terminations are reported with the arm they occurred in.

Result, 5 September 2026 (`docs/measurements/insulin_profile_rise.json`). Forty subjects, 42
days, seed 101, six terminations across the 160 subject-arms (three of them adult#033), read on
per-subject medians over covered meals, p10/50/90 and the paired median difference against `sim`
with a bootstrap interval:

    window  arm         n   rise/10 g          ttp   by peak/10 g   against sim, rise/10 g
    240     loop        40   8.1 / 9.9 / 12.0    70   1.65           -0.05 [-1.66, 0.84]
    240     sim         33   6.9 / 10.3 / 13.6   78   1.84
    240     real        34   6.6 / 10.3 / 13.7   78   1.76           -0.07 [-0.75, 0.50]
    240     real_bolus  38   6.9 / 10.6 / 13.8   80   1.69           +0.78 [-0.42, 1.41]
    300     loop        39   8.8 / 11.0 / 14.5   88   1.84           -0.26 [-1.24, 1.12]
    300     sim         30   8.2 / 11.8 / 14.9   85   1.98
    300     real        32   7.5 / 11.3 / 15.6   88   1.84           +0.03 [-0.99, 1.03]
    300     real_bolus  36   9.0 / 12.2 / 15.0   90   1.87           +0.85 [0.13, 1.50]

The profiles reached the body. The insulin by the peak orders as the arms were built, `sim`
above `real` above `real_bolus`, and `real` minus `sim` is -0.07 U per 10 g [-0.13, -0.03] at
240 min where the profiles differ by -0.19; the shortfall on `sim` (1.84 against its 1.96) is
the 91 minute span running past a peak that arrives at 78, so a seventh of its addition lands
after the peak the window reads. The bolus column reads 0.96 and 1.07 rather than 0.75 and 1.00
because the additions inside the 30 minutes after the entry count as bolus under the shared
definition, on both sides of the original comparison alike.

The method check fell just outside its rule at the registered window: `sim` reads 10.3 mg/dL per
10 g against the loop's 11.5 at 240 min, a shortfall of 1.2 where 1.0 was allowed, and 11.8
against 12.6 at 300. The arm spreads to the peak what oref0 SMB places in the first half hour,
and reads lower for it, so the stand-in is close and slightly flatter. `real` minus `sim` is then
-0.07 mg/dL per 10 g [-0.75, 0.50] at 240 min and +0.03 [-0.99, 1.03] at 300, under 1.0 with the
interval clear of 1.8 at both windows, which is the registered outcome that places the gap in
the physiology. Across the four arms the insulin by the peak spans 1.65 to 1.84 U per 10 g at
240 min and the rise spans 9.9 to 10.6; a real profile, a simulated one and the correction loop
alone all leave the simulated person 4.5 to 5.2 mg/dL per 10 g under the adult record of 15.1.
The rise is recorded as a bound in `docs/VALIDATION.md` and not pursued further.

Two things the run also shows. `real_bolus`, the real bolus with the loop back after 30 minutes,
peaks later than the others (+8.75 min [3.75, 15.00] at 240 min) and reads 0.8 higher, so the
loop's own addition after the bolus is worth under 1 mg/dL per 10 g on the peak. And the whole
panel ran alike between meals: mean glucose 146 to 147 mg/dL, troughs 129 to 133, on every arm,
with time below 70 mg/dL 1.7 per cent under the loop alone and 2.3 to 2.6 under the fixed
profiles, whose additions are held back only by the suspension and carry on where the loop
would have scaled its basal down.

    python examples/insulin_profile_rise.py
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np
from simglucose.controller.base import Action

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds
from timsim.analysis import meal_shape as ms

OUT = os.path.join(MEASUREMENTS, "insulin_profile_rise.json")
WORKERS = 7
MIN_MEALS = 20
BOLUS_FLOOR = 1.0
WINDOWS = (180, 240, 300)
# From `insulin_by_peak.json`, per-person medians at 240 min: (bolus, total by peak) in U per 10
# entered grams and the median trough to peak in minutes, for the simulated oref0 SMB loop and
# for the adult Loop participants.
ARMS = {"loop": None, "sim": (0.75, 1.96, 91.0), "real": (1.00, 1.77, 85.0),
        "real_bolus": (1.00, None, 0.0)}


class ProfileReplay:
    """The built-in correction loop between meals and a fixed insulin profile inside them.

    Reads the profile it doses against off the run (`info["profile"]`), so the rig's settings
    and the driver's are one object and the matching check in `run.py` has nothing to compare.
    The inner driver is `run._BasalBolus` in its default shape, built on the first step of each
    run, and every unit the profile delivers is entered in its ledger so that the correction
    that follows a meal is computed against the insulin actually given.
    """
    name = "profile-replay"

    def __init__(self, bolus_per_10g, total_per_10g, span_min,
                 bolus_window_min=ms.BOLUS_WINDOW_MIN):
        self.bolus_per_10g = float(bolus_per_10g)
        self.total_per_10g = None if total_per_10g is None else float(total_per_10g)
        self.span_min = float(span_min)
        self.bolus_window_min = float(bolus_window_min)
        self.reset()

    def reset(self):
        self.pending = []      # [until_minute, units per step] additions in flight
        self.inner = None
        self.window_until = -1.0
        self.previous = None

    def policy(self, observation, reward, done, **info):
        from timsim.simulation.run import _BasalBolus
        sample = float(info.get("sample_time", 5.0))
        minute = float(info.get("clock_minutes", 0.0))
        prof = info["profile"]
        cgm = float(observation.CGM)
        grams = float(info.get("meal", 0.0)) * sample
        if self.inner is None:
            self.inner = _BasalBolus(prof, adaptive=True, loop="trend")
        fall = (cgm - self.previous) / sample if self.previous else 0.0
        self.previous = cgm
        loop = self.inner.loop
        basal = prof.basal_at(minute)                       # U/min, at schedule
        bolus = 0.0
        if grams > 0:
            tens = grams / 10.0
            bolus = tens * self.bolus_per_10g
            # The meal bolus itself opens the window, so a bolus-only profile still keeps the
            # loop's corrections away from the 30 min either side of the entry that the covered
            # stratum reads its bolus from.
            self.window_until = max(self.window_until,
                                    minute + max(self.span_min, self.bolus_window_min))
            if self.total_per_10g is not None and self.span_min > 0:
                # The basal the measurement window will contain anyway, from 30 min before the
                # entry to the peak, at the rate scheduled at the entry. The addition is what
                # brings the window's total to the profile's, delivered as boluses so that the
                # basal ceiling (four times the peak scheduled rate) does not clip a large meal
                # where the loop's super micro boluses were not clipped. A negative addition,
                # where the scheduled basal alone exceeds the profile's total, is withheld from
                # the basal over the span, down to zero.
                window_basal = basal * (self.bolus_window_min + self.span_min)
                extra = tens * (self.total_per_10g - self.bolus_per_10g) - window_basal
                steps = max(int(round(self.span_min / sample)), 1)
                self.pending.append([minute + self.span_min, extra / steps])
        if minute >= self.window_until:
            # Between meals: the correction loop as every other measurement runs it. No grams
            # are passed, since any entry has already been dosed by the profile above.
            return self.inner.act(0.0, cgm, minute, sample, fall)
        add = 0.0
        for p in self.pending:
            if minute < p[0]:
                add += p[1]
        self.pending = [p for p in self.pending if minute < p[0]]
        if add < 0:
            basal = max(basal + add / sample, 0.0)
            add = 0.0
        # Inside the window the loop keeps its readings and its ledger current and applies only
        # its low-glucose suspension, which also holds back the profile's addition on that step.
        loop.observe(minute, cgm)
        if self.inner.ratios is not None:
            self.inner.ratios.observe(minute, cgm, self.inner.target)
        if loop.basal_scale(cgm, fall) == 0.0:
            basal, add = 0.0, 0.0
        loop.add(minute, bolus + add)
        return Action(basal=basal, bolus=(bolus + add) / sample)


def job(args):
    """One subject in one arm, reduced in the worker to its meal records and outcome."""
    name, arm, days, windows, bolus_floor = args
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    spec = ARMS[arm]
    r = simulate(name, days=days, seed=seeds.BENCH, layers=DEFAULT_LAYERS,
                 controller="trend" if spec is None else ProfileReplay(*spec))
    if r.termination:
        return name, arm, None, r.termination
    minutes = np.asarray(r.minutes, float)
    cgm = np.asarray(r.cgm, float)
    bolus_u = np.asarray(r.bolus_series, float)
    ins_u = np.asarray(r.insulin_series, float)
    meals = [(float(m), float(est)) for m, _, est in r.announced_log if est > 0]
    rescues = [float(x[1]) for x in r.rescue_log]
    carbs = [m for m, _ in meals] + rescues
    out = {"meals": len(meals)}
    for w in windows:
        recs, _ = ms.shapes(meals, carbs, minutes, cgm, window_min=w,
                            bolus_minutes=minutes[:len(bolus_u)], bolus_units=bolus_u,
                            insulin_minutes=minutes[:len(ins_u)], insulin_units=ins_u)
        cov = [x for x in recs if x["bolus_u"] >= bolus_floor]
        out[w] = {"n": len(recs), "covered": len(cov),
                  "rise_per_10g": [(x["peak_mgdl"] - x["trough_mgdl"]) / (x["grams"] / 10.0)
                                   for x in cov],
                  "ttp": [x["trough_to_peak_min"] for x in cov],
                  "bolus_per_10g": [x["bolus_u"] / (x["grams"] / 10.0) for x in cov],
                  "to_peak_per_10g": [x["insulin_to_peak_u"] / (x["grams"] / 10.0) for x in cov],
                  "trough_mgdl": [x["trough_mgdl"] for x in cov]}
    out["outcome"] = {"tir": float(r.time_in_range), "tbr": float(r.time_below_70),
                      "tar": float(r.time_above_180),
                      "mean_cgm": float(np.mean(cgm)),
                      "insulin_per_day": float(r.insulin_units / max(r.days_requested, 1)),
                      "rescues": int(r.rescue_events)}
    return name, arm, out, None


def pct(v, q):
    return float(np.percentile(np.asarray(v, float), q)) if len(v) else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=42)
    ap.add_argument("--windows", nargs="+", type=int, default=list(WINDOWS))
    ap.add_argument("--arms", nargs="+", default=list(ARMS))
    ap.add_argument("--min-meals", type=int, default=MIN_MEALS)
    ap.add_argument("--bolus-floor", type=float, default=BOLUS_FLOOR)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    from examples.panel import dosable
    subs = dosable(a.subjects)
    jobs = [(n, arm, a.days, tuple(a.windows), a.bolus_floor) for n in subs for arm in a.arms]
    print(f"{len(subs)} subjects, arms {a.arms}, {a.days} days each, on {a.workers} workers")
    with mp.Pool(a.workers) as pool:
        results = pool.map(job, jobs)

    got, dropped = {}, []
    for name, arm, out, term in results:
        if out is None:
            dropped.append({"subject": name, "arm": arm, "termination": term})
        else:
            got[(name, arm)] = out
    for d in dropped:
        print(f"  {d['subject']} {d['arm']} terminated: {d['termination']}")

    rng = np.random.default_rng(20260904)

    def ci(d):
        d = np.asarray(d, float)
        b = np.array([np.median(rng.choice(d, size=d.size, replace=True)) for _ in range(10000)])
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    keys = ("rise_per_10g", "ttp", "bolus_per_10g", "to_peak_per_10g", "trough_mgdl")
    per_subject, rows, pairs = [], [], []
    for w in a.windows:
        print(f"\n{'window':>7}{'arm':>12}{'n':>4}{'meals':>7}"
              f"{'rise/10 g p10/50/90':>24}{'ttp':>8}{'bolus/10 g':>12}{'by peak/10 g':>14}"
              f"{'trough':>8}")
        med = {}
        for arm in a.arms:
            per = {}
            for n in subs:
                o = got.get((n, arm))
                if o is None or o[w]["covered"] < a.min_meals:
                    continue
                per[n] = {k: float(np.median(o[w][k])) for k in keys}
                per[n]["covered"] = o[w]["covered"]
                per_subject.append({"subject": n, "arm": arm, "window_min": w, **per[n],
                                    "outcome": o["outcome"]})
            med[arm] = per
            if not per:
                continue
            col = {k: [p[k] for p in per.values()] for k in keys}
            rows.append({"window_min": w, "arm": arm, "subjects": len(per),
                         "meals": int(sum(p["covered"] for p in per.values())),
                         **{k: [pct(col[k], 10), pct(col[k], 50), pct(col[k], 90)]
                            for k in keys}})
            r = rows[-1]
            rise = " / ".join(f"{v:.1f}" for v in r["rise_per_10g"])
            print(f"{w:>7}{arm:>12}{len(per):>4}{r['meals']:>7}{rise:>24}"
                  f"{r['ttp'][1]:>8.0f}{r['bolus_per_10g'][1]:>12.2f}"
                  f"{r['to_peak_per_10g'][1]:>14.2f}{r['trough_mgdl'][1]:>8.0f}")
        base = "sim" if "sim" in med else a.arms[0]
        for arm in a.arms:
            if arm == base or arm not in med:
                continue
            common = sorted(set(med[base]) & set(med[arm]))
            if len(common) < 2:
                continue
            for k in ("rise_per_10g", "ttp", "to_peak_per_10g"):
                d = [med[arm][s][k] - med[base][s][k] for s in common]
                lo, hi = ci(d)
                pairs.append({"window_min": w, "arm": arm, "against": base, "key": k,
                              "subjects": len(common), "paired_diff": float(np.median(d)),
                              "ci95": [lo, hi]})
                print(f"{w:>7}{arm + ' - ' + base:>18}{len(common):>4}  {k:<16}"
                      f"{np.median(d):>8.2f}  [{lo:.2f}, {hi:.2f}]")

    print(f"\n{'arm':>12}{'n':>4}{'TIR':>7}{'TBR':>7}{'TAR':>7}{'mean':>7}{'U/day':>8}{'rescues':>9}")
    outcome = {}
    for arm in a.arms:
        o = [got[(n, arm)]["outcome"] for n in subs if (n, arm) in got]
        if not o:
            continue
        outcome[arm] = {k: float(np.median([x[k] for x in o])) for k in o[0]}
        outcome[arm]["subjects"] = len(o)
        oc = outcome[arm]
        print(f"{arm:>12}{len(o):>4}{oc['tir']:>7.1f}{oc['tbr']:>7.2f}{oc['tar']:>7.1f}"
              f"{oc['mean_cgm']:>7.0f}{oc['insulin_per_day']:>8.1f}{oc['rescues']:>9.0f}")

    json.dump({"provenance": provenance.stamp(), "subjects": list(subs), "days": a.days,
               "seed": seeds.BENCH, "arms": {k: ARMS[k] and list(ARMS[k]) for k in a.arms},
               "min_meals": a.min_meals, "bolus_floor": a.bolus_floor, "dropped": dropped,
               "rows": rows, "pairs": pairs, "outcome": outcome, "per_subject": per_subject},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
