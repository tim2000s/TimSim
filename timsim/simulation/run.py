"""Run a simulated person for a number of days, driven by some controller.

Three things are in play here and they are not the same kind of thing. Keeping them
separate matters, because an earlier version of this module did not and listed a
correction algorithm among the properties of a body.

The person is `LAYERS`, and every one of them can be switched off so that a difference
between two runs is attributable to a named mechanism rather than to the bundle:

    physiology   insulin sensitivity that varies by time of day and day to day
    behaviour    meals announced imperfectly, lows treated with carbohydrate,
                 a sensitivity setting that adapts
    sensor       measurement jitter and compression lows, on the reading the person and
                 the algorithm both act on
    site         infusion sets that fail quietly, and get noticed and changed late

The rig is the interface an algorithm reaches that person through, and it is always
present because there is no other way to touch a body: a continuous glucose monitor
reporting on a five-minute grid, and a pump with the delivery ceilings in
`therapy/limits.py`. Without the ceilings the bench is unphysical. simglucose's own pump
accepts 150 units in a single step, and the reference algorithm has been observed asking
for 35 units in one bolus.

The controller is whatever is driving. It is not part of the person and it is not
optional, since a person with nobody dosing them is a person in trouble within a day.
`controller` takes:

    "trend"         the built-in basal-bolus with a correction loop, the default and what
                    every figure in `docs/` was measured against
    "control-iq"    the same with a loop shaped like the published description of the
                    algorithm the reference trial ran. It does not reproduce that trial's
                    outcomes and is not the default; see `controller/loop.py`
    "basal-bolus"   neither, which is open-loop therapy
    an object       anything with `policy(observation, reward, done, **info) ->
                    Action(basal, bolus)`, which is simglucose's own interface and the
                    hook for testing a real algorithm

One consequence is worth stating plainly rather than leaving to be discovered. The
fidelity figures in `docs/FIDELITY.md` compare this person plus the reference controller
against real people plus Control-IQ. That is the right comparison, because a real person
cannot be observed without their algorithm either. But it validates the pair. Bringing
your own algorithm replaces half of what was validated, and `docs/OSAID.md` covers what
that means for a claim.

Four things about this runner are worth knowing before reading a result from it.

The grid is five minutes, which is what real continuous glucose monitors report on and
what the open-source algorithms compute their deltas over. simglucose's Dexcom model
declares three, so the sensor used here is `GuardianRT`, whose noise parameters are
identical and whose sample time is five.

Sensor artefacts are inside the loop. The reading handed to the controller, and to the
simulated person, carries the jitter and the compression lows. The underlying blood
glucose in `Result.bg` does not, so a compression low remains a false reading.

Delivery passes through the limits in `therapy/limits.py` before it reaches the pump, and
every clamp is counted. simglucose's own pump would accept 150 units in one step.

`Result.bg` is interstitial glucose without sensor error, not plasma. simglucose's patient
exposes only `Gsub`, and both it and the reading are five-minute means of a one-minute
integration. So `bg` and `cgm` differ by sensor noise alone, and that noise fragments
threshold crossings: see `docs/MODEL.md`.

Insulin is measured at the body rather than at the controller, so the figure is right
whichever controller produced it. The one thing added back is insulin a failed infusion
site swallowed, since that really did leave the pump and would appear in any real log.
"""
import hashlib
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from simglucose.actuator.pump import InsulinPump
from simglucose.controller.base import Action
from simglucose.sensor.cgm import CGMSensor
from simglucose.simulation.env import T1DSimEnv
from simglucose.simulation.scenario import CustomScenario

from ..controller.loop import CorrectionLoop
from ..patient.varying import (HYPO_DEFENCE_GAIN, HYPO_EGP_DEFENCE, HYPO_EGP_FLOOR,
                               HYPO_RISK_GAIN, LIVER_DELAY_SCALE, LIVER_FAST_FRACTION,
                               LIVER_FAST_KI_SCALE, MEAL_ABSORPTION_CV,
                               MEAL_ABSORPTION_SCALE, VaryingPatient)
from ..person import behaviour as behaviour_mod
from ..person.behaviour import AdaptiveRatios, BehaviourScenario, Person
from ..population import params_for, therapy_for
from ..sensor.realism import OnlineArtefacts
from ..therapy import Enforcer, InfusionSite, profile as profile_mod

# The person. The correction loop used to be listed here as a fifth entry, which was a
# category error: it is a controller, it lives in `controller/loop.py`, and its own
# docstring says it is the baseline rather than the subject. Passing it in `layers` now
# raises rather than being quietly accepted, because a run that thinks a dosing algorithm
# is a property of a body will produce numbers nobody can attribute.
#
# The site layer was the last one in, on a decision worth recording.
#
# It costs one of the eleven signatures in `docs/FIDELITY.md`, taking that table from
# six of eleven to five, which is the worst score of any configuration measured. It is
# also the configuration hardest to tell from real data: against 3,023 windows from the
# DCLP3 closed-loop participants it scores 0.739 where the same person without it scores
# 0.785, and it held that rank when every figure was remeasured on the regenerated
# population. Both statements are true. The
# signature table asks whether eleven medians land in eleven ranges; the classifier asks
# whether a day of this looks like a day of that, and it is the stronger question.
#
# The reason that settles it rather than merely deciding it is what this package is for.
# Infusion site failure was a declared uncovered hazard in `validation/gate.py` and turned
# out to be where most real time above 180 mg/dL comes from. A bench that never presents a
# failed set cannot see what an algorithm does when it is high, dosing, and getting
# nowhere, which is a condition open-source systems handle very differently from each
# other. Leaving it off keeps the bench flattering on the hazard it exists to probe.
#
# `validation/replication.py` records the arbitration, `therapy/site.py` the mechanism.
# `activity` is available and not default. It is the only layer with no grounding in the
# local database, because the Nightscout records carry no exercise events, so it has to earn
# its place on the fidelity signatures alone before it goes in the default stack. That is the
# same route the site layer took.
LAYERS = ("physiology", "behaviour", "sensor", "site", "activity")
DEFAULT_LAYERS = ("physiology", "behaviour", "sensor", "site")

