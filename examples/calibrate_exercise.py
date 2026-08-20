"""What the activity layer actually does to glucose, against what exercise does to people.

The layer in `person/activity.py` has never been grounded. Its two gains were chosen so that a
moderate session moves glucose by "the tens of mg/dL that the literature reports", which is a
statement about an order of magnitude rather than a calibration, and it is off by default for
that reason.

The reference is observational and far larger than anything else in this package: 428,058
exercise sessions from 3,248 people with type 1 diabetes, giving the acute glucose fall by
exercise type and the rate of delayed hypoglycaemia in the six hours afterwards.

    walking      -1.24 +/- 0.81 mmol/L     -22.3 mg/dL
    aerobic      -1.43 +/- 1.02            -25.8
    anaerobic    -0.52 +/- 0.81             -9.4
    delayed hypoglycaemia within 6 h: 21.2 per cent aerobic, 11.2 per cent resistance

The ordering is the part that matters and the part a single intensity scalar cannot produce.
Anaerobic exercise is the most intense and moves glucose least, because it recruits
counter-regulatory hormones that oppose the uptake. A model where a session's effect rises
monotonically with intensity will get walking and aerobic roughly right and anaerobic backwards.

This measures before it changes anything: a session is imposed on a subject held on basal alone,
and the fall is read against the same subject on the same day with no session, so the session is
separated from whatever the subject was doing anyway.

    python examples/calibrate_exercise.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from simglucose.controller.base import Action

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "exercise_calibration.json")

DAYS = 2
SESSION_AT_H = 15.0            # mid-afternoon, clear of the overnight and of breakfast
SESSION_MIN = 45.0
WINDOW_MIN = 360.0             # the six hours the delayed-hypoglycaemia figure covers
HYPO_MGDL = 70.0

# The observational reference, converted from mmol/L.
REAL = {"walking": -22.3, "aerobic": -25.8, "anaerobic": -9.4}
REAL_DELAYED = {"aerobic": 21.2, "resistance": 11.2}

# What this package currently offers, which is one kind of session at an intensity. The
# intensities here bracket the range `activity.INTENSITY` draws from.
INTENSITIES = (0.35, 0.7, 1.0)


class BasalOnly:
    """The subject's own basal and nothing else, so the session is uncovered."""

    def __init__(self, profile):
        self.profile = profile

    def policy(self, observation, reward, done, **info):
        return Action(basal=self.profile.basal_at(float(info.get("clock_minutes", 0.0))),
                      bolus=0.0)

    def reset(self):
        pass


def _one(job):
    name, intensity, gain_scale, with_meal = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    import timsim.person.activity as A

    prof = titrate.profile_for(name)
    start = SESSION_AT_H * 60.0
    sessions = ((start, SESSION_MIN, float(intensity)),)
    # A meal three hours before the session, bolused, so there is insulin on board when it
    # starts. Delayed post-exercise hypoglycaemia needs that by construction: the layer raises
    # only the insulin-dependent term afterwards, so a run on basal alone cannot produce it and
    # measuring it there says nothing about the mechanism.
    meals = [(SESSION_AT_H - 3.0, 60.0, False)] if with_meal else []

    def trace(with_session):
        r = simulate(name, days=DAYS, seed=seeds.BENCH,
                     layers=("activity",) if with_session else (),
                     controller="trend" if with_meal else BasalOnly(prof),
                     profile=prof, meals=meals)
        return np.asarray(r.bg, float), np.asarray(r.minutes, float)

    # The layer draws its own sessions, so it is bypassed and one session imposed directly.
    # The gains are scaled in the same window, which is how the sweep asks what magnitude the
    # layer would need to reproduce the measured fall.
    original, vmx0, vm00 = A.draw_sessions, A.VMX_GAIN, A.VM0_GAIN
    A.draw_sessions = lambda rng, days, **kw: sessions
    A.VMX_GAIN, A.VM0_GAIN = vmx0 * gain_scale, vm00 * gain_scale
    try:
        with_bg, minutes = trace(True)
    finally:
        A.draw_sessions, A.VMX_GAIN, A.VM0_GAIN = original, vmx0, vm00
    without_bg, _ = trace(False)

    n = min(len(with_bg), len(without_bg), len(minutes))
    i0 = int(np.searchsorted(minutes[:n], start))
    i_end = int(np.searchsorted(minutes[:n], start + SESSION_MIN))
    i_win = int(np.searchsorted(minutes[:n], start + SESSION_MIN + WINDOW_MIN))
    if i_win <= i_end:
        return None

    delta = with_bg[:n] - without_bg[:n]
    during = float(np.min(delta[i0:i_end + 1]))          # the acute fall the session causes
    after = delta[i_end:i_win]
    low_after = bool(np.any(with_bg[i_end:i_win] < HYPO_MGDL))
    return {"name": name, "intensity": float(intensity), "gain_scale": float(gain_scale),
            "with_meal": bool(with_meal), "acute_mgdl": during,
            "deepest_after_mgdl": float(np.min(after)) if len(after) else float("nan"),
            "hypo_within_6h": low_after}


