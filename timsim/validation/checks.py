"""Checks on whether the simulator can be believed, and about what.

Veracity is not one number. A simulator can be trusted for one question and useless for
the next, so the checks here are graded, and each one says what it licenses.

    Level 1  internal consistency   does the code do what it claims
    Level 2  face validity          does it get the direction and rough size right
    Level 3  distributional         does its output look like real data
    Level 4  known answer           does it reproduce a result established elsewhere
    Level 5  discriminating power   how large a difference can it actually resolve
    Level 6  robustness             do conclusions survive the arbitrary choices

Level 3 is the one `docs/FIDELITY.md` reports and it is the weakest of the six taken
alone: matching marginal statistics does not mean the response to an intervention is
right. Levels 4 and 5 are what a controller comparison actually rests on, and level 5 in
particular is the one most often skipped, because without it an A/B result has no scale
to be read against.

Nothing here validates the simulator for pricing a dosing change in a specific person.
That is a different claim and no check in this file supports it.
"""
import numpy as np
import pandas as pd

from .. import therapy
from ..analysis import signatures as S
from ..population import derive, params_for, therapy_for
from ..simulation.run import simulate

# ---------------------------------------------------------------------- level 1


def check_steady_state_closure():
    """The balance equations must reproduce every published subject exactly.

    If this fails nothing downstream is trustworthy, because every generated subject is
    built by closing these relations.
    """
    from simglucose.patient.t1dpatient import PATIENT_PARA_FILE
    worst = derive.verify(pd.read_csv(PATIENT_PARA_FILE))
    return {"check": "steady-state closure reproduces published subjects",
            "level": 1, "value": worst, "target": "< 1e-9",
            "pass": bool(worst < 1e-9),
            "note": "worst relative residual across all 30 published subjects"}


def check_quiet_subject_holds(name, days=2):
    """A subject on its own basal, with no meals, must hold its fasting glucose.

    A steady state that is not steady means the parameters and the initial state
    disagree, which would put a slow trend under every result.

    Measured on the underlying blood glucose against the subject's own fasting parameter,
    as the largest excursion across the whole run.

    Two earlier versions of this check were wrong and each was wrong instructively.
    Comparing the first reading with the last aliases an oscillation, and passed at two
    and four days while failing at one. Measuring the excursion on the sensor reading
    instead measures the sensor: the Dexcom model's noise is strongly autocorrelated, so
    it wanders about 40 mg/dL either side over two days while the blood glucose underneath
    does not move at all. That is also why the simulator can look quiet on the
    high-frequency jitter statistic and still produce a visibly noisy trace.

    Pump quantisation is switched off here. It is a real effect and it really does move
    the steady state, which `check_pump_quantisation_costs_what_it_should` measures. What
    this check is for is whether the parameters and the initial state agree, and that is a
    property of the physiology rather than of the device.
    """
    r = simulate(name, days=days, seed=0, layers=(), meals=[],
                 controller="basal-bolus", limits=_unquantised_limits(name))
    fasting = float(params_for(name)["Gb"])
    excursion = float(np.max(np.abs(r.bg - fasting)))
    return {"check": f"{name} holds its fasting glucose with no meals",
            "level": 1, "value": excursion, "target": "< 5 mg/dL excursion in blood glucose",
            "pass": bool(excursion < 5.0),
            "note": f"fasting parameter {fasting:.0f} mg/dL, largest excursion "
                    f"{excursion:.2f} over {days} days"}


def _unquantised_limits(name):
    """The subject's own ceilings with the delivery increments removed."""
    base = therapy.for_subject(name).limits
    return therapy.PumpLimits(base.max_basal_u_per_hour, base.max_bolus_u,
                              base.max_iob_u, basal_increment_u_per_hour=0.0,
                              bolus_increment_u=0.0)


