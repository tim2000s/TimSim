#!/usr/bin/env python3
"""What Boost's hypo damper does, measured as a paired difference.

`ml_hypo_risk` has always been None in this package, so every published Boost result here is Boost
with its damper absent: a null leaves the aggression budget unscaled. The floor arm is therefore
today's behaviour exactly, and the treated arm supplies the shipped four-column model. Nothing else
differs: same subjects, same seed, same days, same settings.

Read as `docs/READING_A_RESULT.md` and paper 19 require. On the sensor trace, because the reference
is a sensor trace. Paired per subject, with the median of the differences bootstrapped over
subjects, because subjects differ far more than arms do. Completions reported by direction, since a
subject who fails one arm and not the other is not a paired observation. The floor on the
forty-adult panel is 2.8 points of TIR, 0.6 of TBR70 and 0.25 of TBR54, measured rather than
assumed, and a difference inside it is not resolved whatever its sign.

The damper can only ever reduce a dose, so the expected direction is less insulin and less time
below range, at some cost above it.

python examples/hypo_damper_arms.py --subjects 40 --days 28
"""
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SEED = 0
FLOOR = {"tir": 2.8, "tbr70": 0.6, "tbr54": 0.25, "tar180": 6.59 * 2.8 / 6.28}


def metrics(cgm):
    g = np.asarray(cgm, dtype=float); g = g[np.isfinite(g)]
    return {"tir": 100 * np.mean((g >= 70) & (g <= 180)), "tbr70": 100 * np.mean(g < 70),
            "tbr54": 100 * np.mean(g < 54), "tar180": 100 * np.mean(g > 180),
            "mean": float(g.mean())}


def one(job):
    import warnings; warnings.filterwarnings("ignore")
    from timsim.simulation.run import simulate
    from timsim.controller import boost_bridge
    from timsim.controller.hypo_four_column import HypoFourColumn
    from timsim.therapy import titrate
    name, days, arm = job
    prof = titrate.profile_for(name)
    c = boost_bridge.BoostBridgeController(name, profile=prof)
    if arm == "damper":
        c.hypo_model = HypoFourColumn()
    try:
        r = simulate(name, days=days, seed=SEED, controller=c, profile=prof)
    except Exception as e:
        return {"name": name, "arm": arm, "completed": False, "error": str(e)[:120]}
    finally:
        if hasattr(c, "close"):
            c.close()
    m = metrics(r.cgm)
    m.update(name=name, arm=arm, completed=bool(r.completed), insulin=float(r.insulin_units))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--boot", type=int, default=4000)
    a = ap.parse_args()
    from examples.panel import dosable
    names = dosable(a.subjects, quiet=True)
    jobs = [(n, a.days, arm) for n in names for arm in ("floor", "damper")]
    print(f"{len(names)} subjects x 2 arms, {a.days} days, seed {SEED}\n"
          f"floor = ml_hypo_risk None, which is this package's behaviour today\n"
          f"damper = the shipped four-column model\n")
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        rows = list(pool.map(one, jobs))

    by = {}
    for r in rows:
        by.setdefault(r["name"], {})[r["arm"]] = r
    paired = [v for v in by.values()
              if v.get("floor", {}).get("completed") and v.get("damper", {}).get("completed")]
    lost = {n: [a for a in ("floor", "damper") if not v.get(a, {}).get("completed")]
            for n, v in by.items() if len(paired) and n not in {p["floor"]["name"] for p in paired}}
    print(f"{len(paired)} subjects completed both arms; {len(by) - len(paired)} did not")
    for n, arms in lost.items():
        print(f"  {n} failed: {', '.join(arms) or 'one arm'}")

    rng = np.random.default_rng(SEED)
    print(f"\n{'outcome':>10}{'floor':>9}{'damper':>9}{'paired diff':>13}{'95% CI':>20}"
          f"{'floor':>8}{'verdict':>16}")
    out = {}
    for k in ("tir", "tbr70", "tbr54", "tar180", "insulin"):
        f = np.array([p["floor"][k] for p in paired], dtype=float)
        d = np.array([p["damper"][k] for p in paired], dtype=float)
        diff = d - f
        med = float(np.median(diff))
        bs = np.array([np.median(rng.choice(diff, len(diff), replace=True)) for _ in range(a.boot)])
        lo, hi = np.percentile(bs, [2.5, 97.5])
        fl = FLOOR.get(k)
        if fl is None:
            verdict = "resolved" if lo * hi > 0 else "not resolved"
        elif abs(med) < fl:
            verdict = "inside the floor"
        else:
            verdict = "resolved" if lo * hi > 0 else "not resolved"
        print(f"{k:>10}{f.mean():>9.2f}{d.mean():>9.2f}{med:>+13.3f}"
              f"{f'{lo:+.3f} to {hi:+.3f}':>20}{(f'{fl:.2f}' if fl else '-'):>8}{verdict:>16}")
        out[k] = dict(floor=float(f.mean()), damper=float(d.mean()), median_diff=med,
                      lo=float(lo), hi=float(hi), floor_value=fl, verdict=verdict)
    print("\nConfiguration: titrated settings, default layers (no activity), "
          f"seed {SEED}, {a.days} days, read on the sensor trace.")
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "hypo_damper_arms.json")
    json.dump({"summary": out, "n_paired": len(paired), "rows": rows}, open(path, "w"), indent=1)
    print(f"wrote {path}")


if __name__ == "__main__":
    sys.exit(main())
