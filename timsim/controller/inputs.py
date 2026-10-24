"""The inputs an automated insulin delivery algorithm expects, reconstructed once.

TimSim hands a controller a glucose reading, a therapy profile and an announced
carbohydrate rate. Every algorithm worth testing wants considerably more: deltas over
several horizons, insulin on board measured the way the application measures it, and in
oref's case the whole forward curve of insulin activity rather than a single figure.

This module holds that reconstruction so the algorithms under test share one version of it.
The reason is not tidiness. Two adapters computing insulin on board slightly differently
would produce a difference between Boost and oref that belongs to neither algorithm, and
the package would have no way to tell that from a real one.

The reconstruction is the part most likely to be wrong, and it has been wrong here before.
Four defects were found by comparing against 193,714 logged input records rather than by
reading the code: deltas built as consecutive differences instead of AndroidAPS's windowed
averages, insulin on board counted from boluses alone so it never went negative, a maximum
delta taken as the largest absolute recent difference, and a delta history of raw
differences. Each is recorded at the method it affects.
"""
from collections import deque

# The AndroidAPS adapters compute insulin on board as AndroidAPS does, with oref0's exponential
# curve. Until 9 October 2026 they used the package's own `iob_fraction`, which leaves more of
# each unit on board between one and four hours; see docs/ISSUES.md 54.
from ..therapy.insulin import DIA_MIN, PEAK_MIN
from ..therapy.insulin import oref_iob_fraction as iob_fraction

HISTORY_SAMPLES = 8               # 40 minutes at five-minute sampling
CARB_ABSORPTION_G_PER_MIN = 0.5   # a plain linear decay, in the usual clinical region


