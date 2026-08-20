"""Which configuration of this simulator is hardest to tell from real data?

Four mechanisms are available and switched off: the infusion site layer, the conservative
therapy settings, Visentin's diurnal sensitivity classes, and S2013's risk term. Each
improves the match on something and costs it on something else, and counting signatures
cannot settle that. A configuration that gains one and loses another has not obviously
improved.

So the question is put to a classifier instead. Take 24-hour windows of real DCLP3
closed-loop participants and of each candidate configuration, hold out whole subjects, and
ask how well the two can be separated. The configuration that is hardest to separate is the
one that looks most like real data on every axis at once, including axes nobody chose to
measure.

Read the result against the null, not against 0.5. Between-subject variation is large
enough that a classifier will separate any two groups of different people, so the null
permutes subject labels and the number that matters is how far the observed AUC sits above
what a random split of the same people achieves. `validation/replication.py` explains why
an earlier version of this test, which permuted windows, reported 0.85 for a cohort split
against itself.

The `default` row is the baseline every other row is read against. It does not exactly
reproduce the 0.709 recorded in `validation.replication.AGAINST_DCLP3`, which was measured
before `real_windows` existed: this gives 3,023 real windows where that run had 3,752. The
marginals agree to a fraction of a point, and every configuration here is scored against the
same real set, so the comparison between them is the part to trust.

Needs the DCLP3 data; see `docs/VALIDATION.md`. Each configuration is a full cohort run of
about half an hour, so `--config` runs one and the four can go in parallel.

    python examples/configuration_arbiter.py --config default
    python examples/configuration_arbiter.py --table
"""
import argparse, json, os

import numpy as np

from timsim import provenance, simulate_cohort
from timsim.population import names
from timsim.validation import dclp3, replication

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "docs")

BASE = ("physiology", "behaviour", "sensor")

# `isf_scale` 2.4 puts the median correction factor at 41.2 mg/dL per unit across the 34 adults
# this runs, against the 17.2 measured from their own physiology. DCLP3 participants ran 40.0
# across all 112 and 35.0 across the 67 in the calibration half, so the arm sits at the top of
# what real people ran rather than in the middle of it. The figures were 35.3 and 14.7 on the
# hundred-subject population and both moved when it grew to 600.
CONFIGS = {
    # Three layers, not four. This is the shipped configuration with the site layer taken off,
    # which is what makes it the comparator for `site`. It was labelled "the four default
    # layers" while `DEFAULT_LAYERS` held four including site, so a table keyed on these labels
    # read the three-layer arm as the shipped one.
    "default": (BASE, {}, "the default layers without infusion site failure"),
    "site": (BASE + ("site",), {}, "and infusion sites that fail"),
    "settings": (BASE, {"isf_scale": 2.4}, "and the settings real people run"),
    "both": (BASE + ("site",), {"isf_scale": 2.4}, "both"),
    "visentin": (BASE, {"si_pattern": "visentin"}, "and per-subject diurnal sensitivity"),
    "bare": ((), {}, "no layers at all, as a floor for the test"),
}


def run_config(key, subjects, days, seed=0, permutations=100):
    layers, kwargs, label = CONFIGS[key]
    results = simulate_cohort(subjects, days=days, seed=seed, layers=layers,
                              progress=False, **kwargs)
    out = replication.against_dclp3(results, permutations=permutations)
    # Keep the feature rows. Re-scoring against a corrected real reference is otherwise a
    # second cohort run, and the real reference has already been corrected once.
    sim, groups = replication.result_windows(results)
    np.savez_compressed(os.path.join(OUT, f"arbiter_{key}_windows.npz"),
                        x=sim, groups=groups)
    out.update({"config": key, "label": label, "layers": list(layers),
                "settings": kwargs, "days": days,
                "completed": int(sum(r.completed for r in results)),
                "n_subjects_run": len(results),
                "time_in_range": float(np.mean([r.time_in_range for r in results])),
                "time_above_180": float(np.mean([r.time_above_180 for r in results])),
                "time_below_70": float(np.mean([r.time_below_70 for r in results])),
                "provenance": provenance.stamp()})
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, f"arbiter_{key}.json"), "w"), indent=1)
    return out


def table():
    """Every configuration on disk that belongs to the experiment running now.

    The rows are read against each other, so mixing populations makes the table meaningless
    while leaving it complete and plausible. These files sit in `docs/` rather than
    `docs/measurements/`, which is where the rebuild archives, and this script is not part of
    the rebuild, so nothing clears them. On 19 August 2026 they were four days old and measured
    on a population that had since been regenerated. A row is now shown only if its stamp binds
    against the current one, and anything dropped is named.
    """
    now = provenance.stamp()
    have, stale = [], []
    for k in CONFIGS:
        path = os.path.join(OUT, f"arbiter_{k}.json")
        if not os.path.exists(path):
            continue
        stored = json.load(open(path)).get("provenance")
        if stored and all(stored.get(f) == now.get(f) for f in provenance.BINDING):
            have.append(k)
        else:
            stale.append(k)
    if stale:
        print(f"omitted, measured under another experiment: {', '.join(sorted(stale))}\n")
    if not have:
        print("no configuration on disk belongs to the current experiment")
        return
    data = {k: json.load(open(os.path.join(OUT, f"arbiter_{k}.json"))) for k in have}
    order = sorted(have, key=lambda k: data[k]["auc"])

    print("| Configuration | AUC | null p95 | excess | separated by | TIR % | above 180 % |")
    print("|---|---|---|---|---|---|---|")
    for k in order:
        d = data[k]
        print(f"| {k} | {d['auc']:.3f} | {d['null_auc_p95']:.3f} "
              f"| {d['excess_over_null']:+.3f} | {', '.join(d['top_features'][:2])} "
              f"| {d['time_in_range']:.1f} | {d['time_above_180']:.1f} |")
    print()
    print("Lower AUC is better: the configuration is harder to tell from real data.")
    print("Excess is AUC minus the null's 95th percentile, so a value at or below zero "
          "means\nthe classifier does no better than splitting the same people at random.")
    print()

    ref = data[order[0]]
    print(f"Marginals for the closest configuration, {order[0]}, medians per 24-hour window.")
    print("| Feature | DCLP3 | simulated | difference |")
    print("|---|---|---|---|")
    for name, (real, sim) in ref["marginals"].items():
        print(f"| {name} | {real:.2f} | {sim:.2f} | {sim - real:+.2f} |")
    print()
    for k in order:
        d = data[k]
        print(f"{k:>9}: {d['n_windows'][1]} windows from {d['n_subjects_run']} subjects, "
              f"{d['completed']} completed, against {d['n_windows'][0]} real windows "
              f"from {d['n_subjects'][0]} participants")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", choices=sorted(CONFIGS))
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--subjects", type=int, default=34)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--permutations", type=int, default=100)
    a = ap.parse_args()

    if not dclp3.available():
        raise SystemExit(f"DCLP3 not found at {dclp3.DCLP3_DIR}. "
                         "See docs/VALIDATION.md and set DCLP3_DIR.")
    if a.table:
        return table()
    subjects = names("adult")[:a.subjects]
    for key in ([a.config] if a.config else sorted(CONFIGS)):
        print(f"running {key} ...", flush=True)
        d = run_config(key, subjects, a.days, permutations=a.permutations)
        print(f"  AUC {d['auc']:.3f} against a null p95 of {d['null_auc_p95']:.3f}",
              flush=True)
    if a.config is None:
        print()
        table()


if __name__ == "__main__":
    main()
