"""The therapy profile an automated insulin delivery system reads.

Until now a subject carried one flat basal rate, one carbohydrate ratio and one
correction factor. No real system is configured that way. Every one of them reads a
24-hour basal schedule, sensitivity and ratio by time block, a target range rather than a
target number, a duration of insulin action, and the ceilings in `limits.py`. Handing a
system three scalars and calling the result a test of that system is testing something
else.

The flat schedule remains the default, so results measured before this module existed
still reproduce. `diurnal=True` gives the dawn-shaped schedule described below, which is
what you want when the algorithm's own scheduling logic is part of what is under test.

The dawn shape is not decorative. The physiology layer already dips insulin sensitivity to
its lowest around six in the morning, so a person's insulin requirement peaks there. A
basal schedule with a peak at the same hour is the profile a clinician would have arrived
at for that person, and sensitivity and ratio move with it in the opposite direction,
because a unit does less when sensitivity is low.
"""
from dataclasses import dataclass

import numpy as np

from .insulin import DIA_MIN
from .limits import PumpLimits

DAWN_AMPLITUDE = 0.20      # fractional swing in basal requirement across the day
DAWN_PEAK_HOUR = 6.0

# Target range. The open-source systems mostly ship a narrow band in this region, and a
# single number would make any test of an algorithm's target handling vacuous.
TARGET_LO = 100.0
TARGET_HI = 120.0

HOURS = np.arange(24)


def dawn_shape(amplitude=DAWN_AMPLITUDE, peak_hour=DAWN_PEAK_HOUR):
    """A 24-entry multiplier with mean one, peaking at `peak_hour`."""
    s = 1.0 + amplitude * np.cos(2 * np.pi * (HOURS - peak_hour) / 24.0)
    return s / s.mean()


@dataclass
class Profile:
    """One subject's programmed therapy, as a system under test would read it."""
    name: str
    basal_u_per_hour: np.ndarray       # 24 entries
    isf: np.ndarray                    # 24 entries, mg/dL per unit
    cr: np.ndarray                     # 24 entries, grams per unit
    target_lo: float = TARGET_LO
    target_hi: float = TARGET_HI
    dia_min: float = DIA_MIN
    limits: PumpLimits = None
    total_daily_insulin: float = float("nan")

    @property
    def target(self):
        return 0.5 * (self.target_lo + self.target_hi)

    def _at(self, values, minute):
        return float(values[int((minute // 60) % 24)])

    def basal_at(self, minute):
        """Scheduled basal in U/min at `minute` from the start of the run."""
        return self._at(self.basal_u_per_hour, minute) / 60.0

    def isf_at(self, minute):
        return self._at(self.isf, minute)

    def cr_at(self, minute):
        return self._at(self.cr, minute)

    def as_dict(self):
        """A plain dictionary, which is the shape an external adapter wants."""
        return {"name": self.name,
                "basal_schedule_u_per_hour": [round(float(v), 4) for v in self.basal_u_per_hour],
                "isf_mgdl_per_u": [round(float(v), 3) for v in self.isf],
                "cr_g_per_u": [round(float(v), 3) for v in self.cr],
                "target_lo": self.target_lo, "target_hi": self.target_hi,
                "dia_hours": self.dia_min / 60.0,
                "total_daily_insulin": self.total_daily_insulin,
                "max_basal_u_per_hour": self.limits.max_basal_u_per_hour,
                "max_bolus_u": self.limits.max_bolus_u,
                "max_iob_u": self.limits.max_iob_u}


def for_subject(name, params=None, settings=None, diurnal=False, limits=None,
                isf_scale=1.0, cr_scale=1.0):
    """Build a subject's profile from the population tables.

    `diurnal=False` gives a flat schedule whose rate is the subject's own steady-state
    basal, which is what every run in this package used before profiles existed.

    `isf_scale` and `cr_scale` weaken or strengthen the settings the algorithm is given,
    without touching the body they are given to. They exist because this package's subjects
    carry settings measured from their own physiology, and no real person has that. A
    correction factor of 35 mg/dL per unit is what DCLP3 participants ran; the same
    subjects' own models put the achievable drop at 12.6 from basal and 18.5 from 250, so
    real settings ask for roughly half the insulin the physiology would take. Scaling the
    correction factor up under-corrects a high in the same way and by the same amount, which
    is a modelling choice rather than a measurement and is why it defaults to off.

    Carbohydrate ratio needs no such treatment. Real settings and measured ones agree, 8.0
    in the trial against 8.9 here, which is why `cr_scale` exists for symmetry and is not
    used by anything.
    """
    from ..population import params_for, therapy_for

    p = params if params is not None else params_for(name)
    q = settings if settings is not None else therapy_for(name)

    flat_u_per_hour = float(p["u2ss"]) * float(p["BW"]) / 6000.0 * 60.0
    shape = dawn_shape() if diurnal else np.ones(24)

    basal = flat_u_per_hour * shape
    isf = float(q["CF"]) * float(isf_scale) / shape
    cr = float(q["CR"]) * float(cr_scale) / shape
    tdi = float(q["TDI"]) if "TDI" in q else 2.0 * 24.0 * flat_u_per_hour

    return Profile(name=name, basal_u_per_hour=basal, isf=isf, cr=cr,
                   limits=limits or PumpLimits.conventional(basal, tdi),
                   total_daily_insulin=tdi)


__all__ = ["Profile", "for_subject", "dawn_shape", "TARGET_LO", "TARGET_HI"]
