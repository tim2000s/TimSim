"""A second body: the Hovorka model, behind the same interface as simglucose's patient.

Every result in this package rests on one set of equations, S2008. A ranking of two algorithms
that reverses when the body is replaced by another published model belongs to the model rather
than to the algorithms, and nothing could test for that while there was only one body. This
module supplies the other one.

The equations are those of Hovorka et al. (Physiol Meas 2004;25:905-920): two glucose
compartments, a two-compartment subcutaneous insulin depot, three remote insulin actions on
transport, disposal and endogenous production, and a two-compartment gut. The parameter values
and the population follow Resalat et al. (PLoS One 2019;14(7):e0217301), whose single-hormone
population is the published Hovorka population with the most explicit sampling procedure, and
whose MATLAB source (github.com/petejacobs/T1D_VPP) was read alongside the paper. Two places
where the paper and the source disagree are noted where the value is used, in
`population/hovorka.py`.

Three choices are made here and are modelling choices rather than measurements.

Endogenous production is floored at zero, as in Hovorka 2004. Resalat's linearised plant
leaves `EGP0 * (1 - x3)` unbounded, so at high insulin their liver takes glucose up. Neither
version has any counterregulation: production depends on insulin alone and not on glucose, so
this body has the defect `docs/PADOVA_LIMITS.md` records for S2008 in a stronger form, and none
of the hepatic defences in `patient/varying.py` is applied to it.

The model has no interstitial compartment. The sensor in `simulation/run.py` reads `Gsub`, so a
first-order lag is added with the median `ksc` of the ten published S2008 adults, which keeps
the sensor's view of the body the same across the two bodies and leaves the body as the only
thing that changes.

Meal-to-meal absorption variation multiplies `1/tmaxG`, the one rate the gut has, by the factor
`patient/varying.py` draws for S2008's three gut rates, from the same distribution and bounds.

Units at the interface are simglucose's: insulin in U/min, carbohydrate in g/min, glucose in
mg/dL, time in minutes.
"""
from collections import namedtuple

import numpy as np

from .varying import (DIURNAL_AMPLITUDE, INTERDAY_CV, MEAL_ABSORPTION_BOUNDS,
                      MEAL_ABSORPTION_CV, MEAL_ABSORPTION_SCALE, SLOW_TAU_DAYS, VaryingPatient)

Observation = namedtuple("Observation", ["Gsub"])

MGDL_PER_MMOL = 18.0          # the conversion Resalat's source uses
GLUCOSE_MMOL_PER_G = 1000.0 / 180.16

# Median `ksc` of the ten published S2008 adults, per minute.
KSC = 0.0915

# Four Runge-Kutta substeps a minute. The fastest rate in the model is insulin elimination at
# 0.138 per minute, so a 15 s step is about fifty times shorter than any time constant.
SUBSTEPS = 4

# State layout. The first eight follow Resalat's `Plant.m`; the gut and the interstitial lag are
# appended.
Q1, Q2, S1, S2, I, X1, X2, X3, D1, D2, GS = range(11)


def _rates(x, u_mu_kg_min, d_mmol_kg_min, p, si):
    """The Hovorka 2004 right-hand side."""
    g = x[Q1] / p["VG"]
    f01c = p["F01"] if g >= 4.5 else p["F01"] * g / 4.5
    fr = 0.003 * (g - 9.0) * p["VG"] if g >= 9.0 else 0.0
    ug = x[D2] / p["_tmaxG_meal"]
    egp = max(0.0, p["EGP0"] * (1.0 - x[X3]))
    dx = np.empty(11)
    dx[Q1] = -f01c - x[X1] * x[Q1] + p["k12"] * x[Q2] - fr + ug + egp
    dx[Q2] = x[X1] * x[Q1] - (p["k12"] + x[X2]) * x[Q2]
    dx[S1] = u_mu_kg_min - x[S1] / p["tmaxI"]
    dx[S2] = (x[S1] - x[S2]) / p["tmaxI"]
    dx[I] = x[S2] / (p["tmaxI"] * p["VI"]) - p["ke"] * x[I]
    dx[X1] = p["ka1"] * (si * p["Sf1"] * x[I] - x[X1])
    dx[X2] = p["ka2"] * (si * p["Sf2"] * x[I] - x[X2])
    dx[X3] = p["ka3"] * (si * p["Sf3"] * x[I] - x[X3])
    dx[D1] = p["AG"] * d_mmol_kg_min - x[D1] / p["_tmaxG_meal"]
    dx[D2] = (x[D1] - x[D2]) / p["_tmaxG_meal"]
    dx[GS] = KSC * (g * MGDL_PER_MMOL - x[GS])
    return dx


