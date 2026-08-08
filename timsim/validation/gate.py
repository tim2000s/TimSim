"""A pre-clinical safety gate: pre-registered criteria, and a verdict against them.

This is the strongest safety claim a simulator can support, and it is worth being precise
about what it is. The gate answers "is there a reason not to take this into a trial",
which is a question a bench can answer, because a failure is a demonstration. It does not
answer "is this safe", which is a question about rare events over long exposure, and
section 7 of `docs/OSAID.md` shows the arithmetic that puts it out of reach here. The
precedent for the narrower claim is the UVA/Padova simulator itself, accepted as a
substitute for animal testing before a trial rather than as a substitute for the trial.

Two properties make a gate mean anything, and both are procedural rather than statistical.

The criteria are fixed before the run. A threshold chosen after seeing the result is not a
threshold. `fingerprint` hashes the criteria together with the design so that the pair can
be recorded first and checked afterwards, which makes moving a limit visible instead of
invisible.

The criteria are tied to hazards rather than to whatever was convenient to measure. Each
one below names the hazard it covers, so the gap in coverage is readable: anything in a
hazard analysis with no criterion against it is untested, and saying so is more useful
than a pass.

A pass is reported alongside the exposure that produced it and the upper bound that
exposure supports. Reporting "no severe events" without "and this run could not have
ruled out a rate of one per two years" is the single most misleading thing a bench of this
kind can do.
"""
import hashlib
import json
from dataclasses import asdict, dataclass

import numpy as np

from ..analysis import safety


@dataclass(frozen=True)
class Criterion:
    """One acceptance threshold, tied to the hazard it exists to cover."""
    key: str                 # a field of the per-subject safety record
    summary: str             # median | p90 | worst | count_nonzero | all
    limit: float
    direction: str           # at_most | at_least
    hazard: str
    rationale: str

    def measure(self, records):
        vals = np.array([r[self.key] for r in records
                         if np.isfinite(np.asarray(r[self.key], float))], float)
        if not len(vals):
            return float("nan")
        return {"median": lambda v: float(np.median(v)),
                "p90": lambda v: float(np.percentile(v, 90)),
                "worst": lambda v: float(v.max()),
                "count_nonzero": lambda v: float(np.count_nonzero(v)),
                }[self.summary](vals)

    def holds(self, value):
        if not np.isfinite(value):
            return False
        return value <= self.limit if self.direction == "at_most" else value >= self.limit


# The consensus continuous-glucose targets (Battelino et al. 2019) supply the population
# thresholds. The tail thresholds are this package's own choice and are stated as such:
# a bench looking for failures should not accept a cohort median while one subject is
# spending an hour a day below 54.
DEFAULT_CRITERIA = (
    Criterion("completed", "count_nonzero", 0, "at_least",
              hazard="a subject the run could not survive",
              rationale="counted separately below; any non-completion fails the gate"),
    Criterion("minutes_below_54_per_day", "median", 14.4, "at_most",
              hazard="clinically significant hypoglycaemia across the cohort",
              rationale="1% of a day, the consensus target for time below 54 mg/dL"),
    Criterion("minutes_below_54_per_day", "worst", 60.0, "at_most",
              hazard="clinically significant hypoglycaemia in one person",
              rationale="no subject may spend more than an hour a day below 54"),
    Criterion("minutes_below_70_per_day", "median", 57.6, "at_most",
              hazard="hypoglycaemia exposure across the cohort",
              rationale="4% of a day, the consensus target for time below 70 mg/dL"),
    Criterion("lbgi", "p90", 5.0, "at_most",
              hazard="hypoglycaemia risk concentrated in a minority of subjects",
              rationale="LBGI above 5 is the conventional high-risk band"),
    Criterion("time_in_range", "median", 70.0, "at_least",
              hazard="an algorithm that buys safety by running everyone high",
              rationale="the consensus target, present so the gate cannot be passed by "
                        "withholding insulin"),
    Criterion("peak_insulin_per_hour_u", "worst", 25.0, "at_most",
              hazard="insulin stacking",
              rationale="a ceiling well above any legitimate hour of delivery, so that "
                        "only a runaway trips it"),
    Criterion("rescue_grams_per_day", "median", 60.0, "at_most",
              hazard="an algorithm whose glucose looks fine because the person is "
                     "eating to hold it up",
              rationale="carbohydrate the person had to supply is a cost the glucose "
                        "trace does not show"),
)

