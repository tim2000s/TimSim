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
from ..patient.varying import (HYPO_DEFENCE_GAIN, HYPO_EGP_DEFENCE, HYPO_RISK_GAIN,
                               MEAL_ABSORPTION_CV, MEAL_ABSORPTION_SCALE, VaryingPatient)
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
# It costs three of the eleven signatures in `docs/FIDELITY.md`, taking that table from
# eight of eleven to five, which is the worst score of any configuration measured. It is
# also the configuration hardest to tell from real data: against 3,023 windows from the
# DCLP3 closed-loop participants it scores 0.671 where the same person without it scores
# 0.710, beating it in ten cross-validation splits out of ten. Both statements are true. The
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
DEFAULT_MEALS = [
    (7.0, 1.0, 45, 15, 0.92, False),
    (12.5, 1.2, 65, 20, 0.95, False),
    (18.5, 1.3, 80, 25, 0.97, False),
    (15.5, 1.5, 20, 10, 0.45, True),
    (22.0, 1.0, 18, 10, 0.35, True),
]

SENSOR_NOISE_SIGMA = 2.0
SENSOR_COMPRESSION_PER_30D = 4.5


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
        mid = profile.isf_at(12 * 60), profile.cr_at(12 * 60)
        self.ratios = AdaptiveRatios(mid[0], mid[1]) if adaptive else None
        self.loop = CorrectionLoop(loop) if loop else None
        self.target = float(target)

    def act(self, announced_grams, cgm, minute, sample_time, fall_rate=0.0):
        cf, cr = self.profile.isf_at(minute), self.profile.cr_at(minute)
        if self.ratios is not None:
            self.ratios.observe(minute, cgm, self.target)
            cf, cr = cf * self.ratios.factor, cr * self.ratios.factor
        bolus = 0.0
        if announced_grams > 0:
            bolus = max(announced_grams / cr + (cgm > 150) * (cgm - self.target) / cf, 0.0)
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
    equal profile. Only the three quantities an algorithm doses from are checked, because a
    controller is entitled to differ on the target it is asked to hold.
    """
    other = getattr(controller, "profile", None)
    if other is None or other is prof:
        return
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


def simulate(name, days=28, seed=0, layers=DEFAULT_LAYERS,
             controller=DEFAULT_CONTROLLER,
             meals=None,
             sensor_noise=SENSOR_NOISE_SIGMA,
             compression_per_30d=SENSOR_COMPRESSION_PER_30D,
             params=None, settings=None, profile=None, diurnal_basal=False,
             limits=None, faults=None, sample_minutes=DEFAULT_SAMPLE_MINUTES,
             hypo_risk_gain=None, si_pattern="sinusoid", si_interday_cv=None,
             isf_scale=1.0, settings_spread=None, behaviour_spread=None,
             meal_absorption_cv=None, meal_absorption_scale=None, si_slow_cv=None,
             sessions_per_week=None, hypo_defence_gain=None,
             hypo_egp_defence=None, set_life_days=None, announcement="some",
             meal_delay_min=None):
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

    # Keyed on the subject as well as the integer, so that two subjects at one seed are two
    # independent months rather than the same month twice. See `subject_seed`.
    rng = np.random.default_rng(subject_seed(name, seed))
    params = pd.Series(params if params is not None else params_for(name))
    settings = settings if settings is not None else therapy_for(name)

    prof = profile if profile is not None else profile_mod.for_subject(
        name, params=params, settings=settings, diurnal=diurnal_basal, limits=limits,
        isf_scale=isf_scale,
        **({} if settings_spread is None else {"settings_spread": settings_spread}))

    patient = VaryingPatient(params)
    # Meal-to-meal absorption variation belongs to the physiology layer: it is a property of
    # the gut rather than of anything the person decides or the sensor reports.
    if "physiology" in effective:
        patient.set_meal_variability(
            rng,
            MEAL_ABSORPTION_CV if meal_absorption_cv is None
            else float(meal_absorption_cv),
            MEAL_ABSORPTION_SCALE if meal_absorption_scale is None
            else float(meal_absorption_scale))
    if "physiology" in effective:
        patient.set_sensitivity(
            rng, days, pattern=si_pattern,
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

    if "activity" in effective:
        from ..person.activity import Activity, draw_sessions
        activity = Activity(draw_sessions(rng, days, **(
            {} if sessions_per_week is None
            else {"sessions_per_week": float(sessions_per_week)})))
        patient.set_activity(activity)
    else:
        activity = None

    body_weight = float(params["BW"])
    schedule = meals if meals is not None else draw_meals(days, rng, body_weight)
    start = pd.Timestamp("2026-01-01 00:00:00").to_pydatetime()

    threshold, refractory = behaviour_mod.rescue_style(
        name, 0.0 if behaviour_spread is None else behaviour_spread)
    person = Person(rng, rescue="behaviour" in effective,
                    announce="behaviour" in effective,
                    rescue_threshold=threshold, rescue_refractory_min=refractory,
                    announcement=announcement)
    if "behaviour" in effective:
        scenario = BehaviourScenario(
            start, schedule, person,
            **({} if meal_delay_min is None else {"meal_delay_min": meal_delay_min}))
    else:
        scenario = CustomScenario(start_time=start,
                                  scenario=[(h, g) for h, g, _ in schedule])

    env = T1DSimEnv(patient,
                    CGMSensor.withName(_sensor_name(sample_minutes),
                                       seed=int(rng.integers(1, 1_000_000))),
                    InsulinPump.withName("Insulet"), scenario)
    env.reset()
    step_minutes = float(env.sample_time)
    steps = int(days * 24 * 60 / step_minutes)

    artefacts = None
    if "sensor" in effective:
        artefacts = OnlineArtefacts(rng, steps, step_minutes, noise_sigma=sensor_noise,
                                    compression_per_30d=compression_per_30d)

    enforcer = Enforcer(prof.limits)
    site = (InfusionSite(rng, **({} if set_life_days is None
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

    # Prime with the subject's own scheduled basal rather than zero. simglucose's examples
    # open with a zero-insulin step, which kicks a subject off the steady state its
    # parameters were closed at and leaves a slow ring through the first day or two.
    obs, reward, done, info = env.step(Action(basal=prof.basal_at(0), bolus=0))

    cgm, bg, insulin = [], [], []
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
    minutes = np.arange(len(cgm), dtype=float) * step_minutes

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
        rescue_events=person.rescue_events, rescue_grams=person.rescue_grams,
        rescue_log=tuple(person.rescue_log),
        meal_log=tuple((float(h) * 60.0, float(g)) for h, g, _ in schedule),
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


def simulate_cohort(names=None, days=28, seed=0, layers=DEFAULT_LAYERS,
                    controller=DEFAULT_CONTROLLER, controller_factory=None,
                    progress=True, **kwargs):
    """Run many subjects. Returns a list of Result, one per subject.

    `controller` is the same argument `simulate` takes. `controller_factory` is for an
    algorithm that carries per-subject state: it is called with the subject name and must
    return a fresh instance, so nothing leaks between subjects. Give one or the other.
    """
    from ..population import names as all_names
    if controller_factory is not None and controller != DEFAULT_CONTROLLER:
        raise ValueError("give either controller or controller_factory, not both")
    names = names or all_names()
    out = []
    for name in names:
        driver = controller_factory(name) if controller_factory else controller
        with warnings.catch_warnings():
            warnings.simplefilter("once", UserWarning)
            # Every subject is run at the seed as passed. The offset by list position used
            # to be what stopped a cohort drawing one shared random month, and
            # `subject_seed` now does that from the name; keeping the offset as well would
            # make a subject's run depend on where it sat in `names`, so a subject would
            # come out differently in a full cohort and in a subset of it.
            r = simulate(name, days=days, seed=seed, layers=layers,
                         controller=driver, **kwargs)
        out.append(r)
        if progress:
            s = r.summary()
            print(f"  {name:>16}  mean {s['mean']:3.0f}  CV {s['cv']:4.1f}%  "
                  f"TIR {s['tir']:4.1f}%  TBR {s['tbr']:4.1f}%  "
                  f"{'' if s['completed'] else 'DID NOT COMPLETE'}", flush=True)
    return out


__all__ = ["simulate", "simulate_cohort", "Result", "LAYERS", "DEFAULT_LAYERS",
           "CONTROLLERS", "DEFAULT_CONTROLLER", "draw_meals", "subject_seed",
           "DEFAULT_SAMPLE_MINUTES"]