def check_pump_quantisation_costs_what_it_should(name, days=2):
    """A pump that cannot deliver the exact basal rate leaves the subject slightly off.

    Worth measuring rather than assuming. A basal rate rounded to the nearest 0.05 U/h is
    out by up to 2% on a typical adult, and on a subject whose steady state was closed at
    the exact rate that shows up as a small standing offset in glucose. It is bounded and
    it is real, and a version of this that rounded down instead of to the nearest
    increment produced three times the offset in the same direction on every subject.
    """
    fasting = float(params_for(name)["Gb"])
    exact = simulate(name, days=days, seed=0, layers=(), meals=[],
                     controller="basal-bolus",
                     limits=_unquantised_limits(name))
    real = simulate(name, days=days, seed=0, layers=(), meals=[],
                    controller="basal-bolus")
    offset = float(np.max(np.abs(real.bg - fasting)) - np.max(np.abs(exact.bg - fasting)))
    return {"check": f"{name}: pump quantisation moves the steady state by a bounded amount",
            "level": 1, "value": offset, "target": "< 15 mg/dL",
            "pass": bool(abs(offset) < 15.0),
            "note": f"delivering to the nearest 0.05 U/h costs {offset:.2f} mg/dL against "
                    f"a fasting glucose of {fasting:.0f}"}


class _DeafController:
    """Holds a fixed basal and never looks at the sensor. Used to isolate the sensor."""

    def __init__(self, basal_u_per_min):
        self.basal = float(basal_u_per_min)

    def policy(self, observation, reward, done, **info):
        from simglucose.controller.base import Action
        return Action(basal=self.basal, bolus=0.0)


def check_the_sensor_layer_is_a_reading_and_not_a_glucose(name, days=3):
    """The sensor layer must change what is seen and not what is true.

    An earlier version of this check compared the underlying glucose with the sensor layer
    on and off while the loop was running, and passed trivially, because the layer was
    applied to the finished trace after the run had ended. Nothing could have failed it.

    The sensor layer now sits inside the loop, so an algorithm that reads glucose will
    dose differently and the body will genuinely differ. That is the intended behaviour
    and it means the isolation has to be tested against a controller that ignores the
    sensor. For that controller, and only for that one, the two runs must agree exactly on
    blood glucose while disagreeing on the reading.
    """
    prof = therapy.for_subject(name)
    quiet = simulate(name, days=days, seed=3, layers=(),
                     controller=_DeafController(prof.basal_at(0)))
    noisy = simulate(name, days=days, seed=3, layers=("sensor",),
                     controller=_DeafController(prof.basal_at(0)))
    n = min(len(quiet.bg), len(noisy.bg))
    body_same = bool(np.array_equal(quiet.bg[:n], noisy.bg[:n]))
    reading_moved = float(np.max(np.abs(quiet.cgm[:n] - noisy.cgm[:n])))
    ok = body_same and reading_moved > 1.0
    return {"check": "the sensor layer changes the reading and not the body",
            "level": 1, "value": reading_moved,
            "target": "blood glucose identical, reading moved",
            "pass": bool(ok),
            "note": f"underlying BG {'identical' if body_same else 'DIFFERS'}; the "
                    f"reading moved by up to {reading_moved:.1f} mg/dL"}


def check_the_algorithm_sees_the_sensor_artefacts(name, days=21):
    """What the controller was handed must carry the artefacts, not just the output.

    The failure this exists to catch is a sensor layer applied to the finished trace: the
    statistics look right, the compression lows are in the file, and no algorithm was ever
    exposed to one. Here the recorded trace is the reading the controller acted on, so a
    compression event in the record is an event the controller saw.
    """
    r = simulate(name, days=days, seed=5, layers=("physiology", "behaviour", "sensor"),
                 controller="basal-bolus")
    quiet = simulate(name, days=days, seed=5, layers=("physiology", "behaviour"),
                     controller="basal-bolus")
    jitter = float(np.std(np.diff(np.diff(r.cgm))) - np.std(np.diff(np.diff(quiet.cgm))))
    return {"check": "the algorithm is handed the sensor artefacts",
            "level": 1, "value": float(r.compression_events),
            "target": "compression events placed, and jitter added",
            "pass": bool(r.compression_events > 0 and jitter > 1.0),
            "note": f"{r.compression_events} compression events over {days} days, and "
                    f"{jitter:.1f} mg/dL of added second-difference jitter"}


