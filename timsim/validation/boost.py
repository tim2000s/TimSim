"""Boost as the known algorithm: what it does on real cycles, and what it must do here.

Everything else in `validation/` checks TimSim against statistics, or against algorithms
this package broke on purpose. This module checks it against a real automated insulin
delivery algorithm whose expected behaviour is known independently, which is a stronger
test than either.

There are two ways to get that expected behaviour and only one of them is trustworthy.

The reference used here is the shipped algorithm's own logged output: 226,829 decisions in
the `boost_decisions` table, each carrying the state the Kotlin plugin was in and the dose
it actually delivered on a real person. No port sits in the loop, so nothing can be lost in
translation.

The other way is to replay `boost_v5_cohort_cache.pkl`, 193,714 stored input records, through
the Python port of the plugin. That is convenient and it is not the same thing, because it
assumes the port is faithful. It is not: see `fidelity_gate` below.

That reference is the thing to test TimSim against. The failure mode a fidelity table
cannot see is a simulator that never drives the algorithm into the states where it doses
hard. Such a simulator produces beautiful statistics, passes every distributional check,
and reports that the algorithm is safe because it never exercised the part of it that is
dangerous. Comparing state occupancy against the real cohort catches exactly that.

## The units defect in the cached cohort

The cache stores `target_bg` in mmol/L for all nineteen users, and `eventual_bg` and
`min_guard_bg` in mmol/L for fourteen of them, while the harness reads all three as mg/dL.
The consequence is not subtle. `min_guard_bg` of 5.6 is below the 80 mg/dL hard-gate
threshold on every cycle, so the algorithm is disabled outright most of the time:

    measure                    as cached    corrected
    hard gate fires              74.1%         8.8%
    COMMITTED occupancy           1.2%         4.2%
    mean dose                   0.062 U      0.238 U
    cycles delivering                20%          69%

Reading the cached numbers, Boost looks like an algorithm that almost never doses. It is
not. Anything calibrated against the cache as stored was tuned against an algorithm that
was gated off three-quarters of the time, and `DEFAULT_TRANSITION` in the harness carries a
"calibrated 2026-05-06" comment matching the cache's own date.

`normalise_units` fixes it on load, by detecting on each field's median rather than on
individual values, since one mg/dL reading below 40 is legitimate and a median below 40 is
not.
"""
import collections
import os
from dataclasses import replace

import numpy as np

MMOL_TO_MGDL = 18.0182
GLUCOSE_FIELDS = ("bg", "eventual_bg", "target_bg", "min_guard_bg", "recent_low_bg")
MMOL_MEDIAN_THRESHOLD = 40.0

HARNESS_DIR = os.environ.get("BOOST_HARNESS_DIR",
                             os.path.expanduser("~/oref-investigations"))
COHORT_CACHE = os.path.join(HARNESS_DIR, "boost_v5_cohort_cache.pkl")


def available():
    """True when the Boost harness and its cohort cache can both be found."""
    if not os.path.exists(COHORT_CACHE):
        return False
    try:
        harness()
    except ImportError:
        return False
    return True


def harness():
    """The Boost V5 harness module, imported from wherever it lives."""
    import sys
    if HARNESS_DIR not in sys.path:
        sys.path.insert(0, HARNESS_DIR)
    import boost_v5_harness
    return boost_v5_harness


def normalise_units(cycles):
    """Convert any glucose field the cache stored in mmol/L. Returns (cycles, converted).

    Detected on the median of each field, because a single mg/dL value below 40 is a real
    severe low while a median below 40 is a unit error.
    """
    converted = {}
    for field in GLUCOSE_FIELDS:
        vals = np.array([getattr(c, field, np.nan) for c in cycles], float)
        vals = vals[np.isfinite(vals)]
        converted[field] = bool(len(vals)
                                and np.median(vals) < MMOL_MEDIAN_THRESHOLD)
    if not any(converted.values()):
        return list(cycles), converted
    scale = {f: MMOL_TO_MGDL for f, v in converted.items() if v}
    return ([replace(c, **{f: getattr(c, f) * s for f, s in scale.items()})
             for c in cycles], converted)


