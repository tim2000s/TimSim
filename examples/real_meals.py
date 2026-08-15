"""What an uncovered meal does to a real person, measured the same way as the simulated one.

The simulated measurement gives a subject a single meal on basal alone and reads the rise
above the counterfactual and the time to the peak. The nearest real equivalent is a logged
carbohydrate entry that nobody bolused for, which on a closed loop is uncommon and never
entirely uncovered, since the loop keeps acting. Both facts are handled explicitly: a meal is
admitted only when no bolus is recorded from 30 minutes before it to 120 minutes after, and
the automatic insulin delivered across the window is reported alongside the rise, so the
reader can see how far from uncovered these meals are.

Definitions match `meal_response.py` deliberately. Baseline is the reading at the meal,
the peak is the maximum over the following six hours, and the rise is quoted per 10 g as
logged. Logged grams are an under-estimate of true intake, which is why the rise per logged
10 g is an upper bound on the rise per true 10 g.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")
import json
import glob
import numpy as np

from examples.commons_cohort import ROOT, user_series   # the validated entries parser

OUT = os.path.join(MEASUREMENTS, "real_meals_dia.json")

GRAMS_LO, GRAMS_HI = 30.0, 90.0
CLEAR_BEFORE_MIN, CLEAR_AFTER_MIN = 300.0, 240.0     # a full insulin action duration before, and the whole window after
WINDOW_MIN = 360.0
BOLUS_FLOOR_U = 0.1                                   # below this is not a meal bolus


def basal_schedule(user_dir):
    """The user's scheduled basal as 24 hourly rates in U/h, or None."""
    best = None
    for path in sorted(glob.glob(os.path.join(user_dir, "**", "*profile*.json"),
                                 recursive=True)):
        try:
            data = json.load(open(path))
        except Exception:
            continue
        for rec in (data if isinstance(data, list) else [data]):
            store = rec.get("store") or {}
            name = rec.get("defaultProfile")
            prof = store.get(name) or (list(store.values())[0] if store else None)
            if not prof or not prof.get("basal"):
                continue
            rates = np.zeros(24)
            try:
                pts = sorted((int(float(b.get("timeAsSeconds", 0))) // 3600,
                              float(b["value"])) for b in prof["basal"])
            except (KeyError, TypeError, ValueError):
                continue
            if not pts:
                continue
            cur = pts[0][1]
            for h in range(24):
                for hh, v in pts:
                    if hh <= h:
                        cur = v
                rates[h] = cur
            best = rates
    return best


def temp_basals(user_dir):
    """(start_minute, duration_min, absolute_u_per_h) for every temporary basal."""
    out = []
    for path in sorted(glob.glob(os.path.join(user_dir, "**", "*treatments*.json"),
                                 recursive=True)):
        try:
            data = json.load(open(path))
        except Exception:
            continue
        for t in data:
            if t.get("eventType") != "Temp Basal":
                continue
            stamp = t.get("created_at") or t.get("timestamp")
            if not isinstance(stamp, str) or t.get("absolute") is None:
                continue
            try:
                import datetime as dt
                when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                out.append((when.timestamp() / 60.0, float(t.get("duration") or 0),
                            float(t["absolute"])))
            except Exception:
                continue
    out.sort()
    return out


def delivered_vs_scheduled(t0, minutes, rates, temps):
    """Basal insulin delivered over [t0, t0+minutes) and what the schedule asked for.

    Minutes not covered by a temporary basal fall back to the schedule, which is what the
    pump does. Overlapping temporary basals are resolved by taking the latest one to start,
    since a new temporary basal replaces the one running.
    """
    if rates is None:
        return None, None
    grid = np.arange(t0, t0 + minutes, 5.0)
    hours = ((grid / 60.0) % 24).astype(int)
    sched = rates[hours]
    actual = sched.copy()
    for start, dur, absolute in temps:
        if dur <= 0 or start + dur < t0 or start > t0 + minutes:
            continue
        covered = (grid >= start) & (grid < start + dur)
        actual[covered] = absolute
    return float(np.sum(actual) * 5.0 / 60.0), float(np.sum(sched) * 5.0 / 60.0)


def treatments(user_dir):
    """(minute, carbs, bolus_units) for a user, ascending."""
    rows = []
    for path in sorted(glob.glob(os.path.join(user_dir, "**", "*treatments*.json"),
                                 recursive=True)):
        try:
            data = json.load(open(path))
        except Exception:
            continue
        for t in data:
            stamp = t.get("created_at") or t.get("timestamp")
            if not isinstance(stamp, str):
                continue
            try:
                import datetime as dt
                s = stamp.replace("Z", "+00:00")
                when = dt.datetime.fromisoformat(s)
                minute = when.timestamp() / 60.0
            except Exception:
                continue
            carbs = t.get("carbs") or 0
            ins = t.get("insulin") or 0
            try:
                rows.append((minute, float(carbs), float(ins)))
            except (TypeError, ValueError):
                continue
    rows.sort()
    return rows


