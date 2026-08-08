"""Run a subject for a number of days, with any subset of the layers switched on.

The layers, and what each is for:

    physiology   insulin sensitivity that varies by time of day and day to day
    behaviour    meals announced imperfectly, lows treated with carbohydrate,
                 a sensitivity setting that adapts
    loop         continuous correction with an insulin-on-board bound
    sensor       measurement jitter and compression lows, applied inside the loop
    site         infusion sets that fail quietly, and get noticed and changed late

Every layer can be switched off, so a difference between two runs is attributable to a
named mechanism rather than to the bundle. `LAYERS` is every layer that exists and
`DEFAULT_LAYERS` is what runs unless you say otherwise; passing a subset is how the
ablation in `examples/layer_ablation.py` works.

The controller interface is simglucose's: anything with `policy(observation, reward,
done, **info) -> Action(basal, bolus)` can be passed as `controller` and will be driven
in place of the built-in one. That is the hook for testing a real algorithm, and
`docs/OSAID.md` covers what an automated insulin delivery system needs beyond it.

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

Insulin is measured at the body rather than at the controller, so the figure is right
whichever controller produced it. The one thing added back is insulin a failed infusion
site swallowed, since that really did leave the pump and would appear in any real log.
"""
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
from ..patient.varying import HYPO_RISK_GAIN, VaryingPatient
from ..person.behaviour import AdaptiveRatios, BehaviourScenario, Person
from ..population import params_for, therapy_for
from ..sensor.realism import OnlineArtefacts
from ..therapy import Enforcer, InfusionSite, profile as profile_mod

# Every layer that exists, and the subset that runs unless a caller asks for more. They are
# the same set, and the site layer was the last one in, on a decision worth recording.
#
# It costs three of the eleven signatures in `docs/FIDELITY.md`, taking that table from
# eight of eleven to five, which is the worst score of any configuration measured. It is
# also the configuration hardest to tell from real data: against 3,023 windows from the
# DCLP3 closed-loop participants it scores 0.671 where the four-layer default scores 0.710,
# beating it in ten cross-validation splits out of ten. Both statements are true. The
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
LAYERS = ("physiology", "behaviour", "loop", "sensor", "site")
DEFAULT_LAYERS = LAYERS

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
    meals_announced: int = 0
    meals_unannounced: int = 0
    isf_weekly_cv: float = float("nan")
    compression_events: int = 0
    layers: tuple = ()
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

    def __init__(self, profile, adaptive=True, loop=False, target=CORRECTION_TARGET):
        self.profile = profile
        mid = profile.isf_at(12 * 60), profile.cr_at(12 * 60)
        self.ratios = AdaptiveRatios(mid[0], mid[1]) if adaptive else None
        self.loop = CorrectionLoop() if loop else None
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
            self.loop.add(minute, bolus)
            bolus += self.loop.correction(minute, cgm, cf)
            basal *= self.loop.basal_scale(cgm, fall_rate)
        return Action(basal=basal, bolus=bolus / sample_time)


def _sensor_name(sample_minutes):
    try:
        return SENSOR_BY_SAMPLE_TIME[float(sample_minutes)]
    except KeyError:
        raise ValueError(
            f"no simglucose sensor samples every {sample_minutes} minutes; "
            f"available: {sorted(SENSOR_BY_SAMPLE_TIME)}") from None


