# Testing an open-source AID system on TimSim

The six levels in [VALIDATION.md](VALIDATION.md) validate TimSim as a simulator of a
person on a generic correction loop. Driving OpenAPS, AndroidAPS, Loop, Trio or iAPS
through it is a different job, and the existing levels do not cover it. This document
sets out what a validation for that purpose has to establish, which parts of the harness
are not yet fit for it, and what a result from such a bench can and cannot be used to
say.

## 1. Decide which claim you are trying to support

Three claims get confused, and they need very different evidence.

The weakest is that the bench can surface a failure mode: put a system in front of a
simulated person who eats without announcing it and treats their own lows, and watch for
insulin stacking, oscillation, over-correction of a false low, or a failure to withdraw
basal. A failure found this way is informative on its own, because it is a demonstration
rather than an estimate.

The middle claim is a pre-clinical gate. Fix the acceptance criteria before the run, run
the cohort, and report whether anything trips them. That is the claim the UVA/Padova
simulator was accepted for in 2008, as a substitute for animal testing ahead of a trial
rather than as a substitute for the trial, and it is the most useful thing this bench can
support. `validation/gate.py` implements it, and `docs/EVIDENCE.md` sets out what has to
be true for the verdict to mean anything.

The strongest is that the bench can certify a system as safe, or price a settings change
for a person. Section 7 has the exposure arithmetic that puts both out of reach, and no
amount of further work on the simulator changes it.

Aim at the middle claim. Everything below is written to make that one defensible.

## 2. Harness defects, and what was done about them

Eight defects were found by reading the code against the claims. Each is now fixed, and
each fix carries a check that would have caught it, because most of them survived a
passing test suite by being wired up wrongly rather than by being wrong in isolation.

| Defect | Fix | Check that would now catch it |
|---|---|---|
| The sensor layer was applied to the finished trace, so no algorithm ever saw a compression low | `sensor/realism.OnlineArtefacts` transforms each reading before the controller and the simulated person see it | `check_the_algorithm_sees_the_sensor_artefacts` |
| The isolation check was true by construction and could not fail | it now runs against a controller that ignores the sensor, which is the only case where the body should be unchanged | `check_the_sensor_layer_is_a_reading_and_not_a_glucose` |
| The run stepped every three minutes while real CGM reports every five | the sensor is now `GuardianRT`, whose noise parameters match Dexcom's and whose sample time is five | the whole fidelity table was remeasured on the new grid |
| The artefact rate arithmetic assumed a five-minute grid regardless of the real one | both the rate and the dip shape are now computed in minutes | `test_compression_lows_are_placed_at_about_the_requested_rate` on two grids |
| Insulin delivered by an external controller was recorded as NaN | insulin is measured at the body from `env.insulin_hist`, so the figure is right whichever controller produced it | `Result.insulin_series`, read by the safety record |
| The layer record claimed the loop layer ran when an external controller had switched it off | the effective layers are recorded and a warning is raised | `test_an_external_controller_switches_the_loop_layer_off` |
| No delivery ceilings, so an algorithm could ask for 150 units in one step | `therapy/limits.py` sits in front of the pump and counts every clamp | `check_delivery_limits_bind` |
| One flat basal rate and two scalars in place of a therapy profile | `therapy/profile.py` supplies a 24-hour schedule, time-blocked sensitivity and ratio, a target range and a duration of action | `test_a_diurnal_profile_peaks_before_breakfast_and_holds_its_daily_total` |

A ninth turned up while rereading the run loop after the other eight were done, and it is
the largest of them. simglucose reports announced carbohydrate as grams per minute
averaged over the step, while the behaviour layer's scenario accumulates grams. The runner
passed the first through as though it were the second, so every run with the behaviour
layer switched off bolused a fifth of what it should have. That is the bare and
physiology-only arms of the ablation, which are the baseline the whole fidelity table is
read against: on a single 60 g meal the bare arm peaked at 230 mg/dL where it should have
peaked at 185. Both arms were remeasured. `test_a_meal_is_bolused_the_same_whether_or_not_the_behaviour_layer_is_on`
is the check, and it compares the two paths against each other rather than against a
constant, which is what makes it able to fail.

