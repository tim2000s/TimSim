"""Why hypoglycaemia differences between drivers are larger on the Hovorka body than on S2008.

`docs/HOVORKA.md` ran the driver ranking on both bodies at the same code. Seventeen of eighteen
pairs agree in sign, and every hypoglycaemia difference involving the Control-IQ stand-in is three
to five times larger on Hovorka: the stand-in minus the trend loop is +3.01 [1.77, 3.56] points
below 70 mg/dL there against +1.07 [0.86, 1.69] on S2008. Boost minus the trend loop resolves on
Hovorka at -1.41 [-2.10, -0.91] and not on S2008 at 0.04 [-0.13, 0.34]. This producer locates
where the difference in size arises. It doses nobody and changes no body: every arm that alters
an equation does so inside this script, for the run it is in.

Stages, each writing its own file under `docs/measurements/`:

  existing   reads the two ranking files and computes, per pair, the ratio of time below 70 mg/dL
             as well as the difference, the insulin difference, the time below 70 per unit of
             extra daily insulin, how far the Hovorka difference is carried by a few subjects,
             and its rank correlation with each subject's parameters  -> hovorka_gap_existing.json
  probe      the bodies alone, no controller, no meal: insulin held at a multiple of basal from
             the basal steady state, and single boluses of increasing size, on the 40 subjects of
             each ranking panel                                           -> hovorka_gap_probe.json
  runs       trend, the stand-in and Boost rerun on both panels with the time series reduced to
             where each low sits (after a meal, after a correction, overnight, otherwise), and
             two swap arms                                       -> hovorka_gap_runs_<arm>.json
  report     pairs the runs and writes the decomposition               -> hovorka_gap_runs.json

The swap arms. `risk`: S2008 with S2013's risk term on at r1 = 0.05, the value calibrated in
`patient/varying.py` and then switched off, which amplifies insulin-dependent uptake below basal
glucose. `autoreg`: the Hovorka body given S2008's glucose autoregulation of production, a lift
of kp2 times the plasma glucose deficit below the subject's own basal, inside the zero floor,
with kp2 the median of the 40 S2008 panel subjects. It is applied below basal only, so the steady
state, the closure and everything above basal are unchanged. Both are modelling choices made for
this probe; neither body is changed outside it, and settings titrated on the unmodified bodies are
used throughout, so a swap arm measures the body change together with settings that were not
fitted to it.

Registered before the probe and the runs (the `existing` stage reads files already on disk, and
the column medians of those files had been seen when this was written).

  1. Level. Time below 70 mg/dL is bounded at zero and the trend loop spends 3.66 per cent there
     on Hovorka against 1.30 on S2008. Expected: on the ratio scale the stand-in against the trend
     loop is the same on both bodies, intervals overlapping, so most of the three-to-five-fold
     difference in points is the level. Boost against the trend loop is expected to differ on the
     ratio scale as well, below one on Hovorka and near one on S2008.
  2. Dose. The stand-in delivers more insulin than the trend loop on both bodies, and more more on
     Hovorka (medians 6.2 and 3.7 U/day). Expected positive on both, larger on Hovorka.
  3. Gain in the loop. Time below 70 mg/dL per extra unit a day, stand-in against trend: expected
     larger on Hovorka.
  4. Subgroup. Expected broad: the quarter of subjects with the largest stand-in excess carries
     under half of the summed excess on Hovorka. Expected sign of the correlation with insulin
     sensitivity (Sf1, Sf3): positive, the more sensitive subjects carrying more.
  5. Low type. Expected most of the stand-in's excess on both bodies after meals, since it boluses
     announced meals and corrects the rise; overnight a minor share.
  6. Clamp probe. At twice basal insulin held fixed, Hovorka falls further and faster below 70
     mg/dL than S2008, since its production has no glucose term and S2008's rises as glucose
     falls. Expected: Hovorka's twelve-hour glucose lower, its rate of fall at 70 mg/dL faster.
  7. Bolus probe. The drop per unit of the first unit is larger on Hovorka (its correction factor
     is 28.9 against 18.6), and the drop per unit where the nadir crosses 70 mg/dL relative to the
     first unit is nearer one on Hovorka and below one on S2008, which flattens as it falls.
  8. Swaps. `risk` raises the stand-in minus trend difference below 70 mg/dL on S2008. `autoreg`
     lowers it on Hovorka. Each is read as the paired change in the pair difference, with a
     bootstrap interval, against the base arm on the same subjects.

    python examples/hovorka_gap.py existing
    python examples/hovorka_gap.py probe --workers 4
    python examples/hovorka_gap.py runs --arm base --workers 4
    python examples/hovorka_gap.py runs --arm risk --workers 4
    python examples/hovorka_gap.py runs --arm autoreg --workers 4
    python examples/hovorka_gap.py report
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from itertools import combinations

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
M = os.path.join(REPO, "docs", "measurements")
RANK = {"hovorka": os.path.join(M, "driver_ranking_hovorka.json"),
        "s2008": os.path.join(M, "driver_ranking_s2008_current.json")}
DRIVERS = ("trend", "control-iq", "boost")
RISK_GAIN = 0.05          # r1 as calibrated in patient/varying.py before it was switched off
MEAL_WINDOW = 240         # minutes after a meal that a low counts as post-meal
CORRECTION_WINDOW = 180   # minutes after a non-meal bolus that a low counts as post-correction
CORRECTION_MIN_U = 0.3
MEAL_BOLUS_SLACK = 30     # a bolus within this many minutes of a meal is a meal bolus
BOOT = 5000


def _boot(rng, f, *cols):
    """Percentile interval of `f` over subjects resampled with replacement."""
    n = len(cols[0])
    out = []
    for _ in range(BOOT):
        i = rng.integers(0, n, n)
        out.append(f(*(np.asarray(c)[i] for c in cols)))
    out = np.asarray(out, float)
    out = out[np.isfinite(out)]
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def _ratio(a, b):
    return float(np.mean(a) / np.mean(b)) if np.mean(b) > 0 else float("nan")


def _gain(dt, du):
    return float(np.mean(dt) / np.mean(du)) if np.mean(du) != 0 else float("nan")


# --------------------------------------------------------------------------------- existing
def stage_existing():
    import pandas as pd
    from scipy.stats import spearmanr
    from timsim import provenance
    from timsim.population import params_for
    rng = np.random.default_rng(20261110)
    out = {"provenance": provenance.stamp(), "sources": {}, "bodies": {}}
    for body, path in RANK.items():
        d = json.load(open(path))
        out["sources"][body] = {"file": os.path.relpath(path, REPO),
                                "commit": d["provenance"]["commit"][:7]}
        runs = {(r["subject"], r["arm"]): r for r in d["per_run"]}
        subs = d["subjects"]
        prm = pd.DataFrame([params_for(s) for s in subs]).set_index("Name")
        if body == "hovorka":
            prm["sens_uptake"], prm["sens_egp"] = prm["Sf1"], prm["Sf3"]
        else:
            prm["sens_uptake"], prm["sens_egp"] = prm["Vmx"], prm["kp3"]
        prm["basal_per_kg"] = prm["u2ss"]
        b = {"spread": {k: {"median": float(prm[k].median()),
                            "cv": float(prm[k].std() / prm[k].mean())}
                        for k in ("sens_uptake", "sens_egp", "BW", "basal_per_kg")},
             "pairs": []}
        for d1, d2 in combinations(["trend", "control-iq", "boost", "oref"], 2):
            common = [s for s in subs if runs[(s, d1)]["completed"] and runs[(s, d2)]["completed"]]
            a = np.array([runs[(s, d2)]["tbr70"] for s in common])
            c = np.array([runs[(s, d1)]["tbr70"] for s in common])
            ua = np.array([runs[(s, d2)]["insulin_per_day"] for s in common])
            uc = np.array([runs[(s, d1)]["insulin_per_day"] for s in common])
            diff, du = a - c, ua - uc
            order = np.argsort(-diff)
            top = order[: max(1, len(common) // 4)]
            pos = diff.sum()
            rec = {"pair": f"{d2} - {d1}", "subjects": len(common),
                   "tbr70_mean_diff": float(diff.mean()),
                   "tbr70_mean_diff_ci": _boot(rng, np.mean, diff),
                   "tbr70_ratio_of_means": _ratio(a, c),
                   "tbr70_ratio_ci": _boot(rng, _ratio, a, c),
                   "insulin_mean_diff": float(du.mean()),
                   "insulin_mean_diff_ci": _boot(rng, np.mean, du),
                   "insulin_ratio_of_means": _ratio(ua, uc),
                   "tbr70_per_unit_day": _gain(diff, du),
                   "tbr70_per_unit_day_ci": _boot(rng, _gain, diff, du),
                   "top_quarter_share_of_sum": float(diff[top].sum() / pos) if pos else None,
                   "top_quarter_subjects": [common[i] for i in top],
                   "spearman": {}}
            for k in ("sens_uptake", "sens_egp", "BW", "basal_per_kg"):
                rho, p = spearmanr(prm.loc[common, k].values, diff)
                rec["spearman"][k] = {"rho": float(rho), "p": float(p)}
            rec["spearman"]["insulin_diff"] = dict(zip(("rho", "p"),
                                                      map(float, spearmanr(du, diff))))
            b["pairs"].append(rec)
        out["bodies"][body] = b
    path = os.path.join(M, "hovorka_gap_existing.json")
    json.dump(out, open(path, "w"), indent=1)
    for body, b in out["bodies"].items():
        print(f"\n{body}: spread " + ", ".join(f"{k} cv {v['cv']:.2f}"
                                            for k, v in b["spread"].items()))
        for r in b["pairs"]:
            print(f"  {r['pair']:>22} n{r['subjects']:3d}  dTBR {r['tbr70_mean_diff']:+.2f} "
                  f"{np.round(r['tbr70_mean_diff_ci'], 2)}  ratio {r['tbr70_ratio_of_means']:.2f} "
                  f"{np.round(r['tbr70_ratio_ci'], 2)}  dU {r['insulin_mean_diff']:+.1f} "
                  f"{np.round(r['insulin_mean_diff_ci'], 1)}  per U {r['tbr70_per_unit_day']:+.3f} "
                  f"{np.round(r['tbr70_per_unit_day_ci'], 3)}  top25% "
                  f"{r['top_quarter_share_of_sum']}  rho(Sup) "
                  f"{r['spearman']['sens_uptake']['rho']:+.2f} rho(dU) "
                  f"{r['spearman']['insulin_diff']['rho']:+.2f}")
    print(f"wrote {path}")


# ------------------------------------------------------------------------------------ bodies
def _s2008_kp2():
    from timsim.population import params_for
    subs = json.load(open(RANK["s2008"]))["subjects"]
    return float(np.median([params_for(s)["kp2"] for s in subs]))


def install_autoreg(kp2):
    """Give the Hovorka body S2008's glucose autoregulation of production, below basal only.

    Patched on the module the patient reads `_rates` from, in this process only. Production
    becomes max(0, EGP0 (1 - x3) + kp2 (Q1b - Q1)) for Q1 below Q1b, where Q1b is the plasma glucose
    mass at the subject's own basal glucose; at and above basal it is unchanged.
    """
    from timsim.patient import hovorka as H
    if getattr(H, "_autoreg_installed", None) == kp2:
        return
    original = getattr(H, "_rates_stock", H._rates)

    def rates(x, u, d, p, si):
        dx = original(x, u, d, p, si)
        q1b = float(p["Gb"]) / H.MGDL_PER_MMOL * p["VG"]
        if x[H.Q1] < q1b:
            base = p["EGP0"] * (1.0 - x[H.X3])
            dx[H.Q1] += max(0.0, base + kp2 * (q1b - x[H.Q1])) - max(0.0, base)
        return dx

    H._rates_stock = original
    H._rates = rates
    H._autoreg_installed = kp2


def _body(name, arm, kp2=None):
    """A body as the bench builds it, without the time-varying layers."""
    from timsim.population import params_for
    if name.startswith("hovorka#"):
        from timsim.patient.hovorka import HovorkaPatient
        if arm == "autoreg":
            install_autoreg(kp2)
        p = HovorkaPatient(params_for(name))
        bw, u2ss = float(p._params["BW"]), float(p._params["u2ss"])
        gb = float(p._params["Gb"])
    else:
        from timsim.patient import varying as V
        p = V.from_population(name)
        if arm == "risk":
            p.set_hypo_risk(RISK_GAIN)
        # The shipped hepatic defence, which every bench run on S2008 carries; `nodefence` is
        # the stock S2008 liver without it.
        p.set_hypo_defence(V.HYPO_DEFENCE_GAIN, 0.0 if arm == "nodefence" else V.HYPO_EGP_DEFENCE)
        bw, u2ss = float(p._params["BW"]), float(p._params["u2ss"])
        gb = float(p._params["Gb"])
    return p, u2ss * bw / 6000.0, gb


def _trace(p, insulin_at, minutes):
    from simglucose.patient.t1dpatient import Action
    g = np.empty(minutes)
    for m in range(minutes):
        p.step(Action(CHO=0.0, insulin=insulin_at(m)))
        g[m] = float(p.observation.Gsub)
    return g


def _rate_at(g, level):
    """Rate of fall in mg/dL per hour where the trace first crosses `level` going down."""
    i = np.where((g[:-1] >= level) & (g[1:] < level))[0]
    if not len(i):
        return None
    j = int(i[0])
    lo, hi = max(0, j - 15), min(len(g) - 1, j + 15)
    return float(-(g[hi] - g[lo]) / (hi - lo) * 60.0)


DOSES = np.arange(0.5, 12.01, 0.5)
MULTIPLES = (1.5, 2.0)


def probe_job(job):
    name, arm, kp2 = job
    rec = {"subject": name, "arm": arm, "hold": {}, "bolus": {}}
    p, basal, gb = _body(name, arm, kp2)
    rec["gb"], rec["basal_u_h"] = gb, basal * 60.0
    for mult in MULTIPLES:
        p, basal, _ = _body(name, arm, kp2)
        g = _trace(p, lambda m: basal * mult, 720)
        rec["hold"][str(mult)] = {"g_2h": float(g[119]), "g_4h": float(g[239]),
                                  "g_12h": float(g[-1]), "min": float(g.min()),
                                  "minutes_below_70": int((g < 70).sum()),
                                  "fall_at_90": _rate_at(g, 90.0), "fall_at_70": _rate_at(g, 70.0)}
    nadir, below = [], []
    for dose in DOSES:
        p, basal, _ = _body(name, arm, kp2)
        g = _trace(p, lambda m, b=basal, d=dose: b + (d if m == 0 else 0.0), 600)
        nadir.append(float(g.min()))
        below.append(int((g < 70).sum()))
    nadir, below = np.array(nadir), np.array(below)
    rec["bolus"] = {"doses": DOSES.tolist(), "nadir": nadir.tolist(), "minutes_below_70": below.tolist()}
    # Drop per unit for the first unit, and where the nadir crosses 70 mg/dL.
    first = float((gb - nadir[1]) / DOSES[1])
    k = np.where(nadir < 70.0)[0]
    if len(k) and k[0] >= 1 and k[0] + 1 < len(DOSES):
        j = int(k[0])
        slope = float((nadir[j - 1] - nadir[j + 1]) / (DOSES[j + 1] - DOSES[j - 1]))
        d70 = float(np.interp(70.0, nadir[::-1], DOSES[::-1]))
        extra = int(np.interp(d70 + 1.0, DOSES, below))
    else:
        slope, d70, extra = None, None, None
    rec["bolus"].update(first_unit_drop=first, drop_per_unit_at_70=slope, dose_to_70=d70,
                        steepening=(slope / first) if slope else None,
                        minutes_below_70_one_unit_past=extra)
    return rec


def stage_probe(workers):
    from timsim import provenance
    rng = np.random.default_rng(20261110)
    kp2 = _s2008_kp2()
    arms = [("s2008", "base"), ("s2008", "nodefence"), ("s2008", "risk"),
            ("hovorka", "base"), ("hovorka", "autoreg")]
    jobs = [(s, arm, kp2) for body, arm in arms for s in json.load(open(RANK[body]))["subjects"]]
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers) as pool:
        rows = pool.map(probe_job, jobs, chunksize=1)
    print(f"{len(rows)} probes in {(time.time() - t0) / 60:.1f} min")
    summary = {}
    for body, arm in arms:
        rs = [r for r in rows if r["arm"] == arm and r["subject"].startswith(
            "hovorka#" if body == "hovorka" else "adult")]
        key = f"{body}/{arm}"
        s = {"n": len(rs)}

        def med(vals):
            v = np.array([x for x in vals if x is not None], float)
            return {"median": float(np.median(v)), "ci": _boot(rng, np.median, v), "n": int(len(v))}
        s["gb"] = med([r["gb"] for r in rs])
        s["basal_u_h"] = med([r["basal_u_h"] for r in rs])
        for mult in MULTIPLES:
            h = [r["hold"][str(mult)] for r in rs]
            s[f"hold_{mult}"] = {k: med([x[k] for x in h]) for k in
                                 ("g_4h", "g_12h", "min", "minutes_below_70", "fall_at_90",
                                  "fall_at_70")}
            s[f"hold_{mult}"]["reached_70"] = int(sum(x["fall_at_70"] is not None for x in h))
        bo = [r["bolus"] for r in rs]
        s["bolus"] = {k: med([x[k] for x in bo]) for k in
                      ("first_unit_drop", "drop_per_unit_at_70", "dose_to_70", "steepening",
                       "minutes_below_70_one_unit_past")}
        summary[key] = s
        print(f"\n{key} n={len(rs)}  Gb {s['gb']['median']:.0f}  basal {s['basal_u_h']['median']:.2f} U/h")
        for mult in MULTIPLES:
            h = s[f"hold_{mult}"]
            print(f"  hold x{mult}: 4h {h['g_4h']['median']:.0f}  12h {h['g_12h']['median']:.0f} "
                  f"{np.round(h['g_12h']['ci'], 0)}  min<70 {h['minutes_below_70']['median']:.0f}  "
                  f"fall@90 {h['fall_at_90']['median']:.1f}  fall@70 {h['fall_at_70']['median']:.1f} "
                  f"(n {h['fall_at_70']['n']})")
        b = s["bolus"]
        print(f"  bolus: first unit {b['first_unit_drop']['median']:.1f} "
              f"{np.round(b['first_unit_drop']['ci'], 1)}  at 70 {b['drop_per_unit_at_70']['median']:.1f} "
              f"{np.round(b['drop_per_unit_at_70']['ci'], 1)}  steepening {b['steepening']['median']:.2f} "
              f"{np.round(b['steepening']['ci'], 2)}  dose to 70 {b['dose_to_70']['median']:.1f}  "
              f"min<70 one unit past {b['minutes_below_70_one_unit_past']['median']:.0f}")
    path = os.path.join(M, "hovorka_gap_probe.json")
    json.dump({"provenance": provenance.stamp(), "kp2_autoreg": kp2, "risk_gain": RISK_GAIN,
               "multiples": MULTIPLES, "summary": summary, "per_subject": rows},
              open(path, "w"), indent=1)
    print(f"wrote {path}")


# -------------------------------------------------------------------------------------- runs
def _classify(r):
    """Time below 70 mg/dL on the sensor and the truth, split by where each reading sits."""
    t = np.asarray(r.minutes, float)
    bol = np.asarray(r.bolus_series, float)
    meals = np.array(sorted(m for m, _ in r.meal_log), float)
    step = float(r.sample_time)
    # A bolus within the slack of a meal is a meal bolus; everything else is a correction.
    near = np.zeros(len(t), bool)
    if len(meals):
        j = np.searchsorted(meals, t)
        for k in (j - 1, j):
            ok = (k >= 0) & (k < len(meals))
            near[ok] |= np.abs(meals[np.clip(k, 0, len(meals) - 1)][ok] - t[ok]) <= MEAL_BOLUS_SLACK
    corr = np.where(near, 0.0, bol)
    ccum = np.concatenate([[0.0], np.cumsum(corr)])
    w = int(round(CORRECTION_WINDOW / step))
    idx = np.arange(len(t))
    corr_recent = ccum[idx + 1] - ccum[np.maximum(0, idx + 1 - w)]
    if len(meals):
        j = np.searchsorted(meals, t, side="right") - 1
        since = np.where(j >= 0, t - meals[np.clip(j, 0, None)], np.inf)
    else:
        since = np.full(len(t), np.inf)
    cat = np.where(since <= MEAL_WINDOW, 0,
                   np.where(corr_recent >= CORRECTION_MIN_U, 1,
                            np.where((t % 1440) < 360, 2, 3)))
    names = ("post_meal", "post_correction", "nocturnal", "other")
    days = max(len(t) * step / 1440.0, 1e-9)
    out = {}
    for label, g in (("cgm", np.asarray(r.cgm, float)), ("bg", np.asarray(r.bg, float))):
        low = g < 70
        out[label] = {n: float(100.0 * np.mean(low & (cat == i))) for i, n in enumerate(names)}
    out["share_of_time"] = {n: float(np.mean(cat == i)) for i, n in enumerate(names)}
    ins = np.asarray(r.insulin_series, float)
    out["insulin"] = {"total": float(ins.sum() / days), "bolus_meal": float(bol[near].sum() / days),
                      "bolus_other": float(bol[~near].sum() / days),
                      "basal_and_temp": float((ins.sum() - bol.sum()) / days)}
    return out


def run_job(job):
    name, driver, seed, days, arm, kp2 = job
    from timsim.analysis.safety import lbgi_hbgi
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    from examples.capability_table import driver_for
    if arm == "autoreg":
        install_autoreg(kp2)
    prof = titrate.profile_for(name)
    ctrl = driver_for(name, driver, prof)
    t0 = time.time()
    kw = {"hypo_risk_gain": RISK_GAIN} if arm == "risk" else {}
    try:
        r = simulate(name, days=days, seed=seed, layers=DEFAULT_LAYERS, controller=ctrl,
                     profile=prof, **kw)
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    cgm, bg = np.asarray(r.cgm, float), np.asarray(r.bg, float)
    ran = max(len(cgm) * float(r.sample_time) / 1440.0, 1e-9)
    out = {"subject": name, "driver": driver, "arm": arm, "completed": bool(r.completed),
           "seconds": float(time.time() - t0), "days_ran": float(ran),
           "tir": float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
           "tbr70": float(100.0 * np.mean(cgm < 70)), "tbr54": float(100.0 * np.mean(cgm < 54)),
           "tbr70_bg": float(100.0 * np.mean(bg < 70)), "lbgi": float(lbgi_hbgi(cgm)[0]),
           "mean_cgm": float(np.mean(cgm)),
           "insulin_per_day": float(r.insulin_units / ran),
           "rescue_g_per_day": float(r.rescue_grams / ran), "low_type": _classify(r)}
    return out


def stage_runs(arm, workers, days):
    from timsim import provenance, seeds
    kp2 = _s2008_kp2()
    bodies = {"base": ("s2008", "hovorka"), "risk": ("s2008",), "autoreg": ("hovorka",)}[arm]
    jobs = []
    for body in bodies:
        subs = json.load(open(RANK[body]))["subjects"]
        jobs += [(s, d, seeds.BENCH, days, arm, kp2) for d in DRIVERS for s in subs]
    jobs.sort(key=lambda j: j[1] != "boost")      # the bridge runs are the slow ones
    print(f"arm {arm}: {len(jobs)} runs on {workers} workers", flush=True)
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers) as pool:
        rows = pool.map(run_job, jobs, chunksize=1)
    print(f"{len(rows)} runs in {(time.time() - t0) / 60:.1f} min", flush=True)
    path = os.path.join(M, f"hovorka_gap_runs_{arm}.json")
    json.dump({"provenance": provenance.stamp(), "arm": arm, "days": days, "seed": seeds.BENCH,
               "risk_gain": RISK_GAIN, "kp2_autoreg": kp2, "runs": rows}, open(path, "w"), indent=1)
    print(f"wrote {path}")


# ------------------------------------------------------------------------------------ report
def stage_report():
    from timsim import provenance
    rng = np.random.default_rng(20261111)
    arms = {}
    for arm in ("base", "risk", "autoreg"):
        f = os.path.join(M, f"hovorka_gap_runs_{arm}.json")
        if os.path.exists(f):
            arms[arm] = {(r["subject"], r["driver"]): r for r in json.load(open(f))["runs"]}
    base = arms["base"]
    out = {"provenance": provenance.stamp(), "reproduction": {}, "bodies": {}}
    # The base arm reruns the ranking's own runs, so it has to agree with them to the decimal.
    for body, path in RANK.items():
        ref = {(r["subject"], r["driver"]): r for r in json.load(open(path))["per_run"]
               if r["seed"] == json.load(open(path))["seed"]}
        dev = [max(abs(base[k]["tir"] - ref[k]["tir"]), abs(base[k]["tbr70"] - ref[k]["tbr70"]))
               for k in base if k in ref and k[0].startswith("hovorka#") == (body == "hovorka")]
        out["reproduction"][body] = {"compared": len(dev), "max_abs_diff": float(max(dev))}
        print(f"reproduction {body}: {len(dev)} runs, largest |TIR or TBR70 difference| "
              f"{max(dev):.2e}")
    cats = ("post_meal", "post_correction", "nocturnal", "other")
    for body in RANK:
        subs = json.load(open(RANK[body]))["subjects"]
        b = {"pairs": []}
        for d1, d2 in (("trend", "control-iq"), ("trend", "boost"), ("boost", "control-iq")):
            common = [s for s in subs if base[(s, d1)]["completed"] and base[(s, d2)]["completed"]]
            rec = {"pair": f"{d2} - {d1}", "subjects": len(common), "by_type": {}}
            for src in ("cgm", "bg"):
                for c in cats:
                    diff = np.array([base[(s, d2)]["low_type"][src][c] - base[(s, d1)]["low_type"][src][c]
                                     for s in common])
                    rec["by_type"][f"{src}/{c}"] = {"mean": float(diff.mean()),
                                                    "ci": _boot(rng, np.mean, diff),
                                                    f"{d1}_mean": float(np.mean([base[(s, d1)]["low_type"][src][c] for s in common]))}
            for k in ("total", "bolus_meal", "bolus_other", "basal_and_temp"):
                diff = np.array([base[(s, d2)]["low_type"]["insulin"][k]
                                 - base[(s, d1)]["low_type"]["insulin"][k] for s in common])
                rec[f"insulin_{k}"] = {"mean": float(diff.mean()), "ci": _boot(rng, np.mean, diff)}
            tot = np.array([base[(s, d2)]["tbr70"] - base[(s, d1)]["tbr70"] for s in common])
            rec["tbr70"] = {"mean": float(tot.mean()), "ci": _boot(rng, np.mean, tot)}
            # Swap: the change in the pair difference, paired per subject, against base.
            for arm in ("risk", "autoreg"):
                if arm not in arms or not any(k[0] in subs for k in arms[arm]):
                    continue
                A = arms[arm]
                cc = [s for s in common if A[(s, d1)]["completed"] and A[(s, d2)]["completed"]]
                for key in ("tbr70", "tbr70_bg", "insulin_per_day", "tir"):
                    sw = np.array([A[(s, d2)][key] - A[(s, d1)][key] for s in cc])
                    bs = np.array([base[(s, d2)][key] - base[(s, d1)][key] for s in cc])
                    rec[f"{arm}_{key}"] = {"subjects": len(cc), "base": float(bs.mean()),
                                           "swap": float(sw.mean()),
                                           "change": float((sw - bs).mean()),
                                           "change_ci": _boot(rng, np.mean, sw - bs),
                                           "swap_ci": _boot(rng, np.mean, sw)}
                    rec[f"{arm}_{key}"]["d1_level_base"] = float(np.mean([base[(s, d1)][key] for s in cc]))
                    rec[f"{arm}_{key}"]["d1_level_swap"] = float(np.mean([A[(s, d1)][key] for s in cc]))
            b["pairs"].append(rec)
            print(f"\n{body} {rec['pair']} n{len(common)}: TBR70 {rec['tbr70']['mean']:+.2f} "
                  f"{np.round(rec['tbr70']['ci'], 2)}")
            for c in cats:
                x = rec["by_type"][f"cgm/{c}"]
                print(f"   {c:>16}: {x['mean']:+.2f} {np.round(x['ci'], 2)}  ({d1} {x[f'{d1}_mean']:.2f})")
            print("   insulin " + ", ".join(f"{k} {rec[f'insulin_{k}']['mean']:+.1f}"
                                            for k in ("total", "bolus_meal", "bolus_other", "basal_and_temp")))
            for arm in ("risk", "autoreg"):
                if f"{arm}_tbr70" in rec:
                    x = rec[f"{arm}_tbr70"]
                    print(f"   {arm}: base {x['base']:+.2f} swap {x['swap']:+.2f} change "
                          f"{x['change']:+.2f} {np.round(x['change_ci'], 2)}  ({d1} level "
                          f"{x['d1_level_base']:.2f} -> {x['d1_level_swap']:.2f})")
        out["bodies"][body] = b
    path = os.path.join(M, "hovorka_gap_runs.json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=("existing", "probe", "runs", "report"))
    ap.add_argument("--arm", choices=("base", "risk", "autoreg"), default="base")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--days", type=int, default=28)
    a = ap.parse_args()
    if a.stage == "existing":
        stage_existing()
    elif a.stage == "probe":
        stage_probe(a.workers)
    elif a.stage == "runs":
        stage_runs(a.arm, a.workers, a.days)
    else:
        stage_report()


if __name__ == "__main__":
    main()