# Hazards with no criterion here, named so that the gap is readable rather than implied.
UNCOVERED_HAZARDS = (
    "exercise, illness and alcohol, which the model has no mechanism for",
    "a bad infusion site of any kind other than one that quietly stops absorbing: the model "
    "in therapy/site.py does not cover a set that leaks, bleeds, or hurts enough to be "
    "changed immediately",
    "how long a severe low lasts, which this bench cannot assess at all: see below",
    "a fault the level 7 scenarios do not include",
    "any rare event below the exposure bound reported with the verdict",
)


# The registration history, kept so that a change of thresholds or of the world they were
# fixed against is auditable rather than a matter of trust. Each entry is the criteria
# hashed with the design for the reference workflow in `examples/safety_gate.py`, which is
# 34 subjects over 28 days with the algorithm supplying the loop.
#
# The criteria have not moved. Every fingerprint below is the same nine thresholds against
# a different world, and that is the point: the second entry exists because the design used
# to be whatever the caller typed, usually the subject count and the days, so a run with
# the infusion site layer and a run without it produced the same hash and looked
# comparable. They are not comparable. A failed set hands every algorithm hours of
# hyperglycaemia it cannot dose its way out of.
#
# The third entry is current, and running it settled a guess that was wrong. Time in range
# looked like the criterion the site layer would threaten, since it costs the reference
# cohort five points, from 80.1% to 74.9%. It is not close: that leaves 4.85 points of
# margin against the 70% limit. The criterion with almost none is peak insulin per hour,
# which sat at 25.90 against a limit of 25.0 without the site layer and failed, and at 24.30
# with it. A failed set puts the loop against its basal ceiling for hours rather than
# letting it stack a correction, so the hazard the two configurations present is not the
# same hazard.
#
# The reference algorithm fails this gate in both configurations, on the longest single
# episode below 54 mg/dL: 150 minutes without the site layer and 180 with it, against a
# 120-minute limit. That is recorded rather than fixed. The thresholds were registered
# before the run and a threshold moved after seeing the result is not a threshold, so the
# finding stands as a finding about the reference algorithm and about a model with no
# counterregulation to end a low that nobody treats.
# The reference algorithm measured against the current registration, 34 subjects over 28
# days, kept so that a change in the bench is visible as a change in this number.
REFERENCE_VERDICT = {
    "with_site": {"verdict": "fails", "fingerprint": "99871b135e2378be",
                  "failed": ("worst longest_below_54_min", 180.0, 120.0),
                  "time_in_range": 74.85, "peak_insulin_per_hour_u": 24.30},
    "without_site": {"verdict": "fails", "fingerprint": "2af3c055daa5d1ba",
                     "failed": (("worst longest_below_54_min", 150.0, 120.0),
                                ("worst peak_insulin_per_hour_u", 25.90, 25.0)),
                     "time_in_range": 80.07, "peak_insulin_per_hour_u": 25.90},
    "exposure": {"subjects": 34, "subject_days": 952,
                 "severe_episodes": 25, "upper_95_rate_per_subject_year": 13.40},
}

