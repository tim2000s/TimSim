"""Alpha-cell glucagon secretion, kinetics and action during hypoglycaemia.

S2013 added a glucagon compartment to UVA/Padova and its secretion parameters were never
published: Dalla Man et al. 2014 describes the structure, Pompa et al. 2021 reproduces it and
marks those parameters calibrated without giving values, and Resalat et al. 2019 discloses a
full alternative but models glucagon infused from a pump rather than secreted by an alpha cell.
So the structure here follows the published description and every number in it comes from a
measurement on people.

The reason to build it despite that is a disagreement between two clamp studies. Rickels et al.
2015 measured twelve people with long-standing type 1 diabetes and no discernible glucagon
response at all, which is the population `HYPO_EGP_DEFENCE` is fitted to. The Hypo-RESOLVE clamp
measured 47 people with type 1 diabetes and found a response of 9.4 +/- 0.8 pmol/L against
30.6 +/- 4.7 in 16 controls: attenuated to about a third, not absent. Both describe real people.
What the package has never had is the variation between them, so `RESPONSIVITY_RANGE` spans none
to about a third of healthy and each subject draws its own.

Two warnings about magnitude, both of which the design document states as refutation criteria.

The action parameters come from Hinshaw et al. 2015, in 29 people with type 1 diabetes. Its
glycogenolysis sensitivity is 0.112 to 0.272 umol/kg/min per ng/mL, and a 9.4 pmol/L response is
about 0.033 ng/mL, so that arm contributes on the order of 0.001 mg/kg/min against a production
target of 0.42 to 0.84. The gluconeogenesis sensitivity is quoted from 0.008 to 16.15
umol/kg/min per ng/mL, a range spanning a factor of two thousand, which is a parameter that study
could not identify rather than a parameter with a wide true spread.

And this mechanism must not run alongside a defence gain fitted to a population without it, or
the same production is counted twice. `simulate` refuses that combination.
"""
import numpy as np

# Glucagon molar mass, for converting the clamp studies' pmol/L to the action model's ng/mL.
MW_GLUCAGON = 3482.75          # g/mol

# Hypo-RESOLVE, Fabricius et al. 2024, at a 2.8 mmol/L clamp held 60 minutes.
T1D_RESPONSE_PMOL_L = 9.4      # +/- 0.8 across 47 people with type 1 diabetes
CONTROL_RESPONSE_PMOL_L = 30.6  # +/- 4.7 across 16 people without diabetes
CLAMP_TARGET_MMOL_L = 2.8

# How much alpha-cell response a subject retains, as a fraction of the healthy response. The
# span is what the two clamp studies together describe: Rickels' subjects sit at the bottom and
# the Hypo-RESOLVE median sits near the top.
RESPONSIVITY_RANGE = (0.0, 0.45)

# Secretion. The static arm responds to glucose below a threshold and the dynamic arm to the
# rate of fall, which is the shape Dalla Man et al. 2014 describes. `SIGMA` and `DELTA` are
# scaled by the subject's responsivity and then fitted so the cohort reproduces the measured
# concentration at the clamp; they are not published values and are not presented as any.
SECRETION_THRESHOLD_MGDL = 80.0    # above this the static arm is silent
SIGMA = 1.0                        # static responsivity, pmol/L per mg/dL below threshold
DELTA = 6.0                        # dynamic responsivity, pmol/L per mg/dL/min of fall
BASAL_PMOL_L = 25.0                # fasting concentration the response sits on top of

# Kinetics. One compartment. Hinshaw et al. 2015 reports clearance of 17.3 to 18.8 mL/kg/min,
# which with a distribution volume near 200 mL/kg gives a time constant of roughly 11 minutes.
CLEARANCE_ML_KG_MIN = 18.0
VOLUME_ML_KG = 200.0

# Action, from Hinshaw et al. 2015, in umol/kg/min per ng/mL. `B` is the glycogenolysis arm and
# `D` the gluconeogenesis arm. The midpoint of each published range is the default; the sweep in
# `examples/calibrate_glucagon.py` explores the range rather than assuming a point.
B_GLYCOGENOLYSIS = (0.112, 0.272)
D_GLUCONEOGENESIS = (0.008, 16.15)
ACTION_DELAY_MIN = 1.0 / 0.033     # from the dephosphorylation rate, 0.032 to 0.034 per min

