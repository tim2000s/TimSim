"""Does a production floor reach the subjects no gain can reach?

A third of subjects produce nothing at a 55 mg/dL clamp plateau where no real person produces
nothing, and the defence gain cannot fix it: production is `kp1 - kp2*Gp - kp3*Id`, it floors at
zero, and multiplying zero returns zero. Raising the gain fivefold removes nine of thirty-seven
from the floor while carrying the median outside the human band.

This sweeps a floor instead, over the same clamp and the same subjects, and asks the two
questions `docs/DESIGN_HYPOGLYCAEMIA.md` fixed in advance: does the count producing nothing fall
below ten of a hundred and ten, and does the median stay inside 0.42 to 0.84?

    python examples/calibrate_egp_floor.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from examples.hypoglycaemic_clamp import clamp, HUMAN_EGP
from examples.calibrate_hypo_defence import PLATEAU_TOLERANCE
from timsim import provenance
from timsim.population import names
from timsim.patient import varying as V

OUT = os.path.join(MEASUREMENTS, "egp_floor.json")
FLOORS = (0.0, 0.20, 0.30, 0.42, 0.55)
PLATEAUS = (55.0, 45.0)
HUMAN_MEAN = 0.59


def _one(arg):
    name, floor = arg
    # The clamp builds its own patient, so the floor is applied by patching the constant the
    # patient reads at construction. Restored in the same call.
    original = V.HYPO_EGP_FLOOR
    V.HYPO_EGP_FLOOR = float(floor)
    try:
        rows = clamp(name, 0.0, V.HYPO_EGP_DEFENCE, egp_floor=floor)
        return floor, name, {float(r["target"]): (float(r["egp"]), float(r["glucose"]))
                             for r in rows}
    except Exception as exc:
        return floor, name, {"error": str(exc)[:140]}
    finally:
        V.HYPO_EGP_FLOOR = original


def main(n=110, workers=10):
    subs = [s for s in names() if s.startswith("adult")][:n]
    jobs = [(s, f) for f in FLOORS for s in subs]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        out = list(ex.map(_one, jobs))

    print(f"{len(subs)} adults, human {HUMAN_EGP[0]} to {HUMAN_EGP[1]} mg/kg/min, "
          f"mean {HUMAN_MEAN}\n")
    print(f"{'floor':>7}" + "".join(f"  {f'--- {t:.0f} mg/dL ---':^30}" for t in PLATEAUS))
    print(f"{'':>7}" + "".join(f"  {'median':>8}{'p10':>8}{'p90':>7}{'zeros':>7}"
                               for _ in PLATEAUS))
    rows = []
    for f in FLOORS:
        got = [r for ff, _, r in out if ff == f and r and "error" not in r]
        rec, line = {"floor": f}, f"{f:>7.2f}"
        for t in PLATEAUS:
            pairs = [r[t] for r in got if t in r]
            held = np.array([h for _, h in pairs], float)
            arrived = np.abs(held - t) <= PLATEAU_TOLERANCE
            v = np.array([e for e, _ in pairs], float)[arrived]
            if not len(v):
                line += f"{'-':>30}"
                continue
            zeros = int((v < 0.01).sum())
            rec[f"p{t:.0f}"] = {"median": float(np.median(v)), "p10": float(np.percentile(v, 10)),
                                "p90": float(np.percentile(v, 90)), "zeros": zeros,
                                "n": int(len(v))}
            line += (f"  {np.median(v):>8.2f}{np.percentile(v, 10):>8.2f}"
                     f"{np.percentile(v, 90):>7.2f}{f'{zeros}/{len(v)}':>7}")
        rows.append(rec)
        print(line, flush=True)

    print(f"\n  the criteria fixed before this was run:")
    for r in rows:
        p = r.get("p55")
        if not p or r["floor"] == 0.0:
            continue
        few = p["zeros"] <= 10
        inside = HUMAN_EGP[0] <= p["median"] <= HUMAN_EGP[1]
        print(f"    floor {r['floor']:.2f}: producing nothing {p['zeros']}/{p['n']} "
              f"({'under ten' if few else 'still above ten'}), median {p['median']:.2f} "
              f"({'inside' if inside else 'OUTSIDE'} the human band)"
              f"{'   <- both met' if few and inside else ''}")
    json.dump({"floors": rows, "human": list(HUMAN_EGP),
               "provenance": provenance.stamp()}, open(OUT, "w"), indent=1)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