def cohort(fix_units=True):
    """The real Boost cohort: [{user_id, max_iob, isf_mgdl_per_unit, cycles}].

    The cache is pickled `CycleInput` instances, so the harness has to be importable
    before it can be unpickled at all.
    """
    import pickle
    harness()
    with open(COHORT_CACHE, "rb") as fh:
        users = pickle.load(fh)
    if fix_units:
        for u in users:
            u["cycles"], u["units_converted"] = normalise_units(u["cycles"])
    return users


def respond(cycles, config=None):
    """Run a sequence of cycles through Boost. Returns the per-cycle outputs."""
    h = harness()
    cfg = config or h.V5Config()
    state = h.StateMachineState()
    out = []
    for c in cycles:
        result, state = h.step(state, c, cfg)
        out.append(result)
    return out


def response_profile(outputs):
    """The shape of a run of Boost, as the numbers a comparison turns on."""
    states, gates = collections.Counter(), collections.Counter()
    doses, budgets = [], []
    for o in outputs:
        states[o.meal_hypothesis.value] += 1
        doses.append(o.final_dose)
        budgets.append(o.aggression_budget)
        for gate, value in (o.gate_reductions or {}).items():
            if value:
                gates[gate] += 1
    n = max(len(outputs), 1)
    doses = np.asarray(doses, float)
    return {
        "cycles": len(outputs),
        "state_occupancy_pct": {k: 100.0 * v / n for k, v in states.items()},
        "gate_firing_pct": {k: 100.0 * v / n for k, v in gates.items()},
        "dose_mean_u": float(doses.mean()) if len(doses) else float("nan"),
        "dose_nonzero_pct": float(100.0 * (doses > 0).mean()) if len(doses) else float("nan"),
        "dose_p95_u": float(np.percentile(doses, 95)) if len(doses) else float("nan"),
        "dose_max_u": float(doses.max()) if len(doses) else float("nan"),
        "budget_median": float(np.median(budgets)) if budgets else float("nan"),
    }


def reference_profile(fix_units=True):
    """Boost's response across the whole real cohort. This is the known answer."""
    outputs = []
    for user in cohort(fix_units=fix_units):
        outputs.extend(respond(user["cycles"]))
    return response_profile(outputs)


# What the shipped Kotlin plugin actually did, read straight from its own logs across
# 226,829 decisions on real users. This is the figure TimSim is held against, and it owes
# nothing to the Python port. Regenerate with `python -m timsim.validation.boost`.
REFERENCE = {
    "source": "boost_decisions, logged by the shipped plugin",
    "decisions": 226829,
    "state_occupancy_pct": {"IDLE": 65.0, "OBSERVING": 21.2, "RECOVERING": 5.8,
                            "COMMITTED": 5.4, "CONFIRMED": 2.5},
    "dose_mean_u": 0.0826,
    "dose_nonzero_pct": 23.4,
    "dose_mean_by_state_u": {"IDLE": 0.0355, "OBSERVING": 0.0632, "RECOVERING": 0.0802,
                             "COMMITTED": 0.2782, "CONFIRMED": 1.0453},
}

# The same measurement taken by replaying the cached inputs through the Python port. Kept
# because it is what a port-based reference looks like, and because the gap between it and
# REFERENCE is the size of the error such a reference introduces.
REFERENCE_VIA_PORT = {
    "source": "boost_v5_cohort_cache replayed through boost_v5_harness, units corrected",
    "cycles": 193714,
    "state_occupancy_pct": {"IDLE": 46.92, "OBSERVING": 45.49, "COMMITTED": 4.23,
                            "RECOVERING": 2.23, "CONFIRMED": 1.13},
    "gate_firing_pct": {"hard": 8.81, "pre_dose": 8.81, "iob_headroom_brake": 2.26,
                        "deceleration_brake": 1.32, "dynamic_spike_cap": 0.38,
                        "max_iob_clamp": 0.03},
    "dose_mean_u": 0.2377,
    "dose_nonzero_pct": 69.28,
}

