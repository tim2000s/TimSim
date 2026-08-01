"""Run a subject for a number of days, with any subset of the layers switched on.

The layers, and what each is for:

    physiology   insulin sensitivity that varies by time of day and day to day
    behaviour    meals announced imperfectly, lows treated with carbohydrate,
                 a sensitivity setting that adapts
    loop         continuous correction with an insulin-on-board bound
    sensor       measurement jitter and compression lows, applied to the finished trace

Every layer can be switched off, so a difference between two runs is attributable to a
named mechanism rather than to the bundle. `LAYERS` is the full set; passing a subset is
how the ablation in `examples/layer_ablation.py` works.

The controller interface is simglucose's: anything with `policy(observation, reward,
done, **info) -> Action(basal, bolus)` can be passed as `controller` and will be driven
in place of the built-in one. That is the hook for testing a real algorithm.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from simglucose.actuator.pump import InsulinPump
from simglucose.controller.base import Action
from simglucose.sensor.cgm import CGMSensor
from simglucose.simulation.env import T1DSimEnv
from simglucose.simulation.scenario import CustomScenario

from ..controller.loop import CorrectionLoop
from ..patient.varying import VaryingPatient
from ..person.behaviour import AdaptiveRatios, BehaviourScenario, Person
from ..population import params_for, therapy_for
from ..sensor.realism import apply as apply_sensor

LAYERS = ("physiology", "behaviour", "loop", "sensor")

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

    Deliberately simple. It is the substrate the behaviour and loop layers act through,
    not an algorithm under test.
    """

    def __init__(self, cr, cf, basal, target=140.0, adaptive=True, loop=False):
        self.cr0, self.cf0, self.basal, self.target = cr, cf, basal, target
        self.ratios = AdaptiveRatios(cf, cr) if adaptive else None
        self.loop = CorrectionLoop() if loop else None
        self.units = 0.0

    def act(self, announced_grams, cgm, minute, sample_time, fall_rate=0.0):
        cr, cf = self.cr0, self.cf0
        if self.ratios is not None:
            self.ratios.observe(minute, cgm, self.target)
            cr, cf = self.ratios.cr, self.ratios.cf
        bolus = 0.0
        if announced_grams > 0:
            bolus = max(announced_grams / cr + (cgm > 150) * (cgm - self.target) / cf, 0.0)
        basal = self.basal
        if self.loop is not None:
            self.loop.add(minute, bolus)
            bolus += self.loop.correction(minute, cgm, cf)
            basal *= self.loop.basal_scale(cgm, fall_rate)
        self.units += bolus + basal * sample_time
        return Action(basal=basal, bolus=bolus / sample_time)


def simulate(name, days=28, seed=0, layers=LAYERS, controller=None, meals=None,
             sensor_noise=SENSOR_NOISE_SIGMA,
             compression_per_30d=SENSOR_COMPRESSION_PER_30D):
    """Run one subject. Returns a Result.

    `layers` is any subset of LAYERS. `controller`, if given, replaces the built-in
    basal-bolus controller and is driven through simglucose's own policy interface, so
    the behaviour layer still supplies unannounced meals and rescue carbohydrate around
    it.
    """
    layers = tuple(l for l in LAYERS if l in set(layers))
    rng = np.random.default_rng(seed)

    params = pd.Series(params_for(name))
    settings = therapy_for(name)
    patient = VaryingPatient(params)
    if "physiology" in layers:
        patient.set_sensitivity(rng, days)

    body_weight = float(params["BW"])
    schedule = meals if meals is not None else draw_meals(days, rng, body_weight)
    start = pd.Timestamp("2026-01-01 00:00:00").to_pydatetime()

    person = Person(rng, rescue="behaviour" in layers, announce="behaviour" in layers)
    if "behaviour" in layers:
        scenario = BehaviourScenario(start, schedule, person)
    else:
        scenario = CustomScenario(start_time=start,
                                  scenario=[(h, g) for h, g, _ in schedule])

    env = T1DSimEnv(patient,
                    CGMSensor.withName("Dexcom", seed=int(rng.integers(1, 1_000_000))),
                    InsulinPump.withName("Insulet"), scenario)
    env.reset()
    step_minutes = env.sample_time

    basal = float(params["u2ss"]) * body_weight / 6000.0
    builtin = _BasalBolus(float(settings["CR"]), float(settings["CF"]), basal,
                          adaptive="behaviour" in layers, loop="loop" in layers)

    obs, reward, done, info = env.step(Action(basal=0, bolus=0))
    cgm, bg, minute, previous, fall_rate = [], [], 0, None, 0.0
    steps = int(days * 24 * 60 / step_minutes)
    completed = True
    for _ in range(steps):
        announced = scenario.drain()[0] if "behaviour" in layers else info.get("meal", 0.0)
        if controller is not None:
            action = controller.policy(obs, reward, done,
                                       **{**info, "meal": announced / step_minutes})
        else:
            action = builtin.act(announced, obs.CGM, minute, step_minutes, fall_rate)
        obs, reward, done, info = env.step(action)
        value = env.CGM_hist[-1] if env.CGM_hist else obs.CGM
        cgm.append(value)
        bg.append(env.BG_hist[-1] if env.BG_hist else value)
        minute += step_minutes
        if value and value > 0:
            fall_rate = (value - previous) / step_minutes if previous else 0.0
            previous = value
            if "behaviour" in layers:
                person.observe(minute, value, fall_rate)
        if done:
            completed = False
            break

    cgm = np.asarray([c for c in cgm if c is not None and c > 0], float)
    bg = np.asarray(bg[:len(cgm)], float)
    minutes = np.arange(len(cgm), dtype=float) * step_minutes

    events = 0
    if "sensor" in layers and len(cgm) > 20:
        cgm, events = apply_sensor(minutes * 60.0, cgm, rng, noise_sigma=sensor_noise,
                                   compression_rate=compression_per_30d)

    return Result(
        name=name, cgm=cgm, bg=bg, minutes=minutes, sample_time=step_minutes,
        days_requested=days, completed=completed,
        insulin_units=builtin.units if controller is None else float("nan"),
        rescue_events=person.rescue_events, rescue_grams=person.rescue_grams,
        meals_announced=person.announced_meals,
        meals_unannounced=person.unannounced_meals,
        isf_weekly_cv=(builtin.ratios.weekly_cv() if builtin.ratios else float("nan")),
        compression_events=events, layers=layers,
        meta={"seed": seed, "body_weight": body_weight, "basal_u_per_min": basal,
              "cr": float(settings["CR"]), "cf": float(settings["CF"])},
    )


def simulate_cohort(names=None, days=28, seed=0, layers=LAYERS, controller_factory=None,
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
        r = simulate(name, days=days, seed=seed + i, layers=layers,
                     controller=controller, **kwargs)
        out.append(r)
        if progress:
            s = r.summary()
            print(f"  {name:>16}  mean {s['mean']:3.0f}  CV {s['cv']:4.1f}%  "
                  f"TIR {s['tir']:4.1f}%  TBR {s['tbr']:4.1f}%  "
                  f"{'' if s['completed'] else 'DID NOT COMPLETE'}", flush=True)
    return out


__all__ = ["simulate", "simulate_cohort", "Result", "LAYERS", "draw_meals"]