def check_delivery_limits_bind(name, days=2):
    """An algorithm that asks for far too much insulin must be stopped by the limits.

    simglucose's own pump would accept 150 units in one step. The limits in
    `therapy/limits.py` sit in front of it, and a bench whose ceilings do not bind is
    testing an algorithm with its safeties removed.

    Binding is necessary and not sufficient, which this check used to miss. The verdict was
    that each of the three counters had fired at least once, so a run whose insulin on board
    ended above the ceiling passed as long as the clamp had fired on the way. The stored
    result from 8 August 2026 says exactly that: it reports a peak of 10.8 U against a
    declared 8.6 and records a pass. Those are the same two numbers the comment in
    `therapy/limits.py` uses to describe the defect it was written to repair, and the check
    has not been run since that repair landed on 17 August. The ceiling holding is asserted
    now as well as the clamp firing, so the question cannot be left open again.
    """
    from simglucose.controller.base import Action

    class Greedy:
        def policy(self, observation, reward, done, **info):
            return Action(basal=1.0, bolus=20.0 / info.get("sample_time", 5.0))

    r = simulate(name, days=days, seed=0, layers=(), controller=Greedy())
    bound = r.meta["limit_bound"]
    hit = sum(bound.values())
    peak, ceiling = r.meta["peak_iob_u"], r.meta["max_iob_u"]
    # A tolerance of one bolus increment, since the peak is recorded before rounding down.
    held = peak <= ceiling + 0.05
    return {"check": "delivery limits bind on an algorithm that asks for too much",
            "level": 1, "value": float(hit),
            "target": "the three ceilings all bind, and insulin on board stays under its own",
            "pass": bool(bound["basal"] > 0 and bound["bolus"] > 0 and bound["iob"] > 0
                         and held),
            "note": f"clamped {bound['basal']} times on basal, {bound['bolus']} on bolus "
                    f"and {bound['iob']} on insulin on board; peak insulin on board "
                    f"{peak:.1f} U against a ceiling of {ceiling:.1f}"
                    f"{'' if held else ', which it exceeds'}"}


# ---------------------------------------------------------------------- level 2


def _settle(name, minutes=600, params=None):
    """Run a subject on basal alone until it settles, and return it."""
    from simglucose.patient.t1dpatient import Action, T1DPatient
    p = pd.Series(params if params is not None else params_for(name))
    patient = T1DPatient(p)
    basal = derive.basal_rate(p)
    for _ in range(minutes):
        patient.step(Action(insulin=basal, CHO=0.0))
    return patient, basal


def check_correction_moves_glucose_by_its_correction_factor(name):
    """A unit of insulin should drop glucose by roughly the subject's correction factor.

    On a generated subject this is a consistency check, because the setting was measured
    from the model in the first place. It still earns its place: it catches a subject
    whose settings were measured under one steady state and are being applied under
    another. The independent version is `check_published_cohort_obeys_clinical_rules`.
    """
    from simglucose.patient.t1dpatient import Action

    cf = float(therapy_for(name)["CF"])
    drops = []
    for units in (1.0, 2.0):
        patient, basal = _settle(name)
        start = patient.observation.Gsub
        patient.step(Action(insulin=basal + units, CHO=0.0))
        low = start
        for _ in range(300):
            patient.step(Action(insulin=basal, CHO=0.0))
            low = min(low, patient.observation.Gsub)
        drops.append((start - low) / units)
    observed = float(np.mean(drops))
    ratio = observed / cf
    return {"check": f"{name}: 1 U drops glucose by about its correction factor",
            "level": 2, "value": ratio, "target": "0.5 to 2.0 x CF",
            "pass": bool(0.5 <= ratio <= 2.0),
            "note": f"observed {observed:.0f} mg/dL per U against a set CF of {cf:.0f}"}