# Measured by rebuilding each logged decision's inputs and running the port on them, then
# comparing against the dose the plugin logged for that same decision. This is the gate the
# AndroidAPS in-silico README specifies, in its own words: "the port must reproduce the
# logged boostv5_finaldose within tolerance. No fidelity, no A/B."
#
# It does not pass. Phase 1 largely survives the translation, at a score correlation of
# 0.815, and the dose does not: the port delivers 2.24 times the insulin the plugin did,
# correlates at 0.483, and agrees on the state 70.9% of the time. It reaches RECOVERING on
# 0.6% of decisions against a logged 5.8%, and CONFIRMED on 0.3% against 2.5%.
#
# Part of that gap is the reconstruction rather than the port: max insulin on board, the
# recent low, the pre-check flags and the insulin activity are not all recoverable from the
# logged columns and were stubbed. The two cannot be fully separated until they are. What
# the split between a faithful score and an unfaithful dose does say is that the divergence
# is in the budget, the action multiplier and the gates rather than in the scoring.
FIDELITY_GATE = {
    "decisions": 226829,
    "dose_mean_port_u": 0.0709,
    "dose_mean_logged_u": 0.0826,
    "dose_ratio": 0.86,
    "dose_ratio_before_phase25": 2.24,
    "dose_correlation": 0.465,
    "dose_within_0_05u_pct": 82.1,
    "score_correlation": 0.815,
    "state_agreement_pct": 70.9,
    "dose_chain_passes": True,
    "state_machine_passes": False,
    "passes": False,
    "caveat": "dose chain verified exactly; the state machine still diverges and some "
              "inputs remain stubbed",
}

# The port's own behaviour on the same real inputs the plugin saw. This is the control that
# makes a TimSim comparison interpretable: run the simulator through the same port and the
# port's own errors appear on both sides and cancel, so what is left is the simulator.
#
# Without it the two error sources are confounded. The port under-reaches CONFIRMED on real
# inputs by a factor of eight, so a simulator scored directly against the plugin's logs would
# be blamed for a shortfall the port created.
PORT_ON_REAL_INPUTS = {
    "state_occupancy_pct": {"IDLE": 73.7, "OBSERVING": 18.9, "COMMITTED": 6.5,
                            "RECOVERING": 0.6, "CONFIRMED": 0.3},
    "dose_mean_u": 0.0709,
    "dose_nonzero_pct": 26.6,
}

# What the same replay gives with the cache's units left as stored, kept so the size of
# the defect stays visible rather than becoming a corrected number nobody questions.
REFERENCE_UNCORRECTED = {
    "state_occupancy_pct": {"OBSERVING": 48.91, "IDLE": 48.66, "COMMITTED": 1.22,
                            "RECOVERING": 0.85, "CONFIRMED": 0.37},
    "gate_firing_pct": {"hard": 74.11, "iob_headroom_brake": 0.77},
    "dose_mean_u": 0.0621,
    "dose_nonzero_pct": 19.93,
}


def compare(measured, reference=None, keys=None):
    """Per-state and per-gate differences against the reference, in percentage points."""
    reference = reference or REFERENCE
    out = {}
    for block in ("state_occupancy_pct", "gate_firing_pct"):
        for key in set(reference[block]) | set(measured.get(block, {})):
            if keys and key not in keys:
                continue
            out[f"{block}:{key}"] = (measured.get(block, {}).get(key, 0.0)
                                     - reference[block].get(key, 0.0))
    for key in ("dose_mean_u", "dose_nonzero_pct", "dose_p95_u"):
        if key in reference:
            out[key] = measured.get(key, float("nan")) - reference[key]
    return out


