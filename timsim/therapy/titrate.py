"""Titrating a subject's settings, and refusing to benchmark on settings nobody titrated.

A controller cannot be judged on a bench whose settings it was never given a fair version of.
This package's subjects carry a correction factor and a carbohydrate ratio measured from their
own physiology, which is a quantity no real person has access to: real settings are arrived at
by titration against the person's own record, and they end up conservative relative to what the
body would take. Measured across the 306 subjects this store titrates, the physiological
correction factor has a median of 18.6 mg/dL per unit with an interquartile range of 12.9 to
27.6. The real figure it is set against is 40.0 mg/dL per unit, the
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

The open-loop arm is not that regimen, and the reason recorded here until 28 August 2026 was
refuted by `examples/titration_reference.py`. It said the arm spends 0.25 per cent of time
below 70 mg/dL and so never exercises the settings, returning its own starting point for 13 of
15 subjects. Rerun on the current population it spends 2.39 per cent, which is more than the
1.92 the correction loop produces on the same rung, and it moves 19 of 90 subjects.

What it does instead is exclude. The open-loop ladder clears no combination for 15 of 90
subjects against the correction loop's 4, and 11 of those 15 are subjects the loop dosed
safely, 4 of them without touching their settings. An open-loop regimen cannot withdraw
background insulin as glucose falls, so a subject the loop would have caught goes low and a
basal reduction bounded at a fifth does not recover it. Exclusion propagates, since every
downstream cohort drops an untitrated subject, so titrating there would shrink each cohort by
a sixth for a reason belonging to the regimen rather than to the subject. The arm also misses
the hyperglycaemia targets wholesale, at 69 of 90 subjects below the time in range target and
68 of 90 above the time above 250 mg/dL limit.

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
# physiological value and ends at 2.5 times it, which carries a physiological median of 18.6
# mg/dL per unit to 45.5 and so covers the measured DCLP3 median of 40.0 without extrapolating
# far past it.
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


class TitrationError(RuntimeError):
    """A titration attempt failed for a reason that is not a clinical result.

    Kept distinct so a caller can tell a subject who cannot be dosed safely from a subject
    whose run never happened. The first is a finding and excludes the subject from every
    cohort; the second is a fault and should stop the work rather than quietly shrink it.
    """


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
            # A rung that raises is not a rung that failed the clinical floors, and until
            # 21 August 2026 both produced the same verdict: the ladder carried on and the
            # subject could be recorded as having no settings that cleared the floors. A
            # missing dependency, an unpicklable argument or an ordinary programming defect
            # was therefore indistinguishable from a subject who genuinely cannot be dosed
            # safely, and the exclusion is load-bearing: excluded subjects are dropped from
            # every cohort. A run that terminates does not raise, it returns `completed`
            # False, so nothing expected arrives here.
            trace.append({"scale": isf_scale, "basal_scale": basal_scale,
                          "completed": False, "error": str(exc)[:140]})
            raise TitrationError(
                f"titrating {name} at isf_scale {isf_scale} and basal_scale {basal_scale} "
                f"raised {type(exc).__name__}: {exc}") from exc
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

# The Hovorka body (`population/hovorka.py`) keeps its own store against its own population, so
# a regeneration of either body invalidates only the settings fitted to it.
HOVORKA_STORE = os.path.join(os.path.dirname(STORE), "titrated_settings_hovorka.json")
HOVORKA_PARAMS = os.path.join(os.path.dirname(STORE), "hovorka_params.csv")


def store_for(name):
    """The store a subject's titration is kept in, chosen by its name."""
    from ..population.hovorka import PREFIX
    return HOVORKA_STORE if str(name).startswith(PREFIX) else STORE


def _population_of(store_path):
    return HOVORKA_PARAMS if os.path.abspath(store_path) == HOVORKA_STORE else PARAMS


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


# The modules whose behaviour decides what a titration finds. A change to any of them makes an
# existing store a record of a different procedure, and the population fingerprint cannot see it:
# the subjects are the same bodies, dosed by different code.
_CODE = ("patient/varying.py", "patient/glucagon.py", "simulation/run.py",
         "person/behaviour.py", "person/activity.py", "therapy/limits.py",
         "therapy/profile.py", "therapy/insulin.py", "therapy/titrate.py")


# The Hovorka body's own modules, fingerprinted for its store only, so an edit to one body does
# not invalidate the other's settings.
_HOVORKA_CODE = ("patient/hovorka.py", "population/hovorka.py")


def code_fingerprint(root=None, store=None):
    """A digest of the code a titration outcome depends on, or None if it cannot be read.

    `store` selects the body: the Hovorka store adds that body's modules to the shared ones.
    """
    import hashlib
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = _CODE + (_HOVORKA_CODE if store is not None
                     and os.path.abspath(store) == HOVORKA_STORE else ())
    h = hashlib.sha256()
    for rel in files:
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                h.update(rel.encode())
                h.update(fh.read())
        except OSError:
            return None
    return h.hexdigest()[:16]


