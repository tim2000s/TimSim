"""Overnight sensitivity against each side's own settings, and what autosens sees at night.

`examples/post_cob_isf.py` (4 October 2026) found glucose falling 4.5 mg/dL per unit of acting
insulin in fasting overnight hours on the simulated panel against 22.7 across 115 Trio and oref0
users, and recorded the gap without explaining it. Two things were noticed afterwards that make
the absolute figures unreadable as they stand.

The first is scale. The real users' profile correction factors have a median of 55 mg/dL per unit
(34 to 118, 10th to 90th percentile), and the real script also reports the effective figure as a
ratio to each user's profile, with a median of 0.43 (0.11 to 0.79). The titrated adults run
correction factors near 17 to 25, so the simulated 4.5 is about a quarter of profile, which may
sit inside the real band. The like-for-like quantity is the ratio, which the simulated side has
not computed.

The second is a contradiction. Glucose falling at a quarter of what the profile predicts means
it is rising against insulin relative to the settings, which is a positive deviation in oref's
terms and ought to push autosens towards resistant. `examples/sim_autosens.py` found it reading
resistant on 0.43 per cent of cycles against 42 for Commons users. Both can hold if the night
windows are an unrepresentative sample. A window counts only when the integrated insulin activity
is positive and predicts a drop of at least 8 mg/dL. Activity is net of the scheduled basal, so
overnight it is positive mainly when the loop has been delivering above schedule, which it does
in response to a rise. Autosens instead reads every non-meal cycle.

Method. Both sides go through `night_rows` below, so the definitions are the same code. A night
window starts at 23:00 to 04:59 with sensor glucose 70 to 300 mg/dL, carbohydrate on board zero
for the 150 minutes before and the 60 after (the loop's own dynamic estimate on both sides), and
ends 60 minutes later. Over each window:

    D, hourly deviation   (glucose change) + profile ISF x (integral of net activity), mg/dL
                          per hour, activity unclamped as AndroidAPS reads it. Positive means
                          glucose ended higher than the settings predicted, which is the
                          quantity autosens takes the median of.
    admitted              the window passes the post_cob_isf.py rule: integral of activity
                          clamped at zero positive, and profile ISF times it at least 8 mg/dL.
    ratio                 on admitted windows, effective sensitivity over profile ISF.

Per person: the median of D over all windows and over admitted windows, the admitted share, the
median ratio, the median net activity in U/h and the share of night cycles with it negative,
the median glucose change per window, the median net insulin on board, and the share of night
cycles on which net insulin on board exceeds twice the scheduled basal rate. That last is the
rule by which oref sets a cycle aside as an unannounced meal, so a deviation on such a cycle never
reaches the autosens median however positive it is. The real basal is the user's mean profile
rate from `canonical_cohort.json`, where the loop compares against the rate scheduled at that
hour, so the real share is approximate where a profile varies overnight. The real side is read from the oref database
(`oref_v5` for Trio, `oref_v7` for oref0) for the users of `canonical_cohort.json` that
`inv008/post_cob_isf.py` admitted, with that script's profile ISF. The simulated side is forty
titrated adults, 28 days on the bench seed under oref0 SMB with the shipped layers, in two arms
paired per subject:

    shipped          the person as shipped
    night_resistant  insulin sensitivity multiplied by 0.7 from 23:00 to 04:59

The second arm is the positive control. A person less sensitive at night than its settings say
has, by construction, glucose ending higher than predicted, so D has to rise and the ratio fall.
The simulated side also records the deviation autosens itself computed on each cycle and how it
classified the cycle, as a check that D is the quantity autosens reads.

Reproduction. The shipped arm repeats the oref0 SMB arm of `driver_ranking.json` and the
shipped arm of `post_cob_isf.json`, so time in range and the per-subject overnight effective
sensitivity must match both exactly. The real per-user effective sensitivity must match
`results/post_cob_isf_peruser.parquet` in oref-investigations to its rounding.

Registered before the run, 4 October 2026.

A three-day run of adult#001 in both arms, and four real users, were run first to check the
wiring, and the record of that is part of the registration. The four real users reproduced the
real script's effective sensitivity and ratio exactly. The control moved D from 6.2 to 12.5 mg/dL
per hour, and a shipped run after a control run in the same process reproduced the first shipped
run, so the patch is restored. The draft expectation had net activity negative on most simulated
night cycles; on adult#001 it was positive on 80 per cent, at a median of +1.0 U/h, with 97 per
cent of windows admitted, D at +6.2 mg/dL per hour and net insulin on board of 2.6 to 4.2 U
against twice the basal at 2.2. That is one subject over three nights and decides nothing, but it
changed the expectation below and added the insulin on board statistic.

Expectation. The simulated median ratio is about 0.2 to 0.3, below the real 0.43 and inside its
10th to 90th percentile, so most of the 4.5 against 22.7 is the settings. Simulated D over all
windows is positive, which contradicts the reading of 25 September that the simulated fasting
deviations centre on zero, and the simulated share of night cycles with insulin on board above
twice basal is above the real one, so the positive night deviations are set aside as unannounced
meals before autosens sees them. Selection between admitted and all windows is small on the
simulated side.

Rule.
  Control. night_resistant must raise D over all windows and lower the ratio, each with a
  paired 95 per cent interval clear of zero. Otherwise the statistics cannot see a known
  overnight resistance and the comparison is void.
  Overnight discrepancy. The simulated cohort median ratio is placed against the real 10th to
  90th percentile across users. Inside: the 4.5 against 22.7 is recorded as a difference in
  settings scale and closed. Below: the simulated person falls less per unit of its own
  settings than real people at night, and it stays open.
  Autosens at night. The difference between the simulated and real cohort medians of D over all
  windows is bootstrapped, people resampled on each side. An interval wholly below zero locates
  the missing resistance in the fasting night, which is then the place to look for the
  mechanism. An interval containing zero says the night does not explain the autosens result,
  and the daytime non-meal cycles become the place instead.
  Exclusion. The same bootstrap is applied to the share of night cycles with insulin on board
  above twice basal. A simulated share above the real one, interval clear of zero, together with
  simulated D over all windows above zero (its cohort interval clear of zero), says the bench has
  the night resistance and oref's meal rule hides it. That would make the autosens result of 25
  September a property of how insulin on board compares with basal overnight, which is then the
  thing to explain.
  Selection. Admitted minus all-window D, per person, is reported on each side as the size of
  the selection the night windows impose. It decides nothing on its own.

    python examples/night_sensitivity.py
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "night_sensitivity.json")
RANKING = os.path.join(MEASUREMENTS, "driver_ranking.json")
POST_COB = os.path.join(MEASUREMENTS, "post_cob_isf.json")
OREF = os.path.expanduser("~/oref-investigations")
REAL_PERUSER = os.path.join(OREF, "results", "post_cob_isf_peruser.parquet")
COHORT = os.path.join(OREF, "canonical_cohort.json")
COB_COL = {"oref_v5": '"sug_COB"', "oref_v7": "sug_cob"}
WORKERS = 7
ARMS = {"shipped": {}, "night_resistant": {"night_si": 0.7}}

# The real script's constants, in minutes.
NIGHT = {23, 0, 1, 2, 3, 4}
H60 = 60
TOL = 7
LOOKBACK = 150
MIN_PRED = 8.0
MIN_N = 15
BG_LO, BG_HI = 70, 300
PER_PERSON = ("n_windows", "admitted_share", "d_all", "d_admitted", "d_selection", "ratio",
              "eff", "act_u_per_h", "act_negative_share", "glucose_change", "iob_u",
              "iob_over_2_basal_share")


def night_rows(t, bg, act, cob, isf, hour, iob, basal, full_lookback=False):
    """Per-person night statistics from one record. Times in minutes, activity in U/min.

    `isf` is per sample, so a constant profile and a scheduled one go through the same code.
    `iob` is net insulin on board in units and `basal` the scheduled rate in U/h, compared as
    oref compares them when it sets a cycle aside as an unannounced meal.
    `full_lookback` drops windows in the first 150 minutes of a record, which `post_cob_isf.py`
    does and the real script does not; each side keeps its own reference's rule so that both
    reproduce.
    """
    t = np.asarray(t, float)
    bg = np.asarray(bg, float)
    act = np.asarray(act, float)
    cob = np.asarray(cob, float)
    isf = np.asarray(isf, float)
    iob = np.asarray(iob, float)
    basal = np.asarray(basal, float)
    hour = np.asarray(hour).astype(int)
    n = t.size
    dt = np.diff(t)
    dt = np.where(dt > 15.0, 0.0, dt)
    cum_net = np.concatenate([[0.0], np.cumsum(0.5 * (act[:-1] + act[1:]) * dt)])
    pos = np.clip(act, 0.0, None)
    cum_pos = np.concatenate([[0.0], np.cumsum(0.5 * (pos[:-1] + pos[1:]) * dt)])
    end = np.searchsorted(t, t + H60)
    end = np.where(end < n, end, n - 1)
    ok = np.abs(t[end] - (t + H60)) <= TOL
    back = np.searchsorted(t, t - LOOKBACK)
    # Carbohydrate on board is zero across [back, end] when the running maximum there is zero.
    had = np.concatenate([[0], np.cumsum(cob > 0)])

    d_all, d_adm, ratio, eff, change, cyc = [], [], [], [], [], []
    for i in range(n):
        if hour[i] not in NIGHT or not ok[i] or not (BG_LO <= bg[i] <= BG_HI):
            continue
        if full_lookback and t[i] - t[0] < LOOKBACK:
            continue
        j = end[i]
        if had[j + 1] - had[back[i]] > 0:
            continue
        cyc.append(i)
        drop = bg[i] - bg[j]
        d = -drop + isf[i] * (cum_net[j] - cum_net[i])
        d_all.append(d)
        change.append(-drop)
        a = cum_pos[j] - cum_pos[i]
        if a > 0 and j - i >= 4 and isf[i] * a >= MIN_PRED:
            d_adm.append(d)
            e = np.clip(drop / a, -400, 400)
            eff.append(e)
            ratio.append(e / isf[i])
    out = {"n_windows": len(d_all), "n_admitted": len(d_adm)}
    if len(d_all) < MIN_N:
        return out
    cyc = np.unique(cyc)
    out.update(admitted_share=len(d_adm) / len(d_all), d_all=float(np.median(d_all)),
               act_u_per_h=float(np.median(act[cyc]) * 60.0),
               act_negative_share=float(np.mean(act[cyc] < 0)),
               glucose_change=float(np.median(change)),
               iob_u=float(np.median(iob[cyc])),
               iob_over_2_basal_share=float(np.mean(iob[cyc] > 2.0 * basal[cyc])))
    if len(d_adm) >= MIN_N:
        out.update(d_admitted=float(np.median(d_adm)), ratio=float(np.median(ratio)),
                   eff=float(np.median(eff)))
        out["d_selection"] = out["d_admitted"] - out["d_all"]
    return out


# ------------------------------------------------------------------------------ real side
def real_job(args):
    user, table, isf, basal = args
    import pandas as pd
    import psycopg2
    conn = psycopg2.connect("dbname=oref")
    try:
        d = pd.read_sql(f"""SELECT ts_relative_sec AS ts, hour, cgm_mgdl AS bg,
                                   iob_activity AS act, {COB_COL[table]} AS cob,
                                   iob_iob AS iob
                            FROM {table} WHERE user_id=%s AND cgm_mgdl IS NOT NULL
                              AND iob_activity IS NOT NULL ORDER BY ts_relative_sec""",
                        conn, params=(user,))
    finally:
        conn.close()
    pisf = isf * 18.018 if isf < 20 else isf
    act = pd.to_numeric(d.act, errors="coerce").fillna(0.0).values
    cob = pd.to_numeric(d.cob, errors="coerce").fillna(0.0).values
    t = d.ts.values.astype(float) / 60.0
    iob = pd.to_numeric(d.iob, errors="coerce").fillna(0.0).values
    out = night_rows(t, d.bg.values, act, cob, np.full(len(d), pisf), d.hour.values, iob,
                     np.full(len(d), basal))
    out.update(subject=user, table=table, profile_isf=float(pisf))
    return out


def real_side(workers):
    import pandas as pd
    ref = pd.read_parquet(REAL_PERUSER)
    tables = dict(zip(ref.user, ref.platform))
    cohort = {r["user_id"]: r for r in json.load(open(COHORT))}
    jobs = [(u, tables[u], float(cohort[u]["isf"]), float(cohort[u]["profile_mean_basal"]))
            for u in ref.user]
    with mp.Pool(workers) as pool:
        rows = pool.map(real_job, jobs, chunksize=1)
    want = dict(zip(ref.user, ref.eff_night))
    diffs = [abs(r["eff"] - want[r["subject"]]) for r in rows if "eff" in r]
    repro = {"compared": len(diffs), "max_abs_eff_diff": float(max(diffs)) if diffs else None}
    return rows, repro


# ------------------------------------------------------------------------- simulated side
def recorder():
    from timsim.controller import oref

    class Recording(oref.OrefController):
        """Keeps what each cycle read, and the deviation and class autosens gave it."""

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            # minute, cgm, activity, cob, isf, autosens deviation, non-meal, iob, basal
            self.trace = []
            self._act = 0.0
            self._dev = (np.nan, 0.0, np.nan, np.nan)
            observe = self.autosens.observe

            def watched(*oa, **ok):
                dev = observe(*oa, **ok)
                self._dev = (dev, 1.0 if self.autosens.kind == "non-meal" else 0.0,
                             float(ok["iob"]), float(ok["current_basal"]))
                return dev
            self.autosens.observe = watched

        def iob_curve(self, *a, **k):
            out = super().iob_curve(*a, **k)
            self._act = float(out[0]["activity"])
            return out

        def policy(self, observation, reward, done, **info):
            action = super().policy(observation, reward, done, **info)
            minute = float(info.get("clock_minutes", 0.0))
            self.trace.append((minute, float(observation.CGM), self._act,
                               float(self.autosens.meal_cob),
                               float(self.profile.isf_at(minute)), *self._dev))
            return action
    return Recording


def night_si(factor):
    """Multiply the person's insulin sensitivity by `factor` from 23:00 to 04:59.

    Returns the original method, which the caller restores: a pool worker runs many jobs, and a
    patch left on the class would carry into the shipped runs after it and compound on itself.
    """
    from timsim.patient import varying
    original = varying.VaryingPatient.sensitivity

    def sensitivity(self):
        s = original(self)
        hour = int((self.t / 60.0) % 24)
        return s * factor if hour in NIGHT else s
    varying.VaryingPatient.sensitivity = sensitivity
    return original


def sim_job(args):
    name, arm, seed, days = args
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    from timsim.patient import varying
    opts = dict(ARMS[arm])
    restore = night_si(opts.pop("night_si")) if "night_si" in opts else None
    prof = titrate.profile_for(name)
    ctrl = recorder()(name, profile=prof)
    t0 = time.time()
    try:
        r = simulate(name, days=days, seed=seed, layers=DEFAULT_LAYERS, controller=ctrl,
                     profile=prof, **opts)
        tr = np.array(ctrl.trace, float)
    finally:
        ctrl.close()
        if restore is not None:
            varying.VaryingPatient.sensitivity = restore
    cgm = np.asarray(r.cgm, float)
    hour = ((tr[:, 0] // 60) % 24).astype(int)
    out = night_rows(tr[:, 0], tr[:, 1], tr[:, 2], tr[:, 3], tr[:, 4], hour, tr[:, 7], tr[:, 8],
                     full_lookback=True)
    # The deviation autosens computed, per five minutes, on night non-meal cycles.
    night = np.isin(hour, list(NIGHT)) & (tr[:, 6] > 0) & np.isfinite(tr[:, 5])
    out.update(subject=name, arm=arm, completed=bool(r.completed),
               seconds=float(time.time() - t0),
               tir=float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
               night_mean_cgm=float(np.mean(tr[np.isin(hour, list(NIGHT)), 1])),
               autosens_night_dev_per_h=float(np.median(tr[night, 5]) * 12.0) if night.any() else None,
               autosens_night_nonmeal_cycles=int(night.sum()),
               autosens_night_nonmeal_share=float(night.sum() / max(np.isin(hour, list(NIGHT)).sum(), 1)))
    return out


# ---------------------------------------------------------------------------- summaries
def spread(values):
    v = np.asarray([x for x in values if x is not None], float)
    if v.size == 0:
        return {"n": 0}
    return {"n": int(v.size), "median": float(np.median(v)), "mean": float(np.mean(v)),
            "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)),
            "min": float(v.min()), "max": float(v.max())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=WORKERS)
    a = ap.parse_args()
    from examples.panel import dosable

    t0 = time.time()
    real, real_repro = real_side(a.workers)
    print(f"real: {len(real)} users in {(time.time() - t0) / 60:.1f} min, effective sensitivity "
          f"reproduced on {real_repro['compared']}, largest difference "
          f"{real_repro['max_abs_eff_diff']}", flush=True)

    subs = dosable(a.subjects)
    jobs = [(n, arm, seeds.BENCH, a.days) for arm in ARMS for n in subs]
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        sim = pool.map(sim_job, jobs, chunksize=1)
    print(f"simulated: {len(sim)} runs in {(time.time() - t0) / 60:.1f} min", flush=True)
    got = {(r["subject"], r["arm"]): r for r in sim}

    repro = {}
    ref = {x["subject"]: x for x in json.load(open(RANKING))["per_run"] if x["arm"] == "oref"}
    d = [abs(got[(n, "shipped")]["tir"] - ref[n]["tir"]) for n in subs
         if n in ref and ref[n]["completed"] and got[(n, "shipped")]["completed"]]
    repro["driver_ranking"] = {"compared": len(d), "max_abs_tir_diff": float(max(d)) if d else None}
    pc = {x["subject"]: x for x in json.load(open(POST_COB))["per_run"] if x["arm"] == "shipped"}
    d = [abs(got[(n, "shipped")]["eff"] - pc[n]["dynamic"]["eff_night"]) for n in subs
         if "eff" in got[(n, "shipped")] and "eff_night" in pc[n]["dynamic"]]
    repro["post_cob_isf"] = {"compared": len(d), "max_abs_eff_diff": float(max(d)) if d else None}
    print(f"reproduction: {repro}", flush=True)

    rng = np.random.default_rng(20261004)

    def ci_paired(v):
        v = np.asarray(v, float)
        b = [np.median(rng.choice(v, v.size, replace=True)) for _ in range(10000)]
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    def ci_unpaired(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        b = [np.median(rng.choice(x, x.size)) - np.median(rng.choice(y, y.size))
             for _ in range(10000)]
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    keys = PER_PERSON + ("autosens_night_dev_per_h", "autosens_night_nonmeal_share",
                         "night_mean_cgm", "tir")
    stats = {"real": {k: spread(r.get(k) for r in real) for k in PER_PERSON}}
    for arm in ARMS:
        stats[arm] = {k: spread(got[(n, arm)].get(k) for n in subs) for k in keys}

    control = {}
    for k in ("d_all", "ratio", "night_mean_cgm", "act_u_per_h"):
        v = [got[(n, "night_resistant")][k] - got[(n, "shipped")][k] for n in subs
             if got[(n, "night_resistant")].get(k) is not None
             and got[(n, "shipped")].get(k) is not None]
        control[k] = {"subjects": len(v), "paired_median": float(np.median(v)), "ci95": ci_paired(v)}
    sees = control["d_all"]["ci95"][0] > 0 and control["ratio"]["ci95"][1] < 0

    sim_ratio = stats["shipped"]["ratio"]["median"]
    band = (stats["real"]["ratio"]["p10"], stats["real"]["ratio"]["p90"])
    place = "inside" if band[0] <= sim_ratio <= band[1] else ("below" if sim_ratio < band[0] else "above")
    sd = [got[(n, "shipped")]["d_all"] for n in subs if got[(n, "shipped")].get("d_all") is not None]
    rd = [r["d_all"] for r in real if r.get("d_all") is not None]
    d_ci = ci_unpaired(sd, rd)
    def cohort_ci(v):
        v = np.asarray(v, float)
        b = [np.median(rng.choice(v, v.size)) for _ in range(10000)]
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    se = [got[(n, "shipped")]["iob_over_2_basal_share"] for n in subs
          if got[(n, "shipped")].get("iob_over_2_basal_share") is not None]
    re_ = [r["iob_over_2_basal_share"] for r in real if r.get("iob_over_2_basal_share") is not None]
    e_ci = ci_unpaired(se, re_)
    sd_ci = cohort_ci(sd)
    verdicts = {
        "control_sees_night_resistance": bool(sees),
        "iob_over_2_basal_sim_minus_real": {
            "median_difference": float(np.median(se) - np.median(re_)), "ci95": e_ci,
            "sim_d_all_ci95": sd_ci,
            "meal_rule_hides_night_resistance": bool(e_ci[0] > 0 and sd_ci[0] > 0)},
        "ratio": {"sim_median": sim_ratio, "real_median": stats["real"]["ratio"]["median"],
                  "real_p10_p90": list(band), "place": place},
        "d_all_sim_minus_real": {"median_difference": float(np.median(sd) - np.median(rd)),
                                 "ci95": d_ci,
                                 "night_locates_missing_resistance": bool(d_ci[1] < 0)},
    }

    print(f"\n{'per person':>26}{'real':>22}{'shipped':>22}{'night_resistant':>22}")
    for k in PER_PERSON:
        cells = []
        for side in ("real", "shipped", "night_resistant"):
            s = stats[side][k]
            cells.append(f"{s['median']:.2f} ({s['p10']:.2f}, {s['p90']:.2f})" if s["n"] else "-")
        print(f"{k:>26}" + "".join(f"{c:>22}" for c in cells))
    print(f"\ncontrol: {json.dumps(control)}")
    print(f"verdicts: {json.dumps(verdicts)}")

    json.dump({"provenance": provenance.stamp(), "subjects": subs, "days": a.days,
               "seed": seeds.BENCH, "arms": ARMS, "reproduction": repro,
               "real_reproduction": real_repro, "stats": stats, "control": control,
               "verdicts": verdicts, "real_per_user": real, "per_run": sim},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