# Resolved in `_resolve_controller`. "reference" is kept as an alias for the default so
# that a caller asking for the baseline gets the baseline rather than a frozen choice.
CONTROLLERS = ("control-iq", "trend", "basal-bolus", "reference")
DEFAULT_CONTROLLER = "trend"

# simglucose ships three sensors whose noise parameters are identical and whose sample
# times differ. Five minutes is the real reporting interval and the cadence the
# open-source algorithms are written against.
SENSOR_BY_SAMPLE_TIME = {1.0: "Navigator", 3.0: "Dexcom", 5.0: "GuardianRT"}
DEFAULT_SAMPLE_MINUTES = 5.0

# (centre hour, hour spread, grams, gram spread, probability it happens, is it a snack)
#
# Regrounded on 24 August 2026 against 292,140 carbohydrate entries from 147 OpenAPS Data
# Commons users over 48,454 user-days, each entry placed at its local hour through the
# timezone the user's own Nightscout profile records (`examples/intake_clock.py`, output in
# `docs/measurements/intake_clock.json`). The previous template ate three meals and an
# occasional snack on a conventional clock, and it disagreed with the record at both ends of
# the day: real intake peaks at 08:00 where the template's breakfast sat at 07:00, and the six
# hours from 21:00 to 03:00 carry 12.8 per cent of real grams against the template's 3.6.
#
# The rows below reproduce the measured share of grams in every window of the day to within
# 0.7 percentage points (morning 16.1 against a real 15.9, midday 32.1 against 31.4, afternoon
# 13.7 against 14.2, evening 25.5 against 24.8, night 12.4 against 12.8), at 5.2 eating
# occasions a day against a logged 5.56 and the old template's 3.64.
#
# Two deliberate departures from the record. Total intake is held near the old template's level,
# at 192 g/day expected at 70 kg rather than the logged median of 162, because logged grams
# under-state eaten grams and the under-statement cannot be placed by hour. And the 00:36 snack
# inherits `draw_meals`' clipping of draws to 00:30 at the earliest, so a small pile-up sits at
# the clip rather than the tail wrapping past midnight.
#
# This is usage data, not a glucose outcome: no trace from any reference population was
# consulted, so the comparisons against DCLP3 and the Commons remain tests of the template
# rather than restatements of it.
DEFAULT_MEALS = [
    (8.4, 1.2, 36, 13, 0.90, False),
    (11.0, 0.9, 10, 5, 0.45, True),
    (12.8, 1.0, 54, 18, 0.95, False),
    (16.2, 1.1, 29, 13, 0.80, True),
    (19.0, 0.9, 52, 19, 0.95, False),
    (22.1, 1.2, 32, 14, 0.70, True),
    (0.6, 1.5, 20, 11, 0.45, True),
]

# Every subject was given the same sensor until 22 August 2026, so the population varied in the
# noise it received and not in how noisy its sensor was. Measured across the 103 OpenAPS Data
# Commons users of the reference cohort with the same second-difference statistic the simulator is
# scored on, real per-person jitter has a median of 5.30 mg/dL and a tenth to ninetieth percentile
# of 3.50 to 7.45. The population spanned 5.55 to 5.70, so its centre was already right and it
# carried no spread at all.
#
# Jitter is a second-difference standard deviation, to which white noise of standard deviation s
# contributes s times the square root of six and the curvature of the glucose itself contributes
# the rest. With the sensor layer off that curvature measures 2.4 mg/dL, which puts the real
# quantiles at sigma 1.04, 1.93 and 2.88. A lognormal about a median of 1.93 carries them, with
# the log standard deviation fitted to both tails rather than to their ratio: 0.33 gives a jitter
# tenth percentile of 3.92 and a ninetieth of 7.60 against a real 3.50 and 7.45, where fitting the
# ratio alone matched the tenth and overshot the ninetieth by a full mg/dL. The residual is the
# real distribution having a lighter right tail than a lognormal, which is not worth a second
# parameter at 103 users.
#
# The draw takes its own stream, so a subject's noise level does not disturb the realisation of
# the noise itself and the two can be varied independently.
SENSOR_NOISE_SIGMA = 1.93
SENSOR_NOISE_LOG_SD = 0.33
SENSOR_COMPRESSION_PER_30D = 4.5


def sensor_style(name, seed, sigma=SENSOR_NOISE_SIGMA, log_sd=SENSOR_NOISE_LOG_SD):
    """How noisy this subject's sensor is, held for the whole run."""
    if not log_sd:
        return float(sigma)
    return float(sigma * stream(name, seed, "sensor_style").lognormal(0.0, log_sd))


