"""Whether transforming the safety score buys sensitivity, or shrinks signal and noise alike.

`ranking_power.json` puts the A/A detection floor at 0.231 across forty subjects. Inspecting the
per-subject A/A differences behind that figure suggested the noise was concentrated in a few
subjects and grew with a subject's LBGI level, which is what prompted this check. That inspection
was made on a per-subject table nothing stored, so its figures are not quoted here; nothing in
`docs/measurements/` holds them and they should not be cited until a producer writes them.

That invites a variance-stabilising transform, and the invitation is a trap. A square root takes
the floor from 0.231 to 0.130, which reads as nearly doubling the bench's sensitivity, and it does
nothing of the kind: it compresses the defects by the same factor it compresses the noise. The
only figure that decides anything is each defect's shift divided by the floor measured on the same
transform.

Written because the floor alone looked like an improvement and the check was cheap. A floor can be
made arbitrarily small by squashing the score, so any future proposal to change how the safety
score is aggregated should be judged on the ratios this prints rather than on the floor.

    python examples/ranking_transform.py
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from timsim.validation import ranking
from timsim.analysis import safety
from timsim.population import names
from timsim.therapy import titrate

TRANSFORMS = (("raw", lambda v: v), ("sqrt", np.sqrt), ("log1p", np.log1p))

def lbgi(res):
    return {r["name"]: r["lbgi"] for r in safety.cohort(res)}

if __name__ == "__main__":
    have = set(titrate.titrated_subjects())
    subs = [s for s in names("adult") if s in have][:40]
    ref = lbgi(ranking.run_variant(subs, days=14, seed=0))
    null = lbgi(ranking.run_variant(subs, days=14, seed=1000))
    arms = {}
    for label, defect in ranking.VARIANTS.items():
        if label in ("reference", "timid"):
            continue
        arms[label] = lbgi(ranking.run_variant(subs, days=14, seed=0, **defect))

    out = {}
    print(f"{'transform':>10}{'floor':>9}" + "".join(f"{k:>24}" for k in arms))
    print(f"{'':>19}" + "".join(f"{'shift  ratio':>24}" for _ in arms))
    for name, t in TRANSFORMS:
        shared = [n for n in ref if n in null]
        d = np.array([t(null[n]) - t(ref[n]) for n in shared], float)
        floor = ranking.detectable_shift(d, n_subjects=len(d))
        row, cells = {"floor": float(floor)}, []
        for label, arm in arms.items():
            sh = [n for n in ref if n in arm]
            delta = float(np.median([t(arm[n]) - t(ref[n]) for n in sh]))
            row[label] = {"shift": delta, "ratio": delta / floor}
            cells.append(f"{delta:>+9.3f} {delta/floor:>7.2f}   ")
        out[name] = row
        print(f"{name:>10}{floor:>9.3f}" + "".join(f"{c:>24}" for c in cells))
    print("\nratio is shift over floor; above 1.0 is detected. A transform helps only if the")
    print("ratio rises, since it shrinks the signal and the noise together.")
    from timsim import provenance
    out["provenance"] = provenance.stamp()
    dst = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "measurements", "ranking_transform.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"\nwrote {dst}")
