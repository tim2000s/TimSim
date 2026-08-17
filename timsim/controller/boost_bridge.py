"""Drive the real Boost decision code, compiled from AndroidAPS, rather than a port of it.

A port of an algorithm is a second implementation, and a second implementation drifts. The
Python port this replaces reproduces the logged dose to 0.0000 U and still agrees with the
logged state machine on 70.9% of decisions, reaching RECOVERING on 0.6% of real inputs
against a logged 5.8%. Every comparison against the field then needs a control run purely to
subtract that error, and the control is itself built on stubbed fields.

`bridge/boost/build.sh` compiles the five decision files and the orchestrator straight from
the AndroidAPS working tree into a jar. Nothing is copied and nothing is reimplemented: this
class marshals a cycle across a pipe and the real `decide` runs on the other side. What
remains between this and the shipped application is the input reconstruction, which is a
separate problem with three known defects recorded in `validation/boost.py`.

One process per controller, so one per subject, because the algorithm keeps state between
cycles and the plugin keeps that state in its own store. Holding it on the far side rather
than marshalling it each way removes another place for the two sides to disagree.

The protocol is positional rather than JSON because a hundred subjects over 28 days is more
than 800,000 round trips. `FIELDS` is read back from the jar at startup and checked against
what this module thinks it is sending, so a change to the Kotlin side fails loudly instead of
silently shifting every value by one column.
"""
import os
import shutil
import subprocess

from simglucose.controller.base import Action, Controller

from ..therapy.site import _asleep
from .boost import BoostController

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JAR = os.path.join(HERE, "bridge", "boost", "boost-bridge.jar")

# The value the Kotlin side reads back as a null. Boost treats a missing model output
# differently from a zero one: a null hypo risk leaves the budget unscaled, and a run of null
# meal likelihoods renormalises the score weights.
MISSING = -99999.0

STATES = ("IDLE", "OBSERVING", "CONFIRMED", "COMMITTED", "RECOVERING")

OUTPUTS = ("final_dose", "score", "state_ordinal", "state_age", "state_reset",
           "budget", "action_multiplier", "insulin_to_deliver", "hard_gate",
           "max_iob_clamp", "iob_headroom_brake", "post_action_risk_check",
           "deceleration_brake", "sensor_quality_check", "dynamic_spike_capped",
           "ml_renormalised")


def java_binary():
    """A JVM to run the bridge on.

    Falls back to the runtime Android Studio ships, because a machine that builds this
    algorithm has that even when it has no system JDK, which is the common case on macOS.
    """
    for candidate in (os.environ.get("JAVA_HOME"),
                      "/Applications/Android Studio.app/Contents/jbr/Contents/Home"):
        if candidate:
            path = os.path.join(candidate, "bin", "java")
            if os.path.exists(path):
                return path
    found = shutil.which("java")
    if found:
        return found
    raise RuntimeError("no Java runtime found; set JAVA_HOME")


def available(jar=JAR):
    return os.path.exists(jar)


