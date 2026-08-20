"""What the layers do and what withdrawing meal announcement does, with the controller fixed.

The bench matrix runs the bare model at one meal scenario and the layered model at three, so the
cost of withdrawing announcement has only ever been measured with the layers switched on. It
could be a property of the simulated person or an interaction with the behaviour and site layers,
and nothing on disk could tell the two apart. `bench_matrix.py --benches baseline` measures both
arms at all three scenarios under one controller, and this reads the result.

Three things are reported per cohort, in this order.

Completion first, per arm, with the direction of every early stop, because every median below is
conditioned on survival and the arms do not lose the same subjects.

Then the two effects, each paired at the subject level. The layer effect is bare against layered
at a fixed announcement, so the announcement is held constant. The announcement effect is always
against never within one arm, so the layers are held constant. Reading them side by side is the
point: an announcement effect that appears only in the layered arm belongs to the rig rather than
to the person.

Then, for DCLP3 only, the same split by age. It is the only reference that can be cut this way.
The Commons carries no age at all and was matched on daily insulin alone. The CLOSE-IT reference
is a stand-in whose ages are drawn uniformly across the eligibility range, so splitting it would
be splitting invented data. The split is on each subject's age rather than on its class, because
the adolescent class spans 14 to 24 here and a split on the name would put a 24-year-old in the
paediatric group.

A subgroup is refused below `MIN_GROUP` rather than printed, because the floor a difference has
to clear scales with the group and a cohort of 84 and a subgroup of 22 do not share one.

    python examples/baseline_effects.py --file docs/measurements/baseline_trend.json
"""

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import numpy as np

from examples.bench_tables import MEASURES, _ci, _paired_median_difference, paired
from timsim import provenance, seeds

# `group_floor.py` refuses a group below twenty for the same reason. A subgroup smaller than this
# is reported as a count and not as a comparison.
MIN_GROUP = 20
AGE_BANDS = [("under 18", lambda a: a < 18), ("18 and over", lambda a: a >= 18)]


def load(path):
    d = json.load(open(path))
    idx = {}
    for r in d["runs"]:
        idx.setdefault(r["cohort"], {}).setdefault(r["bench"], {})[r["name"]] = r
    return d, idx


def completion(arms):
    print(f"  {'arm':16}{'completed':>12}{'ended low':>11}{'ended high':>12}")
    for name in sorted(arms):
        rows = list(arms[name].values())
        done = sum(1 for r in rows if r.get("completed"))
        low = sum(1 for r in rows if not r.get("completed") and (r.get("final_bg") or 0) < 70)
        high = sum(1 for r in rows if not r.get("completed") and (r.get("final_bg") or 0) > 180)
        print(f"  {name:16}{done:>7}/{len(rows):<4}{low:>11}{high:>12}")


def effect(arms, a, b, subjects, label, rng):
    """One paired comparison. Returns the rows so the caller can keep them."""
    keep = paired(arms, a, b, subjects, require_complete=True)
    if len(keep) < MIN_GROUP:
        print(f"\n  {label}: {len(keep)} subjects complete both arms, below the {MIN_GROUP} "
              f"this reports on. Not compared.")
        return None
    print(f"\n  {label}   paired over {len(keep)} subjects")
    print(f"  {'Measure':28}{a:>22}{b:>22}{'difference':>24}")
    out = {}
    for key, name, _ in MEASURES:
        va = np.array([arms[a][n][key] for n in keep], float)
        vb = np.array([arms[b][n][key] for n in keep], float)
        diff, dlo, dhi = _paired_median_difference(va, vb, rng)
        alo, ahi = _ci(va, rng)
        blo, bhi = _ci(vb, rng)
        out[key] = {"a": float(np.median(va)), "b": float(np.median(vb)),
                    "difference": float(diff), "interval": [float(dlo), float(dhi)],
                    "n": len(keep), "excludes_zero": bool(dlo > 0 or dhi < 0)}
        print(f"  {name:28}{np.median(va):>10.2f} [{alo:>5.2f},{ahi:>5.2f}]"
              f"{np.median(vb):>10.2f} [{blo:>5.2f},{bhi:>5.2f}]"
              f"{diff:>+11.2f} [{dlo:>+5.2f},{dhi:>+5.2f}]")
    return out


def real_ages():
    """Participant ages for DCLP3, or None when the release is not on this machine."""
    try:
        from timsim.validation import dclp3
        if not dclp3.available():
            return None
        return dclp3.ages_by_participant()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default=os.path.join(MEASUREMENTS, "baseline_trend.json"))
    ap.add_argument("--out", default=os.path.join(MEASUREMENTS, "baseline_effects.json"))
    a = ap.parse_args()

    d, idx = load(a.file)
    if d.get("bench_set") != "baseline":
        raise SystemExit(
            f"{a.file} records bench_set {d.get('bench_set')!r}. This reads the baseline set, "
            f"which measures the bare arm at all three meal scenarios; the matrix does not, and "
            f"the announcement effect cannot be attributed from it.")
    controllers = {p["controller"] for p in d.get("pairings", [])}
    print(f"{a.file}\ncontroller {', '.join(sorted(controllers))}, "
          f"{len(d['runs'])} runs, population {d['population'][:8]}\n")

    from timsim.population import cohort
    rng = np.random.default_rng(seeds.BENCH)
    report = {"file": os.path.basename(a.file), "controller": sorted(controllers),
              "provenance": provenance.stamp(), "cohorts": {}}

    for name in sorted(idx):
        arms = idx[name]
        subjects = sorted({n for arm in arms.values() for n in arm})
        print(f"\n{'=' * 78}\n{name}, {len(subjects)} subjects\n")
        completion(arms)
        rec = {"n": len(subjects), "layer_effect": {}, "announcement_effect": {}}
        for ann in ("always", "some", "never"):
            r = effect(arms, f"bare_{ann}", f"layered_{ann}", subjects,
                       f"layers, at announcement {ann}", rng)
            if r:
                rec["layer_effect"][ann] = r
        for arm in ("bare", "layered"):
            r = effect(arms, f"{arm}_always", f"{arm}_never", subjects,
                       f"announcement, always against never, {arm} arm", rng)
            if r:
                rec["announcement_effect"][arm] = r

        # The age split, on DCLP3 alone and on age rather than class.
        if name == "dclp3":
            traits = cohort.traits(subjects)
            print(f"\n{'-' * 78}\n  by age. Simulated ages come from the population; the real "
                  f"side is DCLP3's own participants.")
            reals = real_ages()
            for band, test in AGE_BANDS:
                grp = [n for n in subjects if test(traits[n][0])]
                line = f"\n  {band}: {len(grp)} simulated subjects"
                if reals:
                    line += f", {sum(1 for v in reals.values() if test(v))} real participants"
                print(line)
                if len(grp) < MIN_GROUP:
                    print(f"    below {MIN_GROUP}, so not compared. A subgroup this size carries "
                          f"a wider floor than the cohort and would read as a finding.")
                    continue
                r = effect(arms, "bare_some", "layered_some", grp,
                           f"layers at announcement some, {band}", rng)
                if r:
                    rec.setdefault("by_age", {})[band] = r
            if not reals:
                print("\n  the DCLP3 release is not on this machine, so only the simulated side "
                      "is split. Set DCLP3_DIR to split the real side as well.")
        report["cohorts"][name] = rec

    json.dump(report, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