class LoopInputs:
    """Ledgers of what was delivered and what was read, and the quantities derived from them.

    A mixin rather than a base class with behaviour of its own, so an adapter inherits the
    reconstruction and supplies only the marshalling its own algorithm needs.
    """

    # The activity peak the loop assumes for its insulin. AndroidAPS takes it from the insulin
    # plugin: 75 minutes for its rapid-acting curve, 55 for ultra-rapid and 45 for Lyumjev. It is
    # the loop's belief only, so changing it leaves the simulated body's absorption alone; a run
    # that models a faster insulin changes both, with the body's rates set in the subject's
    # parameters. Boost also derives its dynamic ISF divisor from it.
    insulin_peak_min = PEAK_MIN

    # Whether the adapters send the meal-data deviation slopes AndroidAPS computes each cycle
    # (`deviation_slopes`) or the constants they sent before 24 October 2026: zero for both on
    # the oref bridge, which leaves its unannounced-meal forecast undecayed, and nothing on the
    # Boost runner, whose MealData defaults of 0 and 999 make `slopeFromDeviations` -333 and cut
    # that forecast off after its first step. Off keeps earlier results reproducible.
    send_deviation_slopes = False

    def init_inputs(self, history=HISTORY_SAMPLES):
        self.readings = deque(maxlen=history)
        self.doses = []                # [(minute, units)] boluses this algorithm gave
        self.basal_deviations = []     # [(minute, delivered - scheduled)] for negative IOB
        self.delta_history = []        # successive windowed deltas, not raw differences
        self.cob_g = 0.0
        self.deviation_history = deque(maxlen=13)  # (minute, avgDeviation), an hour and the present

    def deviation_slopes(self, minute, activity_u_per_min, sens):
        """`slopeFromMaxDeviation` and `slopeFromMinDeviation`, as AndroidAPS's IobCobOref1Worker
        computes them (oref0 cob-autosens.js): each 5-minute bucket's average deviation is the
        15-minute average delta less the insulin effect `-activity * sens * 5`, and the slopes
        run from this bucket back to the largest and smallest of the eleven buckets 55 to 5
        minutes ago, the largest floored at 0 from above and the smallest at 999 from below as
        the worker starts them. `sens` is the profile ISF, which is what the worker reads
        (`getIsfMgdlForCarbs`). Until an hour of buckets exists, and across a gap in them, the
        worker's starting values 0 and 999 are returned.
        """
        r = list(self.readings)
        if len(r) < 4:
            return 0.0, 999.0
        bgi = -float(activity_u_per_min) * float(sens) * 5.0
        avg_dev = round(((r[-1] - r[-4]) / 3.0 - bgi) * 1000.0) / 1000.0
        self.deviation_history.append((float(minute), avg_dev))
        h = list(self.deviation_history)
        if len(h) < 13 or abs(h[0][0] - (minute - 60.0)) > 1.0:
            return 0.0, 999.0
        s_max, s_min, d_max, d_min = 0.0, 999.0, 0.0, 999.0
        for t, d in h[1:12]:
            slope = (d - avg_dev) / (t - minute) * 5.0
            if d > d_max:
                s_max, d_max = min(0.0, slope), d
            if d < d_min:
                s_min, d_min = max(0.0, slope), d
        return s_max, s_min

    # ---------------------------------------------------------------------- insulin
    def bolus_iob(self, minute):
        return float(sum(u * iob_fraction(minute - m, DIA_MIN, self.insulin_peak_min)
                         for m, u in self.doses))

    def basal_iob(self, minute):
        """Insulin on board from basal delivery relative to what was scheduled.

        AndroidAPS measures insulin on board against the scheduled basal, so a loop that has
        been withholding basal carries a negative figure: real users sit at -0.4 U at the
        fifth percentile. Counting boluses alone put this cohort at +0.3, lifted the median
        from 0.7 to 2.2 and fired the headroom brake on 25.4% of decisions against a real
        2.3%.
        """
        return float(sum(u * iob_fraction(minute - m, DIA_MIN, self.insulin_peak_min)
                         for m, u in self.basal_deviations))

    def iob_at(self, minute):
        return self.bolus_iob(minute) + self.basal_iob(minute)

    def iob_after(self, minute, horizon):
        """Insulin still on board `horizon` minutes from now, given no further doses."""
        return float(sum(u * iob_fraction(minute + horizon - m, DIA_MIN, self.insulin_peak_min)
                         for m, u in self.doses))

    def activity_u_per_hour(self, minute, include_basal=False):
        """Insulin acting right now: a five-minute difference of insulin on board, per hour.

        `include_basal` decides which ledger is differenced, and the two answer different
        questions. Boost logs the activity of its own boluses, so it wants the bolus ledger
        alone. oref derives its deviation from the activity of everything acting, which
        includes basal delivered away from the schedule, and feeding it boluses alone
        understates the insulin at work whenever a temporary basal is running, which under
        oref0 SMB is most of the time.

        The deviation autosens accumulates is `delta - (-activity * sens * step)`, so
        understating activity understates the fall the insulin should have produced and
        charges the difference to the person's sensitivity instead.
        """
        iob = self.iob_at if include_basal else self.bolus_iob
        now, then = iob(minute), iob(minute - 5.0)
        return max(0.0, then - now) * 12.0

    def observe_basal(self, minute, delivered_u, scheduled_u):
        """Record how far the basal delivered in this step sat from the schedule."""
        deviation = float(delivered_u) - float(scheduled_u)
        if abs(deviation) > 1e-9:
            self.basal_deviations.append((float(minute), deviation))

    def prune(self, minute):
        """Drop ledger entries that can no longer contribute.

        `iob_fraction` is exactly zero once a dose is older than the duration of action, so
        this changes no arithmetic. It exists because oref's forward curve walks the ledger
        196 times a cycle, and a 28-day run appends a basal deviation on every one of 8,064
        cycles, so an unpruned ledger turns a linear run into a quadratic one.

        The cutoff is the duration of action before now and nothing later. A forward tick
        reads the ledger at a later time, where an old entry is older still, so no entry
        dropped here could contribute to it. Until 9 October 2026 this took a margin for the
        forward horizon and added it to the cutoff, which the oref adapter set to 240 minutes:
        every dose more than an hour old was dropped and oref was handed about half the
        insulin on board. See docs/ISSUES.md 54.
        """
        cutoff = minute - DIA_MIN
        self.doses = [d for d in self.doses if d[0] > cutoff]
        self.basal_deviations = [d for d in self.basal_deviations if d[0] > cutoff]

    # ----------------------------------------------------------------- forward curve
    def iob_curve(self, minute, scheduled_u_per_hour, ticks=48, step=5.0,
                  temp_rate=None, temp_minutes=0.0):
        """The forward insulin curve oref integrates, one entry every `step` minutes.

        oref does not take insulin on board as a number. It walks this array to build every
        prediction it makes, so the shape of it decides the predicted minimum that gates
        delivery, and a plausible-looking but inconsistent array produces predictions that
        look like the simulator misbehaving.

        Each entry carries insulin on board and the rate it is acting at. `iobWithZeroTemp`
        answers a different question, which is where glucose would settle if delivery were
        stopped this instant, so it applies a negative deviation of the whole scheduled basal
        across the horizon. That is the floor oref checks before it doses.

        The projection assumes any running temporary basal finishes and the schedule then
        resumes, which is what the pump would do if the loop stopped issuing instructions.
        """
        base = list(self.doses) + list(self.basal_deviations)
        per_step = float(scheduled_u_per_hour) * step / 60.0

        # A projected delivery covers an interval and is stamped at the end of it, so
        # nothing has been delivered yet at the present tick and both curves start from the
        # same insulin on board. Stamping at the start instead credited a whole step of
        # withheld basal to the current moment, which put the zero-delivery floor 0.1 U below
        # where it belongs on every cycle.
        ahead, zero = [], []
        for i in range(1, ticks + 1):
            t = minute + i * step
            if temp_rate is not None and (i - 1) * step < temp_minutes:
                ahead.append((t, (float(temp_rate) * step / 60.0) - per_step))
            zero.append((t, -per_step))

        # `iob_fraction` reports a full unit for a negative age, meaning a dose that has just
        # been given still has all of its effect to come. That is right looking backwards and
        # wrong looking forwards: a projected delivery that has not happened yet contributes
        # nothing to insulin on board at an earlier tick. Without the `m <= t` guard every
        # future entry counted in full at tick zero, which put `iobWithZeroTemp` half a unit
        # below zero at the present moment and corrupted the array on every cycle with a
        # temporary basal running, which was most of them.
        def state(ledger, t):
            v = float(sum(u * iob_fraction(t - m, DIA_MIN, self.insulin_peak_min)
                          for m, u in ledger if m <= t))
            after = float(sum(u * iob_fraction(t + step - m, DIA_MIN, self.insulin_peak_min)
                              for m, u in ledger if m <= t + step))
            return v, (v - after) / step        # activity in U/min, as oref reads it

        out = []
        for i in range(ticks + 1):
            t = minute + i * step
            iob, act = state(base + ahead, t)
            ziob, zact = state(base + zero, t)
            out.append({"iob": iob, "activity": act,
                        "iobWithZeroTemp": {"iob": ziob, "activity": zact}})
        return out

    # ---------------------------------------------------------------------- glucose
    def glucose_status(self, sample=5.0):
        """delta, shortAvgDelta and longAvgDelta as AndroidAPS computes them.

        Not a difference of consecutive readings. Every earlier reading contributes
        `(current - then) / minutesAgo * 5`, and the three figures are averages of those
        contributions over separate windows: 2.5 to 7.5 minutes for the delta, 2.5 to 17.5
        for the short average, and 17.5 to 42.5 for the long average. See `DeltaCalculator`
        in the AndroidAPS tree.

        This exists because `max_delta` is a hard gate and was being built as the largest
        absolute recent difference, which is a different quantity: a median of 6.3 against
        2.0 in the field. The comparison the package held itself against was also wrong,
        taking `abs(delta)` of a single sample, so neither side matched oref.
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

    def raw_deltas(self):
        r = list(self.readings)
        return [r[i + 1] - r[i] for i in range(len(r) - 1)]

    # ------------------------------------------------------------------ carbohydrate
    def observe_carbs(self, grams, sample):
        """Carbohydrate on board under a linear decay, in the usual clinical region.

        The simulator announces a rate rather than a meal, so this integrates it. oref runs
        its own absorption model over the deviations it observes, and this figure only seeds
        it, which is why a plain decay is enough here.
        """
        self.cob_g = max(0.0, self.cob_g - CARB_ABSORPTION_G_PER_MIN * sample) + float(grams)
        return self.cob_g


__all__ = ["LoopInputs", "HISTORY_SAMPLES", "CARB_ABSORPTION_G_PER_MIN"]