class BoostBridgeController(BoostController):
    """`BoostController` with the decision replaced by the compiled Kotlin.

    Everything upstream is inherited, so the inputs handed to the algorithm are identical to
    the ported version's and a difference between the two is the port and nothing else. That
    is the point: it isolates one error source rather than changing two things at once.
    """

    def __init__(self, name, jar=JAR, java=None, knobs=None,
                 fast_carb_confirm=True, **kwargs):
        super().__init__(name, **kwargs)
        # The three user-facing knobs. They were being read off the cycle with a default, and
        # none of them is a field on it, so every run sent 1.0 and a configuration derived for
        # the subject could not reach the algorithm. `boost_autoconfig` supplies them.
        self.knobs = {"aggression": 1.0, "hypo_caution": 1.0, "sensitivity": 1.0}
        self.knobs.update(knobs or {})
        # Same story, and it survived that repair. `fastCarbConfirmEnabled` is a field the jar
        # reads and was being taken from the cycle with a default of True, which no cycle
        # carries, so every run sent True whatever the subject's configuration said.
        # `boost_autoconfig` decides it from whether the subject is hypo-prone, and it arrives
        # here explicitly rather than being fished off an object that does not have it.
        self.fast_carb_confirm = bool(fast_carb_confirm)
        if not available(jar):
            raise FileNotFoundError(
                f"no bridge jar at {jar}; build it with bridge/boost/build.sh")
        self.proc = subprocess.Popen(
            [java or java_binary(), "-jar", jar],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1)
        self.proc.stdin.write("FIELDS\n")
        self.proc.stdin.flush()
        self.fields = self.proc.stdout.readline().split()
        self.decisions = []

    # ------------------------------------------------------------------ marshalling
    def _row(self, cycle, null_streak):
        """One cycle as the positional line the jar expects.

        Order is asserted against the jar's own `FIELDS`, so a change on either side is a
        failure rather than a silent column shift.
        """
        d = list(getattr(cycle, "delta_history", ()) or ())
        d = ([0.0] * (3 - len(d)) + [float(x) for x in d])[-3:]
        values = [
            cycle.delta, cycle.short_avg_delta, cycle.delta_accl, cycle.bg,
            cycle.eventual_bg, cycle.target_bg, cycle.max_delta,
            cycle.min_guard_bg, cycle.min_guard_threshold, d[0], d[1], d[2],
            cycle.iob, cycle.max_iob, cycle.base_insulin_req, cycle.round_smb_to,
            1 if cycle.enable_smb_pre_checks else 0,
            MISSING if cycle.ml_hypo_risk is None else cycle.ml_hypo_risk,
            MISSING if cycle.ml_meal_likely is None else cycle.ml_meal_likely,
            cycle.recent_low_bg, self._cumulative_rise(cycle), cycle.hour,
            1 if cycle.exercise_active else 0,
            1 if cycle.post_exercise_window else 0,
            # Both of these were read with `getattr(cycle, name, default)` and neither name is
            # a field on the cycle, so the jar received a constant on every cycle of every
            # run: never asleep, and fast-carb confirmation always on. That is the failure
            # `docs/METHODS.md` records under "a missing input must fail, not default", and
            # these two survived the repair of the other three.
            #
            # Both have a real source. The simulated person's night is the same one
            # `therapy/site.py` uses to decide when a failed set goes unnoticed, and the
            # confirmation flag arrives through the constructor from `boost_autoconfig.py`,
            # which sets it from whether the subject is hypo-prone.
            1 if _asleep(float(cycle.hour) * 60.0) else 0,
            1 if self.fast_carb_confirm else 0,
            1 if cycle.sensor_quality_ok else 0,
            0, 0, 0, 0.0,                      # profile switch, disconnect, suspend, clock
            float(self.knobs["aggression"]),
            float(self.knobs["hypo_caution"]),
            float(self.knobs["sensitivity"]),
            float(self.config.confirmed_cap_u),
            float(self.config.committed_cap_u),
        ]
        if len(values) != len(self.fields):
            raise RuntimeError(
                f"the bridge expects {len(self.fields)} fields and this is sending "
                f"{len(values)}; rebuild the jar or update _row")
        return " ".join(repr(float(v)) for v in values)

    def _decide(self, cycle, null_streak):
        self.proc.stdin.write(self._row(cycle, null_streak) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("the bridge closed; it may have failed on a cycle")
        raw = [float(x) for x in line.split()]
        out = dict(zip(OUTPUTS, raw))
        out["state"] = STATES[int(out["state_ordinal"])]
        return out

    @staticmethod
    def _cumulative_rise(cycle):
        """The 30-minute rise the algorithm scales its dose by, in mg/dL.

        `velocityScaledDoseFactor` returns a floor of 0.40 for a rise at or below 25 mg/dL, so
        a bridge that sends nothing multiplies every dose in every state by 0.40. Measured over
        28 days that removed 60.0 per cent of the raw request on each of three subjects. The
        plugin derives it as `max(0, shortAvgDelta * 6)` and the Python port does the same, so
        this is the same derivation rather than a reconstruction of it.
        """
        return max(0.0, float(cycle.short_avg_delta) * 6.0)

    # ---------------------------------------------------------------------- driving
    def policy(self, observation, reward, done, **info):
        """Build the cycle exactly as the ported adapter does, then decide on the far side."""
        action = super().policy(observation, reward, done, **info)
        cycle = self.cycles[-1] if self.cycles else None
        if cycle is None:
            return action
        decision = self._decide(cycle, self.null_streak)
        self.decisions.append(decision)
        sample = float(info.get("sample_time", 5.0))
        # The parent recorded its own decision against the insulin ledger, and that decision is
        # discarded here. Left in place the algorithm reads insulin on board that nothing
        # delivered, which propagates into its eventual glucose, its minimum guard and the
        # headroom clamping its request: over 28 days the ledger carried 56.08 U a day of
        # microbolus against 33.45 actually given.
        minute = float(info.get("clock_minutes", 0.0))
        if self.doses and self.doses[-1][0] == minute:
            self.doses.pop()
        dose = float(decision["final_dose"])
        if dose > 0:
            self.doses.append((minute, dose))
        return Action(basal=action.basal, bolus=dose / sample)

    def response_profile(self):
        """State occupancy and gate firing, in the shape `validation/boost.py` compares.

        Named to match the ported adapter rather than `profile`, which the parent already
        uses for the subject's therapy settings.
        """
        import collections

        import numpy as np

        if not self.decisions:
            return {}
        n = len(self.decisions)
        states = collections.Counter(d["state"] for d in self.decisions)
        gates = {
            "hard": sum(d["hard_gate"] for d in self.decisions),
            "max_iob_clamp": sum(d["max_iob_clamp"] for d in self.decisions),
            "iob_headroom_brake": sum(d["iob_headroom_brake"] < 1.0 for d in self.decisions),
            "deceleration_brake": sum(d["deceleration_brake"] < 1.0 for d in self.decisions),
            "sensor_quality_check": sum(d["sensor_quality_check"] < 1.0
                                        for d in self.decisions),
            "dynamic_spike_cap": sum(d["dynamic_spike_capped"] for d in self.decisions),
        }
        doses = np.array([d["final_dose"] for d in self.decisions], float)
        return {
            "cycles": n,
            "state_occupancy_pct": {k: 100.0 * v / n for k, v in states.items()},
            "gate_firing_pct": {k: 100.0 * v / n for k, v in gates.items()},
            "dose_mean_u": float(doses.mean()),
            "dose_nonzero_pct": float(100.0 * (doses > 0).mean()),
        }

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write("QUIT\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, ValueError):
                pass
            self.proc.wait(timeout=10)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def factory(**kwargs):
    return lambda name: BoostBridgeController(name, **kwargs)


__all__ = ["BoostBridgeController", "factory", "available", "java_binary", "JAR", "STATES"]
