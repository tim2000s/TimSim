"""Pump and algorithm delivery limits, enforced between the controller and the body.

simglucose's own pump quantises to about 8e-6 U/min and clamps at 30 U/min, which is 150
units in a single five-minute step. Neither figure resembles a real device, and neither
constrains anything an algorithm might ask for. That is fine for a fidelity study and
wrong for a safety bench, because a large part of what makes an automated insulin
delivery system safe is where its ceilings sit and whether they bind.

So the limits live here, in front of the pump, and every clamp is counted. A run that
reports a maximum bolus limit binding forty times is telling you something about the
algorithm that its glucose trace will not.

The default magnitudes are conventional rather than measured. Maximum basal at four times
the highest scheduled rate and maximum insulin on board around a seventh of the daily
dose are in the region of what the open-source systems ship with and what clinicians set.
They are a modelling choice, they are stated here, and `PumpLimits` takes whatever you
would rather use.
"""
from dataclasses import dataclass, field

from .insulin import DIA_MIN, PEAK_MIN, iob


def _to_nearest(value, step):
    """Round a basal rate to the nearest deliverable increment, as a device does.

    Rounding down instead looks conservative and is not. A basal rate is a rate applied on
    every cycle, so truncating it under-delivers continuously, and on a subject whose
    steady state was closed at the exact rate that shows up as a standing offset: 1.19 U/h
    truncated to 1.15 leaves the subject about 6 mg/dL high, where rounding to the nearest
    0.05 leaves it about 2.
    """
    if step <= 0:
        return float(value)
    return float(int(value / step + 0.5) * step)


def _round_down(value, step):
    """Round a bolus down to a deliverable increment.

    Boluses round the other way from basal rates, for a reason worth keeping. A bolus is
    computed fresh each time rather than applied continuously, so rounding down costs a
    fraction of a percent and does not accumulate. What it buys is that a ceiling holds
    exactly. Rounding a bolus of 0.03 U to the nearest 0.05 returns 0.05, which walks
    straight back through the insulin-on-board ceiling that produced the 0.03.
    """
    if step <= 0:
        return float(value)
    return float(int(value / step) * step)


@dataclass
class PumpLimits:
    """What the device and the algorithm's own configuration will allow."""
    max_basal_u_per_hour: float
    max_bolus_u: float
    max_iob_u: float
    basal_increment_u_per_hour: float = 0.05
    bolus_increment_u: float = 0.05
    dia_min: float = DIA_MIN
    peak_min: float = PEAK_MIN

    @classmethod
    def conventional(cls, scheduled_basal_u_per_hour, total_daily_insulin):
        """Defaults in the region the open-source systems and clinicians use."""
        peak_basal = float(max(scheduled_basal_u_per_hour))
        tdi = float(total_daily_insulin)
        return cls(max_basal_u_per_hour=round(4.0 * peak_basal, 2),
                   max_bolus_u=round(max(10.0, 0.15 * tdi), 2),
                   max_iob_u=round(max(6.0, 0.15 * tdi), 2))


@dataclass
class Enforcer:
    """Applies the limits to a requested action, and records what bound.

    Insulin on board is counted the way the open-source systems count it: bolus insulin
    plus whatever basal was delivered above the scheduled rate. Basal delivered at or
    below schedule is the person's background requirement rather than something the
    algorithm added, so counting it would make the ceiling bind on everyone immediately.
    """
    limits: PumpLimits
    doses: list = field(default_factory=list)      # [(minute, units)] above schedule
    bound: dict = field(default_factory=lambda: {"basal": 0, "bolus": 0, "iob": 0})
    peak_iob_u: float = 0.0

    def iob(self, minute):
        return iob(minute, self.doses, self.limits.dia_min, self.limits.peak_min)

    def apply(self, minute, basal_u_per_min, bolus_u, scheduled_basal_u_per_min,
              sample_minutes):
        """Clamp a requested action. Returns (basal U/min, bolus U) as delivered."""
        lim = self.limits

        rate = max(0.0, float(basal_u_per_min)) * 60.0
        if rate > lim.max_basal_u_per_hour:
            rate = lim.max_basal_u_per_hour
            self.bound["basal"] += 1
        rate = _to_nearest(rate, lim.basal_increment_u_per_hour)
        # Quantising after the clamp can round back through it, since `_to_nearest` rounds up
        # as readily as down: a ceiling of 2.03 U/h on a 0.05 increment returns 2.05. The
        # ceiling is the constraint and the increment is the device, so the increment gives way.
        if rate > lim.max_basal_u_per_hour:
            rate = _round_down(lim.max_basal_u_per_hour, lim.basal_increment_u_per_hour)
        basal = rate / 60.0

        bolus = max(0.0, float(bolus_u))
        if bolus > lim.max_bolus_u:
            bolus = lim.max_bolus_u
            self.bound["bolus"] += 1

        # The insulin-on-board ceiling has to constrain basal above schedule as well as
        # bolus, which is how the open-source systems apply it: a temp basal is cut back
        # when it would breach max IOB. An earlier version here bounded only the bolus, so
        # an algorithm holding its basal at the maximum walked insulin on board straight
        # through the ceiling, 10.8 U against a declared 8.6.
        on_board = self.iob(minute)
        headroom = max(0.0, lim.max_iob_u - on_board)
        if bolus > headroom:
            bolus = headroom
            self.bound["iob"] += 1
        bolus = _round_down(bolus, lim.bolus_increment_u)

        scheduled = max(0.0, float(scheduled_basal_u_per_min))
        above = max(0.0, basal - scheduled) * sample_minutes
        remaining = max(0.0, headroom - bolus)
        if above > remaining:
            # Never below the schedule. Rounding down the sum can land under it when the
            # scheduled rate does not sit on an increment boundary, and a scheduled 0.62 U/h
            # then returns 0.60. Basal at or below schedule is the person's own background
            # requirement rather than something the algorithm added, so the ceiling has no
            # claim on it: withholding part of it treats a delivery limit as a reason to
            # under-treat.
            capped = _round_down((scheduled + remaining / sample_minutes) * 60.0,
                                 lim.basal_increment_u_per_hour) / 60.0
            basal = max(scheduled, capped)
            above = max(0.0, basal - scheduled) * sample_minutes
            self.bound["iob"] += 1

        if bolus + above > 0:
            self.doses.append((minute, bolus + above))
        self.peak_iob_u = max(self.peak_iob_u, on_board + bolus + above)
        return basal, bolus

    def report(self):
        return {"limit_bound": dict(self.bound), "peak_iob_u": float(self.peak_iob_u),
                "max_iob_u": float(self.limits.max_iob_u),
                "max_basal_u_per_hour": float(self.limits.max_basal_u_per_hour),
                "max_bolus_u": float(self.limits.max_bolus_u)}


__all__ = ["PumpLimits", "Enforcer"]