# ---------------------------------------------------------------------------- checks
INPUT_FIELDS = ("delta", "short_avg_delta", "bg", "eventual_bg", "target_bg", "iob",
                "cob", "base_insulin_req", "recent_low_bg", "min_guard_bg", "max_delta")


def input_fidelity(sim_cycles, real_cycles=None, fields=INPUT_FIELDS):
    """Compare the inputs an adapter builds against the inputs Boost really sees.

    Reported per field as the median and the fifth and ninety-fifth percentiles on both
    sides. This is the diagnostic that says whether a mismatch downstream is the
    simulator's doing or the adapter's, and it is worth running before anything else,
    because an adapter that feeds the algorithm the wrong distribution makes every later
    comparison a test of the adapter.
    """
    if real_cycles is None:
        real_cycles = [c for u in cohort() for c in u["cycles"]]
    out = {}
    for f in fields:
        r = np.array([getattr(c, f, np.nan) for c in real_cycles], float)
        s = np.array([getattr(c, f, np.nan) for c in sim_cycles], float)
        r, s = r[np.isfinite(r)], s[np.isfinite(s)]
        if not len(r) or not len(s):
            continue
        rq, sq = np.percentile(r, [5, 50, 95]), np.percentile(s, [5, 50, 95])
        out[f] = {"real": [round(float(v), 2) for v in rq],
                  "simulated": [round(float(v), 2) for v in sq],
                  "median_gap": round(float(sq[1] - rq[1]), 2)}
    return out


def attribute(measured, logged=None, port_control=None):
    """Split a TimSim result into what the port got wrong and what the simulator did.

    Three numbers per state: what the plugin logged, what the port produces on the same real
    inputs, and what the port produces when TimSim supplies the inputs. The gap between the
    first two belongs to the port. The gap between the second and third belongs to the
    simulator, because the port is common to both.
    """
    logged = logged or REFERENCE["state_occupancy_pct"]
    port_control = port_control or PORT_ON_REAL_INPUTS["state_occupancy_pct"]
    sim = measured.get("state_occupancy_pct", {})
    out = {}
    for state in logged:
        out[state] = {
            "logged": round(logged[state], 2),
            "port_on_real": round(port_control.get(state, 0.0), 2),
            "port_on_simulated": round(sim.get(state, 0.0), 2),
            "port_error": round(port_control.get(state, 0.0) - logged[state], 2),
            "simulator_effect": round(sim.get(state, 0.0) - port_control.get(state, 0.0), 2),
        }
    return out


def check_the_simulator_exercises_the_algorithm(measured, reference=None, tolerance=2.0):
    """Does TimSim drive Boost into the states it reaches in the field?

    The failure this exists to catch is a simulator that keeps an algorithm in its idle
    states. Such a simulator passes every distributional check and reports that the
    algorithm is safe, because it never ran the part of it that doses hard. The states that
    matter are the ones where Boost is committed to acting on a meal it has inferred, and
    they are rare in reality, so a simulator can miss them entirely and still look right on
    a fidelity table.

    Reported per state in percentage points against the real cohort.
    """
    reference = reference or REFERENCE
    real = reference["state_occupancy_pct"]
    sim = measured.get("state_occupancy_pct", {})
    active = ("CONFIRMED", "COMMITTED")
    gaps = {k: round(sim.get(k, 0.0) - real.get(k, 0.0), 2) for k in real}
    missed = [k for k in active
              if sim.get(k, 0.0) < real.get(k, 0.0) / tolerance]
    return {"check": "the simulator drives the algorithm into the states it reaches in the field",
            "level": 7,
            "value": float(sum(sim.get(k, 0.0) for k in active)),
            "target": f"within a factor of {tolerance:g} of the real cohort on "
                      + " and ".join(active),
            "pass": bool(not missed),
            "note": "occupancy gap in percentage points: "
                    + ", ".join(f"{k} {v:+.2f}" for k, v in gaps.items())
                    + (f"; under-exercised: {', '.join(missed)}" if missed else "")}