def check_unbolused_carbohydrate_raises_glucose(name, grams=50.0):
    """Carbohydrate with no insulin must raise glucose, by roughly grams/CR x CF.

    The same rule from the other side. A model that gets this badly wrong would make
    every unannounced meal in the behaviour layer the wrong size.
    """
    from simglucose.patient.t1dpatient import Action

    q = therapy_for(name)
    expected = grams / float(q["CR"]) * float(q["CF"])
    patient, basal = _settle(name)
    start = patient.observation.Gsub
    patient.step(Action(insulin=basal, CHO=grams))
    peak = start
    for _ in range(300):
        patient.step(Action(insulin=basal, CHO=0.0))
        peak = max(peak, patient.observation.Gsub)
    rise = peak - start
    ratio = rise / expected
    return {"check": f"{name}: {grams:.0f} g unbolused raises glucose by about grams/CR x CF",
            "level": 2, "value": ratio, "target": "0.5 to 2.0 x expected",
            "pass": bool(0.5 <= ratio <= 2.0),
            "note": f"rose {rise:.0f} mg/dL against an expected {expected:.0f}"}


def _peak_minutes(params, cr, grams, bolus=True):
    from simglucose.patient.t1dpatient import Action

    patient, basal = _settle(None, params=params)
    patient.step(Action(insulin=basal + (grams / cr if bolus else 0.0), CHO=grams))
    trace = []
    for _ in range(300):
        patient.step(Action(insulin=basal, CHO=0.0))
        trace.append(patient.observation.Gsub)
    return int(np.argmax(trace)) + 1


def check_meal_peaks_at_a_plausible_time(name, grams=60.0):
    """A bolused meal should peak roughly an hour to two hours later.

    The meal has to be bolused for this to mean anything. An unbolused meal in this model
    peaks at around four hours, but that is the absence of insulin rather than the speed
    of absorption, so it says nothing about the timing a loop reacts to. The published
    adults bolused peak at a median of 75 minutes, which is where the target comes from.
    """
    cr = float(therapy_for(name)["CR"])
    peak = _peak_minutes(params_for(name), cr, grams, bolus=True)
    return {"check": f"{name}: a bolused meal peaks 45 to 150 minutes later",
            "level": 2, "value": float(peak), "target": "45 to 150 min",
            "pass": bool(45 <= peak <= 150),
            "note": f"peak at {peak} minutes"}


def check_published_cohort_obeys_clinical_rules():
    """The model itself must agree with the rules real settings are built on.

    This is the independent version of the two rule checks. The generated subjects have
    their settings measured from the model, so on them those checks are consistency tests
    rather than tests of the model. The published subjects' settings were not derived that
    way, so if the model agrees with them the agreement means something.

    Measured across the ten published adults: one unit moves glucose by 1.10 times the
    stated correction factor, a 50 g unbolused meal raises it by 1.19 times grams over
    ratio times factor, and a bolused meal peaks at 75 minutes. The model and the clinical
    rules describe the same person.
    """
    import pandas as pd
    from simglucose.controller.basal_bolus_ctrller import CONTROL_QUEST
    from simglucose.patient.t1dpatient import Action, PATIENT_PARA_FILE

    published = pd.read_csv(PATIENT_PARA_FILE)
    quest = pd.read_csv(CONTROL_QUEST)
    cf_ratios, cr_ratios, peaks = [], [], []
    for name in [f"adult#{i:03d}" for i in range(1, 11)]:
        p = published.loc[published.Name == name].squeeze()
        q = quest.loc[quest.Name == name].squeeze()
        cf, cr = float(q.CF), float(q.CR)

        patient, basal = _settle(None, params=p)
        start = patient.observation.Gsub
        patient.step(Action(insulin=basal + 1.0, CHO=0.0))
        nadir = start
        for _ in range(300):
            patient.step(Action(insulin=basal, CHO=0.0))
            nadir = min(nadir, patient.observation.Gsub)
        cf_ratios.append((start - nadir) / cf)

        patient, basal = _settle(None, params=p)
        start = patient.observation.Gsub
        patient.step(Action(insulin=basal, CHO=50.0))
        peak = start
        for _ in range(300):
            patient.step(Action(insulin=basal, CHO=0.0))
            peak = max(peak, patient.observation.Gsub)
        cr_ratios.append((peak - start) / (50.0 / cr * cf))

        peaks.append(_peak_minutes(p, cr, 60.0, bolus=True))

    cf_m, cr_m, pk_m = np.median(cf_ratios), np.median(cr_ratios), np.median(peaks)
    ok = bool(0.7 <= cf_m <= 1.5 and 0.7 <= cr_m <= 1.5 and 45 <= pk_m <= 150)
    return {"check": "the published cohort obeys the clinical dosing rules",
            "level": 2, "value": float(cf_m),
            "target": "correction and carbohydrate rules within 0.7-1.5, peak 45-150 min",
            "pass": ok,
            "note": f"correction {cf_m:.2f}x, carbohydrate {cr_m:.2f}x, "
                    f"bolused peak {pk_m:.0f} min, across 10 published adults"}


