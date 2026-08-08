"""A generic correction loop.

Not any particular automated insulin delivery algorithm: correction insulin towards a
target subject to an insulin-on-board bound, plus basal withdrawal when low or falling.
It exists because every real cohort these statistics are compared against is running a
closed loop, and a simulated person on open-loop basal-bolus is not comparable to them.
Adding it returned both glucose autocorrelations and glucose variability to the real
range after the behaviour layer had pushed them out.

For a comparison of real algorithms, replace this with the algorithm under test; it is
the baseline, not the subject.
"""
import numpy as np

from ..therapy.insulin import iob_fraction as _iob_fraction

# The residual after the behaviour layer (rebound and autocorrelation both too high, CV
# too high) all point the same way: the simulated person is treated by a basal-bolus
# controller that does nothing between meals, while every real cohort in the comparison
# is running a closed loop that corrects continuously. An over-treated low rebounds
# freely here and gets mopped up there. This layer tests that reading.
#
# It is a generic correction loop, not any shipped algorithm: correction insulin towards
# target subject to an insulin-on-board bound, and basal withdrawal when low or falling.
# The point is to establish whether continuous correction accounts for the residual, not
# to reproduce any particular algorithm.
DIA_MIN = 300.0           # insulin action duration
PEAK_MIN = 75.0           # bilinear activity peak
LOOP_TARGET = 120.0
LOOP_MAX_IOB_U = 6.0
LOOP_MIN_INTERVAL = 5.0   # minutes between corrections
LOOP_LOW_SUSPEND = 80.0   # withdraw basal below this
LOOP_FALL_SUSPEND = -1.5  # mg/dL/min


class CorrectionLoop:
    """Continuous correction with an insulin-on-board bound and basal withdrawal."""

    def __init__(self):
        self.boluses = []          # [(minute, units)]
        self.last_correction = -1e9

    def add(self, minute, units):
        if units > 0:
            self.boluses.append((minute, units))

    def iob(self, minute):
        return float(sum(u * _iob_fraction(minute - m) for m, u in self.boluses))

    def correction(self, minute, cgm, cf):
        if minute - self.last_correction < LOOP_MIN_INTERVAL:
            return 0.0
        need = (cgm - LOOP_TARGET) / cf - self.iob(minute)
        if need <= 0.05 or cgm < 150 or self.iob(minute) >= LOOP_MAX_IOB_U:
            return 0.0
        self.last_correction = minute
        dose = min(need * 0.5, 2.0)          # partial correction, as loops dose
        self.add(minute, dose)
        return float(dose)

    def basal_scale(self, cgm, fall_rate):
        if cgm < LOOP_LOW_SUSPEND or (cgm < 110 and fall_rate < LOOP_FALL_SUSPEND):
            return 0.0
        if cgm < 110:
            return 0.5
        return 1.0
