"""A subject whose insulin sensitivity varies, in the way the S2013 model added.

The published 2008 personae hold every parameter fixed for the length of a run, so the
same person on the same day responds identically every time. Real sensitivity moves: it
dips before dawn and it drifts from one day to the next by a substantial fraction.

The licensed S2013 model's headline refinement over 2008 is exactly this. The licensed
model is not freely available, so what is implemented here is the mechanism rather than
the model: a common time-varying factor scaling insulin-dependent glucose uptake (Vmx)
and hepatic insulin action on endogenous production (kp3), with a dawn component and a
day-to-day component at clinically reported magnitudes.

Measured, this closes the glucose-variability gap between the published personae and real
data, and it closes nothing else, which is the useful thing to know about it: refining
the physiology fixes the physiology-linked statistics and leaves the disturbances alone.
"""
import numpy as np
from simglucose.patient.t1dpatient import T1DPatient

# Dalla Man et al. (2014) calibrate intraday and interday sensitivity variation from
# clinical data. These magnitudes are in the range that literature reports; they are a
# modelling choice at the centre of it rather than a fit to anything here.
DIURNAL_AMPLITUDE = 0.20      # fractional dip in sensitivity, lowest around 06:00
INTERDAY_CV = 0.22            # day-to-day coefficient of variation
SENSITIVITY_BOUNDS = (0.3, 2.5)


class VaryingPatient(T1DPatient):
    """T1DPatient with a time-varying insulin-sensitivity factor.

    Construct with `withName` as usual, then call `set_sensitivity` before stepping. A
    patient that has not had `set_sensitivity` called behaves exactly as the stock
    T1DPatient, so this class is a safe drop-in.
    """

    def set_sensitivity(self, rng, n_days, diurnal=DIURNAL_AMPLITUDE,
                        interday_cv=INTERDAY_CV):
        self._vmx0 = float(self._params["Vmx"])
        self._kp30 = float(self._params["kp3"])
        self._diurnal = float(diurnal)
        sigma = np.sqrt(np.log(1.0 + interday_cv ** 2))
        self._interday = rng.lognormal(-0.5 * sigma ** 2, sigma, size=int(n_days) + 2)
        self._varying = True

    def sensitivity(self):
        """The factor in force now. 1.0 means the published parameter value."""
        if not getattr(self, "_varying", False):
            return 1.0
        hour = (self.t / 60.0) % 24
        day = int(self.t // 1440)
        dawn = 1.0 - self._diurnal * np.cos(2 * np.pi * (hour - 6) / 24)
        return float(np.clip(dawn * self._interday[day], *SENSITIVITY_BOUNDS))

    def step(self, action):
        if getattr(self, "_varying", False):
            si = self.sensitivity()
            self._params["Vmx"] = self._vmx0 * si
            self._params["kp3"] = self._kp30 * si
        return super().step(action)


def from_population(name, **kwargs):
    """Build a VaryingPatient from this package's generated population."""
    import pandas as pd
    from ..population import params_for
    return VaryingPatient(pd.Series(params_for(name)), **kwargs)
