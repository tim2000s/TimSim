"""Excursions above 180 mg/dL in the OpenAPS Data Commons, by TimSim's own definition.

excursion_recovery.py measured simulated excursions peaking at a median 194.6 mg/dL against 209.0 on
the DCLP3 closed-loop arm (calibration split), the only real reference so far. This repeats the real
side on the Commons, a cohort of open-source loop users, using `excursions()` and `summarise()` from
that script unchanged, and DCLP3 is recomputed here per person so both real cohorts carry an interval.

The trace is built as dclp3.traces builds it: per participant, readings in time order, a gap longer
than 8 minutes ends a segment, segments shorter than 288 readings are dropped, and a participant needs
a record spanning 7 days. Two steps are added because the Commons is not one sensor at one cadence.
Readings are thinned to one at least 270 seconds after the last kept, since some uploaders record
every minute and `excursions()` assumes five-minute steps. Values outside 39 to 401 mg/dL are dropped
(the sensors' LOW and HIGH codes bound that range, as looping-behaviours/scripts/commons_days.py
reads them). Glucose is the AAPS uploader's (commons.glucose) and the Nightscout entries
(commons.ns_glucose) merged, both in mg/dL.

Each reading carries the system its UTC day ran, from the Nightscout devicestatus counted by
load_commons_ns.py (the commonest system that day), or AAPS for the AAPS uploader's own glucose; a
change of system ends a segment, so no excursion spans two systems. Days with no algorithm record are
kept apart as "no loop record": they include people who were not looping and uploads that carried
only glucose, so they are not a closed-loop reference.

Intervals are 95 per cent from resampling people (1,000 draws), pooling the excursions of the people
drawn, which is how the point estimate pools them. Expected before running: Commons peaks within
about 10 mg/dL of DCLP3's, since both are closed-loop cohorts with similar time above 180; OpenAPS
and AAPS should run no lower than Loop, whose temporary-basal-only dosing in the older records is the
gentlest.

    ~/.venvs/boost-insilico/bin/python -I examples/2026-11-commons-excursions/commons_excursions.py
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from examples.excursion_recovery import excursions, summarise, STEP   # noqa: E402

DSN = "dbname=oref host=127.0.0.1 port=5432"
OUT = os.path.join(HERE, "commons_excursions.json")
MAX_GAP_S, MIN_SEG, MIN_DAYS, THIN_S = 8 * 60, 288, 7.0, 270
SEED = 20261110
WORKERS = 3


def thin(t):
    """Indices of readings kept, each at least THIN_S seconds after the last kept."""
    keep, last = [], -10 ** 12
    for i, x in enumerate(t):
        if x - last >= THIN_S:
            keep.append(i)
            last = x
    return np.array(keep, int)


def segments(t, g, sysv):
    """Contiguous stretches of one system, as dclp3.traces cuts them."""
    brk = np.where((np.diff(t) > MAX_GAP_S) | (sysv[1:] != sysv[:-1]))[0]
    out = []
    for lo, hi in zip(np.r_[0, brk + 1], np.r_[brk + 1, len(t)]):
        if hi - lo >= MIN_SEG:
            out.append((sysv[lo], g[lo:hi]))
    return out


def person(p):
    import psycopg2
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("""select ts_ms, value, 'AAPS' from commons.glucose where participant = %s
                   union all select ts_ms, value, null from commons.ns_glucose where participant = %s""", (p, p))
    rows = cur.fetchall()
    cur.execute("""select hour_ms / 86400000 as d, system, sum(n) from commons.ns_devicestatus_hourly
                   where participant = %s and system <> 'none' group by 1, 2""", (p,))
    day_sys = {}
    for d, s, n in cur.fetchall():
        if n > day_sys.get(d, ("", 0))[1]:
            day_sys[d] = (s, n)
    conn.close()
    if not rows:
        return None
    rows.sort(key=lambda r: r[0])
    t = np.array([r[0] for r in rows], np.int64) // 1000
    g = np.array([r[1] for r in rows], float)
    src = [r[2] for r in rows]
    ok = (g >= 39) & (g <= 401)
    t, g, src = t[ok], g[ok], [s for s, k in zip(src, ok) if k]
    if len(t) < MIN_SEG or (t[-1] - t[0]) / 86400.0 < MIN_DAYS:
        return None
    sysv = np.array([s or day_sys.get(int(x // 86400), ("no loop record",))[0] for x, s in zip(t, src)], object)
    keep = thin(t)
    t, g, sysv = t[keep], g[keep], sysv[keep]
    res = {}
    for s, seg in segments(t, g, sysv):
        r = res.setdefault(str(s), {"excursions": [], "days": 0.0, "n180": 0, "n": 0})
        r["excursions"] += excursions(seg)
        r["days"] += len(seg) * STEP / 1440.0
        r["n180"] += int((seg > 180).sum())
        r["n"] += len(seg)
    return res


def as_row(r):
    return {"excursions": r["excursions"], "days": r["days"], "tar180": 100.0 * r["n180"] / max(r["n"], 1),
            "insulin_per_day": float("nan")}


def boot(rows, rng, n=1000):
    """95% intervals for the pooled median peak, median duration and median fall rate, resampling people."""
    peaks = [np.array([e["peak"] for e in r["excursions"]]) for r in rows]
    durs = [np.array([e["duration_min"] for e in r["excursions"]]) for r in rows]
    falls = [np.array([e["fall_rate"] for e in r["excursions"]]) for r in rows]
    out = {"median_peak": [], "median_dur": [], "median_fall_rate": [], "per_day": []}
    days = np.array([r["days"] for r in rows])
    cnt = np.array([len(r["excursions"]) for r in rows])
    for _ in range(n):
        i = rng.integers(0, len(rows), len(rows))
        out["median_peak"].append(np.median(np.concatenate([peaks[j] for j in i])))
        out["median_dur"].append(np.median(np.concatenate([durs[j] for j in i])))
        f = np.concatenate([falls[j] for j in i])
        out["median_fall_rate"].append(np.nanmedian(f))
        out["per_day"].append(cnt[i].sum() / days[i].sum())
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in out.items()}


def dclp3_rows():
    """real_reference() in excursion_recovery.py, kept per participant so it can be resampled."""
    from timsim.validation import dclp3
    cal = set(dclp3.split()["calibration"])
    rows = []
    for pid, segs in dclp3.traces(arm=dclp3.CLOSED_LOOP).items():
        if pid not in cal:
            continue
        ex, days = [], 0.0
        for s in segs:
            g = np.asarray(s, float)[1]
            g = g[np.isfinite(g)]
            if len(g) < 288:
                continue
            ex += excursions(g)
            days += len(g) * STEP / 1440.0
        if ex:
            rows.append({"excursions": ex, "days": days, "tar180": float("nan"), "insulin_per_day": float("nan")})
    return rows


def selfcheck():
    t = np.arange(0, 600 * 60, 60)                    # one-minute readings for ten hours
    t2 = t[thin(t)]
    assert np.all(np.diff(t2) == 300), np.diff(t2)[:5]
    sysv = np.array(["A"] * 300 + ["B"] * 300, object)
    segs = segments(np.arange(600) * 300, np.zeros(600), sysv)
    assert [s for s, _ in segs] == ["A", "B"] and all(len(x) == 300 for _, x in segs)


def main():
    selfcheck()
    import psycopg2
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("select participant from commons.glucose union select participant from commons.ns_glucose")
    parts = sorted(r[0] for r in cur.fetchall())
    conn.close()
    with ProcessPoolExecutor(WORKERS) as ex:
        per = [r for r in ex.map(person, parts) if r]
    rng = np.random.default_rng(SEED)
    groups = {}
    for r in per:
        for s, v in r.items():
            groups.setdefault(s, []).append(v)
    looped = [as_row({"excursions": sum((v["excursions"] for s, v in r.items() if s != "no loop record"), []),
                      "days": sum(v["days"] for s, v in r.items() if s != "no loop record"),
                      "n180": sum(v["n180"] for s, v in r.items() if s != "no loop record"),
                      "n": sum(v["n"] for s, v in r.items() if s != "no loop record")}) for r in per]
    looped = [r for r in looped if r["excursions"]]
    table = []

    def add(label, rows):
        s = summarise(rows, label)
        if s is None:
            return
        s["subjects"] = len(rows)
        s["ci"] = boot(rows, rng)
        s["per_person_median_peak"] = float(np.median([np.median([e["peak"] for e in r["excursions"]]) for r in rows]))
        table.append(s)

    add("Commons, days with a loop record", looped)
    for s in sorted(groups, key=lambda k: -len(groups[k])):
        add(f"Commons, {s}", [as_row(v) for v in groups[s] if v["excursions"]])
    add("DCLP3 (recomputed)", dclp3_rows())
    sim = json.load(open(os.path.join(REPO, "docs", "measurements", "excursion_recovery.json")))["summary"]
    ref = {s["arm"]: s for s in sim}
    print(f"{len(parts)} participants with glucose; {len(per)} with a usable trace\n")
    print(f"{'set':42}{'people':>7}{'n':>8}{'/day':>6}{'peak med [95% CI]':>24}{'per-person':>11}"
          f"{'dur med [CI]':>18}{'fall/h [CI]':>20}{'TAR180':>8}")
    for s in table + [dict(ref["closed"], ci=None, per_person_median_peak=None)]:
        ci = s.get("ci")
        f = lambda k, d=0: (f"{s[k]:.{d}f} [{ci[k][0]:.{d}f}, {ci[k][1]:.{d}f}]" if ci else f"{s[k]:.{d}f}")
        ppm = f"{s['per_person_median_peak']:.1f}" if s.get("per_person_median_peak") else "-"
        print(f"{s['arm'][:42]:42}{str(s.get('subjects')):>7}{s['n_excursions']:>8}{s['per_day']:>6.2f}"
              f"{f('median_peak', 1):>24}{ppm:>11}{f('median_dur'):>18}{f('median_fall_rate', 1):>20}"
              f"{(s['tar180'] if s['tar180'] is not None else float('nan')):>8.1f}")
    print(f"\nexcursion_recovery.json: DCLP3 median peak {ref['DCLP3']['median_peak']:.1f}, simulated closed "
          f"{ref['closed']['median_peak']:.1f}")
    from timsim import provenance
    json.dump({"provenance": provenance.stamp(), "threshold": 180.0, "thin_s": THIN_S, "seed": SEED, "summary": table}, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
