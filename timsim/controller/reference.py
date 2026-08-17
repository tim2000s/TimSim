"""A reference automated insulin delivery algorithm, and named ways of breaking it.

Two jobs. It is a worked example of an algorithm driven through the controller interface,
reading a profile by time of day the way a real system does. And it is the instrument the
ranking validation in `validation/ranking.py` needs, because you cannot check that a bench
ranks algorithms correctly by pointing it at algorithms whose true ranking you do not
know. You can check it against algorithms you have broken on purpose, where the direction
of the answer is known before the run.

The defects are the ones that show up in real incident reports and in the design of the
open-source systems: an insulin sensitivity setting that is too strong, no ceiling on
insulin on board, no basal withdrawal when glucose is falling, and acting on a reading
that is older than the algorithm thinks. Each takes a magnitude, so a defect can be dialled
from none to severe, which turns a pass or fail into a dose-response curve.

This is not a model of any shipped system. It is deliberately plain, so that when the
safety score moves you know which line moved it.
"""
import numpy as np
from simglucose.controller.base import Action, Controller

from ..therapy.insulin import iob as iob_of

CORRECTION_INTERVAL_MIN = 5.0
CORRECTION_FRACTION = 0.5        # dose half the calculated need, as loops do
MAX_CORRECTION_U = 2.0
CORRECT_ABOVE = 150.0
SUSPEND_BELOW = 80.0
SUSPEND_FALL_BELOW = 110.0
SUSPEND_FALL_RATE = -1.5         # mg/dL/min
HALF_BASAL_BELOW = 110.0
MAX_IOB_U = 6.0


