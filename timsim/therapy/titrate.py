"""Titrating a subject's settings, and refusing to benchmark on settings nobody titrated.

A controller cannot be judged on a bench whose settings it was never given a fair version of.
This package's subjects carry a correction factor and a carbohydrate ratio measured from their
own physiology, which is a quantity no real person has access to: real settings are arrived at
by titration against the person's own record, and they end up conservative relative to what the
body would take. Measured across these subjects the physiological correction factor has a
median of 15.1 mg/dL per unit. The real figure it is set against is 40.0 mg/dL per unit, the
median of the recorded pump settings of the 112 closed-loop participants of DCLP3 with an
inter-quartile range of 30.0 to 50.0, read from `InsulinPumpSettings_a.txt` and summarised per
participant before the cohort median is taken. So an algorithm handed the physiological value
is being asked to dose about two and a half times as hard as it would for a real user. Earlier
versions of this note quoted 35 mg/dL per unit, which was never measured from the release.

The response is a procedure rather than a constant. Each subject's settings are weakened until
its own record clears the consensus hypoglycaemia floors, because settings looser than necessary
cost time in range. That leaves every subject with settings whose provenance is a measurement on
that subject rather than a number chosen once for the cohort.

The search is along a path rather than over the grid, and the distinction matters for the
subjects that reach the second lever. Basal is walked down to its floor before the correction
factor is touched at all, and the correction factor is then weakened on top of that floor, so a
subject needing a small correction-factor change receives it alongside the largest basal
reduction available rather than the smallest one that would have worked with it. The combination
of an untouched basal and a slightly weaker correction factor is never tried. This is the order a
clinician moves in and it is not the minimum of the grid: those subjects end more conservative
than they need to be, which costs them time in range and understates their hypoglycaemia. They
are the subjects with the most hypoglycaemia to begin with, so the direction is worth carrying
into any reading of the hypoglycaemia figures.

Basal moves before the correction factor, in that order, because that is the order a titration
is done in and because the two are not interchangeable. A subject having lows under a reference
loop usually has too much background insulin, and answering that by weakening its correction
factor leaves it unable to correct: one subject needed a 1.75-fold weakening on the correction
factor alone, which took it to 65.8 mg/dL per unit, and under an algorithm that sizes its
microboluses from that factor it then failed to cover unannounced carbohydrate and ran to 593
mg/dL inside a day. The same subject's lows clear with a five per cent basal reduction and its
correction factor untouched. Across the ten subjects the correction-factor-only procedure
weakened, six clear on basal alone at reductions of 5 to 20 per cent.

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
import hashlib
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

# Basal first, in reductions a titration would actually make. The floor of 0.80 is a modelling
# choice: basal here is the subject's own steady-state requirement, so a reduction beyond a fifth
# says the steady state is wrong for the closed-loop condition rather than that the basal needs
# trimming, and that is a different problem from the one this procedure solves.
BASAL_SCALES = (1.0, 0.95, 0.90, 0.85, 0.80)

# The correction factor, used only when basal alone cannot clear the floors. It starts at the
# physiological value and ends at 2.5 times it, which reaches the measured DCLP3 median of 40.0
# mg/dL per unit from a physiological median of 15.1, so the search covers real practice without
# extrapolating far past it.
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


def _profile(name, isf_scale, basal_scale):
    from dataclasses import replace
    from . import profile as profile_mod
    p = profile_mod.for_subject(name, isf_scale=isf_scale)
    if basal_scale != 1.0:
        p = replace(p, basal_u_per_hour=p.basal_u_per_hour * float(basal_scale))
    return p


def titrate_subject(name, days=28, seed=0, layers=None, scales=SCALES,
                    basal_scales=BASAL_SCALES, driver=REFERENCE_DRIVER, simulate=None):
    """The weakest settings clearing the hypoglycaemia floors for one subject.

    Basal is tried first at its physiological value and then reduced, with the correction
    factor untouched. Only when no reduction inside the bound clears the floors is the
    correction factor weakened, and then on top of the smallest basal tried, because a
    correction factor weakened to cover a basal problem leaves the subject unable to correct.

    Returns the adopted scales, the trace of every run, and whether the search succeeded. A
    subject that clears at no combination is reported rather than assigned the loosest, because
    settings are then not the explanation and running it as though they were would hide that.
    """
    from ..simulation.run import simulate as _sim
    run = simulate or _sim
    layers = ("physiology", "behaviour", "sensor", "site") if layers is None else layers

    trace = []

    def attempt(isf_scale, basal_scale):
        prof = _profile(name, isf_scale, basal_scale)
        try:
            r = run(name, days=days, seed=seed, layers=layers, controller=driver, profile=prof)
        except Exception as exc:
            trace.append({"scale": isf_scale, "basal_scale": basal_scale,
                          "completed": False, "error": str(exc)[:140]})
            return False
        rep = consensus_report(r.cgm)
        trace.append({"scale": isf_scale, "basal_scale": basal_scale,
                      "completed": bool(r.completed),
                      "isf": float(np.mean(prof.isf)),
                      "basal_u_per_day": float(np.mean(prof.basal_u_per_hour) * 24.0),
                      **rep, "fails": failures(rep)})
        return bool(r.completed) and hypo_floors_met(rep)

    for basal_scale in basal_scales:
        if attempt(1.0, basal_scale):
            return {"name": name, "scale": 1.0, "basal_scale": basal_scale,
                    "lever": "basal", "found": True, "trace": trace}

    floor = min(basal_scales)
    for isf_scale in scales[1:]:
        if attempt(isf_scale, floor):
            return {"name": name, "scale": isf_scale, "basal_scale": floor,
                    "lever": "basal and correction factor", "found": True, "trace": trace}
    return {"name": name, "scale": None, "basal_scale": None, "lever": None,
            "found": False, "trace": trace}


# Titrated settings are generated locally beside the population and are not committed, for the
# same reason the population is not: both are derived from the published parameter tables.
STORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "population", "params", "titrated_settings.json")


PARAMS = os.path.join(os.path.dirname(STORE), "vpop_params.csv")


def population_fingerprint(path=PARAMS):
    """A digest of the generated population, or None if it is not present.

    Subject names are positional: `adult#001` is whatever the generator produced first for
    that class. Regenerating the population reuses every name for a different body, so a
    titration recorded against the old one resolves to settings fitted to somebody else and
    nothing in the arithmetic looks wrong. Reseeding the generator in August 2026 moved
    adolescent#004 from a correction factor of 21.8 to 43.5 under the same name.

    So the store records which population it was fitted to and `profile_for` refuses to use
    it against a different one. A benchmark that silently uses another body's settings is
    the failure `docs/METHODS.md` describes as worse than a crash.
    """
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return None


def save(results, path=STORE, meta=None):
    """Record a titration, including the subjects it failed on and the trace for each."""
    meta = dict(meta or {})
    meta.setdefault("population", population_fingerprint())
    payload = {"meta": meta, "subjects": {r["name"]: r for r in results}}
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1, default=str)
    return path


def check_population(store, path=PARAMS):
    """Raise when a store was fitted to a different population than the one present."""
    recorded = (store.get("meta") or {}).get("population")
    current = population_fingerprint(path)
    if recorded is None:
        raise RuntimeError(
            "The titrated settings record no population fingerprint, so they cannot be shown "
            "to belong to the subjects now on disk. Rerun `python examples/titrate_cohort.py`.")
    if current is not None and recorded != current:
        raise RuntimeError(
            f"These titrated settings were fitted to population {recorded} and the population "
            f"on disk is {current}. Subject names are reused across generations, so applying "
            f"them would dose each subject on another body's settings. Rerun "
            f"`python examples/titrate_cohort.py`.")


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
    check_population(store)
    rec = store["subjects"].get(name)
    if rec is None or not rec.get("found"):
        raise RuntimeError(
            f"{name} has no titrated settings. The consensus hypoglycaemia floors were not "
            f"met at any combination tried, so its settings are not the explanation for what "
            f"it does and it should be excluded rather than run at the loosest available.")
    from dataclasses import replace
    p = profile_mod.for_subject(name, isf_scale=float(rec["scale"]), **kw)
    b = float(rec.get("basal_scale", 1.0) or 1.0)
    return p if b == 1.0 else replace(p, basal_u_per_hour=p.basal_u_per_hour * b)


def titrated_subjects(path=STORE):
    store = load(path)
    if store is None:
        return ()
    check_population(store)
    return tuple(sorted(n for n, r in store["subjects"].items() if r.get("found")))


__all__ = ["consensus_report", "hypo_floors_met", "failures", "titrate_subject",
           "save", "load", "profile_for", "titrated_subjects", "STORE",
           "population_fingerprint", "check_population",
           "SCALES", "BASAL_SCALES", "REFERENCE_DRIVER", "TBR54_LIMIT", "TBR70_LIMIT", "TIR_TARGET",
           "TAR250_LIMIT", "CV_LIMIT"]