A tenth turned up the same way, from writing the check for the sixth. The insulin-on-board
ceiling was applied to boluses and not to basal delivered above schedule, so an algorithm
holding its basal at the maximum walked insulin on board through the ceiling: 10.8 U
against a declared 8.6, with every individual bolus compliant. The open-source systems cut
a temp basal back for exactly this reason. Both are now bounded together, and peak insulin
on board lands on the ceiling rather than past it.

Two of the fixes changed measured behaviour in ways worth stating rather than burying.

Delivery quantisation is now real, and it moves the steady state. A basal rate rounded to
the nearest 0.05 U/h is out by up to about 2%, which leaves a subject a couple of mg/dL
away from its fasting value. An intermediate version rounded down instead of to the
nearest increment and produced three times that offset in the same direction on every
subject, which is a good illustration of why a conservative-looking choice is not always
the safe one. `check_pump_quantisation_costs_what_it_should` measures it, and the
steady-state check that tests the physiology runs with quantisation switched off, because
that check is about whether the parameters and the initial state agree.

Compression lows now reach the simulated person as well as the algorithm, so a false low
can provoke a real rescue and real carbohydrate. That is what happens to people, and it
means the hypoglycaemia statistics now include an artefact-driven component that they did
not before.

## 3. What an OS-AID system needs from the harness

The interface that exists is simglucose's: `policy(observation, reward, done, **info)`
returning `Action(basal, bolus)` in units per minute. That is enough to drive a system,
and not enough to drive one faithfully. The gap, by system family:

| Requirement | Why it matters | Present today |
|---|---|---|
| Five-minute cycle | oref's deltas, staleness tests and SMB interval are keyed to it | done, the run steps every five minutes |
| A profile: basal schedule, ISF and CR by time block, target range, DIA | every dosing decision an AID makes is read from here | done, `info["profile"]`, flat by default and dawn-shaped on request |
| Enforced ceilings on basal, bolus and insulin on board | a large part of what makes an AID safe is where its limits sit and whether they bind | done, `therapy/limits.py`, with every clamp counted |
| Sensor artefacts the algorithm can react to | whether a system over-reacts to a false low is one of the more useful questions to ask it | done, the artefacts are inside the loop |
| Withheld and stale readings | oref falls back to a safer path on a gappy or flat trace, and that path needs testing | done, `validation/faults.py` plus `info["stale_minutes"]` |
| A clock the system can read, with the option to move it | daylight saving and timezone changes have caused real incidents | done, `info["clock_minutes"]` and `faults.ClockShift` |
| Delivery that can silently fail | insulin on board reconstructed from what was commanded diverges from what arrived | done, `faults.NoDelivery` |
| Five-minute glucose history, 24 hours deep, with timestamps | oref reads delta, short_avgdelta and long_avgdelta off it rather than off one reading | not passed; an adapter has to accumulate it |
| Temp basal as rate plus duration | oref returns a temp basal, and its expiry behaviour is part of the algorithm | not accepted; only an instantaneous rate |
| Pump history for IOB | oref recomputes insulin on board from delivery history rather than trusting a running total | not maintained in the shape oref reads |
| Announced carbohydrate as a timestamped carb entry | oref runs its own absorption model and decays carbohydrate on board against observed deviation | passed as a rate for one step |

The first seven were the harness work and are done. The remaining four are the adapter,
and they are structural rather than cosmetic: temp basal with a duration, the pump and
glucose histories, and carbohydrate as an entry rather than a rate are the mechanisms
through which oref does its work. A bench that replaces them with a per-cycle insulin rate
is testing something that shares only a name with the system under test.

The practical shape of an adapter, for the oref family, is a controller that accumulates a
delivery log and a glucose log, writes the Nightscout-shaped JSON that
`oref0-determine-basal` expects, runs it as a subprocess once per five-minute cycle, and
translates the returned temp basal and SMB back into `Action`. For Loop and Trio the same
job means linking against or reimplementing the Swift dosing path, which is a larger
undertaking and worth acknowledging before it is started.

## 4. What TimSim already gives an OS-AID bench that a bare simulator does not

Worth stating, because it is the reason to do this on TimSim at all rather than on stock
simglucose.

