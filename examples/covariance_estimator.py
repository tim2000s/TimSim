"""Is the covariance shrinkage in `population/generate.py` doing damage?

Two charges have been levelled at it. The first is that shrinking towards the diagonal
attenuates the correlation between basal endogenous glucose production and insulin
sensitivity, which is physiologically meaningful, from the +0.79 the published adults show
to the +0.30 the generated adults realise. The second is that it is responsible for the
population carrying about 45 per cent of the real between-subject spread in mean glucose.

The second charge is arithmetic and answerable on inspection: `_shrunk_cov` preserves the
diagonal exactly and multiplies only the off-diagonal entries, so every marginal standard
deviation is identical at every shrinkage intensity. This script measures it anyway, because
the claim has been made in writing more than once.

The first charge needs an interval. A correlation estimated from ten subjects is a weak
statement, and the question is whether the shrunk value is distinguishable from the published
one rather than whether it differs from it. Fisher's transform gives the interval. The script
also reports the analytic shrinkage intensity that minimises expected squared error towards a
diagonal target (Schaefer and Strimmer 2005), which is what the 0.50 in use should be judged
against, and the proportion of the sample correlation matrix that survives a significance
threshold at n = 10, which is what any shrinkage intensity is a response to.

Parameter arithmetic only. Nothing here integrates the model, so it can run beside a rebuild.

    python examples/covariance_estimator.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
from math import atanh, tanh, sqrt

import numpy as np
import pandas as pd
import simglucose

from timsim import provenance
from timsim.population import derive, generate

OUT = os.path.join(MEASUREMENTS, "covariance_estimator.json")
VPOP = os.path.join(REPO, "timsim", "population", "params", "vpop_params.csv")
PUBLISHED = os.path.join(os.path.dirname(simglucose.__file__), "params", "vpatient_params.csv")

REPORT = os.path.join(REPO, "timsim", "population", "params", "vpop_report.json")

# The intensity the population in use was actually built with, rather than the current default
# of `generate.generate`. They agree today, and a comparison against a population built under a
# different one would be reporting a number the population does not have.
def _alpha_in_use():
    if os.path.exists(REPORT):
        recorded = json.load(open(REPORT)).get("shrinkage")
        if recorded is not None:
            return float(recorded), "vpop_report.json"
    import inspect
    default = inspect.signature(generate.generate).parameters["shrinkage"].default
    return float(default), "generate.generate default"


ALPHA, ALPHA_SOURCE = _alpha_in_use()

Z975 = 1.959963984540054

# The critical value of a Pearson correlation at n = 10, two-sided, 5 per cent. Reported so the
# count of surviving correlations can be read against the 5 per cent expected under the null.
CRIT_N10 = 0.6319


def fisher_interval(r, n, z=Z975):
    """Two-sided interval on a correlation, on the transformed scale then back."""
    if n <= 3 or abs(r) >= 1.0:
        return (float("nan"), float("nan"))
    half = z / sqrt(n - 3.0)
    return tanh(atanh(r) - half), tanh(atanh(r) + half)


def optimal_diagonal_shrinkage(z):
    """The intensity minimising expected squared error towards a diagonal target.

    Schaefer and Strimmer's analytic estimator. The numerator is the summed sampling variance
    of the off-diagonal covariance entries and the denominator their summed squared magnitude,
    so a matrix whose off-diagonals are mostly noise returns an intensity near one.
    """
    n, p = z.shape
    x = z - z.mean(0)
    s = x.T @ x / (n - 1.0)
    outer = np.einsum("ki,kj->kij", x, x)
    var_s = outer.var(0, ddof=1) * n / (n - 1.0) ** 2
    off = ~np.eye(p, dtype=bool)
    denominator = float((s[off] ** 2).sum())
    if denominator <= 0.0:
        return float("nan")
    return float(np.clip(var_s[off].sum() / denominator, 0.0, 1.0))


def main():
    free = list(derive.FREE)
    i, j = free.index("EGPb"), free.index("Vmx")
    published = pd.read_csv(PUBLISHED)

    out = {"alpha_in_use": float(ALPHA), "alpha_source": ALPHA_SOURCE,
           "free_parameters": len(free),
           "pair": ["EGPb", "Vmx"], "critical_r_n10": CRIT_N10,
           "provenance": provenance.stamp(), "classes": {}}

    centred = []
    for cls in generate.CLASSES:
        sub = published[published["Name"].str.startswith(cls)]
        z = generate._to_z(sub)
        centred.append(z - z.mean(0))
        cov = np.cov(z, rowvar=False)
        corr = np.corrcoef(z, rowvar=False)
        r = float(corr[i, j])
        lo, hi = fisher_interval(r, len(sub))
        shrunk = (1.0 - ALPHA) * r

        upper = corr[np.triu_indices_from(corr, 1)]
        row = {
            "n": int(len(sub)),
            "covariance_rank": int(np.linalg.matrix_rank(cov)),
            "r_published": r,
            "r_interval": [lo, hi],
            "r_after_shrinkage": shrunk,
            "shrunk_inside_published_interval": bool(lo <= shrunk <= hi),
            "optimal_diagonal_shrinkage": optimal_diagonal_shrinkage(z),
            "correlations_total": int(upper.size),
            "correlations_beyond_critical": int((np.abs(upper) > CRIT_N10).sum()),
        }
        row["correlations_beyond_critical_fraction"] = (
            row["correlations_beyond_critical"] / row["correlations_total"])
        out["classes"][cls] = row

    pooled = np.vstack(centred)
    out["pooled"] = {
        "n": int(pooled.shape[0]),
        "note": "class means removed before pooling, so this is within-class covariation",
        "covariance_rank": int(np.linalg.matrix_rank(np.cov(pooled, rowvar=False))),
        "r_published": float(np.corrcoef(pooled, rowvar=False)[i, j]),
    }

    # The diagonal claim, measured rather than asserted. If the generated population is
    # present its realised marginals are compared with the published ones parameter by
    # parameter; the ratio is bounded away from one only by the truncation in `_draw`.
    if os.path.exists(VPOP):
        vpop = pd.read_csv(VPOP)
        realised = {}
        for cls in generate.CLASSES:
            pub_z = generate._to_z(published[published["Name"].str.startswith(cls)])
            gen_z = generate._to_z(vpop[vpop["Name"].str.startswith(cls)])
            ratio = gen_z.std(0, ddof=1) / pub_z.std(0, ddof=1)
            realised[cls] = {
                "n": int(len(gen_z)),
                "marginal_sd_ratio_min": float(ratio.min()),
                "marginal_sd_ratio_median": float(np.median(ratio)),
                "marginal_sd_ratio_max": float(ratio.max()),
                "r_realised": float(np.corrcoef(gen_z, rowvar=False)[i, j]),
            }
        out["generated"] = realised
    else:
        out["generated"] = None

    os.makedirs(MEASUREMENTS, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")

    for cls, row in out["classes"].items():
        print(f"{cls:11s} r={row['r_published']:+.3f} "
              f"[{row['r_interval'][0]:+.3f}, {row['r_interval'][1]:+.3f}] "
              f"shrunk={row['r_after_shrinkage']:+.3f} "
              f"inside={row['shrunk_inside_published_interval']} "
              f"alpha*={row['optimal_diagonal_shrinkage']:.3f} "
              f"signal={row['correlations_beyond_critical']}/{row['correlations_total']}")
    print(f"pooled     r={out['pooled']['r_published']:+.3f} at n={out['pooled']['n']}")
    if out["generated"]:
        for cls, row in out["generated"].items():
            print(f"{cls:11s} generated n={row['n']:4d} "
                  f"marginal sd ratio {row['marginal_sd_ratio_min']:.2f} to "
                  f"{row['marginal_sd_ratio_max']:.2f} "
                  f"(median {row['marginal_sd_ratio_median']:.2f}), "
                  f"r={row['r_realised']:+.3f}")


if __name__ == "__main__":
    main()
