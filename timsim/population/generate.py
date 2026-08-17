"""Generate a virtual population from the published UVA/Padova 2008 cohort.

simglucose ships 30 subjects: ten adults, ten adolescents, ten children. Thirty is few
enough that a controller comparison can be dominated by which subjects happen to be
awkward, and few enough that a per-subject result is a sample of one. This module
enlarges the population.

What it does NOT do is invent physiology. Each new subject is drawn from the joint
distribution of the published subjects of its own class, in a transformed space where
the parameters are roughly Gaussian, with the covariance shrunk towards its diagonal
because ten subjects cannot support a full 29-dimensional covariance. Only the free
parameters are drawn; every steady-state quantity is then closed exactly by the model's
own balance equations (`derive.py`), so a generated row is internally consistent in the
same way a published one is.

Each candidate then has to survive three gates before it becomes a subject:

  1. the balance equations must admit a positive steady state
  2. left alone on its own basal rate, glucose must actually hold near its fasting value
  3. given three meals and matched boluses over a day, it must stay inside 40-500 mg/dL
     and require a daily insulin dose in a plausible range

Candidates that fail are discarded and the reason is counted, so the acceptance rate and
its breakdown are reported rather than hidden.

Read the result for what it is. These subjects are a resampling of a published cohort of
thirty, not new clinical data, so they inherit whatever that cohort does not represent
and they do not add independent information about human variability. What they add is
resolution: a comparison across 100 subjects is less at the mercy of a single awkward
one, and the population can be regenerated with a different seed to check that a result
is not an artefact of one draw.
"""
import hashlib

import numpy as np
import pandas as pd

from . import derive
from .derive import FREE, NotViable

CLASSES = ("adult", "adolescent", "child")

# Parameters constrained to the unit interval get a logit; the rest are positive and get
# a log. Sampling in these spaces keeps every draw inside its natural support.
UNIT_INTERVAL = {"b", "d"}

# Screening thresholds. Deliberately wide: the point is to exclude subjects that are not
# people, not to select subjects that are easy to control.
FASTING_DRIFT_MGDL = 8.0      # allowed drift over 24 h on basal alone
GLUCOSE_FLOOR = 40.0
GLUCOSE_CEILING = 500.0
TDI_RANGE = (8.0, 160.0)      # units per day, including meal boluses
SCREEN_MEALS = [(7 * 60, 45.0), (13 * 60, 65.0), (19 * 60, 75.0)]


def _to_z(df):
    """Transform free parameters to an approximately Gaussian space."""
    out = {}
    for k in FREE:
        v = df[k].to_numpy(float)
        out[k] = np.log(v / (1.0 - v)) if k in UNIT_INTERVAL else np.log(v)
    return np.column_stack([out[k] for k in FREE])


def _from_z(z):
    """Inverse of _to_z for a single draw."""
    out = {}
    for k, v in zip(FREE, z):
        out[k] = 1.0 / (1.0 + np.exp(-v)) if k in UNIT_INTERVAL else np.exp(v)
    return out


def _shrunk_cov(z, alpha):
    """Sample covariance pulled towards its diagonal.

    Ten subjects give a rank-nine covariance in 29 dimensions, which is singular and
    would collapse every draw onto the span of the published subjects. Shrinking towards
    the diagonal restores rank while keeping the dominant correlations, which are what
    make a parameter vector physiologically coherent.
    """
    cov = np.cov(z, rowvar=False)
    return (1.0 - alpha) * cov + alpha * np.diag(np.diag(cov))


def _draw(mean, cov, rng, trunc):
    """One draw, with each marginal truncated to `trunc` standard deviations.

    Truncation is per-marginal rather than on the joint density, so it bounds how far
    any single parameter can travel from the published range without distorting the
    correlation structure.
    """
    sd = np.sqrt(np.diag(cov))
    for _ in range(200):
        z = rng.multivariate_normal(mean, cov)
        if np.all(np.abs(z - mean) <= trunc * sd):
            return z
    return np.clip(z, mean - trunc * sd, mean + trunc * sd)


# ------------------------------------------------------------------ behavioural screen
def _simulate_day(params, cr, meals=SCREEN_MEALS, basal_only=False):
    """One day of the real model at one-minute steps. Returns (cgm-like BG, total U).

    Uses simglucose's own patient object, so the screen tests the same equations the
    simulator will later integrate rather than a reimplementation of them.
    """
    from simglucose.patient.t1dpatient import T1DPatient, Action

    p = T1DPatient(pd.Series(params))
    basal = derive.basal_rate(params)
    schedule = {} if basal_only else {int(t): g for t, g in meals}
    bg, total = [], 0.0
    for minute in range(1440):
        cho = schedule.get(minute, 0.0)
        bolus = (cho / cr) if cho > 0 else 0.0
        total += basal + bolus
        p.step(Action(insulin=basal + bolus, CHO=cho))
        bg.append(p.observation.Gsub)
    return np.asarray(bg, float), total