class ReferenceAID(Controller):
    """Meal bolus, bounded correction, basal withdrawal. Configurable defects.

    Parameters other than `profile` describe what is wrong with it:

    `isf_scale` below one makes the algorithm believe insulin is weaker than it is, so it
    corrects harder. `cr_scale` does the same for meals. `use_iob_bound=False` removes the
    ceiling on insulin on board, which is what lets corrections stack. `use_low_suspend`
    controls whether basal is withdrawn on a low or a fast fall. `delay_min` makes the
    algorithm act on a reading that old, which is what a communications backlog looks like
    from the inside.
    """

    def __init__(self, name, profile=None, isf_scale=1.0, cr_scale=1.0,
                 use_iob_bound=True, use_low_suspend=True, delay_min=0.0,
                 max_iob_u=MAX_IOB_U, target=None):
        from ..therapy import profile as profile_mod

        self.name = name
        self.profile = profile if profile is not None else profile_mod.for_subject(name)
        self.isf_scale = float(isf_scale)
        self.cr_scale = float(cr_scale)
        self.use_iob_bound = bool(use_iob_bound)
        self.use_low_suspend = bool(use_low_suspend)
        self.delay_min = float(delay_min)
        self.max_iob_u = float(max_iob_u)
        self.target = float(target if target is not None else self.profile.target)

        self.doses = []              # [(minute, units)] as the pump reported delivering
        self._pending = None         # index of a dose awaiting its delivered amount
        self.history = []            # [(minute, reading)]
        self.last_correction = -1e9

    def reset(self):
        """Clear every piece of per-run state, including the index into the dose list.

        `_pending` points at the dose awaiting its delivered amount, and clearing the list
        without clearing it left an index into an empty list. A run that ends on a step where
        a bolus was given leaves one set, so reusing the controller raised IndexError on the
        next run's first cycle rather than on the last one's, which is the kind of failure
        that gets blamed on the wrong subject.
        """
        self.doses, self.history, self.last_correction = [], [], -1e9
        self._pending = None

    def _delayed(self, minute, reading):
        """The reading the algorithm acts on, once `delay_min` has been applied."""
        self.history.append((minute, float(reading)))
        if self.delay_min <= 0:
            return float(reading), 0.0
        want = minute - self.delay_min
        usable = [(m, v) for m, v in self.history if m <= want]
        if not usable:
            return float(self.history[0][1]), 0.0
        recent = usable[-2:]
        rate = ((recent[-1][1] - recent[0][1]) / (recent[-1][0] - recent[0][0])
                if len(recent) == 2 and recent[-1][0] > recent[0][0] else 0.0)
        return usable[-1][1], rate

    def _fall_rate(self, minute, value):
        if len(self.history) < 2:
            return 0.0
        (m0, v0), (m1, v1) = self.history[-2], self.history[-1]
        return (v1 - v0) / (m1 - m0) if m1 > m0 else 0.0

    def policy(self, observation, reward, done, **info):
        sample = float(info.get("sample_time", 5.0))
        minute = float(info.get("clock_minutes", 0.0))
        cgm, delayed_rate = self._delayed(minute, observation.CGM)
        fall = delayed_rate if self.delay_min > 0 else self._fall_rate(minute, cgm)

        isf = self.profile.isf_at(minute) * self.isf_scale
        cr = self.profile.cr_at(minute) * self.cr_scale
        grams = float(info.get("meal", 0.0)) * sample

        # What the pump reports having delivered, which is not what was asked for: the
        # delivery ceilings in therapy/limits.py sit between the two. A loop that keeps
        # its own request as its dose record drifts away from reality on every clamp, and
        # this one had reached a believed 41.7 U on board against a real 10. The
        # open-source systems all reconstruct insulin on board from pump history for
        # exactly this reason.
        delivered = info.get("delivered_bolus_u")
        if delivered is not None and self._pending is not None:
            at, _ = self.doses[self._pending]
            self.doses[self._pending] = (at, float(delivered))
            self._pending = None

        on_board = iob_of(minute, self.doses)
        headroom = (max(self.max_iob_u - on_board, 0.0)
                    if self.use_iob_bound else float("inf"))

        # A meal bolus is a bolus calculator: cover the carbohydrate, correct what is
        # already there, subtract what is already working. Covering the carbohydrate is
        # not bounded by insulin on board, because the carbohydrate is real and arriving.
        # Correcting on top of it is, and it used not to be: this line added an uncapped
        # full correction with no subtraction, on top of a correction block that then
        # fired again on the same reading.
        bolus, corrected_with_meal = 0.0, False
        if grams > 0:
            correction = 0.0
            if cgm > CORRECT_ABOVE:
                correction = min(max((cgm - self.target) / isf - on_board, 0.0), headroom)
                corrected_with_meal = True
            bolus = max(grams / cr + correction, 0.0)

        if (not corrected_with_meal
                and minute - self.last_correction >= CORRECTION_INTERVAL_MIN
                and cgm >= CORRECT_ABOVE):
            need = (cgm - self.target) / isf
            if self.use_iob_bound:
                need -= on_board
            if need > 0.05:
                # The ceiling bounds where insulin on board ends up, not merely whether a
                # dose may start. Testing `on_board < max_iob_u` alone let a full 2 U land
                # at 5.9 U on board and finish at 7.9.
                extra = min(need * CORRECTION_FRACTION, MAX_CORRECTION_U, headroom)
                if extra > 0.0:
                    bolus += float(extra)
                    self.last_correction = minute

        basal = self.profile.basal_at(minute)
        if self.use_low_suspend:
            if cgm < SUSPEND_BELOW or (cgm < SUSPEND_FALL_BELOW and fall < SUSPEND_FALL_RATE):
                basal = 0.0
            elif cgm < HALF_BASAL_BELOW:
                basal *= 0.5

        if bolus > 0:
            self.doses.append((minute, bolus))
            self._pending = len(self.doses) - 1
        return Action(basal=basal, bolus=bolus / sample)


def factory(**defects):
    """A `controller_factory` for `simulate_cohort`, with the defects dialled in."""
    return lambda name: ReferenceAID(name, **defects)


__all__ = ["ReferenceAID", "factory"]
