"""Level 7: what the system under test does when its inputs go wrong.

The six levels in `docs/VALIDATION.md` ask whether the simulator resembles reality and
how finely it can discriminate. Neither question covers the one a safety bench exists to
answer, which is whether an algorithm behaves sensibly when the sensor stops reporting,
the pump stops delivering, or the clock moves. Those are the conditions that produce
incident reports, and no amount of distributional fidelity says anything about them.

Each fault here is injected into an otherwise ordinary run. Pair it with an unfaulted
control on the same subject and seed and the difference is attributable to the fault. The
useful output is a trace someone can look at rather than a summary statistic, because
what you are looking for is a behaviour rather than a number: does the algorithm fall back
to profile basal, does it recover, and does it avoid doing something large and wrong at
the moment the input returns.

A fault does not decide whether the algorithm passed. It creates the conditions and
records what it did. `expected` on each class states what a sensible system does, in
words, so that a reviewer reading the trace knows what they are looking for.
"""
import numpy as np

from ..sensor.realism import dip_profile


class Fault:
    """Base class. Every hook defaults to leaving the run alone."""
    expected = ""

    def cgm(self, minute, reading):
        """The reading the algorithm gets. None means no new reading arrived."""
        return reading

    def delivery(self, minute, basal_u_per_min, bolus_u):
        """What actually reaches the body, after the algorithm has asked for something."""
        return basal_u_per_min, bolus_u

    def clock(self, minute):
        """The time the algorithm thinks it is."""
        return minute

    def describe(self):
        return {"fault": type(self).__name__, "expected": self.expected,
                **{k: v for k, v in vars(self).items() if not k.startswith("_")}}


class NoReadings(Fault):
    """The sensor stops reporting for a while, which is the commonest real failure."""
    expected = ("fall back to profile basal, hold it, and resume without a catch-up "
                "correction for the glucose that moved while it was blind")

    def __init__(self, start_min, duration_min):
        self.start_min = float(start_min)
        self.duration_min = float(duration_min)

    def cgm(self, minute, reading):
        if self.start_min <= minute < self.start_min + self.duration_min:
            return None
        return reading


class SensorRestart(Fault):
    """A session ends, a new sensor warms up, and it comes back reading differently."""
    expected = ("treat the step change at resumption as a new sensor rather than as a "
                "real rise, and not bolus for it")

    def __init__(self, start_min, warmup_min=120.0, offset_mgdl=25.0):
        self.start_min = float(start_min)
        self.warmup_min = float(warmup_min)
        self.offset_mgdl = float(offset_mgdl)

    def cgm(self, minute, reading):
        if self.start_min <= minute < self.start_min + self.warmup_min:
            return None
        if minute >= self.start_min:
            return reading + self.offset_mgdl
        return reading


class StuckReading(Fault):
    """The transmitter repeats its last value. The trace looks alive and is not."""
    expected = ("notice the trace has stopped moving and stop dosing on a delta that is "
                "structurally zero")

    def __init__(self, start_min, duration_min=45.0):
        self.start_min = float(start_min)
        self.duration_min = float(duration_min)
        self._held = None

    def cgm(self, minute, reading):
        if self.start_min <= minute < self.start_min + self.duration_min:
            if self._held is None:
                self._held = reading
            return self._held
        self._held = None
        return reading


class CompressionLow(Fault):
    """A false low from lying on the sensor, placed where you want it rather than at random."""
    expected = ("withdraw insulin if it likes, but not deliver carbohydrate-driven "
                "correction afterwards for a rise that never happened")

    def __init__(self, start_min, depth_mgdl=45.0, sample_minutes=5.0):
        self.start_min = float(start_min)
        self.depth_mgdl = float(depth_mgdl)
        self.sample_minutes = float(sample_minutes)
        self._shape = dip_profile(sample_minutes)

    def cgm(self, minute, reading):
        k = int(round((minute - self.start_min) / self.sample_minutes))
        if 0 <= k < len(self._shape):
            return max(reading - self.depth_mgdl * self._shape[k], 39.0)
        return reading


class NoDelivery(Fault):
    """Insulin is requested and does not arrive: a lost pump link, or an occlusion.

    The algorithm is not told. That is the point of the scenario, and it is why insulin on
    board reconstructed from what was commanded diverges from what the body received.
    """
    expected = ("recover without a large correction at the moment delivery resumes, "
                "since the insulin it believes is on board was never given")

    def __init__(self, start_min, duration_min=60.0):
        self.start_min = float(start_min)
        self.duration_min = float(duration_min)
        self.units_lost = 0.0

    def delivery(self, minute, basal_u_per_min, bolus_u):
        if self.start_min <= minute < self.start_min + self.duration_min:
            self.units_lost += bolus_u
            return 0.0, 0.0
        return basal_u_per_min, bolus_u


class ClockShift(Fault):
    """The clock moves, as it does twice a year and whenever someone changes timezone."""
    expected = ("apply the profile block for the real hour, and neither duplicate nor "
                "skip dosing across the discontinuity")

    def __init__(self, start_min, shift_min=60.0, duration_min=None):
        self.start_min = float(start_min)
        self.shift_min = float(shift_min)
        self.duration_min = duration_min

    def clock(self, minute):
        end = (self.start_min + self.duration_min) if self.duration_min else np.inf
        if self.start_min <= minute < end:
            return minute + self.shift_min
        return minute


class Faults:
    """Several faults on one run, applied in the order given."""

    def __init__(self, *faults):
        self.faults = [f for f in faults if f is not None]

    def cgm(self, minute, reading):
        for f in self.faults:
            if reading is None:
                return None
            reading = f.cgm(minute, reading)
        return reading

    def delivery(self, minute, basal_u_per_min, bolus_u):
        for f in self.faults:
            basal_u_per_min, bolus_u = f.delivery(minute, basal_u_per_min, bolus_u)
        return basal_u_per_min, bolus_u

    def clock(self, minute):
        for f in self.faults:
            minute = f.clock(minute)
        return minute

    def report(self):
        return {"faults": [f.describe() for f in self.faults]}


def unannounced_meal_then_rescue(days, rng, body_weight, meal_hour=13.0, grams=100.0):
    """The classic stacking scenario: a large meal the algorithm is not told about.

    The rescue that follows is supplied by the behaviour layer rather than scripted, since
    whether the person goes low at all is part of what the algorithm determines.
    """
    from ..simulation.run import draw_meals

    schedule = draw_meals(days, rng, body_weight)
    schedule.append((24.0 + meal_hour, float(grams), False))
    return sorted(schedule)


SCENARIOS = {
    "no_readings_1h": lambda: NoReadings(start_min=26 * 60, duration_min=60),
    "no_readings_3h": lambda: NoReadings(start_min=26 * 60, duration_min=180),
    "sensor_restart": lambda: SensorRestart(start_min=26 * 60),
    "stuck_reading": lambda: StuckReading(start_min=26 * 60),
    "compression_low": lambda: CompressionLow(start_min=26 * 60),
    "no_delivery_1h": lambda: NoDelivery(start_min=26 * 60, duration_min=60),
    "no_delivery_2h": lambda: NoDelivery(start_min=26 * 60, duration_min=120),
    "clock_forward_1h": lambda: ClockShift(start_min=26 * 60, shift_min=60),
}


__all__ = ["Fault", "Faults", "NoReadings", "SensorRestart", "StuckReading",
           "CompressionLow", "NoDelivery", "ClockShift", "SCENARIOS",
           "unannounced_meal_then_rescue"]
