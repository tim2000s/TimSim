"""What cohort the ranking check needs, measured rather than extrapolated.

`docs/VALIDATION.md` level 7 records that a 30 per cent insulin sensitivity error shifts paired
LBGI by +0.17 against a detectable 0.176 at twelve subjects, missing by 0.006, and that "thirty-
four subjects would resolve a shift of 0.105 and the full hundred 0.061". Those figures divide a
twelve-subject standard deviation by the square root of a larger cohort, which assumes the spread
does not depend on which subjects are in it.

It does. Run at forty, the A/A standard deviation is 0.522 against 0.218 at twelve, so the
detectable shift rises to 0.231 rather than falling to 0.096. Adding subjects adds noisier ones
faster than the square root absorbs them.

The effect size is not fixed either: the same defect reads +0.17 at twelve subjects and +0.26 at
forty. Signal and noise are both properties of the panel, so a sizing statement has to be measured
at each size rather than projected from one.

This runs the visibility check across cohort sizes and reports the floor, the spread behind it and
each defect's shift, so a null result from this bench can be read against the size it was measured
at. That is the number somebody treating a null as reassurance actually needs.

    python examples/ranking_power.py --sizes 12 20 40
"""
import argparse
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance
from timsim.validation import ranking
from timsim.population import names
from timsim.therapy import titrate

OUT = os.path.join(MEASUREMENTS, "ranking_power.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sizes", nargs="+", type=int, default=[12, 20, 40])
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    have = set(titrate.titrated_subjects())
    pool = [s for s in names("adult") if s in have]
    rec = {"provenance": provenance.stamp(), "days": a.days, "rows": []}

    print(f"{'n':>5}{'A/A sd':>9}{'floor':>8}{'per-subject noise':>19}"
          f"{'smallest defect':>17}{'pass':>6}")
    for n in a.sizes:
        subs = pool[:n]
        # The floor and the spread come from the same A/A arm the check uses, recomputed here
        # so the number reported is the one the verdict rests on rather than a second estimate.
        ref = ranking.run_variant(subs, days=a.days, seed=0)
        null = ranking.run_variant(subs, days=a.days, seed=1000)
        d = ranking.paired_delta(ref, null)
        sd = float(np.asarray(d, float).std(ddof=1))
        floor = ranking.detectable_shift(d, n_subjects=len(d))
        r = ranking.check_each_defect_is_visible(subs, days=a.days)
        shifts = {}
        for part in r["note"].split(";")[0].replace("paired median LBGI shift: ", "").split(", "):
            k, v = part.rsplit(" ", 1)
            shifts[k] = float(v)
        smallest = min(abs(v) for v in shifts.values())
        rec["rows"].append({"n": len(subs), "aa_sd": sd, "floor": floor,
                            "per_subject_noise": float(np.abs(d).mean()),
                            "shifts": shifts, "smallest": smallest, "pass": bool(r["pass"])})
        print(f"{len(subs):>5}{sd:>9.3f}{floor:>8.3f}{np.abs(d).mean():>19.3f}"
              f"{smallest:>17.3f}{'yes' if r['pass'] else 'NO':>6}")

    print(f"\n{'n':>5}" + "".join(f"{k:>24}" for k in rec["rows"][0]["shifts"]))
    for row in rec["rows"]:
        print(f"{row['n']:>5}" + "".join(f"{row['shifts'][k]:>24.2f}"
                                         for k in rec["rows"][0]["shifts"]))

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
