"""oref's sensitivity detection, which is the one piece of the OpenAPS SMB arm not shipped.

Everything else in that arm is other people's code called across a pipe. This is not, and the
reversal needs a reason rather than a shrug.

oref0 ships autosens twice and neither form can be driven from here without fabricating its
input. `lib/determine-basal/autosens.js` reads Medtronic pump history records and rebuilds
insulin and meals from them through four more modules, so running it would mean synthesising
a pump history and would put the reconstruction, rather than the algorithm, in charge of the
answer. AndroidAPS's `SensitivityOref1Plugin` takes an `AutosensDataStore` whose deviations
are already computed elsewhere, so bridging it would leave the part that matters on this side
of the pipe anyway. Given the choice between reimplementing eighty lines of arithmetic and
fabricating the data structure that feeds it, the arithmetic is the smaller risk, and unlike
the pump history it can be tested directly.

What follows is AndroidAPS's Oref1 form, which differs from the JavaScript in two respects
that are kept here: positive deviations are discarded when glucose is below 80 mg/dL, and two
windows are run rather than one, with the lower of the two ratios used. The ratio arithmetic
is identical in both.

The exclusion logic is the substance of it. A deviation only counts when glucose moved for a
reason other than food, so carbohydrate absorption is tracked and excluded, the 45 minutes
after any carbohydrate entry are excluded outright, and a rise while insulin on board is high
is treated as an unannounced meal and excluded too. Without that, every meal reads as insulin
resistance and the ratio climbs until it clamps.
"""
import bisect

# oref keeps the last 96 deviations for the eight-hour window and 288 for the twenty-four,
# which at five-minute sampling is exactly the window length.
WINDOWS = ((8.0, 96), (24.0, 288))

MIN_5M_CARBIMPACT = 8.0        # mg/dL per five minutes, the floor oref assumes food is doing
AUTOSENS_MIN = 0.7
AUTOSENS_MAX = 1.2
MEAL_START_EXCLUSION = 9       # five-minute steps, so the 45 minutes after a carbohydrate entry
ABSORPTION_GIVE_UP = 60        # steps before a meal that will not finish stops excluding


def percentile(sorted_values, fraction):
    """The percentile oref uses, which interpolates between neighbours.

    Written out rather than taken from numpy because the median of an even-length list is
    where a rounding difference would show up, and the ratio is sensitive to it: a deviation
    of 0.1 mg/dL either side of zero is the difference between reading sensitivity and reading
    resistance.
    """
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_values[0])
    rank = fraction * (n - 1)
    low = int(rank)
    high = min(low + 1, n - 1)
    weight = rank - low
    return float(sorted_values[low] * (1 - weight) + sorted_values[high] * weight)


