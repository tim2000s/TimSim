"""Insulin delivered by the time a meal peaks, on both sides of the meal comparison.

Written 4 September 2026, after the announced record (issue 51) and a carbohydrate estimate bias
(`carb_bias.py`) each failed to close the covered meal rise, which then stood at 11.5 mg/dL per
10 entered grams under oref0 SMB against 16.5 in the Loop record at a 240 minute window (15.1
once the record is restricted to adults, issue 52, found by this measurement). Three
input-side perturbations have been absorbed without moving time above 180 mg/dL, and the bias
arm was a fourth: the entry fell 16 per cent and the rise on the eaten record did not move,
because the controller had replaced the bolus within the window. Every one of those is
consistent with the loop, rather than the physiology, setting the height of a covered meal. This
measures that directly.

The statistic is insulin delivered from 30 minutes before the entry (`meal_shape.BOLUS_WINDOW_MIN`,
so a pre-bolus counts) to the minute of the peak, per 10 entered grams, on covered meals. It is
split into the meal bolus, taken in the same window either side of the entry as the covered
stratum uses, and what the loop added after it. The real side integrates the pump's rate record
and sums its boluses in SQL; the simulated side sums the per-step delivery series through the
shared definition in `timsim/analysis/meal_shape.py`, and
`tests/test_meal_shape.py::test_sql_and_python_agree_on_real_subjects` holds the two to within a
hundredth of a unit on real subjects. Daily insulin is reported beside it on both sides, because
a loop that has delivered more by the peak may simply be dosing more.

What follows from each outcome. If the simulated loop has delivered more insulin per 10 g by the
peak than the real one, the covered shortfall is at least partly the controller's timing and
dose against these subjects' settings, and the physiology is not the first place to look. If it
has delivered the same or less, the shortfall is in the response to the insulin, which is the
model. The simulated side is oref0 SMB because that is where the gap is quoted; the real side is
Loop, which ran temp basals without automatic boluses in 2018 to 2020, and ReplaceBG, a
sensor-augmented pump with no loop at all, so the two bracket the controller.

The real side is reported for every participant and for adults alone. 297 of the 767 Loop
participants with enough meals at 240 min are under 18, and the pooled covered rise of 16.5
mg/dL per 10 g that the gap has been quoted against since 30 August 2026 reads 15.1 on the
adults, who are what the simulated panel is (issue 52). The adult rows are the comparison.

Two limits. The simulated delivery series drops steps on which the sensor returned nothing, so a
window with a sensor gap is short by the basal delivered in it; coverage is 80 per cent at
minimum and the effect is at most a fifth of the basal part. And the real record has no body
weight, so insulin is in units rather than units per kilogram; the population's weights are in
each run's `meta`.

Result, 4 September 2026. Per-person medians at 240 min, tenth to ninetieth percentile across
people, on covered meals, from `docs/measurements/insulin_by_peak.json`:

    side                 n   rise / 10 g       meal bolus U / 10 g   by peak U / 10 g   added U / 10 g   peak min
    Loop adults        470   15.1 (10.1-22.3)   1.00 (0.63-1.57)      1.77 (1.17-2.74)   0.71 (0.39-1.26)   85
    ReplaceBG          178   14.2 ( 8.9-21.0)   1.01 (0.67-1.80)      1.66 (1.02-2.60)   0.46 (0.23-0.84)   80
    simulated, oref     36   11.5 ( 8.5-14.5)   0.75 (0.53-1.11)      1.96 (1.41-2.87)   1.31 (0.90-1.86)   91

    daily insulin, U/day   Loop adults 41.1 (26.1-72.0), bolus share 0.38
                           ReplaceBG 42.1 (25.3-72.7), 0.49
                           simulated 69.1 (44.8-90.0), 0.70, at a body weight of 81.5 kg (68.3-92.2)

By the peak the simulated loop has delivered 11 per cent more insulin per 10 g than Loop's adults
and 18 per cent more than ReplaceBG, arranged differently: the meal bolus is three quarters of
the real one, which is the titrated carbohydrate ratio, and the addition after the entry is 1.8
times Loop's and 2.8 times ReplaceBG's, arriving later than a bolus would. So the first outcome
above holds, weakly. The dose by the peak is higher on the simulated side and cannot be ruled out
as a cause of the shortfall, and it is not obviously large enough to be the whole of it, since
the rise is 24 per cent lower on 11 per cent more insulin placed later. What separates those is a
run in which the simulated subject receives the real profile, a bolus of 1.00 U per 10 g at the
entry and 0.71 spread to the peak, and the rise is read again; that has not been done.

The larger discrepancy is the day. The simulated panel takes 1.7 times the daily insulin of Loop's
adults with the bolus share at 0.70 against 0.38, and since the excess by the peak is 11 per cent,
most of the 28 U/day sits after the peaks: corrections and super micro boluses on the fall, on
runs that record 2.0 rescue helpings a day and 4.0 per cent of time below 70 mg/dL
(`sim_meal_shape_announced_oref.json`, the same runs). The 47.6 U/day that `DESIGN_ALIGNMENT.md`
matches to the trial is the reference loop on a different cohort, and does not carry to this
panel under oref0 SMB.

    python examples/insulin_by_peak.py --controller oref
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
from timsim.analysis import meal_shape as ms

OUT = os.path.join(MEASUREMENTS, "insulin_by_peak.json")
DSN = "dbname=oref"
STUDIES = ("Loop", "ReplaceBG")
WINDOWS = (180, 240, 300)
ADULT_AGE = 18.0
WORKERS = 7
MIN_MEALS = 20
BOLUS_FLOOR = 1.0

# Daily insulin per person from the pump record. A day is admitted when the CGM covers 80 per
# cent of it and the rate record covers 90 per cent, with any single rate held for longer than a
# day treated as a gap rather than as a rate, since the record carries a schedule row at least
# daily and a longer hold is a missing stretch (Loop:1009 has one of 99 days).
TDD_SQL = """
with subs as (select subject_id from studies.subject where study_name = %(study)s),
days as (
  select subject_id, date_trunc('day', ts_local) d from studies.cgm
  where subject_id in (select subject_id from subs)
  group by 1, 2 having count(*) >= 230),
