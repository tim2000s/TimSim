"""Drive the shipped oref0 SMB algorithm inside TimSim.

oref0 is the reference open-source closed loop and the one with the longest published
record in the field, which is what makes it worth running here. Boost is a system this
project has a hand in; oref0 is not, and a simulator that only ever meets algorithms built
alongside it has not been tested against anything.

As with the Boost bridge, the algorithm is the shipped code rather than a port of it.
`bridge/oref/index.js` requires `determine-basal.js` straight out of the AndroidAPS tree and
calls it, so nothing here can drift from the algorithm those assets define. What this module
does is reconstruct oref's inputs and hold the pump state its output implies.

Two things make this harder than the Boost adapter, and both are places a careless version
would produce a result that says nothing about either the algorithm or the simulator.

oref asks for insulin on board as a forward curve rather than a number. It walks that array
to build every prediction it makes, and the predicted minimum it derives from it is what
gates delivery. `LoopInputs.iob_curve` builds it from the same ledger the scalar comes from,
including the entry for zero delivery from this instant, which is the floor oref checks
before it doses.

And oref does not return a dose. It returns a temporary basal rate with a duration, and
expects to be told next cycle how much of that duration is left. TimSim's rig takes a basal
rate and a bolus per step, so the temporary basal is held here and counted down. Getting
that wrong is not a subtle error: a loop that forgets its own temporary basal reverts to the
scheduled rate every five minutes and cannot withhold insulin at all.

Two of oref's inputs are deliberately absent, and each is absent for a reason rather than
for convenience. `iob_data.lastTemp` is a pump-history cross-check, and omitting it skips
two cancellation branches that exist to catch a pump disagreeing with the loop; the
simulated pump delivers what it is asked for, so there is nothing for them to catch. Bolus
wizard fields are false throughout, since nothing here uses one.

One further input is supplied as a constant unless `send_deviation_slopes` is set (see
`LoopInputs.deviation_slopes`), and it is a real simplification rather than an absence with no
consequence. `meal_data.slopeFromMaxDeviation` and `slopeFromMinDeviation`
are sent as zero, where oref computes them from how its observed deviations have moved over
the last hour. It combines them as `min(slopeFromMaxDeviation, -slopeFromMinDeviation / 3)`
and uses the result to decay predicted carb impact along the unannounced-meal curve, so a
zero means that curve never decays and the unannounced-meal prediction is more persistent
here than in a real deployment. Reconstructing them needs a record of predicted against
observed deviation that this bridge does not keep. Any result resting on the
unannounced-meal path should be read with that in mind.

`meal_data.lastCarbTime` was a constant too, and that one was a defect rather than a
simplification. It was sent as the epoch, so whenever carbohydrate was on board oref computed
a last-carb age of about 28 million minutes, and `remainingCATime = remainingCATimeMin + 1.5 *
lastCarbAge / 60` became some 700,000 hours. That inflates `totalCA` past any real
carbohydrate amount, so `remainingCarbs = max(0, mealCOB - totalCA)` collapsed to zero on
every cycle where carb impact was being observed, and with it `remainingCIpeak`. The
algorithm was therefore predicting no further carbohydrate absorption throughout every
announced meal, which biases it towards under-delivering. It now carries the clock of the
last carbohydrate this loop was told about.

Autosens is computed by `controller/autosens.py`, which is the one part of this arm that is
reimplemented rather than shipped, for the reasons set out there. `autosens=None` runs it and
a number pins the ratio, which is what the comparison between the two uses.
"""
import json
import os
import shutil
import subprocess

from simglucose.controller.base import Action, Controller

from ..therapy.insulin import DIA_MIN
from .inputs import LoopInputs

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX = os.path.join(HERE, "bridge", "oref", "index.js")

# A wall clock for the run. oref reads the hour from it for its exercise and target
# handling, and measures how long ago the last microbolus was, so it has to advance with the
# simulation rather than with real time. Minute zero is midnight, which is where the
# subject's basal schedule starts.
EPOCH_MS = 1_700_000_000_000 - (1_700_000_000_000 % 86_400_000)