def screen(params, cr):
    """Three gates. Returns None if the subject passes, otherwise the failure reason."""
    quiet, _ = _simulate_day(params, cr, basal_only=True)
    if not np.all(np.isfinite(quiet)):
        return "diverged on basal alone"
    if abs(quiet[-1] - quiet[0]) > FASTING_DRIFT_MGDL:
        return "fasting glucose does not hold"

    fed, total = _simulate_day(params, cr)
    if not np.all(np.isfinite(fed)):
        return "diverged with meals"
    if fed.min() < GLUCOSE_FLOOR:
        return "went below the glucose floor on matched boluses"
    if fed.max() > GLUCOSE_CEILING:
        return "went above the glucose ceiling on matched boluses"
    if not (TDI_RANGE[0] <= total <= TDI_RANGE[1]):
        return "daily insulin requirement outside the plausible range"
    return None


# ------------------------------------------------------------------ therapy settings
# Plausible human ranges. A subject whose measured settings fall outside these is not
# rejected because the settings are wrong, but because the physiology that produced them
# is not a person's.
CF_RANGE = (5.0, 150.0)      # mg/dL per unit
CR_RANGE = (2.0, 50.0)       # grams per unit

SETTLE_MINUTES = 600
OBSERVE_MINUTES = 300
PROBE_CARBS = 20.0


def measure_settings(params):
    """Measure a subject's correction factor and carbohydrate ratio from its own model.

    An earlier version drew these from the published cohort's distribution conditioned on
    body weight and basal rate. That was wrong, and the validation suite caught it. In the
    published cohort the settings track the physiology because they were derived from it:
    one unit moves published subjects by 1.10 times their stated correction factor, median
    across the ten adults. Conditioning on two coarse proxies loses that link, and the
    generated subjects came out at 0.63, which is a subject being dosed by someone else's
    settings on every cycle of every run.

    So they are measured instead, the way a clinician titrates: give one unit from a
    settled state and see how far glucose falls; give a small amount of carbohydrate and
    see how far it rises; the ratio of the two is how much carbohydrate one unit covers.
    That makes the settings consistent with the physiology by construction.

    Note what this costs. Once the settings are derived by measurement, checking that one
    unit moves glucose by the correction factor stops being an independent test of the
    model on generated subjects and becomes a consistency check. The independent version
    of that test is `check_published_cohort_obeys_clinical_rules`, which runs on the
    published subjects, whose settings were not derived this way.
    """
    from simglucose.patient.t1dpatient import T1DPatient, Action

    series = pd.Series(params)
    basal = derive.basal_rate(params)

    def settle():
        p = T1DPatient(series.copy())
        for _ in range(SETTLE_MINUTES):
            p.step(Action(insulin=basal, CHO=0.0))
        return p

    p = settle()
    start = p.observation.Gsub
    p.step(Action(insulin=basal + 1.0, CHO=0.0))
    nadir = start
    for _ in range(OBSERVE_MINUTES):
        p.step(Action(insulin=basal, CHO=0.0))
        nadir = min(nadir, p.observation.Gsub)
    cf = start - nadir

    p = settle()
    start = p.observation.Gsub
    p.step(Action(insulin=basal, CHO=PROBE_CARBS))
    peak = start
    for _ in range(OBSERVE_MINUTES):
        p.step(Action(insulin=basal, CHO=0.0))
        peak = max(peak, p.observation.Gsub)
    rise_per_gram = (peak - start) / PROBE_CARBS

    if cf <= 0 or rise_per_gram <= 0:
        return None, None
    return float(cf), float(cf / rise_per_gram)


class _AgeSampler:
    """Age is not in the model, so unlike the ratios it is drawn rather than measured."""

    def __init__(self, quest, klass):
        ages = np.log(quest[quest.Name.str.startswith(klass)].Age.to_numpy(float))
        self.mu, self.sd = float(ages.mean()), float(ages.std(ddof=1))

    def draw(self, rng):
        return float(np.clip(np.exp(rng.normal(self.mu, self.sd)), 6, 75))


# Room for far more subjects per class than any run would ask for, so the classes cannot
# collide however large the population grows.
CLASS_INDEX_BASE = 10_000