def steady_state(p, glucose_mgdl):
    """States and basal infusion holding glucose at `glucose_mgdl` with no meal.

    Solved in closed form along plasma insulin rather than with `fsolve` as Resalat's source
    does, so it cannot converge to a spurious root. Returns (state, basal in mU/kg/min).
    """
    from scipy.optimize import brentq

    g = glucose_mgdl / MGDL_PER_MMOL
    q1 = g * p["VG"]
    f01c = p["F01"] if g >= 4.5 else p["F01"] * g / 4.5
    fr = 0.003 * (g - 9.0) * p["VG"] if g >= 9.0 else 0.0

    def balance(i):
        x1, x2, x3 = p["Sf1"] * i, p["Sf2"] * i, p["Sf3"] * i
        q2 = x1 * q1 / (p["k12"] + x2)
        return -f01c - fr - x1 * q1 + p["k12"] * q2 + p["EGP0"] * (1.0 - x3)

    if balance(0.0) <= 0.0:
        raise ValueError(f"{p.get('Name', '?')} cannot hold {glucose_mgdl} mg/dL even with "
                         f"no insulin at all")
    i = brentq(balance, 0.0, 1.0 / p["Sf3"])
    u = p["ke"] * p["VI"] * i
    x = np.zeros(11)
    x[Q1] = q1
    x[Q2] = p["Sf1"] * i * q1 / (p["k12"] + p["Sf2"] * i)
    x[S1] = x[S2] = u * p["tmaxI"]
    x[I] = i
    x[X1], x[X2], x[X3] = p["Sf1"] * i, p["Sf2"] * i, p["Sf3"] * i
    x[GS] = glucose_mgdl
    return x, u


class HovorkaPatient:
    """The Hovorka body, steppable by `T1DSimEnv` in place of simglucose's T1DPatient.

    `params` carries the columns `population/hovorka.py` writes: the model parameters, body
    weight `BW` and the glucose `Gb` the subject starts at, in steady state on its own basal.
    """

    sample_time = 1

    def __init__(self, params):
        self._params = {k: params[k] for k in params.index} if hasattr(params, "index") \
            else dict(params)
        self.name = self._params["Name"]
        self.reset()

    def reset(self):
        p = self._params
        p["_tmaxG_meal"] = float(p["tmaxG"])
        self._x, _ = steady_state(p, float(p["Gb"]))
        self._t = 0.0
        self._last_cho = 0.0
        self.is_eating = False

    @property
    def t(self):
        return self._t

    @property
    def state(self):
        return self._x.copy()

    @property
    def observation(self):
        return Observation(Gsub=float(self._x[GS]))

    # The time-varying sensitivity of the physiology layer, drawn exactly as for S2008 and
    # applied to all three insulin actions together, as Resalat's circadian term is.
    def set_sensitivity(self, rng, n_days, diurnal=DIURNAL_AMPLITUDE,
                        interday_cv=INTERDAY_CV, pattern="sinusoid",
                        slow_cv=None, slow_tau_days=SLOW_TAU_DAYS):
        if pattern not in ("sinusoid", "visentin"):
            raise ValueError(f"unknown sensitivity pattern {pattern!r}")
        VaryingPatient._draw_sensitivity(self, rng, n_days, diurnal, interday_cv, pattern,
                                         slow_cv, slow_tau_days)

    sensitivity = VaryingPatient.sensitivity
    _segment = VaryingPatient._segment

    def set_meal_variability(self, rng, cv=MEAL_ABSORPTION_CV, scale=MEAL_ABSORPTION_SCALE):
        self._meal_rng, self._meal_cv, self._meal_scale = rng, float(cv), float(scale)
        self._meal_factor = float(scale)
        self._meal_varying = self._meal_cv > 0.0 or self._meal_scale != 1.0

    def _meal_absorption(self, cho):
        if not getattr(self, "_meal_varying", False):
            return
        if cho > 0.0 and self._last_cho <= 0.0:
            sigma = np.sqrt(np.log(1.0 + self._meal_cv ** 2))
            draw = (self._meal_rng.lognormal(-0.5 * sigma ** 2, sigma)
                    if self._meal_cv > 0.0 else 1.0)
            self._meal_factor = float(np.clip(self._meal_scale * draw,
                                              *MEAL_ABSORPTION_BOUNDS))
        self._params["_tmaxG_meal"] = float(self._params["tmaxG"]) / self._meal_factor

    def step(self, action):
        p = self._params
        cho = float(getattr(action, "CHO", 0.0) or 0.0)
        self._meal_absorption(cho)
        self._last_cho = cho
        self.is_eating = cho > 0.0
        bw = float(p["BW"])
        u = float(action.insulin) * 1000.0 / bw
        d = cho * GLUCOSE_MMOL_PER_G / bw
        si = self.sensitivity() if getattr(self, "_varying", False) else 1.0
        h = 1.0 / SUBSTEPS
        x = self._x
        for _ in range(SUBSTEPS):
            k1 = _rates(x, u, d, p, si)
            k2 = _rates(x + 0.5 * h * k1, u, d, p, si)
            k3 = _rates(x + 0.5 * h * k2, u, d, p, si)
            k4 = _rates(x + h * k3, u, d, p, si)
            x = x + h / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
            np.maximum(x, 0.0, out=x)
        self._x = x
        self._t += 1.0


__all__ = ["HovorkaPatient", "steady_state", "KSC"]
