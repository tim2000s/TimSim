"""Sensor artefacts the Dexcom model in simglucose does not produce.

Two gaps, both measured against 192 real users. Real continuous glucose traces carry
about twice the high-frequency jitter the model produces, and they carry compression
lows: sharp reversing dips from lying on the sensor site, which are an artefact of the
sensor rather than a change in glucose and which the model has no mechanism for.

A compression low is a false low. The reading moves and the underlying glucose does not,
so an algorithm that reacts to one is reacting to nothing. Whether it does react is one of
the more useful questions to ask of an automated insulin delivery system, and asking it
means the artefact has to be inside the loop.

`OnlineArtefacts` is that version, and it is what `simulation.run` uses. It transforms
each reading as it is produced, before the controller sees it, so the artefact influences
dosing and the dosing influences the body. The underlying blood glucose is untouched, and
`Result.bg` still carries the truth.

The batch functions below transform a finished array instead. They were the original
implementation, they are what the unit tests exercise on a known input, and they remain
useful for adding artefacts to a trace that was generated without them. They are not used
in the run path.

Both versions work in minutes rather than in samples, so the event rate and the dip shape
are the same on any sampling grid. An earlier version assumed a five-minute grid while the
harness ran at three, which overstated the span of every trace by a factor of 1.67 and
placed correspondingly more dips.
"""
from collections import deque

import numpy as np