GAIN_SCALES = (1.0, 1.5, 2.0, 2.5)


def main(n_subjects=20, workers=6):
    from timsim.therapy import titrate
    subjects = [s for s in sorted(titrate.titrated_subjects()) if s.startswith("adult")][:n_subjects]
    if not subjects:
        raise SystemExit("no titrated adults; run examples/titrate_cohort.py first")
    # The acute fall is read on basal alone, which isolates the session. Delayed hypoglycaemia
    # is read with a bolused meal three hours earlier, because the mechanism needs insulin on
    # board and a basal-only run cannot show it either way.
    jobs = [(s, 0.7, g, False) for g in GAIN_SCALES for s in subjects]
    jobs += [(s, 0.7, g, True) for g in GAIN_SCALES for s in subjects]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = [r for r in ex.map(_one, jobs) if r]

    print(f"{len(subjects)} titrated adults, a single {SESSION_MIN:.0f} minute session at "
          f"{SESSION_AT_H:.0f}:00, on basal alone\n")
    print(f"  {'gain':>7}{'acute fall':>13}{'IQR':>22}"
          f"{'hypo <6h, basal':>18}{'hypo <6h, insulin on board':>29}")
    out = []
    for g in GAIN_SCALES:
        basal = [r for r in rows if abs(r["gain_scale"] - g) < 1e-9 and not r["with_meal"]]
        meal = [r for r in rows if abs(r["gain_scale"] - g) < 1e-9 and r["with_meal"]]
        if not basal:
            continue
        a = np.array([r["acute_mgdl"] for r in basal])
        hb = 100.0 * np.mean([r["hypo_within_6h"] for r in basal]) if basal else float("nan")
        hm = 100.0 * np.mean([r["hypo_within_6h"] for r in meal]) if meal else float("nan")
        out.append({"gain_scale": g, "n": len(basal), "acute_median": float(np.median(a)),
                    "acute_p25": float(np.percentile(a, 25)),
                    "acute_p75": float(np.percentile(a, 75)),
                    "hypo_basal_pct": float(hb), "hypo_with_insulin_pct": float(hm)})
        print(f"  {g:>7.1f}{np.median(a):>13.1f}"
              f"{f'{np.percentile(a, 25):.1f} to {np.percentile(a, 75):.1f}':>22}"
              f"{hb:>17.1f}%{hm:>28.1f}%")

    print(f"\n  real, by exercise type (mg/dL): "
          + ", ".join(f"{k} {v:+.1f}" for k, v in REAL.items()))
    print(f"  real delayed hypoglycaemia: "
          + ", ".join(f"{k} {v:.1f}%" for k, v in REAL_DELAYED.items()))
    print("\n  The layer has one kind of session, so it can be compared with walking and")
    print("  aerobic but has nothing to compare with anaerobic, which falls least in the real")
    print("  data and would fall most here.")

    json.dump({"subjects": len(subjects), "session_minutes": SESSION_MIN,
               "real_acute_mgdl": REAL, "real_delayed_pct": REAL_DELAYED,
               "provenance": provenance.stamp(),
               "measured": out, "runs": rows}, open(OUT, "w"), indent=1)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