Unannounced meals are the stress that oref1's unannounced-meal detection exists to
handle, and the behaviour layer produces them at a rate drawn from the literature rather
than fitted. Rescue carbohydrate is never announced, which is the correct model of someone
treating a low and is also the input that most readily provokes stacking in a system that
reads the resulting rise as a meal. Insulin sensitivity that varies by time of day and
week to week is what autosens is for, so the harness contains the signal that adaptation
is supposed to track. A hundred subjects rather than thirty raises the resolution of a
paired comparison from about 1.9 percentage points of time in range to about 1.0.

## 5. The metrics to judge on

Time in range is the wrong primary endpoint for a safety bench, and level 2 of
`VALIDATION.md` already shows why: the simulated person defends against lows with
carbohydrate, so an over-aggressive system can produce an unchanged mean while pushing
the person into repeated rescues. Judge on the set below, reported per subject rather than
as a cohort median, because a bench looking for failures cares about the worst subject.

`analysis/safety.py` computes the set below. `Result.safety()` gives one subject's record
and `safety.worst_of` gives the tail summaries, which is what a verdict turns on.

| Metric | Read it for |
|---|---|
| `completed` | subjects the run could not survive, counted rather than dropped |
| `minutes_below_54_per_day`, `longest_below_54_min` | severe hypoglycaemia, which time below 70 hides |
| `rescue_grams_per_day`, `rescue_events_per_day` | the person paying for the system's aggression |
| `lbgi`, `hbgi` | the standard asymmetric risk indices |
| `insulin_per_day` | dosing that is fine on average and wrong for someone |
| `peak_insulin_per_hour_u` | stacking, which a daily total conceals |
| `peak_iob_u` against `max_iob_u`, and `limit_bound` | whether the declared ceilings actually bind, and how often |
| `time_in_range`, `mean_bg` | the conventional summary, reported last |

Glucose figures come from `Result.bg` rather than from the sensor trace. A compression low
is a false reading and should not count as hypoglycaemia, and a system that causes a real
low which its own sensor understates should not get credit for it.

Report the distribution rather than the median for every one of these. A system that is
excellent for 95 subjects and dangerous for five is not a good system, and a median hides
that completely. `worst_of` names the worst subject for each metric so it can be rerun.

One metric on the original version of this list is not implemented: the autocorrelation of
delivery at 30 and 60 minutes, as a measure of an algorithm hunting. `Result.insulin_series`
carries what it needs and nothing computes it yet.

## 6. A seventh level: fault tolerance

The six existing levels ask whether the simulator resembles reality and how finely it can
discriminate. Neither question covers what a safety bench is for, which is whether the
system under test behaves sensibly when its inputs go wrong. Level 7 is now implemented in
`validation/faults.py` and `validation/ranking.py`, and `docs/EVIDENCE.md` sets out the
reasoning behind both halves.

Each scenario below is a fault injected into an otherwise ordinary run, with the same
subject and seed as an unfaulted control, so the difference is attributable. The passing
condition in every case is that the system degrades to a safe fallback and recovers,
rather than that any particular number is achieved.

| Fault | What a sensible system does |
|---|---|
| `NoReadings`, one hour and three hours | falls back to profile basal, holds it, and resumes without a catch-up correction for the glucose that moved while it was blind |
| `SensorRestart`, a two-hour warm-up gap and an offset on resumption | treats the step change as a new sensor rather than as a real rise |
| `StuckReading`, 45 minutes of a repeated value | notices the trace has stopped moving and stops dosing on a delta that is structurally zero |
| `CompressionLow`, placed where you want it | withdraws insulin if it likes, and does not correct afterwards for a rise that never happened |
| `NoDelivery`, one hour and two hours | recovers without a large correction when delivery resumes, since the insulin it believes is on board was never given |
| `ClockShift`, an hour forward | applies the profile block for the real hour, and neither duplicates nor skips dosing across the discontinuity |
| A large unannounced meal followed by a rescue | does not stack, which is the classic failure here |

`faults.SCENARIOS` is the standard set, and `examples/safety_gate.py` runs them. Each is
injected into an otherwise ordinary run against an unfaulted control on the same subject
and seed, so the difference is attributable. The passing condition in every case is that
the system degrades to a safe fallback and recovers, rather than that any particular number
is achieved, which is why every fault class states what it expects in words.