def _insulin_ladder(name, days, layers, scales=(0.7, 0.85, 1.0, 1.15, 1.3)):
    """Run one subject at several insulin doses, holding everything else fixed.

    Open-loop, because a correction loop is something intervening and the point of the
    ladder is the body's own response to a dose.
    """
    base = pd.Series(params_for(name))
    out = []
    for scale in scales:
        p = base.copy()
        p["u2ss"] = float(base["u2ss"]) * scale
        q = dict(therapy_for(name))
        q["CR"] = float(q["CR"]) / scale
        out.append(simulate(name, days=days, seed=0, layers=layers, params=p,
                            settings=q, controller="basal-bolus"))
    return out


def check_glucose_is_monotone_in_insulin(name, days=7):
    """More insulin must lower glucose, at every step, with nobody intervening.

    A simulator that is not monotone in its single most important input cannot rank two
    controllers, whatever its distributional fidelity looks like.

    This has to be run with the behaviour layer off. With it on the relationship is
    genuinely not monotone, and that is the model being right rather than wrong: see
    `check_more_insulin_is_defended_with_carbohydrate`.
    """
    means = [float(r.cgm.mean()) for r in _insulin_ladder(name, days, ())]
    falling = all(b < a for a, b in zip(means, means[1:]))
    return {"check": f"{name}: mean glucose falls monotonically as insulin rises",
            "level": 2, "value": float(means[0] - means[-1]),
            "target": "strictly decreasing", "pass": bool(falling),
            "note": "means at 0.7/0.85/1.0/1.15/1.3 x insulin: "
                    + ", ".join(f"{m:.0f}" for m in means)}


