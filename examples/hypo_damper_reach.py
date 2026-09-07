#!/usr/bin/env python3
"""Before measuring what Boost's hypo damper does, ask whether it can do anything here.

`ml_hypo_risk` has always been None in this package, so every published Boost result is Boost with
its damper absent: the engine reads a null as a missing model and leaves the aggression budget
unscaled. Supplying the real model is a paired arm worth running, but only if the damper engages.
The engine scales nothing below a risk of 0.30, and the panel is titrated to avoid hypoglycaemia,
so a cohort that never approaches a low would return an exact zero that says nothing about the
model.

This scores the model on the floor arm without letting it act, which is the same shadow-first
discipline the engine itself uses. Each subject runs once, unchanged, while the model watches; what
is reported is how often it would have crossed the threshold and how much hypoglycaemia that
subject actually had.

python examples/hypo_damper_reach.py --subjects 40 --days 28
"""
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

THRESHOLD = 0.30            # DetermineBasalBoost scales nothing below this
SEED = 0


def one(job):
    import warnings; warnings.filterwarnings("ignore")
    from timsim.simulation.run import simulate
    from timsim.controller import boost_bridge
    from timsim.controller.hypo_four_column import HypoFourColumn
    from timsim.therapy import titrate
    name, days = job

    class Watcher(HypoFourColumn):
        """Scores every cycle and reports nothing, so the run is the untouched floor arm."""
        def __init__(self):
            super().__init__(); self.seen = []
        def score(self, bg):
            self.seen.append(super().score(bg))
            return None

    prof = titrate.profile_for(name)
    w = Watcher()
    c = boost_bridge.BoostBridgeController(name, profile=prof)
    c.hypo_model = w
    try:
        r = simulate(name, days=days, seed=SEED, controller=c, profile=prof)
    except Exception as e:
        return {"name": name, "completed": False, "error": str(e)[:120]}
    finally:
        if hasattr(c, "close"):
            c.close()
    v = np.array([x for x in w.seen if x is not None], dtype=float)
    g = np.asarray(r.cgm, dtype=float); g = g[np.isfinite(g)]
    if not len(v) or not len(g):
        return {"name": name, "completed": False, "error": "no data"}
    return {"name": name, "completed": bool(r.completed),
            "cycles": int(len(v)), "over": int((v > THRESHOLD).sum()),
            "share_over": float(np.mean(v > THRESHOLD)),
            "p95": float(np.percentile(v, 95)), "max": float(v.max()),
            "tbr70": float(100 * np.mean(g < 70)), "tbr54": float(100 * np.mean(g < 54)),
            "min_bg": float(g.min()), "tir": float(100 * np.mean((g >= 70) & (g <= 180)))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=7)
    a = ap.parse_args()
    from examples.panel import dosable
    names = dosable(a.subjects, quiet=True)
    print(f"{len(names)} subjects, {a.days} days, seed {SEED}, model watching but not acting\n")
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        rows = list(pool.map(one, [(n, a.days) for n in names]))
    ok = [r for r in rows if r.get("completed")]
    bad = [r for r in rows if not r.get("completed")]
    print(f"{'subject':>12}{'TBR70':>8}{'TBR54':>8}{'min':>6}{'cycles>0.30':>13}{'max risk':>10}")
    for r in sorted(ok, key=lambda x: -x["tbr70"]):
        print(f"{r['name']:>12}{r['tbr70']:>8.2f}{r['tbr54']:>8.2f}{r['min_bg']:>6.0f}"
              f"{r['over']:>8} ({100*r['share_over']:>3.1f}%){r['max']:>10.3f}")
    if bad:
        print(f"\n{len(bad)} did not complete: {[b['name'] for b in bad]}")
    reach = [r for r in ok if r["over"] > 0]
    print(f"\n{len(reach)} of {len(ok)} subjects reach the damper at all")
    print(f"  cycles over threshold, pooled: {sum(r['over'] for r in ok):,} of "
          f"{sum(r['cycles'] for r in ok):,} ({100*sum(r['over'] for r in ok)/max(1,sum(r['cycles'] for r in ok)):.2f}%)")
    print(f"  subjects with any time below 70: {sum(1 for r in ok if r['tbr70'] > 0)}/{len(ok)}")
    print(f"  pooled TBR70 {np.mean([r['tbr70'] for r in ok]):.2f}%, "
          f"TBR54 {np.mean([r['tbr54'] for r in ok]):.2f}%")
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "hypo_damper_reach.json")
    json.dump(rows, open(out, "w"), indent=1)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    sys.exit(main())