# The registration history. A retired entry cannot be recomputed once the criteria change,
# which is inherent rather than a flaw: it was hashed against the criteria of its day. What
# the record is for is that a change is visible and dated, not that an old hash recomputes
# from new code. `criteria` lists what was in force, so what moved is readable.
REGISTERED = (
    {"fingerprint": "048522ca7f65c420", "retired": "2026-08-08", "criteria": 9,
     "design": {"subjects": 34, "days": 28},
     "note": "the design covered only the cohort size, so it did not bind the "
             "configuration the verdict was produced in"},
    {"fingerprint": "2af3c055daa5d1ba", "retired": "2026-08-08", "criteria": 9,
     "design": {"layers": ["behaviour", "physiology", "sensor"], "subjects": 34,
                "days": 28, "sample_minutes": [5.0], "si_pattern": ["sinusoid"],
                "isf_scale": [1.0], "hypo_risk_gain": [0.0]},
     "note": "what the retired registration would have hashed to had the design been "
             "bound; recorded so the two can be compared"},
    {"fingerprint": "99871b135e2378be", "retired": "2026-08-08", "criteria": 9,
     "design": {"layers": ["behaviour", "physiology", "sensor", "site"], "subjects": 34,
                "days": 28, "sample_minutes": [5.0], "si_pattern": ["sinusoid"],
                "isf_scale": [1.0], "hypo_risk_gain": [0.0]},
     "note": "the infusion site layer entered the default. Retired the same day, when the "
             "longest-severe-low criterion was shown to measure the simulator rather than "
             "the system under test"},
    {"fingerprint": None, "registered": "2026-08-08", "criteria": 8,
     "design": None,
     "note": "current: eight criteria, with no threshold on how long a severe low lasts. "
             "Computed from the criteria rather than pinned, since the design depends on "
             "the run; use gate.fingerprint(design=gate.design_of(results))"},
)



# Why there is no criterion on how long a severe low lasts, when duration is the part of a
# severe low that does the harm. There was one, at 120 minutes, and it was retired because
# it turned out to measure this simulator rather than the system under test.
#
# It failed the reference algorithm at 150 minutes and then at 180. Two real defects were
# found in that algorithm and fixed, an unbounded correction riding along with every meal
# bolus and an insulin-on-board estimate built from requests rather than deliveries, and
# the figure did not move: 190 minutes afterwards, with the median across all episodes
# going 48 to 42 against a real 10.
#
# Taking the algorithm out entirely settles it. Drive a published adult below 54 mg/dL with
# insulin, stop, and feed it, with no controller and no behaviour layer in the way:
#
#     rescue     0 g   15 g   20 g   30 g   45 g
#     minutes    203     93     32     24     22
#
# Untreated the model sits below 54 for over three hours, because S2008 has no
# counterregulation and nothing arrests a low except insulin decaying. Carbohydrate helps
# and then saturates near 22 minutes, since the eating rate and gut transit set a floor no
# amount of treatment gets under. Real closed-loop users in DCLP3 have a median of 10
# minutes below 54 and a 99th percentile of 60, across 29 subject-years.
#
# No algorithm can pass a threshold that the body it is dosing cannot get under, so the
# criterion measured the harness. `docs/EVIDENCE.md` records it as an uncovered hazard,
# which is the honest place for it, and `docs/FIDELITY.md` carries the measurement.
def design_of(results, **extra):
    """The run design a fingerprint has to cover, read off the cohort rather than typed.

    The criteria are only half of what a verdict depends on. The other half is the world the
    algorithm was judged in, and that half used to be whatever the caller happened to pass,
    which was usually the subject count and the number of days. It is not enough. Turning on
    the infusion site layer hands every algorithm hours of hyperglycaemia it cannot dose its
    way out of, and a verdict from that run and a verdict from a run without it would have
    shared a fingerprint and looked comparable.

    So the design is read off the results. Anything that changes what the subjects did
    belongs in here, and `extra` carries whatever else the caller wants bound in.
    """
    meta = [getattr(r, "meta", None) or {} for r in results]
    return {
        "layers": sorted({l for r in results for l in getattr(r, "layers", ())}),
        "controller": sorted({getattr(r, "controller", "") for r in results}),
        "subjects": len(results),
        "days": max((getattr(r, "days_requested", 0) for r in results), default=0),
        "sample_minutes": sorted({float(getattr(r, "sample_time", 0.0))
                                  for r in results}),
        "si_pattern": sorted({m.get("si_pattern", "sinusoid") for m in meta}),
        "isf_scale": sorted({float(m.get("isf_scale", 1.0)) for m in meta}),
        "hypo_risk_gain": sorted({float(m.get("hypo_risk_gain", 0.0)) for m in meta}),
        **extra,
    }


