"""The meal shape definition, and the agreement between its two implementations.

`timsim/analysis/meal_shape.py` measures the simulated side in Python and
`examples/real_meal_shape.py` measures the real side in SQL, because the real side runs over 132
million CGM readings. One definition with two implementations is the arrangement behind most of
`docs/ISSUES.md`, so `test_sql_and_python_agree_on_real_subjects` pulls real subjects through both
and requires the same meals and the same durations. Without it the comparison is two numbers that
happen to share a name.

The synthetic tests are written to fail against the implementations this replaced: a peak located
on the difference against a counterfactual, an isolation test that admits a following meal, and a
trough searched over the whole window rather than up to the peak.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timsim.analysis import meal_shape as ms

DSN = "dbname=oref"
STEP = 5.0


def trace(points, span=300.0, step=STEP):
    """A glucose trace from (minute, value) knots, linearly interpolated onto the sensor grid."""
    t = np.arange(0.0, span + step, step)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return t, np.interp(t, xs, ys)


def test_trough_and_peak_are_the_rise_between_them():
    t, g = trace([(0, 120), (20, 80), (140, 200), (300, 150)])
    out, rej = ms.shapes([(0.0, 60.0)], [0.0], t, g, window_min=240)
    assert len(out) == 1 and rej == {"size": 0, "isolation": 0, "coverage": 0}
    assert out[0]["trough_to_peak_min"] == 120.0
    assert out[0]["trough_mgdl"] == 80.0 and out[0]["peak_mgdl"] == 200.0


def test_trough_is_not_searched_past_the_peak():
    """A deep low after the peak must not become the trough, which would invert the interval."""
    t, g = trace([(0, 120), (20, 80), (140, 200), (240, 45), (300, 90)])
    out, _ = ms.shapes([(0.0, 60.0)], [0.0], t, g, window_min=240)
    assert out[0]["trough_to_peak_min"] == 120.0, "trough was taken from after the peak"


def test_a_following_meal_breaks_isolation():
    t, g = trace([(0, 120), (20, 80), (140, 200), (300, 150)])
    out, rej = ms.shapes([(0.0, 60.0)], [0.0, 200.0], t, g, window_min=240)
    assert out == [] and rej["isolation"] == 1
    # The same meal is admitted once the window no longer reaches the second one.
    out, _ = ms.shapes([(0.0, 60.0)], [0.0, 200.0], t, g, window_min=180)
    assert len(out) == 1


def test_a_preceding_meal_inside_the_clearance_breaks_isolation():
    t, g = trace([(0, 120), (20, 80), (140, 200), (300, 150)])
    out, rej = ms.shapes([(0.0, 60.0)], [-60.0, 0.0], t, g, window_min=240)
    assert out == [] and rej["isolation"] == 1
    out, _ = ms.shapes([(0.0, 60.0)], [-180.0, 0.0], t, g, window_min=240)
    assert len(out) == 1, "a meal outside the 120 min clearance should not break isolation"


def test_events_sharing_a_minute_are_one_event():
    """Two entries logged at the same instant are a split entry, not two meals, as the SQL reads."""
    t, g = trace([(0, 120), (20, 80), (140, 200), (300, 150)])
    out, _ = ms.shapes([(0.0, 60.0)], [0.0, 0.0], t, g, window_min=240)
    assert len(out) == 1


def test_size_band_and_coverage_are_recorded_not_silent():
    t, g = trace([(0, 120), (20, 80), (140, 200), (300, 150)])
    _, rej = ms.shapes([(0.0, 10.0)], [0.0], t, g, window_min=240)
    assert rej["size"] == 1
    short_t, short_g = t[:10], g[:10]
    _, rej = ms.shapes([(0.0, 60.0)], [0.0], short_t, short_g, window_min=240)
    assert rej["coverage"] == 1


def test_peak_is_the_absolute_maximum_not_a_difference_from_a_counterfactual():
    """The landmark the real side can see.

    A trace whose absolute maximum and whose maximum excursion above a flat counterfactual sit at
    different times separates the two definitions. The counterfactual version reads 60 min here.
    """
    t, g = trace([(0, 100), (30, 70), (90, 190), (150, 185), (240, 120)])
    out, _ = ms.shapes([(0.0, 60.0)], [0.0], t, g, window_min=240)
    assert out[0]["trough_to_peak_min"] == 60.0
    assert out[0]["peak_mgdl"] == pytest.approx(190.0)


def test_per_person_keeps_the_two_components_apart():
    assert ms.per_person([10.0] * 5, min_meals=20) is None
    p = ms.per_person(list(range(20)), min_meals=20)
    assert p["meals"] == 20 and p["median"] == pytest.approx(9.5)
    s = ms.summarise([{"median": 80.0, "iqr": 90.0, "meals": 30},
                      {"median": 100.0, "iqr": 50.0, "meals": 40}])
    assert s["subjects"] == 2 and s["meals"] == 70
    assert s["between_person_median"][1] == pytest.approx(90.0)
    assert s["within_person_iqr"][1] == pytest.approx(70.0)


def test_insulin_by_the_peak_runs_from_the_bolus_window_to_the_peak():
    """Every delivery from 30 min before the entry to the peak minute, and nothing after it.

    Written to fail against a sum over the whole window, which would count the basal delivered
    while the glucose was falling, and against a sum from the entry alone, which would miss a
    pre-bolus.
    """
    t, g = trace([(0, 120), (20, 80), (140, 200), (300, 150)])
    ins_min = np.arange(-60.0, 305.0, 5.0)
    ins_u = np.full(ins_min.size, 0.05)                 # 0.6 U/h of basal on the same clock
    out, _ = ms.shapes([(0.0, 60.0)], [0.0], t, g, window_min=240,
                       bolus_minutes=[-15.0, 200.0], bolus_units=[3.0, 1.0],
                       insulin_minutes=ins_min, insulin_units=ins_u)
    r = out[0]
    assert r["bolus_u"] == 3.0
    assert r["bolus_to_peak_u"] == 3.0, "the bolus after the peak was counted"
    # Steps at -30, -25, ..., 140 inclusive: 35 of them at 0.05 U.
    assert r["insulin_to_peak_u"] == pytest.approx(35 * 0.05)


def _connect():
    psycopg2 = pytest.importorskip("psycopg2")
    try:
        return psycopg2.connect(DSN)
    except Exception as exc:                                   # pragma: no cover
        pytest.skip(f"studies database not reachable: {exc}")


@pytest.mark.parametrize("window", [180, 300])
def test_sql_and_python_agree_on_real_subjects(window):
    """The keystone. Same subjects, same window, both implementations, meal for meal.

    Ten Loop participants is a few thousand meals, which is enough for a disagreement in tie
    breaking or in the boundary of the isolation test to show up.
    """
    from examples.real_meal_shape import SQL, params

    conn = _connect()
    with conn, conn.cursor() as cur:
        cur.execute("select subject_id from studies.subject where study_name='Loop' "
                    "order by subject_id limit 10")
        subs = [r[0] for r in cur.fetchall()]

        cur.execute(SQL, params("Loop", window, min_age=0.0))
        # Subject and duration are the first two columns. Taken by position rather than by
        # unpacking the row, because the query grows columns as the measurement grows and a test
        # that breaks on that is a test that has to be edited for no reason.
        # Insulin by the peak is the last two columns, bolus and basal. A null basal is a meal
        # inside a gap in the rate record, and both sides have to agree on which meals those
        # are.
        sql_rows = [(row[0], float(row[1]),
                     float("nan") if row[9] is None else float(row[8]) + float(row[9]))
                    for row in cur.fetchall() if row[0] in set(subs)]

        python_rows = []
        for sid in subs:
            cur.execute("select ts_local, carbs_g from studies.carbs where subject_id=%s "
                        "order by ts_local", (sid,))
            carb = cur.fetchall()
            cur.execute("select ts_local, cgm_mgdl from studies.cgm where subject_id=%s "
                        "order by ts_local", (sid,))
            cgm = cur.fetchall()
            if not carb or not cgm:
                continue
            origin = min(carb[0][0], cgm[0][0])
            to_min = lambda ts: (ts - origin).total_seconds() / 60.0
            minutes = np.array([to_min(ts) for ts, _ in cgm])
            values = np.array([float(v) for _, v in cgm])
            carb_min = [to_min(ts) for ts, _ in carb]
            index = [(to_min(ts), float(g)) for ts, g in carb]
            cur.execute("select ts_local, bolus_u from studies.bolus where subject_id=%s "
                        "order by ts_local", (sid,))
            bol = cur.fetchall()
            cur.execute("select ts_local, rate_u_hr from studies.basal where subject_id=%s "
                        "order by ts_local", (sid,))
            bas = cur.fetchall()
            # The basal integrated in Python from the same rate record, each rate held until the
            # next row, over the interval `shapes` reports. A per-minute discretisation was
            # tried first and disagreed by 0.8 U on a Loop record that switches between 0 and
            # 25 U/h every five minutes, so the integral is exact here and the tolerance below
            # is floating point. The same gap rule as the SQL: no rate row in the day before
            # the interval starts, no basal.
            bol_min = np.array([to_min(ts) for ts, _ in bol])
            bol_u = np.array([float(u) for _, u in bol])
            rate_min = np.array([to_min(ts) for ts, _ in bas])
            rate = np.array([float(x or 0.0) for _, x in bas])

            def basal_between(a, b):
                lo = np.searchsorted(rate_min, a, side="right") - 1
                hi = np.searchsorted(rate_min, b, side="right")
                total = 0.0
                for k in range(max(lo, 0), hi):
                    t0 = max(rate_min[k], a)
                    t1 = min(rate_min[k + 1] if k + 1 < rate_min.size else b, b)
                    total += rate[k] * max(t1 - t0, 0.0) / 60.0
                return total

            recs, _ = ms.shapes(index, carb_min, minutes, values, window_min=window,
                                bolus_minutes=bol_min, bolus_units=bol_u)
            for r in recs:
                a, b = r["minute"] - ms.BOLUS_WINDOW_MIN, r["peak_minute"]
                known = np.any((rate_min >= a - 1440.0) & (rate_min <= a))
                u = r["bolus_to_peak_u"] + basal_between(a, b) if known else float("nan")
                python_rows.append((sid, r["trough_to_peak_min"], u))

    assert python_rows, "no meals admitted, so the comparison proves nothing"
    assert len(python_rows) == len(sql_rows), (
        f"python admitted {len(python_rows)} meals and sql {len(sql_rows)} at a {window} min "
        "window, so the two are not selecting the same meals")
    # Compared as multisets of (subject, duration) rather than meal by meal, because the SQL
    # returns the duration and the hour and not the index minute. Durations are rounded to a
    # thousandth of a minute: the two sides derive minutes from timestamps by different
    # arithmetic and disagree in the twelfth significant figure, four orders of magnitude below
    # the 5 minute sampling step, so an exact comparison would fail on the floating point alone.
    rnd = lambda rows: sorted((s, round(v, 3)) for s, v, _ in rows)
    assert rnd(python_rows) == rnd(sql_rows), (
        "the same meals gave different durations in the two implementations")
    # A nan sorts inconsistently, so the gap meals are ordered ahead of the rest explicitly.
    order = lambda rows: sorted((s, round(v, 3), -1.0 if np.isnan(u) else u) for s, v, u in rows)
    pairs = list(zip(order(python_rows), order(sql_rows)))
    gaps = [(p[2] < 0, q[2] < 0) for p, q in pairs]
    assert sum(a for a, _ in gaps) == sum(b for _, b in gaps), (
        f"python puts {sum(a for a, _ in gaps)} meals in a rate gap and sql "
        f"{sum(b for _, b in gaps)}")
    assert all(a == b for a, b in gaps), "the two sides disagree on which meals lack a basal"
    assert any(a for a, _ in gaps), "no meal fell in a rate gap, so that branch is untested"
    worst = max(abs(p[2] - q[2]) for p, q in pairs if p[2] >= 0)
    assert worst < 0.01, (
        f"insulin by the peak differs by up to {worst:.2f} U between the implementations")