# Shape of a compression dip as a fraction of peak depth, against minutes from onset:
# fast onset, brief nadir, fast-ish recovery, over half an hour. Sampled onto whatever
# grid the run uses. The window matches the `_compression_rate` detector in
# `analysis/signatures.py`, which inspects six five-minute samples from onset and requires
# a pre-dip baseline of at least 85 mg/dL, a drop of more than 25 mg/dL below it, and
# recovery to within 15 mg/dL of baseline by the end of the window.
DIP_MINUTES = np.array([0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
DIP_SHAPE = np.array([0.0, 0.55, 1.00, 0.85, 0.55, 0.25, 0.0])

BASELINE_BAND = (85.0, 140.0)     # where a plausible dip can cross 70 mg/dL
NADIR_BAND = (42.0, 62.0)
MIN_DEPTH = 26.0
SENSOR_FLOOR = 39.0               # the Dexcom model's own lower bound


def dip_profile(sample_minutes):
    """The dip shape resampled onto a grid of `sample_minutes`."""
    n = max(int(round(30.0 / float(sample_minutes))) + 1, 2)
    return np.interp(np.arange(n) * float(sample_minutes), DIP_MINUTES, DIP_SHAPE)


class OnlineArtefacts:
    """Sensor artefacts applied sample by sample, so an algorithm sees them.

    Compression events are scheduled across the run at the requested rate. An event only
    starts where the recent baseline sits in a band from which a plausible dip reaches
    below 70 mg/dL, so an event whose moment arrives while glucose is already low or very
    high is pushed later rather than dropped. That keeps the achieved rate close to the
    requested one without placing dips where the detector could not see them.
    """

    def __init__(self, rng, n_samples, sample_minutes, noise_sigma=2.0,
                 compression_per_30d=3.0, baseline_band=BASELINE_BAND,
                 nadir_band=NADIR_BAND, min_depth=MIN_DEPTH):
        self.rng = rng
        self.sigma = float(noise_sigma)
        self.sample_minutes = float(sample_minutes)
        self.shape = dip_profile(sample_minutes)
        self.baseline_band = baseline_band
        self.nadir_band = nadir_band
        self.min_depth = float(min_depth)
        self.n_samples = int(n_samples)

        span_days = self.n_samples * self.sample_minutes / 1440.0
        n_target = int(round(float(compression_per_30d) * span_days / 30.0))
        first = len(self.shape) + 2
        last = max(self.n_samples - len(self.shape) - 1, first + 1)
        self.pending = sorted(int(i) for i in rng.integers(first, last, size=n_target)) \
            if n_target > 0 else []

        self.active = []                       # [(start_index, depth)]
        self.events = 0
        self.baseline = deque(maxlen=max(int(round(20.0 / self.sample_minutes)), 2))

    def _try_start(self, index):
        """Start a dip here if the baseline allows it, otherwise push it later."""
        if not self.baseline:
            return self._defer(index)
        pre = float(np.mean(self.baseline))
        if not (self.baseline_band[0] <= pre <= self.baseline_band[1]):
            return self._defer(index)
        depth = pre - float(self.rng.uniform(*self.nadir_band))
        if depth <= self.min_depth:
            return self._defer(index)
        self.active.append((index, depth))
        self.events += 1

    def _defer(self, index):
        later = index + int(self.rng.integers(4, max(5, int(180.0 / self.sample_minutes))))
        if later < self.n_samples - len(self.shape) - 1:
            self.pending.append(later)
            self.pending.sort()

    def __call__(self, index, reading):
        """The reading an algorithm sees, given the sensor's own reading."""
        self.baseline.append(float(reading))

        while self.pending and self.pending[0] <= index:
            self._try_start(self.pending.pop(0))

        offset = 0.0
        still = []
        for start, depth in self.active:
            k = index - start
            if 0 <= k < len(self.shape):
                offset += depth * self.shape[k]
                still.append((start, depth))
            elif k < 0:
                still.append((start, depth))
        self.active = still

        out = float(reading) - offset
        if self.sigma > 0:
            out += float(self.rng.normal(0.0, self.sigma))
        return max(out, SENSOR_FLOOR)


# ------------------------------------------------------------------ batch versions
def add_sensor_noise(cgm, rng, sigma=2.0):
    """IID measurement noise. Note: the 2nd-difference SD of iid noise with std sigma
    is sigma*sqrt(6) (2nd-diff operator [1,-2,1], sum of squares = 6), so a sigma of
    ~2 mg/dL contributes ~5 mg/dL of 2nd-diff jitter on its own; the underlying signal
    contributes some more, so the achieved total has to be verified empirically rather
    than assumed from this formula alone."""
    return cgm + rng.normal(0.0, sigma, size=len(cgm))


def inject_compression_lows(cgm, rng, rate_per_30d=3.0, min_baseline=85.0,
                            max_baseline=140.0, nadir_lo=42.0, nadir_hi=62.0,
                            min_gap_samples=10, sample_minutes=5.0):
    """Inject synthetic compression-low events into a finished CGM array.

    Each event is a brief, sharp downward excursion that does not reflect a real glucose
    change: a fast dip below a pre-event baseline, briefly, then a recovery back towards
    that baseline within the window the detector inspects. Candidates are only accepted
    where the local baseline sits in a band from which a plausible dip drives the reading
    under 70 mg/dL, since the detector reuses the hypoglycaemia onset test and only counts
    an event that crosses it.

    Returns (new_cgm, n_events_placed).
    """
    out = np.asarray(cgm, float).copy()
    shape = dip_profile(sample_minutes)
    span_days = len(out) * float(sample_minutes) / 1440.0
    n_target = int(round(rate_per_30d * span_days / 30.0))
    placed = []
    tries = 0
    max_tries = max(400, n_target * 400)
    while len(placed) < n_target and tries < max_tries:
        tries += 1
        i0 = int(rng.integers(6, max(len(out) - len(shape) - 1, 7)))
        if any(abs(i0 - e) < min_gap_samples for e in placed):
            continue
        pre = out[max(0, i0 - 4):i0].mean()
        if pre < min_baseline or pre > max_baseline:
            continue
        depth = pre - float(rng.uniform(nadir_lo, nadir_hi))
        if depth <= 26.0:
            continue
        out[i0:i0 + len(shape)] -= depth * shape[:len(out) - i0]
        placed.append(i0)
    return out, len(placed)


def apply(t, cgm, rng, noise_sigma=2.0, compression_rate=3.0, sample_minutes=5.0):
    """The batch sensor layer: compression lows first, then measurement noise on top."""
    dipped, n_events = inject_compression_lows(cgm, rng, rate_per_30d=compression_rate,
                                               sample_minutes=sample_minutes)
    noisy = add_sensor_noise(dipped, rng, sigma=noise_sigma)
    return noisy, n_events


__all__ = ["OnlineArtefacts", "dip_profile", "add_sensor_noise",
           "inject_compression_lows", "apply"]