seg as (
  select subject_id, ts_local, rate_u_hr,
         lead(ts_local) over (partition by subject_id order by ts_local) nxt
  from studies.basal where subject_id in (select subject_id from subs)),
basal_day as (
  select d.subject_id, d.d,
         sum(s.rate_u_hr * extract(epoch from (least(s.nxt, d.d + interval '1 day')
                                               - greatest(s.ts_local, d.d))) / 3600) basal_u,
         sum(extract(epoch from (least(s.nxt, d.d + interval '1 day')
                                 - greatest(s.ts_local, d.d))) / 86400) covered
  from days d join seg s on s.subject_id = d.subject_id
    and s.ts_local < d.d + interval '1 day' and s.nxt > d.d
    and s.nxt - s.ts_local <= interval '1 day'
  group by 1, 2),
bolus_day as (
  select subject_id, date_trunc('day', ts_local) d, sum(bolus_u) bolus_u from studies.bolus
  where subject_id in (select subject_id from subs) group by 1, 2)
select b.subject_id, b.d, b.basal_u, coalesce(o.bolus_u, 0) bolus_u
from basal_day b left join bolus_day o using (subject_id, d)
where b.covered >= 0.9
"""


def pct(v, q):
    return float(np.percentile(np.asarray(v, float), q)) if len(v) else float("nan")


def per_meal(grams, bolus, bolus_to_peak, basal_to_peak):
    """One meal's insulin figures per 10 entered grams, or None when the basal is unknown."""
    if basal_to_peak is None or not np.isfinite(basal_to_peak):
        return None
    per = float(grams) / 10.0
    total = float(bolus_to_peak) + float(basal_to_peak)
    return {"bolus_per_10g": float(bolus) / per, "to_peak_per_10g": total / per,
            "added_per_10g": (total - float(bolus)) / per}


KEYS = ("bolus_per_10g", "to_peak_per_10g", "added_per_10g", "rise_per_10g", "ttp_min")


def summarise(per_subject_meals, min_meals=MIN_MEALS):
    """Per-person medians on covered meals, then the between-person spread of those."""
    kept = {s: v for s, v in per_subject_meals.items() if len(v) >= min_meals}
    per = {s: {k: float(np.median([m[k] for m in v])) for k in KEYS} for s, v in kept.items()}
    meals = {s: len(v) for s, v in kept.items()}
    return dict(spread(per, meals), per_subject=per)


def spread(per_subject, meals):
    """The between-person spread of per-person medians, over whichever people are passed."""
    return {"subjects": len(per_subject), "meals": int(sum(meals[s] for s in per_subject)),
            **{k: [pct([p[k] for p in per_subject.values()], q) for q in (10, 50, 90)]
               for k in KEYS}}


def restrict(side, ages, min_age):
    """The same rows over the people at or above `min_age`, from the stored per-person medians.

    A person's median is a property of that person and is unchanged by who else is in the
    table, so the adult rows are a selection of the stored ones rather than a second pass.
    """
    out = {}
    for w, r in side.items():
        if w == "daily":
            keep = {s: v for s, v in r["per_subject"].items() if ages.get(s, -1) >= min_age}
            share = {s: v for s, v in r["bolus_share_per_subject"].items() if s in keep}
            out[w] = daily(keep, share)
            continue
        per = {s: p for s, p in r["per_subject"].items() if ages.get(s, -1) >= min_age}
        out[w] = spread(per, r["meals_per_subject"])
    return out