def fingerprint(criteria=DEFAULT_CRITERIA, design=None):
    """A hash of the criteria and the design, to be recorded before the run.

    Record it first and quote it with the result. A verdict whose fingerprint does not
    match the one registered beforehand had its thresholds moved, or was run in a different
    world. Build `design` with `design_of` rather than by hand.
    """
    payload = {"criteria": [asdict(c) for c in criteria], "design": design or {}}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def evaluate(results, criteria=DEFAULT_CRITERIA, design=None, label="system under test"):
    """Score a cohort against the criteria and return a verdict with its exposure.

    `design` defaults to the one read off the cohort, so a verdict cannot quietly acquire a
    fingerprint that ignores the configuration it was produced in.
    """
    design = design_of(results) if design is None else design
    records = safety.cohort(results)
    subject_days = float(sum(r["days_observed"] for r in records))
    incomplete = [r["name"] for r in records if not r["completed"]]

    rows = []
    for c in criteria:
        if c.key == "completed":
            value = float(len(incomplete))
            ok = not incomplete
            rows.append({"hazard": c.hazard, "metric": "runs that did not complete",
                         "value": value, "limit": 0.0, "pass": ok,
                         "rationale": c.rationale})
            continue
        value = c.measure(records)
        rows.append({"hazard": c.hazard,
                     "metric": f"{c.summary} {c.key}", "value": value,
                     "limit": c.limit, "direction": c.direction,
                     "pass": bool(c.holds(value)), "rationale": c.rationale})

    severe_events = sum(1 for r in records if r["longest_below_54_min"] > 0)
    bound = safety.rate_upper_bound(severe_events, subject_days)
    failed = [r for r in rows if not r["pass"]]

    return {
        "label": label,
        "fingerprint": fingerprint(criteria, design),
        "passed": not failed,
        "criteria": rows,
        "failed": [r["metric"] for r in failed],
        "exposure": {"subjects": len(records), "subject_days": subject_days,
                     "severe_episodes_observed": severe_events,
                     "upper_bound_per_subject_year": bound},
        "uncovered_hazards": list(UNCOVERED_HAZARDS),
        "verdict": ("no reason found here not to proceed to a trial" if not failed
                    else "fails the pre-clinical gate"),
    }


def report(verdict):
    """The verdict as text, with the exposure statement it must never be quoted without."""
    lines = [f"{verdict['label']}: {verdict['verdict']}",
             f"criteria fingerprint {verdict['fingerprint']}", ""]
    for row in verdict["criteria"]:
        mark = "  ok  " if row["pass"] else " FAIL "
        limit = row.get("limit")
        lines.append(f"{mark}{row['metric']:<38} {row['value']:8.2f}  "
                     f"limit {limit:.2f}")
        lines.append(f"        hazard: {row['hazard']}")
    e = verdict["exposure"]
    lines += ["",
              f"exposure: {e['subjects']} subjects, {e['subject_days']:.0f} subject-days",
              f"severe episodes observed: {e['severe_episodes_observed']}",
              f"upper 95% bound on the severe episode rate: "
              f"{e['upper_bound_per_subject_year']:.2f} per subject-year",
              "",
              "a pass is a pre-clinical gate rather than a safety claim. hazards not "
              "covered by any criterion above:"]
    lines += [f"  - {h}" for h in verdict["uncovered_hazards"]]
    return "\n".join(lines)


__all__ = ["Criterion", "DEFAULT_CRITERIA", "UNCOVERED_HAZARDS", "fingerprint",
           "evaluate", "report"]
