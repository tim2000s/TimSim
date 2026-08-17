"""Choose the hepatic defence gain against the human clamp reference.

The defence opposes insulin's suppression of endogenous glucose production as glucose falls,
and its gain was calibrated against a population that could not be rebuilt. On the reproducible
population the undefended model already produces 0.49 mg/kg/min at the 55 mg/dL plateau against
a human 0.42 to 0.84, so the shipped gain of 0.25 carries it to 0.95 and out the other side.

Two things are being fitted at once and they do not agree. The median wants a small gain,
because the median is already inside the human interval. The lower tail wants a large one,
because a third of subjects produce nothing at all at that plateau and no real person does.
Both are reported here so the choice is made on the evidence rather than on the median alone.

Reference: Rickels et al., Diabetes 2015;64(5):1713-1718, stepped hyperinsulinaemic clamp in
twelve people with long-standing type 1 diabetes and no discernible glucagon response.
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
from timsim.population import names

GAINS = (0.0, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25)
PLATEAUS = (55.0, 45.0)
HUMAN_MEAN = 0.59
OUT = os.path.join(MEASUREMENTS, "hypo_defence_gain.json")


# How far from the nominal plateau a subject may sit and still be counted. The clamp's
# controller can only add glucose, so the descent is set by the insulin and a sufficiently
# insulin-resistant subject never arrives: one of the first eight adults settles at 62.8 mg/dL
# against a 55 mg/dL target. Production is read as `kp1 - kp2*Gp - kp3*Id`, so a subject held
# above the plateau reports a lower figure than it would at the plateau and is likelier to floor
# at zero. Pooling those with the ones that arrived drags the median down and inflates the zero
# count, and the gain is fitted on that median.
PLATEAU_TOLERANCE = 3.0        # mg/dL


def _one(arg):
    """One subject at one gain, as {plateau: (egp, glucose actually held)}."""
    name, gain = arg
    try:
        rows = clamp(name, 0.0, gain)
        return gain, name, {float(r["target"]): (float(r["egp"]), float(r["glucose"]))
                            for r in rows}
    except Exception as exc:                       # a subject that will not hold the clamp
        return gain, name, {"error": str(exc)[:120]}


def main(n=34, workers=6):
    subs = [s for s in names() if s.startswith("adult")][:n]
    jobs = [(s, g) for g in GAINS for s in subs]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        out = list(ex.map(_one, jobs))

    print(f"{len(subs)} adults; human {HUMAN_EGP[0]} to {HUMAN_EGP[1]} mg/kg/min, "
          f"mean {HUMAN_MEAN}\n")
    header = f"{'gain':>6}"
    for t in PLATEAUS:
        header += f"  {f'--- {t:.0f} mg/dL ---':^32}"
    print(header)
    print(f"{'':>6}" + f"  {'median':>8}{'p10':>8}{'p90':>8}{'zeros':>8}" * len(PLATEAUS))

    rows, dropped = [], {}
    for g in GAINS:
        got = [r for gg, _, r in out if gg == g and r and "error" not in r]
        rec = {"gain": g}
        line = f"{g:>6.3f}"
        for t in PLATEAUS:
            pairs = [r[t] for r in got if t in r]
            held = np.array([h for _, h in pairs], float)
            arrived = np.abs(held - t) <= PLATEAU_TOLERANCE
            v = np.array([e for e, _ in pairs], float)[arrived]
            dropped[t] = int((~arrived).sum())
            if not len(v):
                line += f"{'-':>34}"
                continue
            zeros = int((v < 0.01).sum())
            rec[f"p{t:.0f}"] = {"median": float(np.median(v)),
                                "p10": float(np.percentile(v, 10)),
                                "p90": float(np.percentile(v, 90)),
                                "zeros": zeros, "n": int(len(v)),
                                "not_at_plateau": int((~arrived).sum())}
            line += (f"  {np.median(v):>8.2f}{np.percentile(v, 10):>8.2f}"
                     f"{np.percentile(v, 90):>8.2f}{f'{zeros}/{len(v)}':>8}")
        rows.append(rec)
        print(line, flush=True)

    print(f"\nexcluded per plateau, subjects the clamp did not bring within "
          f"{PLATEAU_TOLERANCE:.0f} mg/dL of target: "
          + ", ".join(f"{t:.0f} mg/dL {dropped.get(t, 0)}" for t in PLATEAUS))

    # The gain whose 55 mg/dL median lands closest to the human mean, among those keeping the
    # median inside the human interval at both plateaus.
    def inside(rec):
        return all(HUMAN_EGP[0] <= rec.get(f"p{t:.0f}", {}).get("median", -1) <= HUMAN_EGP[1]
                   for t in PLATEAUS)
    ok = [r for r in rows if inside(r)]
    pick = min(ok or rows,
               key=lambda r: abs(r.get("p55", {}).get("median", 99) - HUMAN_MEAN))
    print(f"\nclosest to the human mean while inside the interval at both plateaus: "
          f"gain {pick['gain']:.3f}")
    if not ok:
        print("  no gain keeps the median inside at both plateaus; reporting the closest on 55")
    json.dump({"human": {"range": list(HUMAN_EGP), "mean": HUMAN_MEAN},
               "n_subjects": len(subs), "rows": rows, "recommended": pick["gain"]},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
