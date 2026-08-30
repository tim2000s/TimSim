"""Trough to peak for real meals, per person, from the studies schema of the local TimescaleDB.

The gate deciding the liver delay compares a simulated meal against "a real 112 min, quartiles 70
to 165, 5,189 meals". That figure exists as a constant in `meal_with_bolus.py` and as prose in
`patient/varying.py`, and nothing in this repository recomputes it. This is its producer, written
against a much wider source: 1.6 million logged carbohydrate entries across 1,037 people in two
studies, with CGM on a 5 minute cadence, which is the cadence the run harness steps on.

Three things the measurement has to carry, all of which the stored constant does not.

The value is set by the analysis window. Sweeping it moves the median from 65 min at 180 min to
135 at 720, so a number quoted without its window cannot be compared with anything. The simulated
side uses 720.

A long window does not select a meal, it selects the evening. Isolation is what admits a meal, and
at 720 min the only meals with nothing following them are dinners: 73 per cent fall between 16:00
and 21:00 against a third at 180 min. The simulated meal is eaten at midday, and this package
already records an hour-of-day effect on insulin sensitivity from Hinshaw et al. (2013).

Within-person and between-person variation are different quantities and the simulator has only
one of them. Each subject here contributes hundreds of meals, so both are measurable, and they are
reported separately rather than pooled into one spread.

    python examples/real_meal_shape.py
"""
import argparse
import json
import os
import sys

import numpy as np
import psycopg2

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance

OUT = os.path.join(MEASUREMENTS, "real_meal_shape.json")
DSN = "dbname=oref"

# Loop is a closed loop and ReplaceBG is a sensor-augmented pump, so the pair brackets the
# controller. Insulin dominates the shape of a covered meal, and whether that confounds the
# comparison is a question the two studies answer rather than one this has to assume.
STUDIES = ("Loop", "ReplaceBG")
GRAMS = (30.0, 90.0)          # the band the simulated meal of 60 g sits inside
WINDOWS = (180, 240, 300, 360, 480, 720)
CLEAR_BEFORE_MIN = 120
MIN_MEALS_PER_SUBJECT = 20
COVERAGE = 0.8                # fraction of the window's 5 min slots that must carry a reading

# Trough to peak, defined identically to the simulated side except that the peak is located on the
# absolute trace. `meal_with_bolus.one` locates it by `argmax` of the difference against a
# counterfactual, which no real trace has, so the two sides were not measuring the same thing.
SQL = """
with subs as (select subject_id from studies.subject where study_name = %(study)s),
meals as (
  select c.subject_id, c.ts_local
  from studies.carbs c join subs using (subject_id)
  where c.carbs_g between %(g_lo)s and %(g_hi)s
    and not exists (select 1 from studies.carbs c2
                    where c2.subject_id = c.subject_id and c2.ts_local <> c.ts_local
                      and c2.ts_local >  c.ts_local - %(before)s * interval '1 min'
                      and c2.ts_local <  c.ts_local + %(win)s * interval '1 min')),
pk as (
  select m.*, p.ts_local pk_ts, p.n
  from meals m cross join lateral (
    select ts_local, count(*) over () n from studies.cgm g
    where g.subject_id = m.subject_id and g.ts_local >= m.ts_local
      and g.ts_local <= m.ts_local + %(win)s * interval '1 min'
    order by cgm_mgdl desc, ts_local asc limit 1) p),
tp as (
  select pk.subject_id, pk.ts_local,
         extract(epoch from (pk.pk_ts - t.ts_local)) / 60 ttp
  from pk cross join lateral (
    select ts_local from studies.cgm g
    where g.subject_id = pk.subject_id and g.ts_local >= pk.ts_local and g.ts_local <= pk.pk_ts
    order by cgm_mgdl asc, ts_local asc limit 1) t
  where pk.n >= %(min_readings)s)
select subject_id, ttp, extract(hour from ts_local) meal_hour from tp
"""


def pct(v, q):
    return float(np.percentile(np.asarray(v, float), q)) if len(v) else float("nan")


def one(cur, study, win, a):
    cur.execute(SQL, {"study": study, "g_lo": a.grams[0], "g_hi": a.grams[1], "win": win,
                      "before": a.clear_before,
                      "min_readings": int((win / 5) * a.coverage)})
    rows = cur.fetchall()
    by_subject = {}
    hours = []
    for sid, ttp, hour in rows:
        by_subject.setdefault(sid, []).append(float(ttp))
        hours.append(int(hour))
    kept = {s: v for s, v in by_subject.items() if len(v) >= a.min_meals}
    pooled = [x for v in kept.values() for x in v]
    med = [float(np.median(v)) for v in kept.values()]
    iqr = [float(np.percentile(v, 75) - np.percentile(v, 25)) for v in kept.values()]
    hours = np.asarray(hours)
    return {"study": study, "window_min": win, "subjects": len(kept), "meals": len(pooled),
            "pooled_quartiles": [pct(pooled, 25), pct(pooled, 50), pct(pooled, 75)],
            "between_person_median": [pct(med, 10), pct(med, 50), pct(med, 90)],
            "within_person_iqr": [pct(iqr, 10), pct(iqr, 50), pct(iqr, 90)],
            "hour_share": {"05-10": float(np.mean((hours >= 5) & (hours <= 10))),
                           "11-15": float(np.mean((hours >= 11) & (hours <= 15))),
                           "16-21": float(np.mean((hours >= 16) & (hours <= 21))),
                           "22-04": float(np.mean((hours >= 22) | (hours < 5)))}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dsn", default=DSN)
    ap.add_argument("--studies", nargs="+", default=list(STUDIES))
    ap.add_argument("--windows", nargs="+", type=int, default=list(WINDOWS))
    ap.add_argument("--grams", nargs=2, type=float, default=list(GRAMS))
    ap.add_argument("--clear-before", type=int, default=CLEAR_BEFORE_MIN)
    ap.add_argument("--min-meals", type=int, default=MIN_MEALS_PER_SUBJECT)
    ap.add_argument("--coverage", type=float, default=COVERAGE)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    rec = {"provenance": provenance.stamp(), "source": "TimescaleDB studies schema",
           "grams": list(a.grams), "clear_before_min": a.clear_before,
           "min_meals_per_subject": a.min_meals, "coverage": a.coverage, "rows": []}

    with psycopg2.connect(a.dsn) as conn, conn.cursor() as cur:
        for study in a.studies:
            print(f"\n{study}")
            print(f"{'window':>7}{'subj':>7}{'meals':>8}{'pooled q1':>11}{'median':>8}"
                  f"{'q3':>7}{'per-person median p10/50/90':>30}"
                  f"{'within-person IQR p10/50/90':>30}{'evening share':>15}")
            for win in a.windows:
                r = one(cur, study, win, a)
                rec["rows"].append(r)
                q = r["pooled_quartiles"]
                bp, wp = r["between_person_median"], r["within_person_iqr"]
                print(f"{win:>7}{r['subjects']:>7}{r['meals']:>8}{q[0]:>11.0f}{q[1]:>8.0f}"
                      f"{q[2]:>7.0f}"
                      f"{f'{bp[0]:.0f} / {bp[1]:.0f} / {bp[2]:.0f}':>30}"
                      f"{f'{wp[0]:.0f} / {wp[1]:.0f} / {wp[2]:.0f}':>30}"
                      f"{r['hour_share']['16-21']:>15.2f}")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
