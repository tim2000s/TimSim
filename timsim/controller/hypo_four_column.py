"""Boost's four-column hypoglycaemia model, scored inside the simulator.

The bridge marshals `mlHypoRisk` across to the engine and the adapter has always sent None, so
every Boost result this package has published is Boost with its hypo damper absent: a null leaves
the aggression budget unscaled. This supplies a real value so the damper can be measured against
that, which is the paired comparison the model was built for.

The model is the shipped asset, not a reimplementation. Trees are read from the app's own
`hypo_four_column_sustained.json` and walked exactly as `HypoFourColumnShadow.walk` walks them,
left when the feature is at or below the threshold, summing leaves and passing the total through a
logistic. It was trained on the Loop observational study and deliberately not on this fork's
cohort, and it takes four inputs: glucose and the engine's three trend averages.

Those averages are rebuilt here from the sensor trace rather than taken from the adapter, for two
reasons. The adapter keeps eight readings and the longest average reaches back eight lags, which
needs nine. And the adapter's deltas are windowed in oref's fashion, where the model was trained on
plain lag differences on a five-minute grid: delta is lag one, the short average is lags one to
three, the long average is lags four to eight, each expressed as a per-five-minute rate.

Returns None until nine readings exist, which the engine reads as a missing model, so the opening
forty minutes of a run behave exactly as they do today rather than on a half-filled window.
"""
import json
import math
import os
from collections import deque

DEFAULT_MODEL = os.path.expanduser(
    "~/StudioProjects/Boost-AAPS-core/app/src/main/assets/boost/hypo_four_column_sustained.json")
NEEDED = 9                      # current reading plus eight lags


class HypoFourColumn:
    """One instance per subject, because it carries that subject's recent trace."""

    def __init__(self, path=DEFAULT_MODEL):
        with open(path) as fh:
            m = json.load(fh)
        self.trees = m["trees"]
        self.names = m["feature_names"]
        if self.names != ["cgm", "delta", "short_avg_delta", "long_avg_delta"]:
            raise ValueError(f"unexpected feature order in the asset: {self.names}")
        self.bg = deque(maxlen=NEEDED)

    @staticmethod
    def _walk(node, x):
        while "leaf" not in node:
            node = node["left"] if x[node["feature"]] <= node["threshold"] else node["right"]
        return node["leaf"]

    def _features(self):
        """delta, short and long averages, as per-five-minute rates from plain lag differences."""
        b = list(self.bg)[::-1]                     # b[0] is now, b[k] is k lags back
        rate = lambda k: (b[0] - b[k]) / k
        short = sum(rate(k) for k in (1, 2, 3)) / 3.0
        long_ = sum(rate(k) for k in (4, 5, 6, 7, 8)) / 5.0
        return [b[0], rate(1), short, long_]

    def score(self, bg):
        """Probability of a sustained low, or None while the window is still filling."""
        if bg is None or not math.isfinite(bg):
            return None
        self.bg.append(float(bg))
        if len(self.bg) < NEEDED:
            return None
        x = self._features()
        raw = sum(self._walk(t, x) for t in self.trees)
        return 1.0 / (1.0 + math.exp(-raw))
