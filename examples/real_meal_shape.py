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
from timsim.analysis import meal_shape as ms

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
  select c.subject_id, c.ts_local, c.carbs_g
  from studies.carbs c join subs using (subject_id)
  where c.carbs_g between %(g_lo)s and %(g_hi)s
    and not exists (select 1 from studies.carbs c2
                    where c2.subject_id = c.subject_id and c2.ts_local <> c.ts_local
                      and c2.ts_local >  c.ts_local - %(before)s * interval '1 min'
                      and c2.ts_local <  c.ts_local + %(win)s * interval '1 min')),
pk as (
  select m.*, p.ts_local pk_ts, p.cgm_mgdl pk_cgm, p.n
  from meals m cross join lateral (
    select ts_local, cgm_mgdl, count(*) over () n from studies.cgm g
    where g.subject_id = m.subject_id and g.ts_local >= m.ts_local
      and g.ts_local <= m.ts_local + %(win)s * interval '1 min'
    order by cgm_mgdl desc, ts_local asc limit 1) p),
tp as (
  select pk.subject_id, pk.ts_local, pk.carbs_g,
         extract(epoch from (pk.pk_ts - t.ts_local)) / 60 ttp,
         pk.pk_cgm - t.cgm_mgdl rise,
         -- Insulin delivered around the carbohydrate event, recorded per meal rather than used
         -- to admit or reject it, so the threshold can be moved without reparsing.
         -- The fall. Mean elevation above the trough from the trough to the end of the window,
         -- and the first return to the trough after the peak. Mean rather than area because a
         -- meal is admitted on 80 per cent coverage and an area would be short by the gaps.
         (select avg(greatest(g2.cgm_mgdl - t.cgm_mgdl, 0)) from studies.cgm g2
           where g2.subject_id = pk.subject_id and g2.ts_local >= t.ts_local
             and g2.ts_local <= pk.ts_local + %(win)s * interval '1 min') mean_elev,
         (select extract(epoch from (min(g3.ts_local) - pk.pk_ts)) / 60 from studies.cgm g3
           where g3.subject_id = pk.subject_id and g3.ts_local > pk.pk_ts
             and g3.ts_local <= pk.ts_local + %(win)s * interval '1 min'
             and g3.cgm_mgdl <= t.cgm_mgdl) peak_to_return,
         coalesce((select sum(b.bolus_u) from studies.bolus b
                   where b.subject_id = pk.subject_id
                     and b.ts_local >= pk.ts_local - %(bwin)s * interval '1 min'
                     and b.ts_local <= pk.ts_local + %(bwin)s * interval '1 min'), 0) bolus_u
  from pk cross join lateral (
    select ts_local, cgm_mgdl from studies.cgm g
    where g.subject_id = pk.subject_id and g.ts_local >= pk.ts_local and g.ts_local <= pk.pk_ts
    order by cgm_mgdl asc, ts_local asc limit 1) t
  where pk.n >= %(min_readings)s)
