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
class _TherapySampler:
    """Draws carbohydrate ratio, correction factor and age for a generated subject.

    These are not model parameters; they are the settings a clinician would arrive at,
    and in the published cohort they track body weight and basal requirement. So they
    are drawn from the conditional distribution given the subject's own weight and
    basal rate rather than independently, which keeps a heavy subject from being handed
    a light subject's ratios.
    """

    def __init__(self, quest, patients, klass):
        m = quest.Name.str.startswith(klass)
        q = quest[m].reset_index(drop=True)
        p = patients[patients.Name.str.startswith(klass)].reset_index(drop=True)
        # joint in log space: [CR, CF, Age | BW, u2ss]
        self.cols = ["CR", "CF", "Age"]
        joint = np.column_stack([
            np.log(q.CR.to_numpy(float)), np.log(q.CF.to_numpy(float)),
            np.log(q.Age.to_numpy(float)),
            np.log(p.BW.to_numpy(float)), np.log(p.u2ss.to_numpy(float))])
        self.mu = joint.mean(0)
        cov = np.cov(joint, rowvar=False)
        self.cov = 0.5 * cov + 0.5 * np.diag(np.diag(cov))

    def draw(self, bw, u2ss, rng):
        a, b = slice(0, 3), slice(3, 5)
        mu_a, mu_b = self.mu[a], self.mu[b]
        Saa, Sab, Sbb = self.cov[a, a], self.cov[a, b], self.cov[b, b]
        x = np.array([np.log(bw), np.log(u2ss)])
        solve = np.linalg.solve(Sbb + 1e-9 * np.eye(2), (x - mu_b))
        mean = mu_a + Sab @ solve
        cond = Saa - Sab @ np.linalg.solve(Sbb + 1e-9 * np.eye(2), Sab.T)
        cond = (cond + cond.T) / 2 + 1e-9 * np.eye(3)
        cr, cf, age = np.exp(rng.multivariate_normal(mean, cond))
        return float(np.clip(cr, 3.0, 40.0)), float(np.clip(cf, 5.0, 80.0)), float(np.clip(age, 6, 75))


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
    idx = 1
    for klass in CLASSES:
        want = split.get(klass, 0)
        if not want:
            continue
        sub = published[published.Name.str.startswith(klass)]
        z = _to_z(sub)
        mean, cov = z.mean(0), _shrunk_cov(z, shrinkage)
        sampler = _TherapySampler(quest, published, klass)
        rng = np.random.default_rng(seed + hash(klass) % 10_000)

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
            cr, cf, age = sampler.draw(params["BW"], params["u2ss"], rng)
            why = screen(params, cr)
            if why:
                rejects[why] = rejects.get(why, 0) + 1
                continue
            rows.append(params)
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