@dataclass
class Result:
    """One subject's run. `cgm` is what the algorithm saw; `bg` is the truth."""
    name: str
    cgm: np.ndarray
    bg: np.ndarray
    minutes: np.ndarray
    sample_time: float
    days_requested: int
    completed: bool
    insulin_units: float
    insulin_series: np.ndarray = field(default_factory=lambda: np.zeros(0))
    # Bolus alone, on the same clock as `insulin_series`, which carries basal as well. Telling a
    # meal that was bolused from one that was not needs the two apart, and inferring a bolus from
    # the total by subtracting an assumed basal is the kind of reconstruction this package has
    # had to withdraw figures for. Units delivered in the step, before the site layer swallows
    # any of it, so it is what the pump was asked for rather than what reached the depot.
    bolus_series: np.ndarray = field(default_factory=lambda: np.zeros(0))
    rescue_events: int = 0
    rescue_grams: float = 0.0
    # (decided_at, eaten_at, grams, reading_that_triggered_it), minutes from the start
    rescue_log: tuple = ()
    meals_announced: int = 0
    meals_unannounced: int = 0
    # (minute, grams) for every scheduled meal. Rescue carbohydrate is not here; it is in
    # `rescue_log`, because a rescue and a meal are different events and measuring the
    # response to one requires excluding the other.
    meal_log: tuple = ()
    # (start minute, minutes, intensity) for every exercise session, empty when the layer
    # is off. An exercise-driven low behaves differently from an insulin-driven one, and
    # telling them apart afterwards needs this.
    activity_log: tuple = ()
    isf_weekly_cv: float = float("nan")
    compression_events: int = 0
    layers: tuple = ()
    controller: str = ""
    # None when the run completed, otherwise why it ended: see `analysis/cohort.py`.
    termination: dict = None
    meta: dict = field(default_factory=dict)

    @property
    def time_in_range(self):
        return 100.0 * np.mean((self.cgm >= 70) & (self.cgm < 180))

    @property
    def time_below_70(self):
        return 100.0 * np.mean(self.cgm < 70)

    @property
    def time_above_180(self):
        return 100.0 * np.mean(self.cgm >= 180)

    @property
    def cv(self):
        return 100.0 * self.cgm.std() / self.cgm.mean()

    def summary(self):
        return {"name": self.name, "days": self.days_requested,
                "completed": self.completed, "mean": float(self.cgm.mean()),
                "cv": self.cv, "tir": self.time_in_range,
                "tbr": self.time_below_70, "tar": self.time_above_180,
                "insulin_per_day": self.insulin_units / max(self.days_requested, 1),
                "rescues": self.rescue_events,
                "unannounced_meals": self.meals_unannounced,
                "isf_weekly_cv": self.isf_weekly_cv}

    def safety(self):
        """The safety record, which is the summary a verdict should turn on."""
        from ..analysis import safety
        return safety.summarise(self)


def draw_meals(days, rng, body_weight, template=None):
    """A meal schedule with realistic scatter in timing, size and whether it happens."""
    template = template or DEFAULT_MEALS
    scale = float(np.clip(body_weight / 70.0, 0.5, 1.15))
    out = []
    for day in range(days):
        for hour, hour_sd, grams, gram_sd, prob, snack in template:
            if rng.random() > prob:
                continue
            h = float(np.clip(hour + rng.normal(0, hour_sd), 0.5, 23.5))
            g = max(3.0, rng.normal(grams, gram_sd) * scale)
            out.append((day * 24 + h, round(float(g)), snack))
    return sorted(out)


class _BasalBolus:
    """The built-in controller: bolus the announced carbohydrate, correct if high.

    Deliberately simple. It is the substrate the behaviour and loop layers act through
    rather than an algorithm under test. It reads its settings from the profile by time
    of day, so a diurnal profile exercises the scheduling path.
    """

    # The target this controller corrects towards, held at the value it has always used
    # rather than taken from the profile. The profile's target range is what a system
    # under test reads, and moving the built-in controller onto it would have changed
    # every measured number in the package for a reason unrelated to any of the fixes.
    CORRECTION_TARGET = 140.0

    def __init__(self, profile, adaptive=True, loop=None, target=CORRECTION_TARGET):
        self.profile = profile
        self._adaptive = bool(adaptive)
        self._loop_shape = loop
        self.target = float(target)
        self.reset()

    def reset(self):
        """Rebuild the per-run state, so one instance can drive two runs.

        The correction loop holds a bolus ledger and the adaptive ratios hold a week of
        history, and both are properties of a run rather than of the driver. `simulate` calls
        this before every run, which is what stops a second run of the same subject beginning
        with the first run's insulin.
        """
        mid = self.profile.isf_at(12 * 60), self.profile.cr_at(12 * 60)
        self.ratios = AdaptiveRatios(mid[0], mid[1]) if self._adaptive else None
        self.loop = CorrectionLoop(self._loop_shape) if self._loop_shape else None

    def act(self, announced_grams, cgm, minute, sample_time, fall_rate=0.0):
        cf, cr = self.profile.isf_at(minute), self.profile.cr_at(minute)
        if self.ratios is not None:
            self.ratios.observe(minute, cgm, self.target)
            cf, cr = cf * self.ratios.factor, cr * self.ratios.factor
        # A meal bolus is a bolus calculator: cover the carbohydrate, correct what is already
        # there, and subtract what is already working. Covering the carbohydrate is not bounded
        # by insulin on board, since the carbohydrate is real and arriving. The correction on
        # top of it is, and it was not: this line added a full correction with no subtraction,
        # so every announced meal above 150 mg/dL stacked on whatever was already acting. The
        # pump's own ceiling caught it rather than the arithmetic, binding on about half a per
        # cent of steps and leaving peak insulin on board sitting exactly at the ceiling for
        # every subject measured.
        #
        # This is the driver titration runs under, so the stacking reached every subject's
        # settings: a baseline that provokes hypoglycaemia is answered by the procedure
        # weakening the settings that are then handed to the algorithms being benchmarked.
        # `controller/reference.py` records the same defect and the same fix.
        on_board = self.loop.iob(minute) if self.loop is not None else 0.0
        bolus = 0.0
        if announced_grams > 0:
            correction = (max((cgm - self.target) / cf - on_board, 0.0)
                          if cgm > 150 else 0.0)
            bolus = max(announced_grams / cr + correction, 0.0)
        basal = self.profile.basal_at(minute)
        if self.loop is not None:
            self.loop.observe(minute, cgm)
            self.loop.add(minute, bolus)
            bolus += self.loop.correction(minute, cgm, cf, fall_rate)
            basal *= self.loop.basal_scale(cgm, fall_rate)
        return Action(basal=basal, bolus=bolus / sample_time)


def _sensor_name(sample_minutes):
    try:
        return SENSOR_BY_SAMPLE_TIME[float(sample_minutes)]
    except KeyError:
        raise ValueError(
            f"no simglucose sensor samples every {sample_minutes} minutes; "
            f"available: {sorted(SENSOR_BY_SAMPLE_TIME)}") from None