def check_more_insulin_is_defended_with_carbohydrate(name, days=7):
    """With a person in the loop, extra insulin should be met with extra carbohydrate.

    This is the check that a naive monotonicity test gets wrong, and it is worth having
    for its own sake. Raise the insulin on a subject who eats when they go low and mean
    glucose stops falling cleanly, because the person defends against the lows. The
    defence is the thing to test: rescue carbohydrate must rise with the dose.

    It also names a trap for anyone comparing controllers here. A controller that doses
    more aggressively will not necessarily show a lower mean glucose, because the
    simulated person will eat the difference, and it will show up in carbohydrate and in
    time below range instead. Judging such a comparison on mean glucose alone would find
    no effect where there is a large one.
    """
    runs = _insulin_ladder(name, days, ("behaviour",))
    grams = [r.rescue_grams for r in runs]
    rising = grams[-1] > grams[0] and grams[-1] > grams[len(grams) // 2]
    means = [float(r.cgm.mean()) for r in runs]
    monotone = all(b < a for a, b in zip(means, means[1:]))
    return {"check": f"{name}: extra insulin is met with extra rescue carbohydrate",
            "level": 2, "value": float(grams[-1] - grams[0]),
            "target": "rescue carbohydrate rises with the dose", "pass": bool(rising),
            "note": "rescue grams at 0.7/0.85/1.0/1.15/1.3 x insulin: "
                    + ", ".join(f"{g:.0f}" for g in grams)
                    + f"; mean glucose is {'still' if monotone else 'no longer'} monotone, "
                      "which is the person defending rather than a modelling error"}


# ---------------------------------------------------------------------- level 3


def check_signatures_against_real_data(results, minimum=5):
    """How many of the eleven statistics land inside the real range.

    Necessary and not sufficient. A simulator can match every marginal statistic and
    still respond wrongly to an intervention, which is what levels 4 and 5 are for.
    """
    stats = S.evaluate(results)
    inside = [k for k in S.REAL_RANGE if S.in_real_range(k, stats[k][0])]
    return {"check": "statistics inside the real four-cohort range",
            "level": 3, "value": float(len(inside)),
            "target": f">= {minimum} of {len(S.REAL_RANGE)}",
            "pass": bool(len(inside) >= minimum),
            "note": "in range: " + ", ".join(inside)}


# ---------------------------------------------------------------------- level 4


def check_closing_the_loop_improves_time_in_range(open_results, loop_results):
    """A loop should improve time in range over open-loop therapy, by a known amount.

    Published hybrid closed-loop trials against pump therapy report improvements in the
    region of 10 percentage points. A simulator that shows no improvement, or an
    implausibly large one, is not reproducing the one intervention whose effect is best
    established, and should not be trusted to rank two loops against each other.
    """
    # Not strict: the two arms are different interventions and lose different subjects, so the
    # comparison goes on the subjects completing both and says how many that was.
    pairs = _aligned(open_results, loop_results, strict=False)
    paired = [b.time_in_range - a.time_in_range for a, b in pairs]
    delta = float(np.median(paired))
    lo, hi = S.boot_ci(paired, seed=0)[1:]
    dropped = max(len(open_results), len(loop_results)) - len(paired)
    return {"check": "closing the loop improves time in range",
            "level": 4, "value": delta, "target": "+2 to +25 percentage points",
            "pass": bool(2.0 <= delta <= 25.0),
            "note": f"paired median {delta:+.1f} pp [{lo:+.1f} to {hi:+.1f}], "
                    f"n = {len(paired)} subjects completing both arms"
                    + (f", {dropped} completing only one" if dropped else "")}


# ---------------------------------------------------------------------- level 5


def _aligned(arm_a, arm_b, strict=True):
    """Pairs of results for the same subject, rather than for the same list position.

    Zipping two arms pairs them by position, which is right only while both lists hold the
    same subjects in the same order. Nothing guaranteed that, and a paired difference taken
    across different people is the failure `analysis/cohort.py::paired_subjects` exists to
    refuse. These are the checks whose job is catching that kind of error, so they should not
    contain it.

    `strict` distinguishes two situations. An A/A test runs one controller twice, so the arms
    must hold the same subjects and anything else is a bug worth raising on. A loop against
    open-loop comparison legitimately loses different subjects in each arm, so there the
    intersection is taken and the caller reports how many subjects it was left with.
    """
    a = {r.name: r for r in arm_a}
    b = {r.name: r for r in arm_b}
    common = sorted(set(a) & set(b))
    if not common:
        raise ValueError("the two arms share no subject, so no paired difference exists")
    if strict and len(common) < max(len(a), len(b)):
        differ = sorted(set(a) ^ set(b))[:4]
        raise ValueError(
            f"the arms do not hold the same subjects: {len(common)} in common against "
            f"{len(a)} and {len(b)}, e.g. {differ}. Summarising each arm over its own "
            f"survivors compares different people and the bias always runs favourable.")
    return [(a[n], b[n]) for n in common]


def check_null_contrast_is_null(arm_a, arm_b):
    """The same controller run twice must show no difference.

    An A/A test. It calibrates the noise floor: whatever difference this produces is the
    smallest difference any A/B on the same design can be believed at. Skipping it is
    how a simulator ends up reporting a two-point improvement that is indistinguishable
    from running the same thing twice.
    """
    paired = [b.time_in_range - a.time_in_range for a, b in _aligned(arm_a, arm_b)]
    delta = float(np.median(paired))
    lo, hi = S.boot_ci(paired, seed=1)[1:]
    spans_zero = bool(lo <= 0.0 <= hi)
    return {"check": "the same controller twice shows no difference",
            "level": 5, "value": delta, "target": "interval spans zero",
            "pass": spans_zero,
            "note": f"paired median {delta:+.2f} pp [{lo:+.2f} to {hi:+.2f}], "
                    f"n = {len(paired)}"}


def minimum_detectable_difference(arm_a, arm_b, n_subjects=None, power=0.8, alpha=0.05):
    """The smallest difference in time in range this design could resolve.

    Computed from the paired spread measured in the A/A test, so it is an empirical
    figure rather than an assumption. Read it before believing any A/B result: a
    difference smaller than this is not evidence of anything.
    """
    from scipy import stats as sps

    paired = np.array([b.time_in_range - a.time_in_range
                       for a, b in _aligned(arm_a, arm_b)], float)
    sd = float(paired.std(ddof=1))
    n = int(n_subjects or len(paired))
    z_a = sps.norm.ppf(1 - alpha / 2)
    z_b = sps.norm.ppf(power)
    mdd = (z_a + z_b) * sd / np.sqrt(n)
    return {"check": f"minimum detectable difference at n = {n}",
            "level": 5, "value": float(mdd),
            "target": "reported, not passed or failed", "pass": None,
            "note": f"paired SD {sd:.2f} pp; at 80% power and alpha 0.05 this design "
                    f"resolves {mdd:.2f} percentage points of time in range"}


# ---------------------------------------------------------------------- level 6


def check_population_is_stable_across_seeds(n=24, seeds=(2026, 7)):
    """Two independent draws of the population must describe the same kind of people.

    The subjects are sampled, so any result carries the draw. If two seeds produce
    materially different populations then a conclusion is a property of the seed.
    """
    from ..population.generate import generate

    summaries = []
    for seed in seeds:
        patients, therapy, _ = generate(n=n, seed=seed, verbose=False)
        summaries.append({
            "bw": float(patients.BW.median()),
            "basal": float((patients.u2ss * patients.BW / 6000).median()),
            "gb": float(patients.Gb.median()),
            "cr": float(therapy.CR.median()),
        })
    worst, where = 0.0, ""
    for key in summaries[0]:
        a, b = summaries[0][key], summaries[1][key]
        rel = abs(a - b) / max(abs(a), 1e-9)
        if rel > worst:
            worst, where = rel, key
    return {"check": "two population draws describe the same kind of people",
            "level": 6, "value": worst, "target": "< 0.25 relative difference",
            "pass": bool(worst < 0.25),
            "note": f"largest gap in {where}: {summaries[0][where]:.3f} against "
                    f"{summaries[1][where]:.3f}"}


def check_conclusion_survives_behaviour_parameters(name, days=14):
    """A conclusion must not depend on an unfitted behaviour parameter's exact value.

    The announcement rate and the over-treatment probability were chosen from the
    literature, not fitted. Halving and doubling the announcement failure rate should
    move the numbers and not flip the sign of anything.
    """
    from .. import person

    original = person.behaviour.P_ANNOUNCE_MAIN
    means = []
    try:
        for rate in (0.65, 0.80, 0.95):
            person.behaviour.P_ANNOUNCE_MAIN = rate
            r = simulate(name, days=days, seed=0)
            means.append(float(r.cgm.mean()))
    finally:
        person.behaviour.P_ANNOUNCE_MAIN = original
    rising = means[0] >= means[1] >= means[2]
    spread = max(means) - min(means)
    return {"check": f"{name}: announcing more meals lowers mean glucose",
            "level": 6, "value": spread, "target": "ordered, and a bounded spread",
            "pass": bool(rising and spread < 60.0),
            "note": "means at 65/80/95% announcement: "
                    + ", ".join(f"{m:.0f}" for m in means)}


__all__ = [n for n in dir() if n.startswith(("check_", "minimum_"))]