def daily(tdd, share):
    return {"subjects": len(tdd),
            "units_per_day": [pct(list(tdd.values()), q) for q in (10, 50, 90)],
            "bolus_share": [pct(list(share.values()), q) for q in (10, 50, 90)],
            "per_subject": tdd, "bolus_share_per_subject": share}


def real_side(cur, study, windows, bolus_floor, min_meals):
    from examples.real_meal_shape import SQL, params
    out = {}
    for w in windows:
        cur.execute(SQL, params(study, w, min_age=0.0))
        meals, all_meals, gaps = {}, {}, 0
        for row in cur.fetchall():
            sid, ttp, _, rise, grams, bolus = row[0], float(row[1]), row[2], float(row[3]), \
                float(row[4]), float(row[5])
            all_meals[sid] = all_meals.get(sid, 0) + 1
            if bolus < bolus_floor:
                continue
            m = per_meal(grams, bolus, row[8], row[9])
            if m is None:
                gaps += 1
                continue
            meals.setdefault(sid, []).append(
                dict(m, rise_per_10g=rise / (grams / 10.0), ttp_min=ttp))
        # The person threshold is on every admitted meal, as `real_meal_shape.py` applies it,
        # and the stratum then takes whichever of that person's meals were covered.
        kept = {s: v for s, v in meals.items() if all_meals.get(s, 0) >= min_meals}
        out[w] = dict(summarise(kept, min_meals=1), rate_gap_meals=gaps,
                      meals_per_subject={s: len(v) for s, v in kept.items()})
        print(f"  {study} {w} min: {out[w]['subjects']} people, {out[w]['meals']} covered "
              f"meals, {gaps} in a rate gap")
    cur.execute(TDD_SQL, {"study": study})
    days = {}
    for sid, _, basal, bolus in cur.fetchall():
        days.setdefault(sid, []).append((float(basal), float(bolus)))
    tdd = {s: float(np.median([b + o for b, o in v])) for s, v in days.items() if len(v) >= 14}
    share = {s: float(np.median([o / (b + o) for b, o in v if b + o > 0]))
             for s, v in days.items() if len(v) >= 14}
    out["daily"] = dict(daily(tdd, share), days=int(sum(len(v) for v in days.values())))
    print(f"  {study} daily insulin: {out['daily']['units_per_day'][1]:.1f} U/day median over "
          f"{len(tdd)} people, bolus share {out['daily']['bolus_share'][1]:.2f}")
    return out