class Autosens:
    """Sensitivity detection over a run, fed one five-minute observation at a time.

    Held by the controller rather than recomputed from history each cycle, because the
    exclusion is a state machine: whether this deviation counts depends on whether the last
    one was part of a meal.
    """

    def __init__(self, autosens_min=AUTOSENS_MIN, autosens_max=AUTOSENS_MAX,
                 min_5m_carbimpact=MIN_5M_CARBIMPACT):
        self.autosens_min = float(autosens_min)
        self.autosens_max = float(autosens_max)
        self.min_5m_carbimpact = float(min_5m_carbimpact)

        self.deviations = []       # (minute, deviation) for everything that counted
        self.meal_cob = 0.0
        self.meal_carbs = 0.0
        self.absorbing = False
        self.uam = False
        self.meal_start_counter = ABSORPTION_GIVE_UP + 1
        self.kind = "non-meal"     # the previous step's classification
        self.last_ratio = 1.0

    # ------------------------------------------------------------------ observation
    def observe(self, minute, bg, delta, activity_u_per_min, iob, sens, carb_ratio,
                current_basal, carbs_g=0.0, step=5.0):
        """One five-minute step. `delta` is the change in glucose over it, in mg/dL.

        `activity_u_per_min` is the insulin acting right now, from which oref predicts what
        glucose should have done. What it did instead, minus that, is the deviation.
        """
        bgi = -float(activity_u_per_min) * float(sens) * step
        deviation = float(delta) - bgi

        # AndroidAPS discards positive deviations below 80 mg/dL. A rise off a low is
        # counterregulation or rescue carbohydrate, and reading it as insulin resistance
        # would raise the dose of someone who is already going low.
        if bg < 80.0 and deviation > 0:
            deviation = 0.0

        if carbs_g > 0:
            self.meal_cob += float(carbs_g)
            self.meal_carbs += float(carbs_g)
            self.meal_start_counter = 0

        # Carbohydrate is decayed by what glucose actually did, floored at the impact oref
        # assumes food is having, so a meal that produces no rise still finishes.
        if self.meal_cob > 0:
            impact = max(deviation, self.min_5m_carbimpact)
            self.meal_cob = max(0.0, self.meal_cob - impact * float(carb_ratio) / float(sens))

        self._classify(deviation, iob, current_basal)
        if self.kind == "non-meal":
            self.deviations.append((float(minute), deviation))

        # A neutral deviation every two hours, so a long exclusion decays towards normal
        # rather than leaving a stale ratio in place.
        if minute % 120.0 < step:
            self.deviations.append((float(minute), 0.0))

        self._forget(minute)
        return deviation

    def _classify(self, deviation, iob, current_basal):
        """Decide whether this deviation is food, an unannounced meal, or neither."""
        if self.meal_cob > 0 or self.absorbing or self.meal_carbs > 0:
            self.absorbing = deviation > 0
            # A meal still nominally absorbing after five hours has stopped being a meal.
            if self.meal_start_counter > ABSORPTION_GIVE_UP and self.meal_cob < 0.5:
                self.absorbing = False
            if not self.absorbing and self.meal_cob < 0.5:
                self.meal_carbs = 0.0
            self.meal_start_counter += 1
            self.kind = "csf"
            return

        # oref compares insulin on board, in units, against twice the basal rate, in units per
        # hour. The two are not the same quantity and the comparison is kept as it is written,
        # because the point here is to reproduce the algorithm rather than to improve it.
        if iob > 2.0 * float(current_basal) or self.uam \
                or self.meal_start_counter < MEAL_START_EXCLUSION:
            self.meal_start_counter += 1
            self.uam = deviation > 0
            self.kind = "uam"
            return

        self.uam = False
        self.kind = "non-meal"

    def _forget(self, minute):
        longest = max(hours for hours, _ in WINDOWS) * 60.0
        cutoff = minute - longest
        cut = bisect.bisect_right([m for m, _ in self.deviations], cutoff)
        if cut:
            self.deviations = self.deviations[cut:]

    # ----------------------------------------------------------------------- ratio
    def ratio(self, minute, sens, max_daily_basal):
        """The sensitivity ratio, as oref would report it now.

        Runs both windows and takes the lower, which is AndroidAPS's rule: the twenty-four
        hour figure by default, the eight-hour one when it is smaller. The asymmetry is
        deliberate, since detecting sensitivity late is the more dangerous error.
        """
        ratios = []
        for hours, cap in WINDOWS:
            window = [d for m, d in self.deviations if m > minute - hours * 60.0][-cap:]
            # Too little data is damped rather than ignored, by padding towards no change.
            pad = round((1.0 - len(window) / cap) * 18) if len(window) < cap else 0
            values = sorted(window + [0.0] * max(0, int(pad)))
            median = percentile(values, 0.50)
            basal_off = median * (60.0 / 5.0) / float(sens) if median != 0 else 0.0
            ratios.append(1.0 + basal_off / float(max_daily_basal))

        ratio = min(ratios)
        ratio = min(max(ratio, self.autosens_min), self.autosens_max)
        self.last_ratio = round(ratio, 2)
        return self.last_ratio


__all__ = ["Autosens", "percentile", "WINDOWS", "AUTOSENS_MIN", "AUTOSENS_MAX"]
