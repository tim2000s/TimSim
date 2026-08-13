"""Titrating a subject's settings, and refusing to benchmark on settings nobody titrated.

A controller cannot be judged on a bench whose settings it was never given a fair version of.
This package's subjects carry a correction factor and a carbohydrate ratio measured from their
own physiology, which is a quantity no real person has access to: real settings are arrived at
by titration against the person's own record, and they end up conservative relative to what the
body would take. Measured across these subjects the physiological correction factor has a
median of 15.1 mg/dL per unit against the 35 that DCLP3 participants ran, so an algorithm
handed the physiological value is being asked to dose about twice as hard as it would for a
real user.

The response is a procedure rather than a constant. Each subject's settings are weakened until
its own record clears the consensus hypoglycaemia floors, and no further, because settings
looser than necessary cost time in range. That is what a careful titration does, and it leaves
every subject with settings whose provenance is a measurement on that subject rather than a
number chosen once for the cohort.

Two properties of the procedure matter more than the numbers it returns.

Titration runs under a fixed reference regimen rather than under the algorithm being tested.
Tuning a bench's settings with the controller under test in the loop lets a controller that
provokes hypoglycaemia be rewarded with weaker settings, which is the bench flattering the
thing it is meant to judge. A person arrives at their settings and then chooses an algorithm,
so the bench does the same.

The regimen has to be one that produces hypoglycaemia, which rules out the open-loop arm. Run
there, 13 of 15 completing subjects clear both floors at the physiological settings and the
procedure returns its own starting point, because that regimen spends 0.25 per cent of time
below 70 mg/dL against a real 4.07 and so never exercises the settings at all. Every subject
misses time in range and time above 250 mg/dL there instead. The built-in correction loop
produces lows at a realistic rate and is not among the systems being ranked, so it is what
titration runs under.

The ladder searches upwards from the physiological settings and never below them. Settings
stronger than the body's own response ask for more insulin than the physiology can absorb, so
a subject that runs high at a scale of 1.0 is telling us about the model rather than about its
settings, and the procedure reports that rather than searching for a scale that cannot exist.

The thresholds are the international consensus targets (Battelino et al., Diabetes Care 2019),
not a criterion invented here, and the hypoglycaemia floors are the binding ones. Time in range
and variability are reported and do not gate, because a subject can fail them for reasons no
settings change reaches.
"""
import json
import os

import numpy as np

# Battelino T et al., Clinical Targets for Continuous Glucose Monitoring Data Interpretation,
# Diabetes Care 2019;42(8):1593-1603. Percentages of readings, on the sensor signal.
TBR54_LIMIT = 1.0        # per cent below 54 mg/dL
TBR70_LIMIT = 4.0        # per cent below 70 mg/dL
TIR_TARGET = 70.0        # per cent between 70 and 180 mg/dL
TAR250_LIMIT = 5.0       # per cent above 250 mg/dL
CV_LIMIT = 36.0          # per cent

# The ladder searched. It starts at the physiological settings and ends slightly beyond the
# DCLP3 correction factor, which is 2.3 times the median physiological one across this
# population, so the search covers real practice without extrapolating past it.
SCALES = (1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5)

# Titration runs under this regimen whatever is benchmarked afterwards.
REFERENCE_DRIVER = "trend"


def consensus_report(cgm):
    """The five consensus metrics for one run, on the sensor signal.

    Comparisons against clinical targets go on the reading rather than on `Result.bg`, since
    the targets were set on what a sensor records and the two differ here by a standard
    deviation near 12 mg/dL.
    """
    c = np.asarray(cgm, dtype=float)
    c = c[np.isfinite(c)]
    if not len(c):
        return {}
    return {"tbr54": float(100.0 * np.mean(c < 54)),
            "tbr70": float(100.0 * np.mean(c < 70)),
            "tir": float(100.0 * np.mean((c >= 70) & (c <= 180))),
            "tar250": float(100.0 * np.mean(c > 250)),
            "cv": float(100.0 * np.std(c) / np.mean(c))}