def class_seed(klass, seed):
    """The seed one class's draws start from, stable across processes.

    This used to be `seed + hash(klass) % 10_000`. Python salts string hashing per process,
    so `hash("adult")` returned 5103, 3342 and 8570 on three consecutive interpreters here
    and `generate(seed=2026)` produced a different hundred subjects every time it ran. The
    population was therefore not reproducible from its seed, and since it is deliberately
    not committed, the subjects every figure in `docs/` was measured on existed in exactly
    one uncommitted copy that nothing could rebuild.

    The digest comes from hashlib for the same reason as
    `simulation/run.py::subject_seed` and `therapy/profile.py::accuracy_for`. Changing it
    regenerates every subject, so it invalidates any figure measured before it changed.
    """
    digest = hashlib.sha256(f"{klass}:{seed}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


# ------------------------------------------------------------------ the generator
def generate(n=100, seed=2026, shrinkage=0.5, truncate=2.5, split=None, verbose=True):
    """Generate `n` screened subjects. Returns (patient rows, therapy rows, report).

    `split` is a dict of class to count; by default the classes are as equal as `n`
    allows, which mirrors the published cohort's ten of each.
    """
    from simglucose.patient.t1dpatient import PATIENT_PARA_FILE
    from simglucose.controller.basal_bolus_ctrller import CONTROL_QUEST

    published = pd.read_csv(PATIENT_PARA_FILE)
    quest = pd.read_csv(CONTROL_QUEST)

    if split is None:
        base, extra = divmod(n, len(CLASSES))
        split = {c: base + (1 if i < extra else 0) for i, c in enumerate(CLASSES)}

    rows, therapy, rejects = [], [], {}
    for klass in CLASSES:
        want = split.get(klass, 0)
        if not want:
            continue
        sub = published[published.Name.str.startswith(klass)]
        z = _to_z(sub)
        mean, cov = z.mean(0), _shrunk_cov(z, shrinkage)
        ages = _AgeSampler(quest, klass)
        rng = np.random.default_rng(class_seed(klass, seed))

        # The row identifier is offset by class rather than counted across the whole run, so
        # that asking for more subjects extends the population instead of renumbering it. It
        # used to be a single counter, which meant adolescent#001 carried i=35 in a hundred
        # subjects and i=45 in a hundred and thirty: the same body under a different number,
        # and a different file, so the population fingerprint moved and every titration
        # recorded against it was refused. Nothing reads `i`, but a population that is
        # append-only is worth more than one that is not.
        idx = CLASS_INDEX_BASE * (CLASSES.index(klass) + 1) + 1

        made, tries = 0, 0
        while made < want:
            tries += 1
            if tries > want * 400:
                raise RuntimeError(f"acceptance too low for {klass}: {rejects}")
            free = _from_z(_draw(mean, cov, rng, truncate))
            name = f"{klass}#{made + 1:03d}"
            try:
                params = derive.close(free, name, idx)
            except NotViable as exc:
                rejects[str(exc)] = rejects.get(str(exc), 0) + 1
                continue
            cf, cr = measure_settings(params)
            if cf is None:
                rejects["settings could not be measured"] = \
                    rejects.get("settings could not be measured", 0) + 1
                continue
            if not (CF_RANGE[0] <= cf <= CF_RANGE[1]):
                rejects["correction factor outside the human range"] = \
                    rejects.get("correction factor outside the human range", 0) + 1
                continue
            if not (CR_RANGE[0] <= cr <= CR_RANGE[1]):
                rejects["carbohydrate ratio outside the human range"] = \
                    rejects.get("carbohydrate ratio outside the human range", 0) + 1
                continue
            age = ages.draw(rng)
            why = screen(params, cr)
            if why:
                rejects[why] = rejects.get(why, 0) + 1
                continue
            rows.append(params)
            # Total daily insulin is the subject's own basal requirement doubled, on the
            # conventional half-basal half-bolus split. It is an assumption rather than a
            # simulated or measured quantity, and two things read it: `therapy/profile.py`
            # sizes the delivery ceilings from it, and `population/cohort.py::matched_on_traits`
            # matches cohorts on age and log(TDI) against real people. Because it is a fixed
            # multiple of basal, that second matching dimension carries no information basal
            # does not, while the real side of the match is a recorded pump total that includes
            # how much its owner actually bolused. State that wherever a cohort is described as
            # matched on daily insulin.
            therapy.append({"Name": name, "CR": cr, "CF": cf, "Age": age,
                            "TDI": derive.basal_rate(params) * 1440 * 2.0})
            made += 1
            idx += 1
            if verbose:
                print(f"  {name}  BW {params['BW']:5.1f} kg  Gb {params['Gb']:5.1f} mg/dL  "
                      f"basal {derive.basal_rate(params):.4f} U/min  CR {cr:4.1f}  CF {cf:4.1f}",
                      flush=True)

    accepted = len(rows)
    report = {"requested": n, "accepted": accepted,
              "candidates": accepted + sum(rejects.values()),
              "acceptance_rate": accepted / max(accepted + sum(rejects.values()), 1),
              "rejections": rejects, "seed": seed, "shrinkage": shrinkage,
              "truncate": truncate, "split": split}
    return pd.DataFrame(rows, columns=derive.COLUMNS), pd.DataFrame(therapy), report


__all__ = ["generate", "screen", "CLASSES"]
