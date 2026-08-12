"""Physical activity, which the model has no representation of at all.

It is probably the largest single driver of real glucose variability that UVA/Padova omits.
Exercise raises glucose uptake while it happens and leaves insulin sensitivity elevated for
hours afterwards, and it is a leading cause of hypoglycaemia in type 1 diabetes. Nothing in
this package modelled it before: `exercise_active` appears in the adapters only as an input
that is always false.

It does not work, and the measurement is below rather than at the end. Regressed against
every signature, paired, under the built-in loop, adding this layer takes the count inside the
real range from eight of eleven to five. It raises the autocorrelation at thirty minutes by
0.02 +/- 0.01 and at sixty by 0.05 +/- 0.03, both out of range, where the whole purpose was to
lower them, and it widens variability by 3.2 +/- 0.8, also out of range. Two session
schedules were tried, one concentrated in the evening and one spread across waking hours, and
both did this.

So exercise as modelled here makes the simulated person more predictable rather than less.
The layer is kept, off, because the mechanism is sound and the failure is informative: it says
a regular daily perturbation of glucose is not what the predictability signatures are missing,
whatever else exercise does to a person. What did move them was correlated multi-day
sensitivity, which acts on a horizon of days rather than of hours.

Unlike every other layer here, this one cannot be grounded in the local database. The
Nightscout records carry no exercise events, so the schedule below comes from the literature
and is a modelling choice rather than a measurement. What can be checked against data is the
consequence, which is what the fidelity signatures are for, and the three that this layer is
aimed at are the ones saying the model is too predictable: the autocorrelation at thirty and
sixty minutes sits above its range and the spread of outcomes from a stuck high below its own.

The magnitudes:

Adults with type 1 diabetes who exercise at all average around three sessions a week, and
sessions cluster in the late afternoon and early evening. Moderate aerobic exercise of forty
to sixty minutes lowers glucose by tens of mg/dL in an hour, and insulin sensitivity stays
raised for twelve to twenty-four hours afterwards by a fifth to a third. Those are the figures
the constants below are set to, and each is stated at the constant it sets.

Peripheral glucose utilisation in the model is `Vm0 + Vmx * X`, an insulin-independent part
and an insulin-dependent one. A session raises both, which is what makes exercise lower
glucose even when there is little insulin about. What it leaves behind raises only `Vmx`, so a
post-exercise low needs insulin on board and a low during a session does not. `Fsnc` is left
alone: it is brain and nerve uptake and does not move with exercise.
"""
import numpy as np

# Sessions a week. Three is the middle of what is reported for adults with type 1 diabetes
# who exercise; a person who never exercises is represented by a rate of zero rather than by
# switching the layer off, so the population contains both.
SESSIONS_PER_WEEK = 3.0
SESSION_MINUTES = (25.0, 80.0)        # uniform, one session's length

# When. A first version put seventy per cent of sessions at 17:30 with a two-hour spread,
# which was wrong in a way the fidelity table caught: every subject then dipped at the same
# hour every day, and the diurnal amplitude went from 51.0 to 58.8 mg/dL against a real 34.7
# to 56.3. Concentrating activity at one time of day adds a diurnal signal rather than the
# irregularity it is there to add. Real exercise is spread across waking hours with a mild
# preference for the evening, which is what this is now.
SESSION_HOURS = ((18.0, 3.5, 0.45), (12.0, 3.0, 0.30), (8.0, 2.0, 0.25))

# How hard, as a fraction of the maximum effect the constants below describe. Most sessions
# are moderate and a few are hard.
INTENSITY = (0.35, 1.0)

# What a session does at full intensity. `VMX_GAIN` multiplies insulin-dependent utilisation
# and `VM0_GAIN` the insulin-independent part, both chosen so that a moderate session of an
# hour moves glucose by the tens of mg/dL that the literature reports rather than by a
# clinically implausible amount. At these values a subject held at steady state on basal alone
# falls 23 mg/dL over a sixty-minute session at intensity 0.7. Both are modelling choices.
VMX_GAIN = 1.6
VM0_GAIN = 1.5

# After a session. Sensitivity stays raised and decays with this time constant, which puts
# most of the effect inside twelve hours and a tail beyond it.
AFTER_GAIN = 0.30
AFTER_TAU_MIN = 420.0

# How much people differ in how much they exercise, as a coefficient of variation on the
# weekly rate. Kept wide because real activity is far more unequal between people than most
# behaviours, and a population where everybody exercises the same amount would miss that.
RATE_CV = 0.8


def draw_sessions(rng, days, sessions_per_week=SESSIONS_PER_WEEK, rate_cv=RATE_CV):
    """One person's exercise sessions over a run, as (start minute, minutes, intensity).

    The weekly rate is drawn once for the person and held, so somebody who trains often does
    so all month. Which days carry a session is then drawn independently, because real weeks
    are irregular even for regular people.
    """
    sigma = np.sqrt(np.log(1.0 + float(rate_cv) ** 2))
    rate = float(sessions_per_week) * rng.lognormal(-0.5 * sigma ** 2, sigma)
    per_day = np.clip(rate / 7.0, 0.0, 1.0)

    out = []
    for day in range(int(days)):
        if rng.random() > per_day:
            continue
        centres = [c for c, _, _ in SESSION_HOURS]
        sds = [s for _, s, _ in SESSION_HOURS]
        weights = np.array([w for _, _, w in SESSION_HOURS], float)
        k = int(rng.choice(len(centres), p=weights / weights.sum()))
        hour = float(np.clip(rng.normal(centres[k], sds[k]), 5.0, 22.0))
        minutes = float(rng.uniform(*SESSION_MINUTES))
        intensity = float(rng.uniform(*INTENSITY))
        out.append((day * 1440.0 + hour * 60.0, minutes, intensity))
    return tuple(sorted(out))


class Activity:
    """The exercise a person does, and what it is doing to them at a given minute."""

    def __init__(self, sessions=(), after_gain=AFTER_GAIN, after_tau_min=AFTER_TAU_MIN):
        self.sessions = tuple(sessions)
        self.after_gain = float(after_gain)
        self.after_tau_min = float(after_tau_min)
        self._starts = np.array([s for s, _, _ in self.sessions], float)
        self._ends = np.array([s + d for s, d, _ in self.sessions], float)
        self._intensity = np.array([i for _, _, i in self.sessions], float)

    def during(self, minute):
        """Intensity of the session in progress, or zero. One session at a time."""
        if not self.sessions:
            return 0.0
        m = (self._starts <= minute) & (minute < self._ends)
        return float(self._intensity[m].max()) if m.any() else 0.0

    def after(self, minute):
        """The raised sensitivity left behind by sessions already finished.

        Contributions add, because two sessions in a day leave more behind than one, and the
        sum is capped so that a week of training does not run away.
        """
        if not self.sessions:
            return 0.0
        done = self._ends <= minute
        if not done.any():
            return 0.0
        age = minute - self._ends[done]
        lift = self._intensity[done] * np.exp(-age / self.after_tau_min)
        return float(min(lift.sum(), 2.0))

    def minutes_per_week(self, days):
        if not self.sessions or days <= 0:
            return 0.0
        total = sum(d for _, d, _ in self.sessions)
        return float(total / (days / 7.0))


__all__ = ["Activity", "draw_sessions", "SESSIONS_PER_WEEK", "SESSION_MINUTES",
           "VMX_GAIN", "VM0_GAIN", "AFTER_GAIN", "AFTER_TAU_MIN", "RATE_CV"]
