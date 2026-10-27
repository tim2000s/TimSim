"""The whole Boost engine, as it ships on the dev line, behind a JVM runner.

`boost_bridge.py` runs only the six V6 decision files and rebuilds the rest of Boost in Python:
basal, the eventual and minimum-guard predictions, the base insulin requirement, with no
dynamic ISF, no autosens and a target fixed at 110 mg/dL. This adapter drives the real thing.
The runner lives on the `timsim-runner` branch of the Boost fork
(`plugins/aps/src/test/kotlin/app/aaps/plugins/aps/sim/`) and constructs
`OpenAPSBoostV5Plugin` and `OpenAPSBoostPlugin` as the app does, so a cycle here is
`invoke -> runEngine(v5Active = true)`: the V1 `determine_basal`, both models, auto-config and
the V6 override, unchanged.

What crosses the pipe is what AndroidAPS computes in other modules and the oref arm already
receives from `LoopInputs`: the forward insulin curve, carbohydrate on board and the autosens
ratio. Sharing that reconstruction is deliberate. A difference between the two arms should
belong to the algorithms, not to two versions of insulin on board.

The engine's settings arrive as a dictionary of preference names (`ApsBoostV5Aggression`,
`ApsSmbMaxIob`, ...), stored over a fresh install's defaults. A person switching from oref
arrives with history in the phone's database, and auto-config reads it on the first cycle;
`history` carries a learning run's readings, boluses and daily totals for that purpose.
"""
import json
import os
import subprocess

import numpy as np
from simglucose.controller.base import Action, Controller

from .boost_bridge import java_binary
from .inputs import LoopInputs
from .oref import EPOCH_MS

RUNNER = os.environ.get(
    "BOOST_RUNNER", os.path.expanduser("~/StudioProjects/Boost-timsim-runner"))
# A bundle (made by the trial's bundle_runner.py) carries the classpath relative to itself, its
# own copy of the model assets and a manifest, so a second machine runs the same bytes. Without
# one, the runner's Gradle build directory is used directly.
BUNDLE = os.environ.get("BOOST_RUNNER_BUNDLE")
if BUNDLE:
    CLASSPATH = os.path.join(BUNDLE, "classpath.txt")
    ASSETS = os.path.join(BUNDLE, "assets")
else:
    CLASSPATH = os.path.join(RUNNER, "plugins", "aps", "build", "sim-classpath.txt")
    ASSETS = os.path.join(RUNNER, "app", "src", "main", "assets")
CURVE_TICKS = 48
MEAL_CARBS_WINDOW_MIN = 360     # AndroidAPS sums carbohydrate entered over the last six hours
DAY_MIN = 1440


def available():
    return os.path.exists(CLASSPATH)


def classpath():
    entries = open(CLASSPATH).read().strip().replace("\n", os.pathsep).split(os.pathsep)
    if BUNDLE:
        entries = [os.path.join(BUNDLE, e) for e in entries]
    return os.pathsep.join(entries)