def simulate(name, days=28, seed=0, layers=DEFAULT_LAYERS, controller=None, meals=None,
             sensor_noise=SENSOR_NOISE_SIGMA,
             compression_per_30d=SENSOR_COMPRESSION_PER_30D,
             params=None, settings=None, profile=None, diurnal_basal=False,
             limits=None, faults=None, sample_minutes=DEFAULT_SAMPLE_MINUTES,
             hypo_risk_gain=None, si_pattern="sinusoid", si_interday_cv=None,
             isf_scale=1.0):
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
    requested = tuple(l for l in LAYERS if l in set(layers))
    effective = requested
    if controller is not None and "loop" in effective:
        warnings.warn(
            "the loop layer belongs to the built-in controller, so supplying your own "
            "controller switches it off; it has been dropped from the recorded layers",
            UserWarning, stacklevel=2)
        effective = tuple(l for l in effective if l != "loop")

    rng = np.random.default_rng(seed)
    params = pd.Series(params if params is not None else params_for(name))
    settings = settings if settings is not None else therapy_for(name)

    prof = profile if profile is not None else profile_mod.for_subject(
        name, params=params, settings=settings, diurnal=diurnal_basal, limits=limits,
        isf_scale=isf_scale)

    patient = VaryingPatient(params)
    if "physiology" in effective:
        patient.set_sensitivity(
            rng, days, pattern=si_pattern,
            **({} if si_interday_cv is None else {"interday_cv": si_interday_cv}))
        gain = HYPO_RISK_GAIN if hypo_risk_gain is None else hypo_risk_gain
        if gain:
            patient.set_hypo_risk(gain)

    body_weight = float(params["BW"])
    schedule = meals if meals is not None else draw_meals(days, rng, body_weight)
    start = pd.Timestamp("2026-01-01 00:00:00").to_pydatetime()

    person = Person(rng, rescue="behaviour" in effective,
                    announce="behaviour" in effective)
    if "behaviour" in effective:
        scenario = BehaviourScenario(start, schedule, person)
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
    site = InfusionSite(rng) if "site" in effective else None
    builtin = _BasalBolus(prof, adaptive="behaviour" in effective,
                          loop="loop" in effective)

    # Prime with the subject's own scheduled basal rather than zero. simglucose's examples
    # open with a zero-insulin step, which kicks a subject off the steady state its
    # parameters were closed at and leaves a slow ring through the first day or two.
    obs, reward, done, info = env.step(Action(basal=prof.basal_at(0), bolus=0))

    cgm, bg, insulin = [], [], []
    minute, previous, fall_rate = 0.0, None, 0.0
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
                     "profile": prof, "clock_minutes": clock}

        if controller is not None:
            obs_seen = type(obs)(CGM=seen) if hasattr(obs, "_fields") else obs
            action = controller.policy(obs_seen, reward, done, **step_info)
        else:
            action = builtin.act(announced, seen, clock, step_minutes, fall_rate)

        basal_u_per_min, bolus_u = enforcer.apply(
            minute, float(action.basal), float(action.bolus) * step_minutes,
            prof.basal_at(minute), step_minutes)
        if faults is not None:
            basal_u_per_min, bolus_u = faults.delivery(minute, basal_u_per_min, bolus_u)

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
            "si_pattern": si_pattern, "isf_scale": float(isf_scale),
            "si_class": getattr(patient, "si_class", None),
            "profile": prof.as_dict()}
    meta.update(enforcer.report())
    if site is not None:
        meta.update(site.report())
    if faults is not None:
        meta["faults"] = faults.report()

    return Result(
        name=name, cgm=cgm, bg=bg, minutes=minutes, sample_time=step_minutes,
        days_requested=days, completed=completed,
        insulin_units=float(insulin.sum()), insulin_series=insulin,
        rescue_events=person.rescue_events, rescue_grams=person.rescue_grams,
        meals_announced=person.announced_meals,
        meals_unannounced=person.unannounced_meals,
        isf_weekly_cv=(builtin.ratios.weekly_cv()
                       if (builtin.ratios is not None and controller is None)
                       else float("nan")),
        compression_events=artefacts.events if artefacts is not None else 0,
        layers=effective, meta=meta,
    )


def simulate_cohort(names=None, days=28, seed=0, layers=DEFAULT_LAYERS, controller_factory=None,
                    progress=True, **kwargs):
    """Run many subjects. Returns a list of Result, one per subject.

    `controller_factory` is called with the subject name and must return a fresh
    controller, so no state leaks between subjects.
    """
    from ..population import names as all_names
    names = names or all_names()
    out = []
    for i, name in enumerate(names):
        controller = controller_factory(name) if controller_factory else None
        with warnings.catch_warnings():
            warnings.simplefilter("once", UserWarning)
            r = simulate(name, days=days, seed=seed + i, layers=layers,
                         controller=controller, **kwargs)
        out.append(r)
        if progress:
            s = r.summary()
            print(f"  {name:>16}  mean {s['mean']:3.0f}  CV {s['cv']:4.1f}%  "
                  f"TIR {s['tir']:4.1f}%  TBR {s['tbr']:4.1f}%  "
                  f"{'' if s['completed'] else 'DID NOT COMPLETE'}", flush=True)
    return out


__all__ = ["simulate", "simulate_cohort", "Result", "LAYERS", "DEFAULT_LAYERS",
           "draw_meals",
           "DEFAULT_SAMPLE_MINUTES"]