def save(results, path=STORE, meta=None):
    """Record a titration, including the subjects it failed on and the trace for each.

    Written to a temporary file and renamed, which is atomic on the same filesystem. Writing
    in place leaves a truncated file if the process dies partway, and this one takes hours to
    produce: `load` would refuse the remains, correctly, and the work would be gone.
    """
    meta = dict(meta or {})
    meta.setdefault("population", population_fingerprint(_population_of(path)))
    meta.setdefault("code", code_fingerprint(store=path))
    try:
        from importlib import metadata as _md
        meta.setdefault("simglucose", _md.version("simglucose"))
    except Exception:
        meta.setdefault("simglucose", None)
    payload = {"meta": meta, "subjects": {r["name"]: r for r in results}}
    tmp = f"{path}.partial"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=1, default=str)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path


def check_population(store, path=PARAMS):
    """Raise when a store was fitted to a different population or by different code.

    The population fingerprint alone was checked until 21 August 2026. It cannot see a change
    to the physiology, the delivery limits or the ladder itself: the subjects are the same
    bodies and the settings were found by a different procedure. Everything a titration outcome
    depends on is now recorded and compared, and a store written before that carries no code
    fingerprint and is refused rather than assumed current.
    """
    store_path = HOVORKA_STORE if os.path.abspath(path) == HOVORKA_PARAMS else STORE
    meta = store.get("meta") or {}
    recorded = meta.get("population")
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

    code_now = code_fingerprint(store=store_path)
    code_was = meta.get("code")
    if code_was is None:
        raise RuntimeError(
            "These titrated settings record no code fingerprint, so they cannot be shown to "
            "have been produced by the physiology, delivery limits and ladder now on disk. "
            "Rerun `python examples/titrate_cohort.py`.")
    if code_now is not None and code_was != code_now:
        raise RuntimeError(
            f"These titrated settings were produced by code fingerprinted {code_was} and the "
            f"code on disk fingerprints {code_now}. A settings ladder run against different "
            f"physiology or different delivery limits found different settings, and the "
            f"population fingerprint cannot see that. Rerun "
            f"`python examples/titrate_cohort.py`.")


def load(path=STORE):
    """The recorded titration, or None if the procedure has not been run here."""
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _positive(value, field, name):
    """A settings multiplier, checked before it reaches a body.

    The procedure only ever writes values from `SCALES` and `BASAL_SCALES`, so a bad one means
    the store was edited, merged or partly written rather than produced. The check is here
    because of what the bad values do rather than because they are expected: a negative scale
    gives a negative correction factor, and an algorithm dosing against that corrects in the
    wrong direction on every cycle while every number in the output stays finite and plausible.
    Zero gives an infinite correction. Neither announces itself.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise RuntimeError(
            f"{name} has a {field} of {value!r} in the titrated settings, which is not a "
            f"number. The store has been edited or written by something other than "
            f"`examples/titrate_cohort.py`.") from None
    if not np.isfinite(v) or v <= 0.0:
        raise RuntimeError(
            f"{name} has a {field} of {v} in the titrated settings. Settings multipliers "
            f"scale a correction factor and a basal rate, so a value at or below zero doses "
            f"backwards or not at all rather than weakly. Retitrate this subject.")
    return v


def profile_for(name, path=None, **kw):
    """A subject's titrated profile.

    Raises when the subject has no titrated settings rather than falling back to the
    physiological ones, because a benchmark that silently accepts untitrated settings is
    measuring the settings as much as the algorithm and gives no sign of it.
    """
    from . import profile as profile_mod
    path = path or store_for(name)
    store = load(path)
    if store is None:
        raise RuntimeError(
            "No titrated settings found. Run `python examples/titrate_cohort.py` first: a "
            "controller benchmarked on settings nobody titrated is being handed a correction "
            "factor about twice as aggressive as the one real users of the same algorithm run.")
    check_population(store, _population_of(path))
    rec = store["subjects"].get(name)
    if rec is None or not rec.get("found"):
        raise RuntimeError(
            f"{name} has no titrated settings. The consensus hypoglycaemia floors were not "
            f"met at any combination tried, so its settings are not the explanation for what "
            f"it does and it should be excluded rather than run at the loosest available.")
    from dataclasses import replace
    scale = _positive(rec.get("scale"), "scale", name)
    # `or 1.0` would be wrong here: zero is falsy, so a stored basal scale of zero became 1.0
    # and a subject recorded as receiving no basal at all was run at its full rate. Only a
    # missing or null entry means "unscaled".
    raw = rec.get("basal_scale", 1.0)
    b = _positive(1.0 if raw is None else raw, "basal_scale", name)
    p = profile_mod.for_subject(name, isf_scale=scale, **kw)
    return p if b == 1.0 else replace(p, basal_u_per_hour=p.basal_u_per_hour * b)


def titrated_subjects(path=STORE):
    store = load(path)
    if store is None:
        return ()
    check_population(store, _population_of(path))
    return tuple(sorted(n for n, r in store["subjects"].items() if r.get("found")))


__all__ = ["consensus_report", "hypo_floors_met", "failures", "titrate_subject",
           "save", "load", "profile_for", "titrated_subjects", "STORE", "HOVORKA_STORE",
           "store_for",
           "population_fingerprint", "check_population",
           "SCALES", "BASAL_SCALES", "REFERENCE_DRIVER", "TBR54_LIMIT", "TBR70_LIMIT", "TIR_TARGET",
           "TAR250_LIMIT", "CV_LIMIT"]