def hypo_floors_met(report):
    """Whether a run clears the two floors titration is allowed to act on."""
    if not report:
        return False
    return report["tbr54"] <= TBR54_LIMIT and report["tbr70"] <= TBR70_LIMIT


def failures(report):
    """Every consensus target the run misses, gating or not."""
    if not report:
        return ("no_readings",)
    out = []
    if report["tbr54"] > TBR54_LIMIT:
        out.append("tbr54")
    if report["tbr70"] > TBR70_LIMIT:
        out.append("tbr70")
    if report["tir"] < TIR_TARGET:
        out.append("tir")
    if report["tar250"] > TAR250_LIMIT:
        out.append("tar250")
    if report["cv"] > CV_LIMIT:
        out.append("cv")
    return tuple(out)


def titrate_subject(name, days=28, seed=0, layers=None, scales=SCALES,
                    driver=REFERENCE_DRIVER, simulate=None):
    """The weakest settings clearing the hypoglycaemia floors for one subject.

    Returns the chosen scale, the report at every scale tried, and whether the search
    succeeded. A subject whose floors are not met at any scale is reported rather than
    silently assigned the loosest, because settings are then not the explanation and running
    it as though they were would hide that.
    """
    from ..simulation.run import simulate as _sim
    from . import profile as profile_mod
    run = simulate or _sim
    layers = ("physiology", "behaviour", "sensor", "site") if layers is None else layers

    trace = []
    for scale in scales:
        prof = profile_mod.for_subject(name, isf_scale=scale)
        try:
            r = run(name, days=days, seed=seed, layers=layers, controller=driver,
                    profile=prof)
        except Exception as exc:
            trace.append({"scale": scale, "completed": False, "error": str(exc)[:140]})
            continue
        rep = consensus_report(r.cgm)
        trace.append({"scale": scale, "completed": bool(r.completed),
                      "isf": float(np.mean(prof.isf)), **rep,
                      "fails": failures(rep)})
        if r.completed and hypo_floors_met(rep):
            return {"name": name, "scale": scale, "found": True, "trace": trace}
    return {"name": name, "scale": None, "found": False, "trace": trace}


# Titrated settings are generated locally beside the population and are not committed, for the
# same reason the population is not: both are derived from the published parameter tables.
STORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "population", "params", "titrated_settings.json")


def save(results, path=STORE, meta=None):
    """Record a titration, including the subjects it failed on and the trace for each."""
    payload = {"meta": dict(meta or {}), "subjects": {r["name"]: r for r in results}}
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1, default=str)
    return path


def load(path=STORE):
    """The recorded titration, or None if the procedure has not been run here."""
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def profile_for(name, path=STORE, **kw):
    """A subject's titrated profile.

    Raises when the subject has no titrated settings rather than falling back to the
    physiological ones, because a benchmark that silently accepts untitrated settings is
    measuring the settings as much as the algorithm and gives no sign of it.
    """
    from . import profile as profile_mod
    store = load(path)
    if store is None:
        raise RuntimeError(
            "No titrated settings found. Run `python examples/titrate_cohort.py` first: a "
            "controller benchmarked on settings nobody titrated is being handed a correction "
            "factor about twice as aggressive as the one real users of the same algorithm run.")
    rec = store["subjects"].get(name)
    if rec is None or not rec.get("found"):
        raise RuntimeError(
            f"{name} has no titrated settings. The consensus hypoglycaemia floors were not "
            f"met at any scale tried, so its settings are not the explanation for what it "
            f"does and it should be excluded rather than run at the loosest available.")
    return profile_mod.for_subject(name, isf_scale=float(rec["scale"]), **kw)


def titrated_subjects(path=STORE):
    store = load(path)
    return () if store is None else tuple(
        sorted(n for n, r in store["subjects"].items() if r.get("found")))


__all__ = ["consensus_report", "hypo_floors_met", "failures", "titrate_subject",
           "save", "load", "profile_for", "titrated_subjects", "STORE",
           "SCALES", "REFERENCE_DRIVER", "TBR54_LIMIT", "TBR70_LIMIT", "TIR_TARGET",
           "TAR250_LIMIT", "CV_LIMIT"]