def job(args):
    """One simulated subject, reduced to its covered meals inside the worker.

    macOS spawns, so this is at module level and everything it needs travels in the tuple. The
    announced record is used, as the real side is forced to, so the grams under every figure are
    the grams the person entered.
    """
    name, days, windows, controller, bolus_floor = args
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    ctrl = controller
    if controller == "oref":
        from timsim.controller import oref
        ctrl = oref.OrefController(name)
    r = simulate(name, days=days, seed=seeds.BENCH, layers=DEFAULT_LAYERS, controller=ctrl)
    if r.termination:
        return name, None, r.termination
    minutes = np.asarray(r.minutes, float)
    cgm = np.asarray(r.cgm, float)
    meals = [(float(m), float(est)) for m, _, est in r.announced_log if est > 0]
    carbs = [m for m, _ in meals] + [float(x[1]) for x in r.rescue_log]
    bolus_u = np.asarray(r.bolus_series, float)
    insulin_u = np.asarray(r.insulin_series, float)
    out = {"days_run": float(minutes[-1] / 1440.0),
           "units_per_day": float(insulin_u.sum() / (minutes[-1] / 1440.0)),
           "bolus_share": float(bolus_u.sum() / insulin_u.sum()),
           "body_weight": r.meta.get("body_weight")}
    for w in windows:
        recs, _ = ms.shapes(meals, carbs, minutes, cgm, window_min=w,
                            bolus_minutes=minutes[:len(bolus_u)], bolus_units=bolus_u,
                            insulin_minutes=minutes[:len(insulin_u)], insulin_units=insulin_u)
        out[w] = {"meals": len(recs), "covered": []}
        for x in recs:
            if x["bolus_u"] < bolus_floor:
                continue
            m = per_meal(x["grams"], x["bolus_u"], x["bolus_to_peak_u"],
                         x["insulin_to_peak_u"] - x["bolus_to_peak_u"])
            out[w]["covered"].append(dict(
                m, rise_per_10g=(x["peak_mgdl"] - x["trough_mgdl"]) / (x["grams"] / 10.0),
                ttp_min=x["trough_to_peak_min"]))
    return name, out, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=42)
    ap.add_argument("--controller", default="oref")
    ap.add_argument("--windows", nargs="+", type=int, default=list(WINDOWS))
    ap.add_argument("--studies", nargs="+", default=list(STUDIES))
    ap.add_argument("--min-meals", type=int, default=MIN_MEALS)
    ap.add_argument("--bolus-floor", type=float, default=BOLUS_FLOOR)
    ap.add_argument("--adult-age", type=float, default=ADULT_AGE)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--dsn", default=DSN)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    if a.controller == "oref":
        from timsim.controller import oref as _oref
        if not _oref.available():
            raise SystemExit("the oref bridge is not gathered; run bridge/oref/build.sh")
    from examples.panel import dosable
    import psycopg2
    subs = dosable(a.subjects)
    jobs = [(n, a.days, tuple(a.windows), a.controller, a.bolus_floor) for n in subs]
    print(f"{len(subs)} subjects, {a.days} days each, controller {a.controller}, "
          f"on {a.workers} workers; real side on {a.studies} meanwhile")
    pool = mp.Pool(a.workers)
    pending = pool.map_async(job, jobs)

    real, ages = {}, {}
    with psycopg2.connect(a.dsn) as conn, conn.cursor() as cur:
        cur.execute("select subject_id, age_years from studies.subject")
        ages = {s: (float("nan") if y is None else float(y)) for s, y in cur.fetchall()}
        for study in a.studies:
            real[study] = real_side(cur, study, a.windows, a.bolus_floor, a.min_meals)
            real[study + " adults"] = restrict(real[study], ages, a.adult_age)

    results = pending.get()
    pool.close()
    pool.join()
    sim, dropped = {}, []
    for name, out, term in results:
        if out is None:
            dropped.append({"subject": name, "termination": term})
        else:
            sim[name] = out
    sim_rows = {}
    for w in a.windows:
        # The person threshold on every admitted meal, matching the real side.
        kept = {n: o[w]["covered"] for n, o in sim.items() if o[w]["meals"] >= a.min_meals}
        sim_rows[w] = dict(summarise(kept, min_meals=1),
                           meals_per_subject={n: len(v) for n, v in kept.items()})
    tdd = {n: o["units_per_day"] for n, o in sim.items()}
    share = {n: o["bolus_share"] for n, o in sim.items()}
    sim_rows["daily"] = dict(daily(tdd, share),
                             body_weight_kg=[pct([o["body_weight"] for o in sim.values()], q)
                                             for q in (10, 50, 90)])

    sides = [(f"{s}", real[s]) for s in real] + [(f"sim {a.controller}", sim_rows)]
    print(f"\n{'window':>7}{'side':>18}{'n':>5}{'meals':>7}{'rise/10g':>22}{'bolus/10g':>22}"
          f"{'by peak/10g':>22}{'added/10g':>22}{"trough to peak":>26}")
    for w in a.windows:
        for label, side in sides:
            r = side[w]
            f = lambda k: f"{r[k][0]:.2f} / {r[k][1]:.2f} / {r[k][2]:.2f}"
            print(f"{w:>7}{label:>18}{r['subjects']:>5}{r['meals']:>7}{f('rise_per_10g'):>22}"
                  f"{f('bolus_per_10g'):>22}{f('to_peak_per_10g'):>22}{f('added_per_10g'):>22}"
                  f"{f("ttp_min"):>26}")
    print(f"\n{'side':>18}{'n':>5}{'U/day p10/50/90':>26}{'bolus share':>26}")
    for label, side in sides:
        d = side["daily"]
        print(f"{label:>18}{d['subjects']:>5}"
              f"{f'{d['units_per_day'][0]:.1f} / {d['units_per_day'][1]:.1f} / {d['units_per_day'][2]:.1f}':>26}"
              f"{f'{d['bolus_share'][0]:.2f} / {d['bolus_share'][1]:.2f} / {d['bolus_share'][2]:.2f}':>26}")

    rec = {"provenance": provenance.stamp(), "subjects": list(subs), "days": a.days,
           "seed": seeds.BENCH, "controller": a.controller, "record": "announced",
           "windows": list(a.windows), "bolus_floor_u": a.bolus_floor, "min_meals": a.min_meals,
           "bolus_window_min": ms.BOLUS_WINDOW_MIN, "dropped": dropped,
           "adult_age": a.adult_age,
           "real": {s: {str(k): v for k, v in real[s].items()} for s in real},
           "simulated": {str(k): v for k, v in sim_rows.items()}}
    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
