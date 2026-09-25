"""Two checks on why the simulated autosens ratio rarely reads resistant.

`examples/sim_autosens.py` found the oref0 SMB arm reading resistant on 0.43 per cent of cycles
against 42 for the Commons users, with the ratio at exactly 1.0 on 70 per cent of cycles against
36. Before that is charged to the simulated person, two properties of the rig are checked.

The clamp. `LoopInputs.activity_u_per_hour` differences insulin on board and floors the result
at zero. AndroidAPS's `IobCobOref1Worker` reads activity from the insulin curve, and net of the
scheduled basal it can be negative while a loop withholds basal. The `unclamped` arm removes the
floor.

The classification. AndroidAPS counts a deviation only on a cycle it classifies as non-meal, and
pads a window short of 96 or 288 deviations with up to 18 zeros, so a person whose cycles are
mostly excluded reads exactly 1.0. The `kinds` arm counts the classification per cycle and, for
the excluded ones, which rule excluded them.

Seven panel subjects, 10 days on the bench seed, shipped configuration.

Result, 25 September 2026 (`docs/measurements/autosens_diagnostics.json`). Removing the clamp
moved the share reading resistant by at most 0.66 points in any subject, so it is not the
cause. Between 34 and 65 per cent of cycles were classified non-meal, which is enough to fill
the eight-hour window well past the padding; most exclusions were insulin on board above twice
the basal rate. The ratio sits at 1.0 because the deviations that do count are centred close
enough to zero that the padded zeros hold the median, which says the simulated person's fasting
glucose follows the insulin as the profile predicts where the real users' rises more than it
does.

    python examples/autosens_diagnostics.py
"""
import collections
import json
import multiprocessing as mp
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "autosens_diagnostics.json")
DAYS = 10
SUBJECTS = 7
KEEP = ("resistant_pct", "sensitive_pct", "at_one_pct", "p50", "tir")


def run(args):
    name, arm = args
    from timsim.controller import autosens as A
    from timsim.controller import inputs
    if arm == "unclamped":
        def activity(self, minute, include_basal=False):
            iob = self.iob_at if include_basal else self.bolus_iob
            return (iob(minute - 5.0) - iob(minute)) * 12.0
        inputs.LoopInputs.activity_u_per_hour = activity
    counts = collections.Counter()
    if arm == "kinds":
        original = A.Autosens._classify

        def classify(self, deviation, iob, current_basal):
            iob_rule = iob > 2.0 * float(current_basal)
            carry = self.uam
            original(self, deviation, iob, current_basal)
            counts[self.kind] += 1
            if self.kind == "uam":
                counts["uam_iob_above_2_basal" if iob_rule else
                       "uam_carryover" if carry else "uam_meal_start"] += 1
        A.Autosens._classify = classify
    from examples import sim_autosens
    _, _, out = sim_autosens.job((name, "shipped", seeds.BENCH, DAYS))
    row = {k: out[k] for k in KEEP}
    if counts:
        total = counts["csf"] + counts["uam"] + counts["non-meal"]
        row["classified_pct"] = {k: 100.0 * v / total for k, v in counts.items()}
    return name, arm, row


def main():
    from examples.panel import dosable
    subs = dosable(40)[:SUBJECTS]
    jobs = [(n, arm) for n in subs for arm in ("shipped", "unclamped", "kinds")]
    with mp.Pool(7) as pool:
        rows = pool.map(run, jobs, chunksize=1)
    got = {(n, a): r for n, a, r in rows}
    for n in subs:
        s, u, k = got[(n, "shipped")], got[(n, "unclamped")], got[(n, "kinds")]
        c = k["classified_pct"]
        print(f"{n}: resistant {s['resistant_pct']:.2f} clamped, {u['resistant_pct']:.2f} "
              f"unclamped; at 1.0 {s['at_one_pct']:.1f}; non-meal {c.get('non-meal', 0):.1f}, "
              f"csf {c.get('csf', 0):.1f}, uam {c.get('uam', 0):.1f} "
              f"(iob rule {c.get('uam_iob_above_2_basal', 0):.1f})")
    json.dump({"provenance": provenance.stamp(), "days": DAYS, "seed": seeds.BENCH,
               "subjects": subs,
               "per_run": [{"subject": n, "arm": a, **r} for (n, a), r in sorted(got.items())]},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