# umol/kg/min of glucose to mg/kg/min.
UMOL_TO_MG = 180.156 / 1000.0


def pmol_l_to_ng_ml(pmol_per_l):
    """The clamp studies report pmol/L and the action model takes ng/mL."""
    return float(pmol_per_l) * MW_GLUCAGON / 1e6


def responsivity_for(name, seed=0, span=RESPONSIVITY_RANGE):
    """A subject's retained alpha-cell response, as a fraction of healthy.

    Keyed on the name through sha256 for the same reason every other per-subject draw is: it
    has to reproduce across processes, and a subject's physiology should not depend on where it
    sits in a list.
    """
    import hashlib
    digest = hashlib.sha256(f"{name}:glucagon:{seed}".encode()).digest()
    u = int.from_bytes(digest[:8], "big") / float(1 << 64)
    lo, hi = span
    return float(lo + u * (hi - lo))


class Glucagon:
    """Secretion, kinetics and action for one subject over one run.

    `responsivity` is the fraction of a healthy alpha-cell response this subject retains. Zero
    reproduces the Rickels population exactly, which is the population the rest of the
    hypoglycaemia calibration rests on.
    """

    def __init__(self, responsivity, sigma=SIGMA, delta=DELTA,
                 threshold=SECRETION_THRESHOLD_MGDL, basal=BASAL_PMOL_L,
                 b=None, d=None, weight_kg=70.0):
        self.responsivity = float(responsivity)
        self.sigma, self.delta = float(sigma), float(delta)
        self.threshold, self.basal = float(threshold), float(basal)
        self.b = float(np.mean(B_GLYCOGENOLYSIS) if b is None else b)
        self.d = float(np.mean(D_GLUCONEOGENESIS) if d is None else d)
        self.tau = VOLUME_ML_KG / CLEARANCE_ML_KG_MIN
        self.concentration = self.basal        # pmol/L
        self.action = 0.0                      # delayed action state, ng/mL
        self._last_glucose = None

    def secretion(self, glucose_mgdl, fall_rate_mgdl_min):
        """Glucagon appearing now, in pmol/L per minute, above basal.

        The static arm answers how low glucose is and the dynamic arm how fast it is falling,
        so a glucose sitting steadily at 60 mg/dL produces less than one passing through 60 on
        the way down. That is the distinction the dynamic term exists to make and it is the one
        a bench for hypoglycaemia most needs.
        """
        if self.responsivity <= 0.0:
            return 0.0
        static = max(0.0, self.threshold - float(glucose_mgdl)) * self.sigma
        dynamic = max(0.0, -float(fall_rate_mgdl_min)) * self.delta
        return self.responsivity * (static + dynamic) / self.tau

    def step(self, glucose_mgdl, minutes=1.0):
        """Advance the compartment and the delayed action by `minutes`."""
        g = float(glucose_mgdl)
        fall = 0.0 if self._last_glucose is None else (g - self._last_glucose) / max(minutes, 1e-9)
        self._last_glucose = g

        appearance = self.secretion(g, fall)
        decay = (self.concentration - self.basal) / self.tau
        self.concentration += (appearance - decay) * minutes
        self.concentration = max(self.basal, self.concentration)

        above_basal = pmol_l_to_ng_ml(self.concentration - self.basal)
        self.action += (above_basal - self.action) / ACTION_DELAY_MIN * minutes
        return self.concentration

    def egp_mg_kg_min(self):
        """The production this glucagon is driving, above what it would be without it."""
        return float((self.b + self.d) * self.action * UMOL_TO_MG)


__all__ = ["Glucagon", "responsivity_for", "pmol_l_to_ng_ml", "RESPONSIVITY_RANGE",
           "T1D_RESPONSE_PMOL_L", "CONTROL_RESPONSE_PMOL_L", "B_GLYCOGENOLYSIS",
           "D_GLUCONEOGENESIS", "CLAMP_TARGET_MMOL_L"]