def meals_for(user_dir):
    a = user_series(user_dir)
    if a is None:
        return []
    gm = a[:, 0] / 60000.0                              # glucose sample minutes
    gv = a[:, 1].astype(float)
    tr = treatments(user_dir)
    if not tr:
        return []
    tm = np.array([r[0] for r in tr])
    carbs = np.array([r[1] for r in tr])
    ins = np.array([r[2] for r in tr])
    bolus_at = tm[ins >= BOLUS_FLOOR_U]
    rates, temps = basal_schedule(user_dir), temp_basals(user_dir)

    out = []
    for i in np.nonzero((carbs >= GRAMS_LO) & (carbs <= GRAMS_HI))[0]:
        t0 = tm[i]
        if len(bolus_at) and np.any((bolus_at >= t0 - CLEAR_BEFORE_MIN) &
                                    (bolus_at <= t0 + CLEAR_AFTER_MIN)):
            continue
        sel = (gm >= t0 - 15.0) & (gm <= t0 + WINDOW_MIN)
        if np.sum(sel) < int(0.8 * (WINDOW_MIN + 15.0) / 5.0):
            continue                                    # too little glucose data to read
        gt, gg = gm[sel] - t0, gv[sel]
        pre = gg[gt <= 0]
        if not len(pre):
            continue
        base = float(pre[-1])
        # Carbohydrate logged below 80 mg/dL is a hypoglycaemia treatment rather than a meal,
        # and above 180 the person is already high, so neither is comparable with a simulated
        # meal given at steady state.
        if not (80.0 <= base <= 180.0):
            continue
        after = gt > 0
        if not np.any(after):
            continue
        peak_i = int(np.argmax(gg[after]))
        peak, tpeak = float(gg[after][peak_i]), float(gt[after][peak_i])
        auto = float(np.sum(ins[(tm > t0) & (tm <= t0 + 240.0)]))
        got, want = delivered_vs_scheduled(t0, 240.0, rates, temps)
        out.append({"grams": float(carbs[i]), "baseline": base, "peak": peak,
                    "rise": peak - base, "rise_per_10g": (peak - base) / (carbs[i] / 10.0),
                    "time_to_peak_min": tpeak, "peak_above_180": bool(peak > 180.0),
                    "bolus_4h_u": auto,
                    "basal_delivered_4h_u": got, "basal_scheduled_4h_u": want,
                    "basal_excess_4h_u": (None if got is None else got - want)})
    return out


def main():
    users = sorted(d for d in glob.glob(os.path.join(ROOT, "*")) if os.path.isdir(d))
    rows, n_users = [], 0
    for i, d in enumerate(users, 1):
        try:
            got = meals_for(d)
        except Exception as exc:
            print(f"  skip {os.path.basename(d)}: {exc}", file=sys.stderr)
            continue
        if got:
            n_users += 1
            rows += got
        if i % 20 == 0:
            print(f"  {i}/{len(users)} users, {len(rows)} meals", flush=True)

    print(f"\n{len(rows)} uncovered meals of {GRAMS_LO:.0f} to {GRAMS_HI:.0f} g "
          f"from {n_users} users")
    if not rows:
        return
    summarise(rows, "all bolus-free meals")
    known = [r for r in rows if r.get("basal_excess_4h_u") is not None]
    print(f"\n  of which {len(known)} have a readable basal schedule; "
          f"median excess over schedule {np.median([r['basal_excess_4h_u'] for r in known]):+.2f} U"
          if known else "\n  no readable basal schedules")
    unc = [r for r in known if r["basal_excess_4h_u"] <= 0.5]
    if unc:
        summarise(unc, "meals where the loop added no more than 0.5 U over schedule in 4 h")
    json.dump({"n_meals": len(rows), "n_users": n_users, "n_uncovered": len(unc),
               "meals": rows}, open(OUT, "w"))
    print(f"\nwrote {OUT}")
    return


def summarise(rows, label):
    print(f"\n--- {label}: {len(rows)} meals")
    rp = np.array([r["rise_per_10g"] for r in rows])
    tp = np.array([r["time_to_peak_min"] for r in rows])
    pk = np.array([r["peak"] for r in rows])
    gr = np.array([r["grams"] for r in rows])
    au = np.array([r["bolus_4h_u"] for r in rows])
    print(f"  logged grams        median {np.median(gr):6.1f}")
    print(f"  rise per logged 10g median {np.median(rp):6.2f} mg/dL  "
          f"IQR {np.percentile(rp,25):.2f} to {np.percentile(rp,75):.2f}")
    # A meal whose glucose never rose has no peak to time, and including it puts the peak at
    # the first sample. Timing is reported over the meals that produced a rise.
    rose = np.array([r["rise"] for r in rows]) >= 10.0
    tpr = tp[rose]
    print(f"  time to peak        median {np.median(tpr):6.0f} min  "
          f"IQR {np.percentile(tpr,25):.0f} to {np.percentile(tpr,75):.0f}  "
          f"(over the {rose.sum()} meals rising at least 10 mg/dL)")
    print(f"  absolute peak       median {np.median(pk):6.0f} mg/dL")
    print(f"  peak above 180      {100*np.mean([r['peak_above_180'] for r in rows]):.1f}%")
    print(f"  recorded bolus in the 4 h after, median {np.median(au):.2f} U")


if __name__ == "__main__":
    main()