select subject_id, ttp, extract(hour from ts_local) meal_hour, rise, carbs_g, bolus_u, mean_elev, peak_to_return from tp
"""


def pct(v, q):
    return float(np.percentile(np.asarray(v, float), q)) if len(v) else float("nan")


def one(cur, study, win, a, a_subsample=40, a_band=(40.0, 55.0), a_band_min=8,
        a_bolus_floor=1.0):
    cur.execute(SQL, {"study": study, "g_lo": a.grams[0], "g_hi": a.grams[1], "win": win,
                      "before": a.clear_before, "bwin": ms.BOLUS_WINDOW_MIN,
                      "min_readings": int((win / 5) * a.coverage)})
    rows = cur.fetchall()
    by_subject, by_rise, by_band, hours = {}, {}, {}, []
    by_full, by_ptr = {}, {}
    covered, uncovered = {}, {}
    for sid, ttp, hour, rise, grams, bolus, mean_elev, ptr in rows:
        if rise and float(rise) > 0 and mean_elev is not None:
            by_full.setdefault(sid, []).append(float(mean_elev) / float(rise))
        if ptr is not None:
            by_ptr.setdefault(sid, []).append(float(ptr))
        # The stratum. A correction can fall in the window without covering the meal, so the
        # floor is on the amount rather than on the presence of any delivery, and the same floor
        # runs on both sides.
        (covered if float(bolus) >= a_bolus_floor else uncovered).setdefault(
            sid, []).append(float(rise) / (float(grams) / 10.0))
        by_subject.setdefault(sid, []).append(float(ttp))
        # Rise per 10 g as logged. Logged grams under-state true intake, which the real rescue
        # and meal producers already record, so this is an upper bound on the rise per true 10 g.
        by_rise.setdefault(sid, []).append(float(rise) / (float(grams) / 10.0))
        # The same rise restricted to one narrow size band on both sides, because rise per gram
        # is not constant in size and the two sides do not eat the same distribution inside the
        # 30 to 90 g admission band.
        if a_band[0] <= float(grams) <= a_band[1]:
            by_band.setdefault(sid, []).append(float(rise) / (float(grams) / 10.0))
        hours.append(int(hour))
    kept = {s: v for s, v in by_subject.items() if len(v) >= a.min_meals}
    pooled = [x for v in kept.values() for x in v]
    med = [float(np.median(v)) for v in kept.values()]
    iqr = [float(np.percentile(v, 75) - np.percentile(v, 25)) for v in kept.values()]
    # The rise the excursion work points at. Simulated excursions above 180 mg/dL last 40 minutes
    # against the trial's 60 while falling at the same rate, so they are shorter because they
    # peak lower. Whether a meal rise is smaller is the same question with a per-person reference.
    bmed = [float(np.median(by_band[s_])) for s_ in kept
            if len(by_band.get(s_, ())) >= a_band_min]
    strata = {}
    for label, d in (("covered", covered), ("uncovered", uncovered)):
        med_ = [float(np.median(v)) for s_ in kept for v in (d.get(s_, ()),)
                if len(v) >= a_band_min]
        strata[label] = {"subjects": len(med_),
                         "meals": int(sum(len(d.get(s_, ())) for s_ in kept)),
                         "rise_per_10g": [pct(med_, 10), pct(med_, 50), pct(med_, 90)]}
    fmed = [float(np.median(by_full[s_])) for s_ in kept if len(by_full.get(s_, ())) >= a_band_min]
    pmed = [float(np.median(by_ptr[s_])) for s_ in kept if len(by_ptr.get(s_, ())) >= a_band_min]
    ret = [len(by_ptr.get(s_, ())) / len(by_subject[s_]) for s_ in kept]
    rmed = [float(np.median(by_rise[s_])) for s_ in kept]
    riqr = [float(np.percentile(by_rise[s_], 75) - np.percentile(by_rise[s_], 25))
            for s_ in kept]
    hours = np.asarray(hours)
    # A real participant contributes hundreds of meals and a simulated one a few dozen, and an
    # interquartile range taken over more meals is not the same estimator as one taken over
    # fewer. This recomputes the within-person spread on a random `subsample` meals per person,
    # matched to what the simulated side supports, so the comparison can be shown not to be
    # measuring the length of the record.
    rng = np.random.default_rng(20260830)
    sub_iqr = []
    for v in kept.values():
        w_ = np.asarray(v, float)
        if w_.size > a_subsample:
            w_ = rng.choice(w_, size=a_subsample, replace=False)
        sub_iqr.append(float(np.percentile(w_, 75) - np.percentile(w_, 25)))
    return {"study": study, "window_min": win, "subjects": len(kept), "meals": len(pooled),
            "subsample_meals": a_subsample,
            "within_person_iqr_subsampled": [pct(sub_iqr, 10), pct(sub_iqr, 50),
                                             pct(sub_iqr, 90)],
            "pooled_quartiles": [pct(pooled, 25), pct(pooled, 50), pct(pooled, 75)],
            "between_person_median": [pct(med, 10), pct(med, 50), pct(med, 90)],
            "within_person_iqr": [pct(iqr, 10), pct(iqr, 50), pct(iqr, 90)],
            "rise_per_10g_between_person": [pct(rmed, 10), pct(rmed, 50), pct(rmed, 90)],
            "rise_per_10g_within_person_iqr": [pct(riqr, 10), pct(riqr, 50), pct(riqr, 90)],
            "rise_per_10g_size_matched": [pct(bmed, 10), pct(bmed, 50), pct(bmed, 90)],
            "size_matched_band": list(a_band), "size_matched_subjects": len(bmed),
            "bolus_floor_u": a_bolus_floor, "strata": strata,
            "fullness": [pct(fmed, 10), pct(fmed, 50), pct(fmed, 90)],
            "peak_to_return_min": [pct(pmed, 10), pct(pmed, 50), pct(pmed, 90)],
            "returned_share": [pct(ret, 10), pct(ret, 50), pct(ret, 90)],
            "grams_median": float(np.median([g for v in by_band.values() for g in v]))
                            if by_band else float("nan"),
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
    ap.add_argument("--bolus-floor", type=float, default=1.0,
                    help="units within 30 min of the entry for a meal to count as covered")
    ap.add_argument("--band", nargs=2, type=float, default=[40.0, 55.0],
                    help="grams band for the size-matched rise")
    ap.add_argument("--band-min", type=int, default=8,
                    help="meals a person needs inside the band to contribute to it")
    ap.add_argument("--subsample", type=int, default=40,
                    help="meals per person for the matched-length control")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    rec = {"provenance": provenance.stamp(), "source": "TimescaleDB studies schema",
           "grams": list(a.grams), "clear_before_min": a.clear_before,
           "min_meals_per_subject": a.min_meals, "coverage": a.coverage,
           "subsample_meals": a.subsample, "rows": []}

    with psycopg2.connect(a.dsn) as conn, conn.cursor() as cur:
        for study in a.studies:
            print(f"\n{study}")
            print(f"{'window':>7}{'subj':>7}{'meals':>8}{'pooled q1':>11}{'median':>8}"
                  f"{'q3':>7}{'per-person median p10/50/90':>30}"
                  f"{'within-person IQR p10/50/90':>30}"
                  f"{'same, at 40 meals each':>26}"
                  f"{'rise per 10 g p10/50/90':>26}"
                  f"{'same, 40-55 g only':>22}"
                  f"{'covered rise':>20}{'uncovered rise':>20}"
                  f"{'fullness':>20}{'peak to return':>20}{'ret':>6}")
            for win in a.windows:
                r = one(cur, study, win, a, a.subsample, tuple(a.band), a.band_min,
                        a.bolus_floor)
                rec["rows"].append(r)
                q = r["pooled_quartiles"]
                bp, wp = r["between_person_median"], r["within_person_iqr"]
                sp = r["within_person_iqr_subsampled"]
                rp = r["rise_per_10g_between_person"]
                bd = r["rise_per_10g_size_matched"]
                cv = r["strata"]["covered"]["rise_per_10g"]
                uc = r["strata"]["uncovered"]["rise_per_10g"]
                fl, pr = r["fullness"], r["peak_to_return_min"]
                print(f"{win:>7}{r['subjects']:>7}{r['meals']:>8}{q[0]:>11.0f}{q[1]:>8.0f}"
                      f"{q[2]:>7.0f}"
                      f"{f'{bp[0]:.0f} / {bp[1]:.0f} / {bp[2]:.0f}':>30}"
                      f"{f'{wp[0]:.0f} / {wp[1]:.0f} / {wp[2]:.0f}':>30}"
                      f"{f'{sp[0]:.0f} / {sp[1]:.0f} / {sp[2]:.0f}':>26}"
                      f"{f'{rp[0]:.1f} / {rp[1]:.1f} / {rp[2]:.1f}':>26}"
                      f"{f'{bd[0]:.1f} / {bd[1]:.1f} / {bd[2]:.1f}':>22}"
                      f"{f'{cv[0]:.1f} / {cv[1]:.1f} / {cv[2]:.1f}':>20}"
                      f"{f'{uc[0]:.1f} / {uc[1]:.1f} / {uc[2]:.1f}':>20}"
                      f"{f'{fl[0]:.2f} / {fl[1]:.2f} / {fl[2]:.2f}':>20}"
                      f"{f'{pr[0]:.0f} / {pr[1]:.0f} / {pr[2]:.0f}':>20}"
                      f"{r['returned_share'][1]:>6.2f}")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
