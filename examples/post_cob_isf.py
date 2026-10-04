"""Effective insulin sensitivity in the hour after carbohydrate clears, against overnight.

The real measurement is `~/oref-investigations/inv008/post_cob_isf.py` (results in
`results/post_cob_isf.json` there, committed in 5cd9f45 of that repository). Across 115 Trio and
oref0 users, glucose fell 8.3 mg/dL per unit of insulin acting in the hour after the loop's own
carbohydrate on board reached zero, against 22.7 in genuinely fasting overnight hours. 86 per cent
of users were lower after the carbohydrate cleared, the median gap was 13.2, and glucose rose in
38 per cent of post-clear windows against 26 overnight. That paper read it as absorption
outlasting the carbohydrate model. Unsuppressed glucagon after a meal would produce the same
signature, and the glucose record cannot tell the two apart.

The reason to measure it here. `examples/sim_autosens.py` found the simulated person's autosens
ratio reading resistant on 0.43 per cent of cycles against 42 for real users, with the simulated
fasting deviations centred on zero. Autosens counts the hour after carbohydrate clears as
non-meal, so a real post-meal tail of the size above would push real deviations positive and
real autosens resistant. Whether the simulated person has such a tail decides where to look
next: a person with none is missing something in the hours after a meal, glucagon among the
candidates, and that would join the autosens result to the meal rise and excursion shortfalls
already recorded. A person who already has it rules the tail out as the cause.

Method, ported line for line from the real script so the two definitions match. Each simulated
cycle records the sensor glucose, the hour, the insulin activity oref read (tick zero of the
curve, U/min) and the carbohydrate on board. Effective sensitivity over a window is the glucose
drop divided by the integral of activity, so the profile sensitivity cancels. A post-clear
window starts on the cycle where carbohydrate on board goes from above zero to zero and stays
zero for the hour; a night window starts between 23:00 and 04:59 with carbohydrate on board zero
for the hour and the 150 minutes before. Both need starting glucose 70 to 300 mg/dL, a
predicted drop (profile sensitivity times the activity integral) of at least 8 mg/dL, and 15
windows per arm per person. Medians of effective sensitivity are clipped at plus or minus 400.

Carbohydrate on board on the real side is the loop's own, which is oref's dynamic model:
absorption tracks observed deviations with a floor of 8 mg/dL per five minutes. The simulated
oref bridge is handed a linear decay instead (`LoopInputs.observe_carbs`), so the primary
simulated figure uses the dynamic estimate the autosens object keeps (`Autosens.meal_cob`),
which is the same arithmetic. The linear figure is reported beside it.

Arms, forty titrated adults, 28 days on the bench seed under oref0 SMB, paired per subject:

    shipped     the person as shipped
    slow_meal   carbohydrate absorption at half the rate (`meal_absorption_scale` 0.5)

The second arm is the positive control. Absorption that runs past the model is what produces the
signature by construction, so if halving the absorption rate does not move the post-clear
figure, the statistic cannot see a tail in this simulator and the comparison is void.

Registered before the run, 4 October 2026.

Expectation. The simulated shipped person shows a smaller gap than the real users, because
nothing in it acts after a meal's glucose has arrived and the dynamic estimate is built to
follow what absorption it has.

Rule. The real script's own verdict test is applied to the simulated shipped arm unchanged: a
tail is called present when at least 60 per cent of subjects are lower after carbohydrate clears,
the Wilcoxon test gives p below 0.05, and the median gap, night minus post, exceeds 3 mg/dL per
unit. The size is then read against the real figures: the ratio of post to night medians (real
8.3 over 22.7, 0.37) and the rise fractions. The control must raise the median gap with a
paired interval clear of zero. If the shipped arm shows no tail and the control shows one, the
simulated person lacks a post-meal tail that real people have, and a mechanism acting in the
hours after a meal is the next candidate, to be registered on its own. If the shipped arm shows
a tail of the real size, the tail is not why autosens fails to read resistant.

    python examples/post_cob_isf.py
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

OUT = os.path.join(MEASUREMENTS, "post_cob_isf.json")
RANKING = os.path.join(MEASUREMENTS, "driver_ranking.json")
WORKERS = 7
ARMS = {"shipped": {}, "slow_meal": {"meal_absorption_scale": 0.5}}
REAL = {"source": "~/oref-investigations/results/post_cob_isf.json (5cd9f45)",
        "n_users": 115, "median_eff_post": 8.3, "median_eff_night": 22.7,
        "median_delta_night_minus_post": 13.2, "frac_users_post_lower": 0.86,
        "median_rise_frac_post": 0.38, "median_rise_frac_night": 0.26,
        "trajectory_eff_post_0_30": 6.0, "trajectory_eff_post_30_60": 13.2}

# The real script's constants, in minutes rather than seconds.
NIGHT = {23, 0, 1, 2, 3, 4}
H60, H30 = 60, 30
LOOKBACK = 150
MIN_PRED = 8.0
MIN_N = 15
BG_LO, BG_HI = 70, 300


def recorder():
    """An oref controller that keeps what each cycle read, for the windows."""
    from timsim.controller import oref

    class Recording(oref.OrefController):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.trace = []          # (minute, cgm, activity, cob_dynamic, cob_linear, isf)
            self._act = 0.0

        def iob_curve(self, *a, **k):
            out = super().iob_curve(*a, **k)
            self._act = float(out[0]["activity"])
            return out

        def policy(self, observation, reward, done, **info):
            action = super().policy(observation, reward, done, **info)
            minute = float(info.get("clock_minutes", 0.0))
            self.trace.append((minute, float(observation.CGM), self._act,
                               float(self.autosens.meal_cob), float(self.cob_g),
                               float(self.profile.isf_at(minute))))
            return action
    return Recording


def windows(trace, cob_col):
    """Post-clear and night effective sensitivity, as the real script computes them."""
    t = trace[:, 0]
    bg = trace[:, 1]
    act = np.clip(trace[:, 2], 0.0, None)
    cob = trace[:, cob_col]
    isf = trace[:, 5]
    hr = ((t // 60) % 24).astype(int)
    dt = np.diff(t)
    dt = np.where(dt > 15.0, 0.0, dt)
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (act[:-1] + act[1:]) * dt)])
    n = len(t)
    step = 5
    k60, k30, kb = H60 // step, H30 // step, LOOKBACK // step

    def eff(i, j):
        a = cum[j] - cum[i]
        if a <= 0 or j - i < 4:
            return None
        return (bg[i] - bg[j]) / a, bg[i] - bg[j], isf[i] * a

    post, post_h1, post_h2, night = [], [], [], []
    for i in range(1, n - k60):
        if not (BG_LO <= bg[i] <= BG_HI):
            continue
        j = i + k60
        if cob[i - 1] > 0 and cob[i] <= 0 and cob[i:j + 1].max() <= 0:
            r = eff(i, j)
            if r and r[2] >= MIN_PRED:
                post.append(r)
                h = i + k30
                r1, r2 = eff(i, h), eff(h, j)
                if r1 and r1[2] >= MIN_PRED / 2:
                    post_h1.append(r1[0])
                if r2 and r2[2] >= MIN_PRED / 2:
                    post_h2.append(r2[0])
        elif hr[i] in NIGHT and i >= kb and cob[i:j + 1].max() <= 0 and cob[i - kb:i + 1].max() <= 0:
            r = eff(i, j)
            if r and r[2] >= MIN_PRED:
                night.append(r)
    cl = lambda v: np.clip(np.asarray(v, float), -400, 400)
    out = {"n_post": len(post), "n_night": len(night)}
    if len(post) >= MIN_N and len(night) >= MIN_N:
        p, q = np.array(post), np.array(night)
        out.update(eff_post=float(np.median(cl(p[:, 0]))), eff_night=float(np.median(cl(q[:, 0]))),
                   rise_post=float(np.mean(p[:, 1] < 0)), rise_night=float(np.mean(q[:, 1] < 0)),
                   eff_post_h1=float(np.median(cl(post_h1))) if len(post_h1) >= MIN_N else None,
                   eff_post_h2=float(np.median(cl(post_h2))) if len(post_h2) >= MIN_N else None)
        out["delta"] = out["eff_night"] - out["eff_post"]
    return out


def job(args):
    name, arm, seed, days = args
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    ctrl = recorder()(name, profile=prof)
    t0 = time.time()
    try:
        r = simulate(name, days=days, seed=seed, layers=DEFAULT_LAYERS, controller=ctrl,
                     profile=prof, **ARMS[arm])
        trace = np.array(ctrl.trace, float)
    finally:
        ctrl.close()
    cgm = np.asarray(r.cgm, float)
    out = {"completed": bool(r.completed), "seconds": float(time.time() - t0),
           "tir": float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
           "dynamic": windows(trace, 3), "linear": windows(trace, 4)}
    return name, arm, out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=WORKERS)
    a = ap.parse_args()
    from examples.panel import dosable
    from scipy import stats as sps
    subs = dosable(a.subjects)
    jobs = [(n, arm, seeds.BENCH, a.days) for arm in ARMS for n in subs]
    print(f"{len(subs)} subjects, arms {list(ARMS)}, {a.days} days, {len(jobs)} runs", flush=True)
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        results = pool.map(job, jobs, chunksize=1)
    print(f"{len(results)} runs in {(time.time() - t0) / 60:.1f} min", flush=True)
    got = {(n, arm): o for n, arm, o in results}

    repro = {"compared": 0, "max_abs_tir_diff": None}
    if os.path.exists(RANKING):
        ref = {x["subject"]: x for x in json.load(open(RANKING))["per_run"] if x["arm"] == "oref"}
        d = [abs(got[(n, "shipped")]["tir"] - ref[n]["tir"]) for n in subs
             if n in ref and ref[n]["completed"] and got[(n, "shipped")]["completed"]]
        repro = {"compared": len(d), "max_abs_tir_diff": float(max(d)) if d else None}
        print(f"reproduction against driver_ranking.json: {len(d)} runs, largest TIR "
              f"discrepancy {repro['max_abs_tir_diff']}", flush=True)

    rng = np.random.default_rng(20261004)

    def ci(v):
        v = np.asarray(v, float)
        b = [np.median(rng.choice(v, v.size, replace=True)) for _ in range(10000)]
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    summary = {}
    for cob in ("dynamic", "linear"):
        for arm in ARMS:
            rows = [got[(n, arm)][cob] for n in subs if "delta" in got[(n, arm)][cob]]
            if len(rows) < 5:
                summary[f"{arm}/{cob}"] = {"usable": len(rows)}
                continue
            post = np.array([r["eff_post"] for r in rows])
            night = np.array([r["eff_night"] for r in rows])
            delta = night - post
            w = sps.wilcoxon(post, night)
            h1 = [r["eff_post_h1"] for r in rows if r["eff_post_h1"] is not None]
            h2 = [r["eff_post_h2"] for r in rows if r["eff_post_h2"] is not None]
            s = {"usable": len(rows),
                 "median_eff_post": float(np.median(post)),
                 "median_eff_night": float(np.median(night)),
                 "median_delta_night_minus_post": float(np.median(delta)),
                 "delta_ci95": ci(delta),
                 "frac_post_lower": float(np.mean(post < night)),
                 "wilcoxon_p": float(w.pvalue),
                 "median_rise_frac_post": float(np.median([r["rise_post"] for r in rows])),
                 "median_rise_frac_night": float(np.median([r["rise_night"] for r in rows])),
                 "trajectory_eff_post_0_30": float(np.median(h1)) if h1 else None,
                 "trajectory_eff_post_30_60": float(np.median(h2)) if h2 else None,
                 "median_windows_post": float(np.median([r["n_post"] for r in rows])),
                 "median_windows_night": float(np.median([r["n_night"] for r in rows]))}
            s["tail_present"] = bool(s["frac_post_lower"] >= 0.6 and s["wilcoxon_p"] < 0.05
                                     and s["median_delta_night_minus_post"] > 3)
            summary[f"{arm}/{cob}"] = s
        both = [n for n in subs if "delta" in got[(n, "shipped")][cob]
                and "delta" in got[(n, "slow_meal")][cob]]
        if len(both) >= 5:
            d = [got[(n, "slow_meal")][cob]["delta"] - got[(n, "shipped")][cob]["delta"] for n in both]
            summary[f"control/{cob}"] = {"subjects": len(both), "paired_median": float(np.median(d)),
                                         "ci95": ci(d)}

    print(f"\nreal: post {REAL['median_eff_post']}, night {REAL['median_eff_night']}, gap "
          f"{REAL['median_delta_night_minus_post']}, {REAL['frac_users_post_lower']:.0%} lower, "
          f"rises {REAL['median_rise_frac_post']:.0%} vs {REAL['median_rise_frac_night']:.0%}")
    for k, s in summary.items():
        print(k, json.dumps({x: (round(v, 3) if isinstance(v, float) else v) for x, v in s.items()}))

    json.dump({"provenance": provenance.stamp(), "subjects": subs, "days": a.days,
               "seed": seeds.BENCH, "arms": ARMS, "real": REAL, "reproduction": repro,
               "summary": summary,
               "per_run": [{"subject": n, "arm": arm, **o} for (n, arm), o in sorted(got.items())]},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