def _resolve_controller(controller, profile, adaptive):
    """Turn `controller` into something with a `policy`, and say what it was.

    Returns (object, label, is_builtin). The label goes into the result so that a run can
    always say what drove it, which matters once the driving algorithm is no longer
    recorded among the person's layers.
    """
    if controller is None:
        controller = DEFAULT_CONTROLLER
    # A loop shape means the built-in basal-bolus driven by that shape. The named shapes in
    # `controller/loop.py` cover the two this package ships; passing settings directly is how
    # a variant is driven without registering it, which is what fitting one of its unpublished
    # parameters needs.
    from ..controller.loop import LoopSettings
    if isinstance(controller, LoopSettings):
        return _BasalBolus(profile, adaptive=adaptive, loop=controller), "loop-settings", True
    if isinstance(controller, str):
        if controller not in CONTROLLERS:
            raise ValueError(
                f"unknown controller {controller!r}; expected one of {CONTROLLERS}, "
                "or an object with a policy(observation, reward, done, **info) method")
        if controller == "reference":
            controller = DEFAULT_CONTROLLER
        shape = None if controller == "basal-bolus" else controller
        return _BasalBolus(profile, adaptive=adaptive, loop=shape), controller, True
    if not hasattr(controller, "policy"):
        raise TypeError("a controller needs a policy(observation, reward, done, **info) "
                        "method, which is simglucose's own interface")
    return controller, getattr(controller, "name", type(controller).__name__), False


def _require_matching_profile(controller, prof):
    """Refuse a run where the controller doses against different settings from the rig.

    Compared on the values rather than on identity, since a caller may reasonably rebuild an
    equal profile. The target is deliberately excluded, because a controller is entitled to
    differ on the glucose it is asked to hold.

    Basal, sensitivity and carbohydrate ratio were the only three checked until 21 August 2026,
    and they are not the only inputs a dose is computed from. oref0 reads `max_iob` off the
    profile's limits and every algorithm here reads the duration of insulin action, so a
    controller could compute against a four-hour DIA or a 12 U ceiling while the rig enforced
    five hours and 8 U, agree on all three of the old fields, and pass.
    """
    other = getattr(controller, "profile", None)
    if other is None or other is prof:
        return
    for field in ("dia_min",):
        a, b = getattr(prof, field, None), getattr(other, field, None)
        if a is not None and b is not None and not np.isclose(float(a), float(b)):
            raise ValueError(
                f"the controller's {field} is {b:g} and this run's is {a:g}. An algorithm "
                f"dosing on a different duration of insulin action from the rig delivering it "
                f"is computing insulin on board against a curve that is not being used.")
    la, lb = getattr(prof, "limits", None), getattr(other, "limits", None)
    if la is not None and lb is not None:
        for field in ("max_iob_u", "max_basal_u_per_hour", "max_bolus_u",
                      "basal_increment_u_per_hour", "bolus_increment_u"):
            a, b = getattr(la, field, None), getattr(lb, field, None)
            if a is not None and b is not None and not np.isclose(float(a), float(b)):
                raise ValueError(
                    f"the controller's {field} is {b:g} and the rig enforces {a:g}. The "
                    f"algorithm would dose to a ceiling that is not the one being applied, so "
                    f"its restraint and the rig's would be measured as one thing.")
    for field in ("basal_u_per_hour", "isf", "cr"):
        a = np.asarray(getattr(prof, field), dtype=float)
        b = np.asarray(getattr(other, field), dtype=float)
        if a.shape != b.shape or not np.allclose(a, b, rtol=1e-9, atol=1e-12):
            raise ValueError(
                f"the controller's {field} differs from the profile this run was given. "
                "Pass the same profile to both, or the algorithm will dose against settings "
                "the rig is not delivering: "
                f"controller {np.median(b):.4g} against run {np.median(a):.4g}.")