CURVE_TICKS = 48          # four hours ahead, which is the horizon oref predicts over
SMB_INTERVAL_MIN = 3


def node_binary():
    found = shutil.which("node")
    if found:
        return found
    raise RuntimeError("no node runtime found; install node to run the oref bridge")


def available(index=INDEX):
    """Whether the bridge has been gathered. `bridge/oref/build.sh` does the gathering."""
    return os.path.exists(index) and os.path.exists(
        os.path.join(os.path.dirname(index), "vendor", "oref", "determine-basal.js"))


class OrefController(LoopInputs, Controller):
    """oref0 SMB, with the temporary basal it issues held on this side of the pipe."""

    def __init__(self, name, profile=None, index=INDEX, node=None, target_bg=None,
                 microbolus=True, autosens=None, sensor_noise=1, insulin_peak_min=None):
        from ..therapy import profile as profile_mod
        from .autosens import Autosens

        if not available(index):
            raise FileNotFoundError(
                f"no gathered oref under {os.path.dirname(index)}; run bridge/oref/build.sh")
        self.name = name
        self.profile = profile if profile is not None else profile_mod.for_subject(name)
        self.target_bg = float(target_bg) if target_bg is not None else None
        self.microbolus = bool(microbolus)
        # A number pins the ratio; None runs the detection. Pinning it is what the arm did
        # before the detection existed, and keeping the option is what makes the two
        # comparable on the same subjects.
        self.pinned_autosens = None if autosens is None else float(autosens)
        self.autosens = Autosens() if autosens is None else None
        self.ratios = []
        self.sensor_noise = int(sensor_noise)
        if insulin_peak_min is not None:
            self.insulin_peak_min = float(insulin_peak_min)

        self.init_inputs()
        self.temp_rate = None          # U/hr the pump is running, or None for the schedule
        self.temp_left = 0.0           # minutes of that temporary basal still to run
        self.last_bolus_min = -600.0
        # When carbohydrate last reached this loop. oref divides by the age of the last carb
        # entry to decide how long absorption has left to run, so sending the epoch made every
        # cycle with carbs on board believe they were entered decades ago.
        self.last_carb_min = -600.0
        self.suggestions = []          # every oref result, for the response profile

        self.proc = subprocess.Popen(
            [node or node_binary(), index],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self._send({"profile": self._static_profile()})

    # -------------------------------------------------------------------- the profile
    def _static_profile(self):
        """Everything oref reads that does not move through the day.

        The safety ceilings come from the subject's own pump limits rather than from oref's
        defaults, so this arm is bounded exactly as the other controllers in the package are
        and a difference between them is the algorithm.
        """
        lim = self.profile.limits
        basal = [float(v) for v in self.profile.basal_u_per_hour]
        lo = self.target_bg if self.target_bg is not None else self.profile.target_lo
        hi = self.target_bg if self.target_bg is not None else self.profile.target_hi
        return {
            "dia": float(self.profile.dia_min) / 60.0,
            "max_basal": float(lim.max_basal_u_per_hour),
            "max_daily_basal": max(basal),
            "max_iob": float(lim.max_iob_u),
            "bolus_increment": float(lim.bolus_increment_u),
            "min_bg": float(lo), "max_bg": float(hi),
            "out_units": "mg/dL",
            "max_daily_safety_multiplier": 3, "current_basal_safety_multiplier": 4,
            # SMB is the point of this variant, so it is on. Without a temporary target or
            # carbohydrate entry, `enableSMB_always` is what lets it act on a rise.
            "enableSMB_always": True, "enableSMB_with_COB": True,
            "enableSMB_after_carbs": True, "enableSMB_with_temptarget": False,
            "allowSMB_with_high_temptarget": False, "enableUAM": True,
            "maxSMBBasalMinutes": 75, "maxUAMSMBBasalMinutes": 45,
            "SMBInterval": SMB_INTERVAL_MIN,
            "min_5m_carbimpact": 8.0,
            "autosens_max": 1.2, "autosens_min": 0.7,
            "curve": "rapid-acting", "insulinPeakTime": int(round(self.insulin_peak_min)),
            "skip_neutral_temps": False, "temptargetSet": False,
            "remainingCarbsCap": 90, "remainingCarbsFraction": 1.0,
            "carbsReqThreshold": 1, "A52_risk_enable": False,
            "exercise_mode": False, "half_basal_exercise_target": 160,
            "high_temptarget_raises_sensitivity": False,
            "low_temptarget_lowers_sensitivity": False,
            "sensitivity_raises_target": False, "resistance_lowers_target": False,
            "adv_target_adjustments": False,
            "noisyCGMTargetMultiplier": 1.3, "maxRaw": 200,
            "type": "current",
        }

    # ------------------------------------------------------------------ the pipe
    def _send(self, message):
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("the oref bridge closed; it may have failed on a cycle")
        try:
            reply = json.loads(line)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"the oref bridge wrote something that is not a reply: {line[:200]!r}. "
                "oref narrates to stdout, so anything unsilenced corrupts this channel.")
        if "error" in reply:
            raise RuntimeError(f"oref failed on a cycle: {reply['error']}")
        return reply

    # ------------------------------------------------------------------ the cycle
    def _clock(self, minute):
        return EPOCH_MS + int(minute * 60_000)

    def policy(self, observation, reward, done, **info):
        sample = float(info.get("sample_time", 5.0))
        minute = float(info.get("clock_minutes", 0.0))

        # What the pump actually ran last step, so this cycle's insulin on board reflects it
        # rather than what was asked for.
        delivered, scheduled = info.get("delivered_basal_u"), info.get("scheduled_basal_u")
        if delivered is not None and scheduled is not None:
            self.observe_basal(minute - sample, delivered, scheduled)

        bg = float(observation.CGM)
        self.readings.append(bg)
        delta, short_avg, long_avg = self.glucose_status(sample)
        self.delta_history.append(delta)

        # Nothing older than the duration of action can reach the forward curve, and the
        # curve is walked 196 times a cycle.
        self.prune(minute)

        grams = float(info.get("meal", 0.0)) * sample
        cob = self.observe_carbs(grams, sample)
        if grams > 0.0:
            self.last_carb_min = minute
        scheduled_rate = self.profile.basal_at(minute) * 60.0
        now = self._clock(minute)
        isf, cr = self.profile.isf_at(minute), self.profile.cr_at(minute)

        ratio = self.pinned_autosens
        if self.autosens is not None:
            readings = list(self.readings)
            self.autosens.observe(
                minute, bg,
                delta=readings[-1] - readings[-2] if len(readings) > 1 else 0.0,
                activity_u_per_min=self.activity_u_per_hour(
                    minute, include_basal=True) / 60.0,
                iob=self.iob_at(minute), sens=isf, carb_ratio=cr,
                current_basal=scheduled_rate, carbs_g=grams, step=sample)
            ratio = self.autosens.ratio(minute, isf, max(
                float(v) for v in self.profile.basal_u_per_hour))
        self.ratios.append(ratio)

        curve = self.iob_curve(minute, scheduled_rate, ticks=CURVE_TICKS, step=sample,
                               temp_rate=self.temp_rate, temp_minutes=self.temp_left)
        for tick in curve:
            tick["lastBolusTime"] = self._clock(self.last_bolus_min)

        s_max, s_min = (self.deviation_slopes(minute, curve[0]["activity"], isf)
                        if self.send_deviation_slopes else (0, 0))
        result = self._send({
            "profile": {"sens": isf, "carb_ratio": cr, "current_basal": scheduled_rate},
            "glucose_status": {"glucose": bg, "delta": delta,
                               "short_avgdelta": short_avg, "long_avgdelta": long_avg,
                               "date": now, "noise": self.sensor_noise, "last_cal": 0},
            "currenttemp": {"duration": round(self.temp_left),
                            "rate": self.temp_rate if self.temp_rate is not None else 0.0,
                            "temp": "absolute"},
            "iob": curve,
            "meal_data": {"carbs": cob, "mealCOB": cob, "boluses": 0,
                          "lastBolusTime": self._clock(self.last_bolus_min),
                          "lastCarbTime": self._clock(self.last_carb_min), "bwFound": False,
                          "bwCarbs": 0,
                          "slopeFromMaxDeviation": s_max, "slopeFromMinDeviation": s_min,
                          "maxDeviation": 0, "minDeviation": 0},
            "autosens": {"ratio": ratio},
            "microBolusAllowed": self.microbolus,
            "currentTime": now,
        })
        self.suggestions.append(result)
        return self._apply(result, minute, sample, scheduled_rate)

    def _apply(self, result, minute, sample, scheduled_rate):
        """Turn oref's suggestion into what the pump runs for the next step.

        A returned rate and duration replace the running temporary basal, including the
        zero-duration cancellation oref uses to hand control back to the schedule. Anything
        left over from a previous instruction counts down. The rig then delivers the
        temporary rate if one is live and the scheduled rate otherwise, which is what a pump
        does between instructions.
        """
        rate, duration = result.get("rate"), result.get("duration")
        if rate is not None and duration is not None:
            if duration <= 0:
                self.temp_rate, self.temp_left = None, 0.0
            else:
                self.temp_rate, self.temp_left = float(rate), float(duration)

        running = self.temp_rate if self.temp_rate is not None else scheduled_rate
        self.temp_left = max(0.0, self.temp_left - sample)
        if self.temp_left <= 0.0:
            self.temp_rate = None

        bolus = float(result.get("units") or 0.0)
        if bolus > 0:
            self.doses.append((minute, bolus))
            self.last_bolus_min = minute

        return Action(basal=running / 60.0, bolus=bolus / sample)

    # ------------------------------------------------------------------ reporting
    def response_profile(self):
        """What oref did with the run, in the shape the Boost arm reports.

        Temporary basal share and microbolus rate are the two things that separate this
        algorithm's behaviour from an open loop, so they are what a comparison reads.
        """
        import numpy as np

        if not self.suggestions:
            return {}
        n = len(self.suggestions)
        units = np.array([s.get("units") or 0.0 for s in self.suggestions], float)
        rates = [s.get("rate") for s in self.suggestions]
        eventual = np.array([s["eventualBG"] for s in self.suggestions
                             if s.get("eventualBG") is not None], float)
        carbs_req = sum(1 for s in self.suggestions if s.get("carbsReq"))
        ratios = np.array([r for r in self.ratios if r is not None], float)
        return {
            "autosens_median": float(np.median(ratios)) if ratios.size else None,
            "autosens_min": float(ratios.min()) if ratios.size else None,
            "autosens_max": float(ratios.max()) if ratios.size else None,
            "autosens_below_1_pct": float(100.0 * (ratios < 1.0).mean()) if ratios.size else None,
            "cycles": n,
            "smb_pct": float(100.0 * (units > 0).mean()),
            "smb_mean_u": float(units[units > 0].mean()) if (units > 0).any() else 0.0,
            "dose_mean_u": float(units.mean()),
            "zero_temp_pct": float(100.0 * sum(r == 0 for r in rates) / n),
            "temp_issued_pct": float(100.0 * sum(r is not None for r in rates) / n),
            "eventual_bg_median": float(np.median(eventual)) if eventual.size else None,
            "carbs_required_pct": float(100.0 * carbs_req / n),
        }

    def close(self):
        if getattr(self, "proc", None) and self.proc.poll() is None:
            try:
                self.proc.stdin.write("QUIT\n")
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


def factory(**kwargs):
    return lambda name: OrefController(name, **kwargs)


__all__ = ["OrefController", "factory", "available", "node_binary", "INDEX"]
