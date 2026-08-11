"""Drive the Boost algorithm inside TimSim.

TimSim hands a controller one glucose reading, a therapy profile and an announced
carbohydrate rate. Boost wants rather more than that: deltas over several horizons, the
acceleration between them, oref's forward projection, insulin and carbohydrate on board,
and a predicted minimum for its own hard gate. This adapter reconstructs those.

The reconstruction is a modelling choice and it is the part most likely to be wrong, so it
is worth saying where the risk sits. If the adapter builds inputs that do not resemble the
ones Boost sees in the field, then everything downstream is a test of the adapter rather
than of the algorithm or of the simulator. That failure is checkable rather than
hypothetical: `validation/boost.py` holds 193,714 real input records, and
`tests/test_boost.py` compares the inputs this adapter produces against them field by
field. An adapter that drifts shows up there.

Two quantities are approximations of oref internals that TimSim has no equivalent for, and
both are documented at the point they are computed rather than buried:

`eventual_bg` is oref's projection of where glucose settles, and it is the input that
decides whether Boost ever commits to a meal: the CONFIRMED transition needs it to exceed
target by 50 mg/dL. The naive reconstruction, current glucose minus the full effect of
insulin on board, is badly wrong. Against 704,389 logged decisions it sits 45 mg/dL below
current glucose where oref sits 12 below, correlates at 0.249, and crosses the confirm
threshold on 3.5% of cycles against a real 18.4%. An algorithm fed that will almost never
commit, which is not a property of the simulator but of the reconstruction.

The version here is calibrated against oref's own logged output, which is available because
the plugin records `sug_eventualbg` on every decision. Only about a third of the insulin on
board shows up in the projection, because the rest is already covering the carbohydrate and
the basal need the projection also accounts for. Fitting an input reconstruction to ground
truth is not the same as fitting to the statistic under judgement: what is being tested is
the simulator's state occupancy, and that appears nowhere in this fit.

`min_guard_bg` is oref's predicted minimum over the horizon. It projects the current trend
forward and subtracts the insulin that will actually act within that horizon, which is a
fraction of insulin on board rather than all of it. Getting that wrong is instructive: a
first version subtracted the whole of insulin on board, which put the predicted minimum
about 38 mg/dL below current glucose against a real 20, tripped the hard gate on 39% of
cycles against a real 8.6%, and left Boost gated off for most of the run. The comparison
against the real cycle records is what surfaced it.
"""
from collections import deque

import numpy as np
from simglucose.controller.base import Action, Controller

from ..therapy.insulin import DIA_MIN, PEAK_MIN, iob_fraction

HISTORY_SAMPLES = 8               # 40 minutes at five-minute sampling
CARB_ABSORPTION_G_PER_MIN = 0.5   # a plain linear decay, in the usual clinical region
MIN_GUARD_THRESHOLD = 80.0        # mg/dL, the value the real cohort carries
ROUND_SMB_TO = 0.05
PROJECTION_MINUTES = 30.0
SHORT_DELTA_SAMPLES = 3           # the window Boost's short average and maxDelta read

# Least squares against 704,389 logged decisions, regressing oref's own `sug_eventualbg`
# minus current glucose on the terms oref combines. Correlation 0.538, mean absolute error
# 34.9 mg/dL, and the tail that matters lands: the confirm threshold is crossed on 17.2% of
# cycles against a logged 18.4%, where the naive formula manages 3.5%.
EVENTUAL_IOB_COEF = -0.3338       # per U x mg/dL/U of insulin on board
EVENTUAL_COB_COEF = 0.07561       # per g x mg/dL/U of carbohydrate on board
EVENTUAL_TREND_COEF = 5.843       # per mg/dL per 5 min of short average delta
EVENTUAL_CONST = 6.33

# oref does not ask for the whole gap between the projection and target. Measured on the
# same 704,386 logged decisions, its insulinReq is 0.41 times the naive quotient, it is zero
# whenever the projection sits at or below target on 100% of cycles, and it is still zero on
# a third of the cycles where the projection is above it. Asking for the full quotient is
# what drove this adapter to 0.199 U a cycle against a logged 0.083, and time below range to
# 11.5%.
INSULIN_REQ_FRACTION = 0.41

# Margin above target below which oref runs a reduced temp basal rather than a zero one.
LOW_TEMP_MARGIN_MGDL = 20.0