def subject_seed(name, seed):
    """The seed a subject's random stream is actually started from.

    One generator supplies everything stochastic in a run: the meal schedule, the seed the
    CGM noise model is started from, the infusion set failure times, and the day-to-day
    sensitivity of the physiology layer. Starting it from the integer alone gave every
    subject the same stream, so a cohort at one seed was one random month applied to N
    bodies rather than N months of it. adult#001, adult#016 and adolescent#019 at seed 11
    all ate at minutes 367.8, 701.7, 1073.5, 1373.8, 1883.1 and 2229.2, and all wore the
    same sensor noise realisation.

    What that cost in between-subject spread was measured on ten titrated adults over 14
    days under the trend controller, and the answer was close to nothing. The p10 to p90 of
    sensor jitter across the ten was 5.59 to 5.69 mg/dL on the shared stream and 5.61 to
    5.68 mg/dL with the name folded in, against 3.8 to 12.4 mg/dL across four real cohorts.
    Between-subject standard deviation of mean glucose was 12.84 mg/dL before and 12.33
    after. So the uniformity `docs/CAPABILITY.md` reports is a property of the sensor model
    rather than of the seeding, and the fix is for reproducibility and independence rather
    than for that finding, which stands.

    The digest comes from hashlib because Python's `hash` is salted per process, and a run
    that does not reproduce across processes cannot be cited. Same construction as
    `therapy/profile.py::accuracy_for`, which keys a subject's settings accuracy on its
    name for the same reason.
    """
    digest = hashlib.sha256(f"{name}:{seed}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def stream(name, seed, purpose):
    """An independent generator for one component of one subject's run.

    A single generator shared by every component makes each component's draws depend on which
    other components drew before it. Since a layer only draws when it is switched on, an
    ablation then changed the random month as well as the mechanism: adult#001 at seed 11 ate
    44 g at minute 459 with the physiology layer on and 66 g at minute 476 with it off, so a
    comparison meant to isolate one layer compared two different months.

    That is not a bias, because what is drawn is independent of the layer being tested, but it
    puts the variance the pairing exists to remove back into every ablation, and a layer effect
    small enough to sit under it is reported as indistinguishable from zero.

    `person/behaviour.py::announce` already worked this way, drawing in every announcement mode
    and using the draw only where it applies, after conditional draws made the three modes
    different runs rather than different conditions. This applies the same rule to the layers.

    Streams are keyed on the purpose as well as the subject, so adding a component in future
    leaves every existing component's stream untouched.
    """
    return np.random.default_rng(subject_seed(f"{name}:{purpose}", seed))


def simulate(name, days=28, seed=0, layers=DEFAULT_LAYERS,
             controller=DEFAULT_CONTROLLER,
             meals=None,
             sensor_noise=None,
             compression_per_30d=SENSOR_COMPRESSION_PER_30D,
             params=None, settings=None, profile=None, diurnal_basal=False,
             limits=None, faults=None, sample_minutes=DEFAULT_SAMPLE_MINUTES,
             hypo_risk_gain=None, si_pattern="sinusoid", si_interday_cv=None,
             isf_scale=1.0, settings_spread=None, behaviour_spread=None,
             meal_absorption_cv=None, meal_absorption_scale=None, si_slow_cv=None,
             sessions_per_week=None, hypo_defence_gain=None,
             hypo_egp_defence=None, hypo_egp_floor=None, rescue_bioavailability=None,
             set_life_days=None, announcement="some", meal_delay_min=None,
             engagement_cv=None, liver_delay=None, liver_fast_fraction=None,
             liver_fast_ki_scale=None, liver_kp2_scale=1.0, liver_kp3_scale=1.0):
    """Run one subject. Returns a Result.

    `layers` is any subset of LAYERS. `controller`, if given, replaces the built-in
    basal-bolus controller and is driven through simglucose's own policy interface, so
    the behaviour layer still supplies unannounced meals and rescue carbohydrate around
    it. The `loop` layer is part of the built-in controller, so supplying your own
    controller switches it off; the recorded layers say so rather than claiming it ran.

    `si_pattern` selects the diurnal sensitivity shape of the physiology layer, either the
    common cosine or Visentin's per-subject seven-class model; see `patient/varying.py`.
    `si_interday_cv` overrides the day-to-day term, which matters when comparing the two
    patterns because Visentin's model carries a day-to-day term of its own.

    `params` and `settings` override the shipped population, which is what the validation
    suite uses to test a candidate subject that has not been written into the package.
    `profile` overrides the therapy profile, `limits` the delivery ceilings, and `faults`
    injects the failures in `validation/faults.py`.
    """
    if "loop" in set(layers):
        raise ValueError(
            "'loop' is not a layer of a person, it is a controller. Use "
            "controller='reference' for the correction loop, which is the default, or "
            "controller='basal-bolus' for open-loop therapy. See timsim/simulation/run.py.")
    unknown = set(layers) - set(LAYERS)
    if unknown:
        raise ValueError(f"unknown layers {sorted(unknown)}; expected a subset of {LAYERS}")
    effective = requested = tuple(l for l in LAYERS if l in set(layers))

    # One stream per component, each keyed on the subject and the purpose, so that a
    # component's draws do not depend on which other components ran. See `stream`.
    rng = stream(name, seed, "person")
    params = pd.Series(params if params is not None else params_for(name))
    settings = settings if settings is not None else therapy_for(name)

    prof = profile if profile is not None else profile_mod.for_subject(
        name, params=params, settings=settings, diurnal=diurnal_basal, limits=limits,
        isf_scale=isf_scale,
        **({} if settings_spread is None else {"settings_spread": settings_spread}))

    patient = VaryingPatient(params)
    # The liver insulin delay, applied outside the layer blocks because it is a property of the
    # published model rather than of anything this package adds, so it holds for the stock arm
    # too. 1.0 is S2008 as published; `docs/PADOVA_AUDIT.md` entry 3 has the measurement.
    # The two-timescale liver. Set after `set_liver_delay`, since it reads `ki` to derive the
    # fast rate and the two are alternative treatments of the same divergence: the scale retunes
    # the single pathway and this splits it. `docs/PADOVA_AUDIT.md` entry 3 shows the scale cannot
    # satisfy the clamp and the meal response together, which is why the split exists.
    fast = (LIVER_FAST_FRACTION if liver_fast_fraction is None else float(liver_fast_fraction))
    fast_scale = (LIVER_FAST_KI_SCALE if liver_fast_ki_scale is None
                  else float(liver_fast_ki_scale))
    delay = (LIVER_DELAY_SCALE if liver_delay is None else float(liver_delay))
    if delay != 1.0:
        patient.set_liver_delay(delay)
    # The two gains on production, before anything that captures `kp3`. Both at 1.0 is stock.
    if float(liver_kp2_scale) != 1.0 or float(liver_kp3_scale) != 1.0:
        patient.set_liver_gains(liver_kp2_scale, liver_kp3_scale)
    if fast > 0.0:
        patient.set_liver_two_timescale(fast, fast_scale)
    # Meal-to-meal absorption variation belongs to the physiology layer: it is a property of
    # the gut rather than of anything the person decides or the sensor reports.
    if "physiology" in effective:
        patient.set_meal_variability(
            stream(name, seed, "meal_absorption"),
            MEAL_ABSORPTION_CV if meal_absorption_cv is None
            else float(meal_absorption_cv),
            MEAL_ABSORPTION_SCALE if meal_absorption_scale is None
            else float(meal_absorption_scale))
    if "physiology" in effective:
        patient.set_sensitivity(
            stream(name, seed, "sensitivity"), days, pattern=si_pattern,
            **({} if si_interday_cv is None else {"interday_cv": si_interday_cv}),
            **({} if si_slow_cv is None else {"slow_cv": si_slow_cv}))
        gain = HYPO_RISK_GAIN if hypo_risk_gain is None else hypo_risk_gain
        if gain:
            patient.set_hypo_risk(gain)
        # The counterregulatory arrest of a falling glucose. It belongs to physiology because
        # it is the body opposing the insulin already circulating, so it is present whatever
        # the person eats and whatever the algorithm decides.
        defence = (HYPO_DEFENCE_GAIN if hypo_defence_gain is None
                   else float(hypo_defence_gain))
        hepatic = (HYPO_EGP_DEFENCE if hypo_egp_defence is None
                   else float(hypo_egp_defence))
        if defence or hepatic:
            patient.set_hypo_defence(defence, hepatic)
        # The production floor, which is not a scaling and so is set separately. It binds only
        # where the balance equation has driven production to nothing.
        egp_floor = (HYPO_EGP_FLOOR if hypo_egp_floor is None else float(hypo_egp_floor))
        if egp_floor:
            patient.set_egp_floor(egp_floor)

    if "activity" in effective:
        from ..person.activity import Activity, draw_sessions
        activity = Activity(draw_sessions(stream(name, seed, "activity"), days, **(
            {} if sessions_per_week is None
            else {"sessions_per_week": float(sessions_per_week)})))
        patient.set_activity(activity)
    else:
        activity = None

    body_weight = float(params["BW"])
    schedule = (meals if meals is not None
                else draw_meals(days, stream(name, seed, "meals"), body_weight))
    start = pd.Timestamp("2026-01-01 00:00:00").to_pydatetime()

    threshold, refractory = behaviour_mod.rescue_style(
        name, 0.0 if behaviour_spread is None else behaviour_spread)
    # How closely this subject follows the therapy, drawn once and held for the run. At the
    # default of zero it returns the population values and the run is identical to one taken
    # before the mechanism existed, which is what makes the arm switchable off.
    p_main, p_snack, carb_cv = behaviour_mod.engagement_for(
        name, behaviour_mod.ENGAGEMENT_CV if engagement_cv is None else engagement_cv)
    person = Person(rng, rescue="behaviour" in effective,
                    announce="behaviour" in effective,
                    rescue_threshold=threshold, rescue_refractory_min=refractory,
                    announcement=announcement,
                    p_announce_main=p_main, p_announce_snack=p_snack,
                    carb_estimate_cv=carb_cv)
    # The minutes the meals are actually delivered on, computed the same way for every arm so
    # that the record of what a subject ate does not depend on which layers ran.
    delivery = behaviour_mod.delivery_schedule(schedule)
    if "behaviour" in effective:
        scenario = BehaviourScenario(
            start, schedule, person,
            **({} if meal_delay_min is None else {"meal_delay_min": meal_delay_min}),
            **({} if rescue_bioavailability is None
               else {"rescue_bioavailability": rescue_bioavailability}))
    else:
        scenario = CustomScenario(start_time=start,
                                  scenario=[(m / 60.0, g) for m, g, _ in delivery])

    env = T1DSimEnv(patient,
                    CGMSensor.withName(_sensor_name(sample_minutes),
                                       seed=int(stream(name, seed, "sensor_seed")
                                                .integers(1, 1_000_000))),
                    InsulinPump.withName("Insulet"), scenario)
    env.reset()
    step_minutes = float(env.sample_time)
    steps = int(days * 24 * 60 / step_minutes)

    artefacts = None
    if "sensor" in effective:
        # None means this subject's own noise level. A number applies that level to everybody,
        # which an ablation needs and a cohort does not.
        noise = sensor_style(name, seed) if sensor_noise is None else float(sensor_noise)
        artefacts = OnlineArtefacts(stream(name, seed, "sensor"), steps, step_minutes,
                                    noise_sigma=noise,
                                    compression_per_30d=compression_per_30d)

    enforcer = Enforcer(prof.limits)
    site = (InfusionSite(stream(name, seed, "site"),
                         **({} if set_life_days is None
                            else {"set_life_days": set_life_days}))
            if "site" in effective else None)
    driver, controller_label, builtin_driver = _resolve_controller(
        controller, prof, adaptive="behaviour" in effective)

    # A controller built outside this call carries its own profile, and both bridges fall back
    # to the population's untitrated settings when none is passed. Two profiles then diverge
    # silently: the rig delivers against one and the algorithm doses against the other, which
    # is how a published comparison came to claim two algorithms received the same settings
    # when one of them did not.
    _require_matching_profile(controller, prof)

    # A controller carries state between cycles, and a caller may reasonably hand the same
    # object to two runs. Nothing cleared it, so the second run began with the first run's
    # insulin ledger: two runs of one subject at one seed came out different, and 169 doses
    # crossed between them. `simulate_cohort` with a plain `controller=` object at the default
    # worker count shares one instance across every subject, so each one inherited the last.
    #
    # `reset` is the interface simglucose already defines for this. Testing for it with
    # `hasattr` does not work: the base `Controller` declares the method and raises
    # `NotImplementedError` from it, so every subclass appears to have one and a controller
    # that never overrode it brings the run down. So it is called and that one exception is
    # taken as the answer it is, which is that this controller has no per-run state to clear.
    #
    # A controller that does carry state and does not implement `reset` still carries it
    # between runs. Nothing here can detect that, and `controller_factory` is the way to
    # avoid the question entirely: it builds a fresh instance per subject.
    # Looked up on the type, so an AttributeError raised from inside a real `reset` is not
    # mistaken for the method being absent.
    if callable(getattr(type(driver), "reset", None)):
        try:
            driver.reset()
        except NotImplementedError:
            pass

    # Prime with the subject's own scheduled basal rather than zero. simglucose's examples
    # open with a zero-insulin step, which kicks a subject off the steady state its
    # parameters were closed at and leaves a slow ring through the first day or two.
    obs, reward, done, info = env.step(Action(basal=prof.basal_at(0), bolus=0))

    cgm, bg, insulin, boluses = [], [], [], []
    minute, previous, fall_rate, delivered_bolus = 0.0, None, 0.0, None
    delivered_basal = None
    last_seen, stale_minutes = float(obs.CGM), 0.0
    completed = True

    for _ in range(steps):
        # Read the sensor and the truth at the same instant, before the step that the
        # action about to be chosen will drive. Recording the reading now and the blood
        # glucose after the step would misalign the two series by one sample.
        raw = float(env.CGM_hist[-1]) if env.CGM_hist else float(obs.CGM)
        truth = float(env.BG_hist[-1]) if env.BG_hist else raw
        seen = artefacts(len(cgm), raw) if artefacts is not None else raw
        if faults is not None:
            seen = faults.cgm(minute, seen)
        if seen is None:
            seen, stale_minutes = last_seen, stale_minutes + step_minutes
        else:
            last_seen, stale_minutes = float(seen), 0.0

        # Announced carbohydrate in grams. With the behaviour layer on this comes from the
        # scenario, which accumulates grams. Without it the figure has to be read off the
        # environment, and simglucose reports `meal` as grams per minute averaged over the
        # step, so it needs converting. An earlier version passed the per-minute rate
        # straight through as though it were grams, which under-bolused every run that had
        # the behaviour layer switched off by a factor of the step length.
        announced = (scenario.drain()[0] if "behaviour" in effective
                     else float(info.get("meal", 0.0)) * step_minutes)
        # The time the algorithm believes it is, which a clock fault can move away from
        # the real elapsed minute. Delivery accounting below stays on the real clock.
        clock = faults.clock(minute) if faults is not None else minute
        step_info = {**info, "meal": announced / step_minutes,
                     "sample_time": step_minutes, "stale_minutes": stale_minutes,
                     "profile": prof, "clock_minutes": clock,
                     # What the pump delivered last step, which is what a real algorithm
                     # reads back out of pump history. It is not what was asked for: the
                     # ceilings sit in between, and an algorithm that tracks its own
                     # requests instead will over-estimate its insulin on board.
                     "delivered_bolus_u": delivered_bolus,
                     # What the pump ran as basal last step and what the profile asked for.
                     # AndroidAPS measures insulin on board against the schedule, so an
                     # algorithm reconstructing it needs both to get a negative figure when
                     # the loop has been withholding.
                     "delivered_basal_u": delivered_basal,
                     "scheduled_basal_u": prof.basal_at(minute) * step_minutes}

        if builtin_driver:
            action = driver.act(announced, seen, clock, step_minutes, fall_rate)
        else:
            obs_seen = type(obs)(CGM=seen) if hasattr(obs, "_fields") else obs
            action = driver.policy(obs_seen, reward, done, **step_info)

        basal_u_per_min, bolus_u = enforcer.apply(
            minute, float(action.basal), float(action.bolus) * step_minutes,
            prof.basal_at(minute), step_minutes)
        if faults is not None:
            basal_u_per_min, bolus_u = faults.delivery(minute, basal_u_per_min, bolus_u)

        # What the pump reports to the algorithm next step. Taken after the ceilings and
        # before the fault and the site, because those two are exactly the losses a pump
        # cannot see and would not report.
        delivered_bolus = float(bolus_u)
        delivered_basal = float(basal_u_per_min) * step_minutes

        # A failed site sits between the pump and the depot, so it attenuates after the
        # limits and after any injected fault. Whatever it swallows is added back below:
        # the pump delivered it, and the point of the failure is that nothing says so.
        lost = 0.0
        if site is not None:
            basal_u_per_min, bolus_u, lost = site.apply(
                minute, basal_u_per_min, bolus_u, step_minutes)

        obs, reward, done, info = env.step(
            Action(basal=basal_u_per_min, bolus=bolus_u / step_minutes))

        delivered = float(env.insulin_hist[-1]) * step_minutes if env.insulin_hist else 0.0
        insulin.append(delivered + lost)
        boluses.append(float(delivered_bolus))
        cgm.append(seen)
        bg.append(truth)
        minute += step_minutes

        if seen and seen > 0:
            fall_rate = (seen - previous) / step_minutes if previous else 0.0
            previous = seen
            if "behaviour" in effective:
                person.observe(minute, seen, fall_rate)
            if site is not None:
                site.observe(minute, seen, step_minutes)
        if done:
            completed = False
            break

    keep = [i for i, c in enumerate(cgm) if c is not None and c > 0]
    cgm = np.asarray([cgm[i] for i in keep], float)
    bg = np.asarray([bg[i] for i in keep], float)
    insulin = np.asarray([insulin[i] for i in keep], float)
    boluses = np.asarray([boluses[i] for i in keep], float)
    # The run is primed with one step before the loop, so the first sample is read after the
    # model has already advanced by one interval and sample i belongs to minute (i+1)*step.
    # Numbering from zero put the glucose series one interval behind `meal_log` and
    # `rescue_log`, which carry the model's own clock, so any analysis locating a meal or a
    # rescue in the series landed one sample early. That is one sample on a peak time of about
    # 200 minutes, and it is systematic.
    minutes = (np.arange(len(cgm), dtype=float) + 1.0) * step_minutes

    meta = {"seed": seed, "body_weight": body_weight,
            "basal_u_per_min": prof.basal_at(0), "cr": prof.cr_at(12 * 60),
            "cf": prof.isf_at(12 * 60), "requested_layers": requested,
            "sample_minutes": step_minutes, "diurnal_basal": bool(diurnal_basal),
            "controller": controller_label,
            "si_pattern": si_pattern, "isf_scale": float(isf_scale),
            "settings_spread": float(settings_spread or 0.0),
            "behaviour_spread": float(behaviour_spread or 0.0),
            "rescue_threshold": threshold, "rescue_refractory_min": refractory,
            "si_class": getattr(patient, "si_class", None),
            "profile": prof.as_dict()}
    meta.update(enforcer.report())
    if site is not None:
        meta.update(site.report())
    if faults is not None:
        meta["faults"] = faults.report()

    result = Result(
        name=name, cgm=cgm, bg=bg, minutes=minutes, sample_time=step_minutes,
        days_requested=days, completed=completed,
        insulin_units=float(insulin.sum()), insulin_series=insulin,
        bolus_series=boluses,
        rescue_events=person.rescue_events, rescue_grams=person.rescue_grams,
        rescue_log=tuple(person.rescue_log),
        # What the person was actually given, on the minutes it was given, so the log cannot
        # disagree with the gut and does not change shape when a layer is switched off.
        meal_log=tuple((m, g) for m, g, _ in delivery),
        activity_log=() if activity is None else tuple(activity.sessions),
        meals_announced=person.announced_meals,
        meals_unannounced=person.unannounced_meals,
        isf_weekly_cv=(driver.ratios.weekly_cv()
                       if (builtin_driver and driver.ratios is not None)
                       else float("nan")),
        compression_events=artefacts.events if artefacts is not None else 0,
        layers=effective, controller=controller_label, meta=meta,
    )
    # Why a run ended, recorded where it happened rather than reconstructed by a caller. A
    # completion count cannot separate a run that fell out of the model's range from one that
    # rose out of it, and on this bench both happen: under oref0 SMB on the layered bench five
    # of seven terminations were hyperglycaemic.
    from ..analysis.cohort import classify_termination
    result.termination = classify_termination(result)
    return result


def _cohort_one(job):
    """One subject of a cohort, in whatever process is running it."""
    name, days, seed, layers, controller, factory, profile_factory, kwargs = job
    kwargs = dict(kwargs)
    if profile_factory is not None:
        kwargs["profile"] = profile_factory(name)
    # Only an instance this call created is closed. A controller passed in belongs to the
    # caller, and a serial cohort hands the same object to every subject in turn: closing it
    # after the first left an `OrefController` with a dead node subprocess and a
    # `BoostController` with a dead JVM, to be used again by the next subject.
    owned = factory is not None
    driver = factory(name) if owned else controller
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("once", UserWarning)
            return simulate(name, days=days, seed=seed, layers=layers,
                            controller=driver, **kwargs)
    finally:
        if owned and hasattr(driver, "close"):
            driver.close()


def _parallelisable(controller, controller_factory, profile_factory=None, kwargs=None):
    """Whether this cohort can be spread across processes, and why not when it cannot.

    A worker receives its job by pickle, so anything holding a live resource cannot cross.
    The compiled algorithms are the case that matters: an `OrefController` owns a node
    subprocess and a `BoostController` a JVM, and sending either would either fail to pickle
    or, worse, hand two subjects the same pipe. A factory is fine when it is importable,
    since the worker calls it to build a fresh instance on its own side, which is what the
    factory is for.
    """
    import pickle
    candidates = [(controller, "controller"), (controller_factory, "controller_factory"),
                  (profile_factory, "profile_factory")]
    # The job carries the keyword arguments too, so a fault configuration or a profile built by
    # a lambda crosses with it. Testing only the two controller slots promised a serial fallback
    # and then died in the pool instead of taking it.
    for key, value in (kwargs or {}).items():
        candidates.append((value, f"kwargs[{key!r}]"))
    for what, label in candidates:
        if what is None or isinstance(what, (str, int, float, bool)):
            continue
        try:
            pickle.dumps(what)
        except Exception:
            return False, (f"{label} cannot be sent to a worker process, so the cohort runs "
                           f"serially; define it at module level to parallelise it")
    return True, None


def simulate_cohort(names=None, days=28, seed=0, layers=DEFAULT_LAYERS,
                    controller=DEFAULT_CONTROLLER, controller_factory=None,
                    profile_factory=None, progress=True, workers=1, **kwargs):
    """Run many subjects. Returns a list of Result, one per subject.

    `controller` is the same argument `simulate` takes. `controller_factory` is for an
    algorithm that carries per-subject state: it is called with the subject name and must
    return a fresh instance, so nothing leaks between subjects. Give one or the other.

    `profile_factory` supplies each subject's therapy profile, called with the name. The
    reason it exists is titration: settings are per subject, `profile` in `kwargs` would
    hand every subject the same one, and passing nothing runs the physiological settings
    no real person carries. `timsim.therapy.titrate.profile_for` is the intended value.

    `workers` above one spreads the subjects across processes. Results are identical either
    way and are returned in the order `names` gives, because a subject's random stream comes
    from `subject_seed(name, seed)` and not from where it sits in the list or from when it
    runs. It defaults to one so that no existing caller changes behaviour by upgrading.

    A cohort holding a live resource cannot be spread, and says so rather than failing: an
    `OrefController` owns a node subprocess and cannot be pickled to a worker.

    One caller-side requirement comes with `workers` above one. Python spawns rather than
    forks on macOS, so a worker re-imports the module it was launched from, and a script that
    calls this at module level re-runs itself in every worker. Put the call behind
    `if __name__ == "__main__":`, which is why every runnable example here does.
    """
    from ..population import names as all_names
    if controller_factory is not None and controller != DEFAULT_CONTROLLER:
        raise ValueError("give either controller or controller_factory, not both")
    names = list(names or all_names())

    def report(name, r):
        if not progress:
            return
        s = r.summary()
        print(f"  {name:>16}  mean {s['mean']:3.0f}  CV {s['cv']:4.1f}%  "
              f"TIR {s['tir']:4.1f}%  TBR {s['tbr']:4.1f}%  "
              f"{'' if s['completed'] else 'DID NOT COMPLETE'}", flush=True)

    if workers and workers > 1:
        ok, why = _parallelisable(controller, controller_factory,
                                  profile_factory, kwargs)
        if not ok:
            warnings.warn(why, RuntimeWarning, stacklevel=2)
        else:
            from concurrent.futures import ProcessPoolExecutor
            jobs = [(n, days, seed, layers, controller, controller_factory,
                     profile_factory, kwargs)
                    for n in names]
            with ProcessPoolExecutor(max_workers=int(workers)) as ex:
                out = list(ex.map(_cohort_one, jobs))
            for name, r in zip(names, out):
                report(name, r)
            return out

    out = []
    for name in names:
        # Every subject is run at the seed as passed. The offset by list position used
        # to be what stopped a cohort drawing one shared random month, and
        # `subject_seed` now does that from the name; keeping the offset as well would
        # make a subject's run depend on where it sat in `names`, so a subject would
        # come out differently in a full cohort and in a subset of it.
        r = _cohort_one((name, days, seed, layers, controller, controller_factory,
                         profile_factory, kwargs))
        out.append(r)
        report(name, r)
    return out


__all__ = ["simulate", "simulate_cohort", "Result", "LAYERS", "DEFAULT_LAYERS",
           "CONTROLLERS", "DEFAULT_CONTROLLER", "draw_meals", "subject_seed",
           "DEFAULT_SAMPLE_MINUTES"]