None of these needs a large cohort. Each is a demonstration, and a single subject on a
fixed seed that reproduces exactly is more useful than a cohort median, because a
maintainer can rerun it.

## 7. How much can a bench of this size actually detect

Level 5 gives the minimum detectable difference in time in range, and it is the right
tool for a mean. It is the wrong tool for a rare adverse event, and safety questions are
mostly about rare events.

Take the whole population run for 28 days: 2800 subject-days. Suppose a system produces
zero severe hypoglycaemic events across all of it. The upper 95 per cent bound on the
underlying rate is roughly three over the exposure, which is one event per 933 subject-days,
or about one per 2.6 subject-years. A system whose true rate is one severe event per five
subject-years would show zero here most of the time. So an absence of severe events on
this bench is not evidence that severe events are rare, and it should never be reported
as though it were.

The consequence is that the bench's value on safety is asymmetric. Events it finds are
real and worth acting on. Events it does not find have not been ruled out, and the run
length needed to rule them out is beyond what this design can reach.

Two fidelity gaps bias the verdict further, and their direction is known.

Hypoglycaemia rebound sits at 58.5 per cent against a real 23 to 28, so the simulated
person over-treats lows about twice as often as these cohorts appear to. A system judged
on how it handles rebound highs is being judged on a harsher world than the real one, and
will look worse than it is.

The spread of outcomes 30 minutes after a stuck high is 27.0 mg/dL against a real 26.5 to
33.5, so it is now inside the range, at the confident end of it, on ten subjects with a
bootstrap interval from 22.0 to 30.7. Until that settles, assume a system relying on
prediction is still somewhat flattered here. The two biases run in opposite directions and
do not cancel in any usable way.

## 8. The protocol

The section 2 defects are fixed, so this is the sequence as it stands. It is deliberately front-loaded
with checks that cost little and invalidate everything downstream when they fail.

1. Register the criteria and pin the system under test by commit. `gate.fingerprint`
   hashes the criteria with the design that `gate.design_of` reads off the cohort, which
   covers the layers and settings the run used as well as its size. A verdict whose
   fingerprint does not match the
   registered one had its thresholds moved. OS-AID projects change quickly, so a result
   without a SHA cannot be reproduced or contested.
2. Run `python -m timsim.validation.run --fast`. It is a few minutes and it invalidates
   everything downstream when it fails.
3. Run the adapter against a null algorithm that returns profile basal and nothing else,
   and confirm the resulting trace matches a run with no controller attached. This
   catches adapter bugs before they are attributed to the algorithm.
4. Run the level 7 fault scenarios on a single subject with a fixed seed. Read the
   traces. This is the part that finds things.
5. Run the A/A test: the same system twice, same subjects, different seed. Record the
   paired spread and the minimum detectable difference it implies. Nothing measured later
   can be believed below that figure.
6. Run the comparison, paired, same subjects and same seed in both arms, at the largest
   cohort you can afford. Report the full metric set from section 5 as distributions.
7. Regenerate the population on a second seed and repeat the comparison. A conclusion
   that does not survive a different draw was a property of the draw.
8. State the biases from section 7 alongside the result, with their direction.

## 9. What a result from this bench licenses

| Claim | Supported |
|---|---|
| A specific failure mode exists and reproduces, with the seed and subject that produce it | yes |
| System A beats system B by more than the measured noise floor, on the section 5 metrics, for the population and behaviour model TimSim implements | yes |
| An effect is attributable to a named mechanism, shown by switching a layer off | yes |
| A system is safe, or safer than another | no, for the reasons in section 7 |
| Anything about a particular person | no, the outcome spread is measurably narrower than reality |
| Anything involving exercise, illness or alcohol | no, the model has no mechanism for any of them |
| Anything involving infusion site failure | partly; `therapy/site.py` models absorption dropping away and being noticed late, calibrated on DCLP3, and nothing else about a bad site |
| The same conclusion for a different version of the system under test | no, results are pinned to the commit they were run against |

Anyone using output from this bench in an argument about someone's treatment should state
those limits alongside the numbers. This bench ranks options and finds failures, and a
trial is what decides.
