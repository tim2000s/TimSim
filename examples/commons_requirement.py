"""Total daily insulin for each OpenAPS Data Commons user, so a cohort can be matched to them.

The DCLP3 comparison can match virtual subjects to real ones on age and on total daily
insulin, because the trial publishes both. The Commons publishes neither directly: these are
anonymous uploads with no demographics at all. What they do carry is every bolus and every
temporary basal, so a user's daily requirement can be reconstructed, and that is the one
physiological quantity available to match on.

Delivery is summed the way the pump would have delivered it. Boluses are taken as recorded.
Basal is integrated minute by minute across the user's own programmed schedule, with any
temporary basal overriding the schedule for its duration, so a loop that spent the month
suspending basal is credited with the insulin it withheld rather than the insulin it was
scheduled.

Reported per user over the same 28-day window `commons_cohort.py` scores, so the requirement
and the outcomes describe the same month.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import glob
import json
import numpy as np

from examples.commons_cohort import ROOT, WINDOW_DAYS, MIN_COVERAGE, EXPECTED
from examples.commons_cohort import user_series, window
from examples.real_meals import basal_schedule, temp_basals, treatments, BOLUS_FLOOR_U

OUT = os.path.join(MEASUREMENTS, "commons_requirement.json")


def delivered(t0, minutes, rates, temps):
    """Basal units delivered over a window, temporary basals overriding the schedule."""
    grid = np.arange(t0, t0 + minutes, 5.0)
    actual = rates[((grid / 60.0) % 24).astype(int)].copy()
    for start, dur, absolute in temps:
        if dur <= 0 or start + dur < t0 or start > t0 + minutes:
            continue
        actual[(grid >= start) & (grid < start + dur)] = absolute
    return float(np.sum(actual) * 5.0 / 60.0)


def one(user_dir):
    a = user_series(user_dir)
    if a is None:
        return None
    sel, cov = window(a, "middle")
    if sel is None or cov < MIN_COVERAGE:
        return None
    rates = basal_schedule(user_dir)
    if rates is None:
        return None
    t0 = float(sel[0, 0]) / 60000.0
    minutes = WINDOW_DAYS * 1440.0
    temps = temp_basals(user_dir, rates)
    tr = treatments(user_dir)
    tm = np.array([r[0] for r in tr]) if tr else np.zeros(0)
    ins = np.array([r[2] for r in tr]) if tr else np.zeros(0)
    inside = (tm >= t0) & (tm < t0 + minutes)
    bolus = float(np.sum(ins[inside & (ins >= BOLUS_FLOOR_U)]))
    basal = delivered(t0, minutes, rates, temps)
    carbs = np.array([r[1] for r in tr]) if tr else np.zeros(0)
    grams = float(np.sum(carbs[inside]))

    # The window is chosen on glucose coverage, which says nothing about whether the pump
    # was uploading. Seventeen users looked as though they took 90 per cent or more of their
    # insulin as basal and logged no carbohydrate at all, which reads as fully closed-loop
    # living until you count their records: they carry between 1,256 and 7,417 boluses
    # elsewhere in their history. Their treatments are missing from this window, not their
    # meals, and their reconstructed requirement is understated by whatever is absent.
    n_bolus = int(np.sum(inside & (ins >= BOLUS_FLOOR_U)))
    n_temp = int(np.sum([(t0 <= s < t0 + minutes) for s, _, _ in temps]))
    return {"user": os.path.basename(user_dir), "coverage": round(cov, 3),
            "boluses_in_window": n_bolus, "temp_basals_in_window": n_temp,
            "bolus_per_day_count": n_bolus / WINDOW_DAYS,
            "bolus_per_day": bolus / WINDOW_DAYS, "basal_per_day": basal / WINDOW_DAYS,
            "tdd": (bolus + basal) / WINDOW_DAYS,
            "basal_share": (basal / (bolus + basal)) if (bolus + basal) > 0 else None,
            "carbs_per_day": grams / WINDOW_DAYS,
            "scheduled_basal_per_day": float(np.sum(rates))}


def main():
    users = sorted(d for d in glob.glob(os.path.join(ROOT, "*")) if os.path.isdir(d))
    rows = []
    for i, d in enumerate(users, 1):
        try:
            r = one(d)
        except Exception as exc:
            print(f"  skip {os.path.basename(d)}: {exc}", file=sys.stderr)
            continue
        if r:
            rows.append(r)
        if i % 40 == 0:
            print(f"  {i}/{len(users)} scanned, {len(rows)} usable", flush=True)

    plausible = [r for r in rows if 5.0 <= r["tdd"] <= 200.0]  # a pump misreport, not a person
    # A pump user boluses. Fewer than one bolus every other day across 28 days means the
    # window is missing treatment records rather than describing somebody who never eats.
    keep = [r for r in plausible if r["bolus_per_day_count"] >= 0.5
            and r["temp_basals_in_window"] > 0]
    print(f"\n{len(keep)} users with a reconstructable daily requirement")
    print(f"  {len(rows) - len(plausible)} discarded outside 5 to 200 U/day")
    print(f"  {len(plausible) - len(keep)} discarded for missing treatment records in the "
          f"window despite adequate glucose coverage")
    for k, lab in (("tdd", "Total daily insulin, U/day"),
                   ("bolus_per_day", "  of it bolus, U/day"),
                   ("basal_per_day", "  of it basal, U/day"),
                   ("basal_share", "Basal share"),
                   ("carbs_per_day", "Logged carbohydrate, g/day")):
        v = np.array([r[k] for r in keep if r[k] is not None], float)
        print(f"  {lab:30} median {np.median(v):7.2f}  IQR {np.percentile(v, 25):6.2f} "
              f"to {np.percentile(v, 75):6.2f}  p10-p90 {np.percentile(v, 10):6.2f} "
              f"to {np.percentile(v, 90):6.2f}")
    json.dump({"window_days": WINDOW_DAYS, "n": len(keep), "users": keep}, open(OUT, "w"),
              indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