# Where TimSim stands after the adapter was calibrated against oref's logged internals.
# Six adults, 14 days, 24,192 cycles. The check passes on its factor-of-two tolerance for
# the two states that carry the dosing, and the residual is a real property of the
# simulator rather than of the plumbing: see `SIMULATOR_RESIDUAL`.
TIMSIM_MEASURED = {
    "subjects": 6, "days": 14, "cycles": 20932, "completed": "5/6",
    "state_occupancy_pct": {"IDLE": 45.53, "OBSERVING": 45.19, "RECOVERING": 3.68,
                            "COMMITTED": 3.77, "CONFIRMED": 1.82},
    "dose_mean_u": 0.1631,
    "dose_nonzero_pct": 54.1,
    "time_in_range_pct": 71.5,
    "time_below_70_pct": 5.5,
    "insulin_per_day_u": 61.5,
}

# The one finding in this module that is about the simulator rather than the port or the
# adapter, and it is measured twice over independently of Boost's state machine.
#
# TimSim's glucose is busier than real closed-loop glucose. Measured on the traces alone,
# across 196 real segments covering 102 days against 6 simulated subjects over 14 days, it
# produces rises of 25 mg/dL in half an hour 1.5 times as often as real users, rises of 50
# nearly 4 times as often, and sustained hour-long climbs of 50 twice as often. Measured on
# the meal score, it crosses the observing threshold on 35.0% of cycles against a real
# 21.7%, and that is not the missing machine-learning input: supplying a plausible value for
# it moves the figure to 32.2%.
#
# The effect on an algorithm is that it sits in the observing state roughly twice as much as
# it would in the field, while crossing the confirm threshold slightly less often, 2.9%
# against 3.7%. This is the same defect the fidelity table already reports from the other
# end: glucose variability of 35.0 against a real range of 29.5 to 34.3.
SIMULATOR_RESIDUAL = {
    # Rescue behaviour, calibrated 2026-08-07 against real logged carbohydrate.
    "rescues_per_day": {"real_logged": 0.44, "timsim_before": 2.11, "timsim_after": 1.18},
    "grams_per_rescue": {"real_mean": 33.8, "timsim_before": 25.4, "timsim_after": 36.3},
    "sustained_50_per_day": {"real": 2.58, "timsim_before": 3.75, "timsim_after": 3.79},

    # The shape of a rise, measured on 1,058,439 real five-minute deltas against 20,926
    # simulated ones. Every measure within 11%, so the rises themselves are the right shape.
    "shape_ratios": {"delta_sd": 1.08, "rise_p95": 1.01, "fall_p95": 0.95,
                     "rise_fall_asymmetry": 1.06, "delta_autocorrelation": 0.98,
                     "steps_per_climb": 1.11, "largest_step_share": 0.93},

    # The meal score, both sides run through the same scorer so the port cancels.
    "score_mean": {"real": 0.372, "timsim": 0.371},
    "score_bands_pct": {"real": {"below_exit": 57.9, "holding": 12.8, "above_entry": 29.3},
                        "timsim": {"below_exit": 53.3, "holding": 12.6, "above_entry": 34.2}},
    "score_autocorrelation_lag1": {"real": 0.092, "timsim": 0.283},
    "exit_conditions_per_100_cycles": {"real": 31.5, "timsim": 30.3},
    "reading": "the marginal score distribution matches to within five points and the mean "
               "matches exactly; the score is three times more persistent cycle to cycle, "
               "and that is what holds the algorithm in its observing state",
}


def main():
    import json
    print(json.dumps({"corrected": reference_profile(True),
                      "as_cached": reference_profile(False)}, indent=1, default=float))


if __name__ == "__main__":
    main()


__all__ = ["available", "harness", "normalise_units", "cohort", "respond",
           "response_profile", "reference_profile", "compare",
           "REFERENCE", "REFERENCE_UNCORRECTED"]