class BoostController(Controller):
    """The Boost V5 pipeline, fed from TimSim.

    `config` is a `V5Config` from the harness, so a sweep over its constants is a sweep
    over this controller. Leaving it as None takes the shipped defaults.
    """

    def __init__(self, name, profile=None, config=None, harness=None,
                 min_guard_threshold=MIN_GUARD_THRESHOLD, target_bg=None):
        from ..therapy import profile as profile_mod
        from ..validation import boost as boost_ref

        self.h = harness or boost_ref.harness()
        self.name = name
        self.profile = profile if profile is not None else profile_mod.for_subject(name)
        self.config = config or self.h.V5Config()
        self.state = self.h.StateMachineState()
        self.min_guard_threshold = float(min_guard_threshold)
        # The real cohort runs a target around 90 mg/dL, where this package's profile
        # defaults to 110. A comparison against those users has to match their
        # configuration, since the target is an input to the algorithm rather than a
        # property of the person.
        self.target_bg = float(target_bg) if target_bg is not None else None

        self.readings = deque(maxlen=HISTORY_SAMPLES)
        self.doses = []                # [(minute, units)] this algorithm believes it gave
        self.cob_g = 0.0
        self.null_streak = 0
        self.cycles = []               # every CycleInput built, for comparison against real
        self.outputs = []              # every CycleOutput, for the response profile
        self.basal_deviations = []     # (minute, delivered - scheduled) for negative IOB
        self.delta_history = []        # successive GlucoseStatus deltas, not raw differences

    # ------------------------------------------------------------------ derived inputs
    def _iob(self, minute):
        return float(sum(u * iob_fraction(minute - m, DIA_MIN, PEAK_MIN)
                         for m, u in self.doses))

    def _iob_after(self, minute, horizon):
        """Insulin still on board `horizon` minutes from now, given no further doses."""
        return float(sum(u * iob_fraction(minute + horizon - m, DIA_MIN, PEAK_MIN)
                         for m, u in self.doses))

    def _activity_u_per_hour(self, minute):
        """Insulin acting right now, as the rate Boost logs. A five-minute difference of
        insulin on board, scaled to the hour."""
        now, then = self._iob(minute), self._iob(minute - 5.0)
        return max(0.0, (then - now)) * 12.0

    def _deltas(self):
        r = list(self.readings)
        return [r[i + 1] - r[i] for i in range(len(r) - 1)]

    def glucose_status(self, sample=5.0):
        """delta, shortAvgDelta and longAvgDelta as AndroidAPS computes them.

        Not a difference of consecutive readings. Every earlier reading contributes
        `(current - then) / minutesAgo * 5`, and the three figures are averages of those
        contributions over separate windows: 2.5 to 7.5 minutes for the delta, 2.5 to 17.5
        for the short average, and 17.5 to 42.5 for the long average. See `DeltaCalculator`
        in the AndroidAPS tree.

        This exists because `max_delta` is a hard gate and was being built here as the
        largest absolute recent difference, which is a different quantity: a median of 6.3
        against 2.0 in the field. The comparison the package held itself against was also
        wrong, taking `abs(delta)` of a single sample, so neither side matched oref.
        """
        r = list(self.readings)
        if len(r) < 2:
            return 0.0, 0.0, 0.0
        now = r[-1]
        last, short, long = [], [], []
        for k in range(1, len(r)):
            ago = k * sample
            if ago <= 0:
                continue
            contribution = (now - r[-1 - k]) / ago * 5.0
            if 2.5 <= ago <= 7.5:
                last.append(contribution)
            if 2.5 <= ago <= 17.5:
                short.append(contribution)
            if 17.5 <= ago <= 42.5:
                long.append(contribution)
        mean = lambda v: float(sum(v) / len(v)) if v else 0.0
        return mean(last), mean(short), mean(long)

    def _basal_iob(self, minute):
        """Insulin on board from basal delivery relative to what was scheduled.

        AndroidAPS measures insulin on board against the scheduled basal, so a loop that has
        been withholding basal carries a negative figure: real users sit at -0.4 U at the
        fifth percentile. Counting boluses alone put this cohort at +0.3, lifted the median
        from 0.7 to 2.2 and fired the headroom brake on 25.4% of decisions against a real
        2.3%.
        """
        return float(sum(u * iob_fraction(minute - m, DIA_MIN, PEAK_MIN)
                         for m, u in self.basal_deviations))

    def observe_basal(self, minute, delivered_u, scheduled_u):
        """Record how far the basal delivered in this step sat from the schedule."""
        deviation = float(delivered_u) - float(scheduled_u)
        if abs(deviation) > 1e-9:
            self.basal_deviations.append((float(minute), deviation))

    def policy(self, observation, reward, done, **info):
        # Record what the pump did with the last basal instruction before deciding, so this
        # cycle's insulin on board reflects it.
        delivered = info.get("delivered_basal_u")
        scheduled = info.get("scheduled_basal_u")
        if delivered is not None and scheduled is not None:
            self.observe_basal(float(info.get("clock_minutes", 0.0)) - float(
                info.get("sample_time", 5.0)), delivered, scheduled)
        sample = float(info.get("sample_time", 5.0))
        minute = float(info.get("clock_minutes", 0.0))
        bg = float(observation.CGM)
        self.readings.append(bg)

        deltas = self._deltas()
        delta, short_avg, long_avg = self.glucose_status(sample)
        self.delta_history.append(delta)
        # The acceleration Boost reads is the current delta against the recent average, as
        # a percentage. Confirmed against the real records: a delta of 7.0 with a short
        # average of 2.75 is logged as 154.5.
        accl = 100.0 * (delta - short_avg) / abs(short_avg) if abs(short_avg) > 1e-6 else 0.0
        accl = float(np.clip(accl, -500.0, 500.0))

        isf = self.profile.isf_at(minute)
        cr = self.profile.cr_at(minute)
        target = self.target_bg if self.target_bg is not None else self.profile.target
        iob = self._iob(minute) + self._basal_iob(minute)

        grams = float(info.get("meal", 0.0)) * sample
        self.cob_g = max(0.0, self.cob_g - CARB_ABSORPTION_G_PER_MIN * sample) + grams

        # oref's projection, calibrated against its own logged values rather than derived.
        eventual = (bg
                    + EVENTUAL_IOB_COEF * iob * isf
                    + EVENTUAL_COB_COEF * self.cob_g * isf
                    + EVENTUAL_TREND_COEF * short_avg
                    + EVENTUAL_CONST)

        # The predicted minimum the hard gate reads: the current trend carried forward
        # half an hour, less the insulin that acts within that half hour. Only a fraction
        # of insulin on board acts in thirty minutes, so subtracting all of it is what
        # makes a simulated run look far more hypoglycaemic than it is.
        trend = short_avg * (PROJECTION_MINUTES / sample)
        acting_soon = iob - self._iob_after(minute, PROJECTION_MINUTES)
        min_guard = min(bg, bg + trend - acting_soon * isf)

        recent_low = min(self.readings) if self.readings else bg
        recent_deltas = deltas[-SHORT_DELTA_SAMPLES:]

        # The plugin reads this straight off oref: `(rT.insulinReq ?: 0.0).coerceAtLeast(0.0)`.
        # oref will not ask for insulin that would breach the insulin-on-board ceiling, so the
        # request is bounded by the headroom. Leaving it unbounded is what gave this adapter a
        # ninety-fifth percentile of 9.1 U against a real 1.8, which over-delivered, built
        # insulin on board, and then held the algorithm down through its own brakes.
        headroom = max(0.0, self.profile.limits.max_iob_u - iob)
        base_req = (max(0.0, eventual - target) / isf * INSULIN_REQ_FRACTION) if isf > 0 else 0.0
        base_req = min(base_req, headroom)

        cycle = self.h.CycleInput(
            delta=delta,
            short_avg_delta=short_avg,
            delta_accl=accl,
            bg=bg,
            eventual_bg=eventual,
            target_bg=target,
            iob=iob,
            cob=self.cob_g,
            base_insulin_req=base_req,
            max_iob=self.profile.limits.max_iob_u,
            ml_hypo_risk=None,
            ml_meal_likely=None,
            recent_low_bg=recent_low,
            hour=int((minute // 60) % 24),
            exercise_active=False,
            post_exercise_window=False,
            enable_smb_pre_checks=True,
            min_guard_bg=min_guard,
            min_guard_threshold=self.min_guard_threshold,
            # oref's maxDelta: the largest of the three, signed. Not an absolute maximum
            # over a window, which is what this was and which is a different gate.
            max_delta=max(delta, short_avg, long_avg),
            round_smb_to=ROUND_SMB_TO,
            sensor_quality_ok=float(info.get("stale_minutes", 0.0)) <= sample,
            # Successive GlucoseStatus deltas rather than raw differences of consecutive
            # readings. `deltaDeclining` asks for three strictly decreasing values, and a
            # raw difference on this sensor is mostly noise, so the condition that exits
            # COMMITTED almost never fired: the state held 25.2% of cycles against a logged
            # 5.4%. The windowed delta is what AndroidAPS would supply.
            delta_history=tuple(self.delta_history[-3:]),
            iob_activity_uh=self._activity_u_per_hour(minute),
        )

        # No ML models here, so the null streak grows and the score renormalises, which is
        # the documented behaviour when the models fail to load on a phone.
        self.null_streak += 1
        out, self.state = self.h.step(self.state, cycle, self.config,
                                      null_streak=self.null_streak)

        self.cycles.append(cycle)
        self.outputs.append(out)
        if out.final_dose > 0:
            self.doses.append((minute, out.final_dose))

        # Boost only decides the microbolus. The basal decision belongs to oref's
        # determine-basal, which is not ported, so without something here the profile basal
        # runs at full rate underneath every SMB and the two add up. That over-delivered by
        # roughly a factor of two and put time below range at 9.2%.
        #
        # What is implemented is oref's own low-glucose behaviour rather than a tuned rule:
        # zero temp when the projection is below target or the predicted minimum is under the
        # guard threshold, half rate when the projection is below target plus a margin, and
        # profile rate otherwise.
        basal = self.profile.basal_at(minute)
        if eventual < target or min_guard < self.min_guard_threshold:
            basal = 0.0
        elif eventual < target + LOW_TEMP_MARGIN_MGDL:
            basal *= 0.5
        return Action(basal=basal, bolus=out.final_dose / sample)

    # ------------------------------------------------------------------ reporting
    def profile_of_responses(self):
        from ..validation import boost as boost_ref
        return boost_ref.response_profile(self.outputs)


def factory(**kwargs):
    """A `controller_factory` for `simulate_cohort`."""
    return lambda name: BoostController(name, **kwargs)


__all__ = ["BoostController", "factory", "HISTORY_SAMPLES"]
