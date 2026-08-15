"""Choose the virtual subjects each real reference is compared against, and record the choice.

One cohort per reference population, built from that reference's own participants rather than
from whichever subjects are convenient, and written to disk so a later run uses the same
people rather than redrawing them.

What each reference allows is different, and the cohort can only be as good as that:

    DCLP3     age and recorded total daily insulin, per participant, so both are matched
    Commons   no demographics at all, so only the reconstructed daily requirement is matched
    CLOSE-IT  published summaries only, so a distribution is drawn from them rather than
              matched to participants

The distance achieved is recorded beside each cohort. A cohort matched to a reference the
population cannot reach should say so rather than look matched.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np
import pandas as pd

from timsim.population import cohort, names as all_names
from timsim.therapy import titrate

OUT = os.path.join(MEASUREMENTS, "cohorts.json")
N = 25
DCLP3_DIR = os.path.expanduser(os.environ.get("DCLP3_DIR", "~/Downloads/dclp3/Data Files"))


def dclp3_traits():
    """(age, total daily insulin) for every closed-loop participant of DCLP3."""
    def read(name):
        d = pd.read_csv(os.path.join(DCLP3_DIR, name), sep="|", encoding="utf-16")
        d.columns = [c.strip() for c in d.columns]
        return d

    roster, screen, pump = read("PtRoster_a.txt"), read("DiabScreening_a.txt"), \
        read("InsulinPumpSettings_a.txt")
    closed = set(roster.loc[roster.trtGroup == "CLC", "PtID"])
    age = pd.to_numeric(screen.set_index("PtID")["AgeAtEnrollment"], errors="coerce")
    tdd = pd.to_numeric(pump[pump.PtID.isin(closed)].groupby("PtID")["CurrTotInsDaily"].median(),
                        errors="coerce")
    out = [(age.get(p), tdd.get(p)) for p in sorted(closed)]
    return [(float(a), float(t)) for a, t in out
            if pd.notna(a) and pd.notna(t) and t > 0]


def commons_traits():
    """(age, requirement) for Commons users, with age unavailable and held constant.

    The export carries no demographics. Age is passed as a constant and given zero weight so
    it cannot drive the match, which leaves the reconstructed daily requirement doing all of
    the work. What that costs is recorded in the report: the subjects whose requirement fits
    these users are younger than the users are likely to be, because the generated adults all
    need more insulin than the median Commons user does.
    """
    req = json.load(open(os.path.join(MEASUREMENTS, "commons_requirement.json")))["users"]
    return [(35.0, float(r["tdd"])) for r in req]


def close_it_traits(n=75, seed=0):
    """A cohort standing in for CLOSE-IT, drawn from its published summaries.

    CLOSE-IT randomised 75 adults aged 18 to 70 on an oref-derived system. Participant-level
    data is not published, so nothing here is matched to a person: ages are drawn uniformly
    across the eligibility range and the requirement is drawn from the Commons distribution,
    that being the closest real population running the same algorithm family. This cohort is
    a stand-in and any comparison using it carries that.
    """
    rng = np.random.default_rng(seed)
    req = json.load(open(os.path.join(MEASUREMENTS, "commons_requirement.json")))["users"]
    tdd = np.array([r["tdd"] for r in req], float)
    return [(float(a), float(t)) for a, t in
            zip(rng.uniform(18, 70, n), rng.choice(tdd, n, replace=True))]


def describe(names, label):
    tr = cohort.traits(names)
    age = np.array([v[0] for v in tr.values()], float)
    tdi = np.array([v[1] for v in tr.values()], float)
    return {"cohort": label, "n": len(names), "subjects": list(names),
            "age_median": float(np.median(age)),
            "age_p10_p90": [float(np.percentile(age, 10)), float(np.percentile(age, 90))],
            "fraction_under_18": float(np.mean(age < 18)),
            "tdi_median": float(np.median(tdi)),
            "tdi_iqr": [float(np.percentile(tdi, 25)), float(np.percentile(tdi, 75))]}


def reference_summary(pairs, label, with_age=True):
    a = np.array([p[0] for p in pairs], float)
    t = np.array([p[1] for p in pairs], float)
    out = {"reference": label, "n": len(pairs),
           "tdd_median": float(np.median(t)),
           "tdd_iqr": [float(np.percentile(t, 25)), float(np.percentile(t, 75))]}
    if with_age:
        out.update({"age_median": float(np.median(a)),
                    "fraction_under_18": float(np.mean(a < 18))})
    return out


def main():
    specs = [
        ("dclp3", dclp3_traits(), (1.0, 1.0), None, True),
        ("commons", commons_traits(), (0.0, 1.0), None, False),
        ("close_it", close_it_traits(), (1.0, 1.0), None, True),
    ]
    report = {"n_per_cohort": N, "population": titrate.population_fingerprint(),
              "cohorts": {}, "references": {}}
    union = set()
    for label, pairs, weights, subjects, with_age in specs:
        names, info = cohort.matched_on_traits(pairs, n=N, seed=0, subjects=subjects,
                                               weights=weights)
        d = describe(names, label)
        d["match"] = info
        d["matched_on"] = "age and daily insulin" if weights[0] else "daily insulin only"
        report["cohorts"][label] = d
        report["references"][label] = reference_summary(pairs, label, with_age)
        union |= set(names)
        ref = report["references"][label]
        print(f"\n{label}: {len(names)} subjects, matched on {d['matched_on']}")
        print(f"  reference   n={ref['n']:4d}  TDD median {ref['tdd_median']:6.1f}"
              + (f"  age median {ref['age_median']:5.1f}  under 18 "
                 f"{100*ref['fraction_under_18']:4.1f}%" if with_age else "  age unknown"))
        print(f"  cohort      n={d['n']:4d}  TDI median {d['tdi_median']:6.1f}"
              f"  age median {d['age_median']:5.1f}  under 18 "
              f"{100*d['fraction_under_18']:4.1f}%")
        print(f"  match distance median {info['median_distance']:.3f}, "
              f"p90 {info['p90_distance']:.3f}")

    report["union"] = sorted(union)
    print(f"\nunion across cohorts: {len(union)} subjects to titrate")
    json.dump(report, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