def runner_commit():
    """The Boost commit the runner was built from, for provenance."""
    if BUNDLE:
        return json.load(open(os.path.join(BUNDLE, "MANIFEST.json")))
    try:
        return subprocess.run(["git", "-C", RUNNER, "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def history_from_result(result, days_before=None):
    """A finished run as the database a phone would hold, stamped to end where a new run starts.

    The learning run's minute m becomes `m - length` in the next run's clock, so its last day
    is the day before the switch. Readings, each bolus as an SMB (TimSim's oref arm gives no
    other kind), and one total per day split into basal and bolus.
    """
    mins = np.asarray(result.minutes, float)
    cgm = np.asarray(result.cgm, float)
    ins = np.asarray(result.insulin_series, float)
    bol = np.asarray(result.bolus_series, float)
    span = float(days_before * DAY_MIN) if days_before else float(np.ceil(mins[-1] / DAY_MIN) * DAY_MIN)
    t = lambda m: int(EPOCH_MS + (m - span) * 60_000)
    bg = [[t(m), round(float(g), 1)] for m, g in zip(mins, cgm)]
    boluses = [[t(m - 5.0), round(float(b), 3), "SMB"] for m, b in zip(mins, bol) if b > 0]
    day = np.floor((mins - 5.0) / DAY_MIN).astype(int)
    tdd = []
    for d in np.unique(day):
        sel = day == d
        bolus_u = float(bol[sel].sum())
        basal_u = float(np.clip(ins[sel] - bol[sel], 0, None).sum())
        tdd.append([t(d * DAY_MIN), round(basal_u, 3), round(bolus_u, 3)])
    return {"bg": bg, "boluses": boluses, "tdd": tdd}


def continue_state(state, length_days):
    """A finished run's preference state, re-stamped onto the clock of a run that follows it.

    `history_from_result` moves the earlier run's minute m to `m - length` in the next run, so the
    stored timestamps (auto-config's last derivation, its re-derivation clock) move with it and a
    re-derivation due seven days after the last one falls where it would on a phone. A long that
    reads as a time since the epoch is taken to be a timestamp.
    """
    shift = int(length_days * DAY_MIN * 60_000)
    out = {}
    for k, (kind, v) in state.items():
        if kind == "l" and v > 10 ** 12:
            v = v - shift
        out[k] = [kind, v]
    return out


def join_history(older, newer, newer_days):
    """Two histories in sequence: `older` ended where `newer` began, `newer_days` before now."""
    shift = int(newer_days * DAY_MIN * 60_000)
    moved = {k: [[e[0] - shift, *e[1:]] for e in older.get(k, [])] for k in ("bg", "boluses", "tdd")}
    return {k: moved[k] + list(newer.get(k, [])) for k in ("bg", "boluses", "tdd")}


class BoostEngineController(LoopInputs, Controller):
    """Boost dev, with the temporary basal it issues held on this side of the pipe."""

    def __init__(self, name, profile=None, prefs=None, history=None, target_bg=None,
                 autosens=None, debug=False, state=None, insulin_peak_min=None, smoothing=None):
        from ..therapy import profile as profile_mod
        from .autosens import Autosens

        if not available():
            raise FileNotFoundError(
                f"no runner classpath at {CLASSPATH}; build it with "
                "`./gradlew :plugins:aps:writeSimClasspath` on the timsim-runner branch")
        self.name = name
        self.profile = profile if profile is not None else profile_mod.for_subject(name)
        self.prefs = dict(prefs or {})
        self.target_bg = None if target_bg is None else float(target_bg)
        self.pinned_autosens = None if autosens is None else float(autosens)
        self.autosens = Autosens() if autosens is None else None
        if insulin_peak_min is not None:
            self.insulin_peak_min = float(insulin_peak_min)

        self.init_inputs()
        self.temp_rate = None
        self.temp_left = 0.0
        self.temp_start_min = 0.0
        self.temp_duration = 0.0
        self.pending = []              # boluses delivered since the last cycle
        self.carb_entries = []         # (minute, grams) announced
        self.last_carb_min = None
        self.replies = []

        # ByteBuddy's agent jar is loaded at startup rather than attached at run time: a JRE
        # without the jdk.attach module (the study desktop's) cannot self-attach.
        cp = classpath()
        agent = next((e for e in cp.split(os.pathsep) if "byte-buddy-agent" in os.path.basename(e)), None)
        if agent is None:
            raise FileNotFoundError("byte-buddy-agent is not on the runner classpath")
        cmd = [java_binary(), f"-javaagent:{agent}", "-Xmx512m",
               "-cp", cp, "app.aaps.plugins.aps.sim.BoostSimMain"]
        if debug:
            cmd.insert(1, "-Dsim.debug=1")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL if not debug else None,
                                     text=True, bufsize=1)
        reply = self._send({"cmd": "init", "start_ms": EPOCH_MS, "profile": self._profile(),
                            "prefs": self._prefs(), "history": history, "assets": ASSETS,
                            **({"state": state} if state else {}),
                            # "ukf": the runner passes readings through the app's UKF smoother before the
                            # glucose status, as the phone does when it is the active smoother
                            **({"smoothing": smoothing} if smoothing else {})})
        if not reply.get("ok"):
            raise RuntimeError(f"the Boost runner refused init: {reply}")

    # -------------------------------------------------------------------- settings
    def _profile(self):
        lo = self.target_bg if self.target_bg is not None else self.profile.target_lo
        hi = self.target_bg if self.target_bg is not None else self.profile.target_hi
        lim = self.profile.limits
        return {"basal": [float(v) for v in self.profile.basal_u_per_hour],
                "isf": [float(v) for v in self.profile.isf],
                "cr": [float(v) for v in self.profile.cr],
                "target_lo": float(lo), "target_hi": float(hi),
                "dia_hours": float(self.profile.dia_min) / 60.0,
                # The runner answers the insulin plugin's peak with this, which sets Boost's
                # dynamic ISF divisor as well as the curve its insulin on board is read off.
                "insulin_peak": int(round(self.insulin_peak_min)),
                "max_basal": float(lim.max_basal_u_per_hour),
                "max_bolus": float(lim.max_bolus_u),
                "bolus_step": float(lim.bolus_increment_u)}

    def _prefs(self):
        """The trial's settings over a fresh install, with the person's own pump ceilings.

        AndroidAPS's max IOB and max basal are settings a person enters, so they follow the
        profile's limits unless the trial sets them.
        """
        lim = self.profile.limits
        p = {"ApsSmbMaxIob": float(lim.max_iob_u),
             "ApsMaxBasal": float(lim.max_basal_u_per_hour)}
        p.update(self.prefs)
        return p

    # ------------------------------------------------------------------ the pipe
    def _send(self, message):
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("the Boost runner closed; run with debug=True to see why")
        reply = json.loads(line)
        if "error" in reply:
            raise RuntimeError(f"Boost failed on a cycle: {reply['error']}\n{reply.get('stack', '')}")
        # The runner sends a non-finite field as null and names it. In a reported field that is
        # counted; in a dose it would silently become no dose, so the run stops instead.
        bad = set(reply.get("non_finite") or ()) & {"smb", "rate", "duration"}
        if bad:
            raise RuntimeError(f"Boost returned a non-finite dose field {sorted(bad)}: {reply.get('reason', '')[:400]}")
        return reply

    def _clock(self, minute):
        return int(EPOCH_MS + minute * 60_000)

    # ------------------------------------------------------------------ the cycle
    def policy(self, observation, reward, done, **info):
        sample = float(info.get("sample_time", 5.0))
        minute = float(info.get("clock_minutes", 0.0))

        delivered, scheduled = info.get("delivered_basal_u"), info.get("scheduled_basal_u")
        if delivered is not None and scheduled is not None:
            self.observe_basal(minute - sample, delivered, scheduled)

        bg = float(observation.CGM)
        self.readings.append(bg)
        self.prune(minute)

        grams = float(info.get("meal", 0.0)) * sample
        cob = self.observe_carbs(grams, sample)
        if grams > 0.0:
            self.carb_entries.append((minute, grams))
            self.last_carb_min = minute
        self.carb_entries = [c for c in self.carb_entries if minute - c[0] <= MEAL_CARBS_WINDOW_MIN]
        scheduled_rate = self.profile.basal_at(minute) * 60.0
        isf, cr = self.profile.isf_at(minute), self.profile.cr_at(minute)

        ratio = self.pinned_autosens
        if self.autosens is not None:
            readings = list(self.readings)
            self.autosens.observe(
                minute, bg,
                delta=readings[-1] - readings[-2] if len(readings) > 1 else 0.0,
                activity_u_per_min=self.activity_u_per_hour(minute, include_basal=True) / 60.0,
                iob=self.iob_at(minute), sens=isf, carb_ratio=cr,
                current_basal=scheduled_rate, carbs_g=grams, step=sample)
            ratio = self.autosens.ratio(minute, isf, max(float(v) for v in self.profile.basal_u_per_hour))

        curve = self.iob_curve(minute, scheduled_rate, ticks=CURVE_TICKS, step=sample,
                               temp_rate=self.temp_rate, temp_minutes=self.temp_left)
        curve[0]["basaliob"] = self.basal_iob(minute)

        temp = None
        if self.temp_rate is not None and self.temp_left > 0:
            temp = {"rate": self.temp_rate, "start_ms": self._clock(self.temp_start_min),
                    "duration_min": int(round(self.temp_duration))}
        carbs_window = float(sum(g for _, g in self.carb_entries))
        slopes = (self.deviation_slopes(minute, curve[0]["activity"], isf)
                  if self.send_deviation_slopes else None)
        message = {
            "cmd": "cycle", "now_ms": self._clock(minute), "bg": bg, "iob": curve,
            # AndroidAPS drops carbohydrate older than its maximum absorption time from COB as
            # well as from the sum, so COB never exceeds the carbohydrate entered in the window.
            # The linear decay here can outlast six hours after a large meal; uncapped, dev's
            # `fractionCarbsLeft = mealCOB / carbs` divided by zero, minPredBG went NaN and the
            # engine microbolused on it (adult#033, ablation, 12 October 2026).
            "meal": {"carbs": carbs_window, "cob": min(cob, carbs_window),
                     "last_carb_ms": self._clock(self.last_carb_min) if self.last_carb_min is not None else 0,
                     **({"slope_from_max_deviation": slopes[0], "slope_from_min_deviation": slopes[1]}
                        if slopes is not None else {})},
            "autosens": 1.0 if ratio is None else float(ratio),
            "temp": temp,
            "delivered": self.pending,
        }
        if delivered is not None:
            message["basal_u"] = float(delivered)
            message["bolus_u"] = float(sum(d[1] for d in self.pending))
        self.pending = []
        reply = self._send(message)
        self.replies.append(reply)
        return self._apply(reply, minute, sample, scheduled_rate)

    def _apply(self, reply, minute, sample, scheduled_rate):
        """Turn the engine's result into what the pump runs for the next step.

        AndroidAPS replaces the running temporary basal only when the result requests one; a
        zero duration cancels back to the schedule. An engine run that returned nothing leaves
        the pump as it was, which is what the phone does.
        """
        if reply.get("ok") and reply.get("temp_requested"):
            rate, duration = reply.get("rate"), reply.get("duration")
            if rate is not None and duration is not None:
                if duration <= 0:
                    self.temp_rate, self.temp_left = None, 0.0
                else:
                    self.temp_rate, self.temp_left = float(rate), float(duration)
                    self.temp_start_min, self.temp_duration = minute, float(duration)

        running = self.temp_rate if self.temp_rate is not None else scheduled_rate
        self.temp_left = max(0.0, self.temp_left - sample)
        if self.temp_left <= 0.0:
            self.temp_rate = None

        bolus = float(reply.get("smb") or 0.0) if reply.get("ok") else 0.0
        if bolus > 0:
            self.doses.append((minute, bolus))
            self.pending.append([self._clock(minute), bolus, "SMB"])
        return Action(basal=running / 60.0, bolus=bolus / sample)

    # ------------------------------------------------------------------ reporting
    def managed(self):
        return self._send({"cmd": "managed"})

    def state(self):
        """Every stored preference with its type, for `continue_state` and a later run's `state`."""
        return self._send({"cmd": "state"})["state"]

    def response_profile(self):
        """What the engine did with the run: V6 state occupancy, dose sizes and failures."""
        if not self.replies:
            return {}
        n = len(self.replies)
        ok = [r for r in self.replies if r.get("ok")]
        states = {}
        for r in ok:
            states[r.get("v6_state")] = states.get(r.get("v6_state"), 0) + 1
        units = np.array([r.get("smb") or 0.0 for r in ok], float)
        # The aggression knob scales only the confirm shot, so this is where it shows.
        confirm = [r for r in ok if r.get("v6_state") == "CONFIRMED"]
        confirm_u = np.array([r.get("smb") or 0.0 for r in confirm], float)
        capped = [r for r in confirm if r.get("v6_final") is not None and r.get("confirmed_cap") is not None
                  and r["v6_final"] >= r["confirmed_cap"] - 1e-9]
        return {
            "confirm_cycles": len(confirm),
            "confirm_dose_mean_u": float(confirm_u.mean()) if confirm_u.size else None,
            "confirm_dose_total_u": float(confirm_u.sum()),
            "confirm_at_cap_pct": 100.0 * len(capped) / len(confirm) if confirm else None,
            "cycles": n,
            "no_result": n - len(ok),
            "state_pct": {k: 100.0 * v / max(len(ok), 1) for k, v in states.items()},
            "smb_pct": float(100.0 * (units > 0).mean()) if units.size else 0.0,
            "smb_mean_u": float(units[units > 0].mean()) if (units > 0).any() else 0.0,
            "non_finite": {k: sum(k in (r.get("non_finite") or ()) for r in ok)
                           for k in sorted({k for r in ok for k in (r.get("non_finite") or ())})},
            "post_rescue_pct": float(100.0 * np.mean([bool(r.get("post_rescue")) for r in ok])) if ok else 0.0,
        }

    def close(self):
        if getattr(self, "proc", None) and self.proc.poll() is None:
            try:
                self.proc.stdin.write('{"cmd":"quit"}\n')
                self.proc.stdin.flush()
            except (BrokenPipeError, ValueError):
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


__all__ = ["BoostEngineController", "history_from_result", "continue_state", "join_history", "available",
           "runner_commit"]
