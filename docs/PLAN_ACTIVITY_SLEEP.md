# Plans for physical activity and sleep

Both are absent or nearly absent from the simulator, both are documented influences on glucose,
and neither can currently be calibrated against anything this project holds. That last point
comes first because it determines what the plans are: acquiring exposure data is the first step
in each, not an optional refinement.

## What is absent, and what is there now

Physical activity is implemented and switched off. It draws sessions from literature effect
sizes, raises glucose uptake while a session runs and leaves sensitivity elevated afterwards.
Run against the fidelity signatures it makes the population worse, taking the count inside the
reference range from eight of eleven to five and raising both autocorrelations away from their
ranges where lowering them was the purpose. Session timing has to be spread across waking
hours: concentrating 70 per cent of them at 17:30 give or take two hours makes every subject dip
at the same hour and raises the diurnal amplitude from 51.0 to 58.8 mg/dL. Spreading them
removes that artefact and does not make the layer worth switching on.

Sleep exists only as a window between 23:00 and 07:00 in which an infusion set failure goes
unnoticed. That single use is load bearing, since it produces the overnight hyperglycaemia the
trial shows and the simulator was missing, but nothing else in the package knows whether a
subject is asleep. The dawn phenomenon is implemented as a fixed diurnal shape on insulin
sensitivity, identical for every subject and every night.

## The data problem

No exposure data exists in any reference this project holds.

The DCLP3 public release has 50 data files and none of them records exercise or sleep.

The OpenAPS Data Commons export carries no heart rate or step field in any document, and it does
carry an exercise event type, used 117 times plus 22 activity-mode entries by 12 users across the
whole export. That is a handful of sessions each for a twentieth of the cohort, which is a record
that somebody occasionally logged exercise rather than a measurement of how much anybody did. It
is too sparse to calibrate against and too sparse to say the exposure is absent.

The Boost cohort cache carries `exercise_active` and `post_exercise_window` on every cycle, which
looked promising, and both are false on all 193,714 cycles across all 19 users, so the fields are
plumbed and never populated.

This is why the activity layer cannot be scored. A mechanism drawn from published effect sizes
and tested against records that do not contain the exposure is being asked to improve a
statistic it has no way to move for the right reason. That is the same failure the drift
signature work identified in a different place: a statistic that cannot detect the mechanism it
claims to measure is worse than no statistic, because it returns a verdict.

## Physical activity

### Step one, acquire exposure

Heart rate and step data would supply what is missing, and neither appears in any document of
the current export. The Boost tree already contains a Health Connect ingest path, so the
collection route exists on the device side. What is needed is
a cohort of users contributing that stream alongside the glucose and treatment records already
contributed, over a window long enough to contain a representative amount of activity. Anything
short of that leaves the layer uncalibratable, and the layer should stay off until it arrives.

### Step two, the question to ask first

Not how far glucose falls during exercise, which the literature already answers, but how much of
the between-subject variation this simulator lacks is attributable to activity. The population
carries about 45 per cent of the real between-subject spread in mean glucose, 6.0 to 6.8 mg/dL
against an implied 14.2. If activity accounts for a substantial share of the missing spread then
it earns its place on that ground alone, independently of whether it improves any individual
signature. If it does not, the layer is a realism claim with no measurable consequence and
should be documented as available and unjustified.

### Step three, the acceptance criterion, fixed in advance

The layer goes on if it moves the statistic it is built to move, in a paired comparison with the
same subjects and the same seed, with an interval excluding zero, under every driver tested; and
if the count of signatures inside their reference ranges does not fall. It is currently failing
the second of those, which is why it is off. Setting the criterion before the run is what stops
the layer being switched on because it helped one number.

## Sleep

Sleep is the better prospect of the two, because a large part of it can be characterised from
data already held.

### What can be done now

The hour-by-hour comparison against the trial already shows the deepest disagreement between
midnight and 04:00, where the trial sat at 35 and 25 per cent above 180 mg/dL and the simulator
at 13 and 11. Part of that is now attributed to overnight infusion set failures going unnoticed.
Whether the remainder is a sensitivity effect is answerable from the same records, by comparing
the overnight insulin requirement per unit of carbohydrate against the daytime one across the
Commons users, which needs no new stream.

Sleep timing is also inferable without a wearable. A person's last carbohydrate entry, last
manual interaction and first morning entry bound their night, and those are in the treatment
records already. That would replace the fixed 23:00 to 07:00 window with a per-subject
distribution, which matters because the window currently determines when nobody notices a failed
infusion set, and every subject is presently assumed to sleep at the same hours.

### What needs new data

The sensitivity change across the night, separated from the dawn phenomenon, needs either the
overnight requirement measurement above or a wearable-derived sleep stage, and the first is
cheaper and available. Sleep quality and its effect on next-day sensitivity needs a wearable and
is out of reach.

### The acceptance criterion

A per-subject sleep window replaces a constant, so it should be scored on the overnight
statistics specifically: the hour-by-hour profile against the trial between midnight and 04:00,
and the duration distribution of infusion set failures, which the window bounds. It should not
be scored on whole-run statistics, which it will barely move.

## Hormonal variation

Listed here because it is the third item and because it raises a measurement problem the other
two do not. The menstrual cycle moves insulin sensitivity by an amount the literature describes,
and it would affect roughly half the population. The multi-day correlated sensitivity component
already in the simulator currently represents that movement as noise rather than as structure.

The problem is period. A 28-day run contains one cycle, so any statistic computed over a run
cannot separate cycle phase from subject. Scoring the addition requires either longer runs or
runs aligned to phase, and until that is settled the mechanism cannot be tested even if it is
implemented correctly. That ordering should be respected: settle the measurement design first,
then build.

## Order of work

Sleep first, because the largest part of it is answerable from records already held and because
it bears directly on the infusion set detection that currently bounds how long a failure runs.

Activity second, and only after exposure data exists. The layer stays off until then, and the
reason it is off should be recorded as an absence of calibration data rather than as a finding
that activity does not matter.

Hormonal variation third, beginning with the measurement design rather than the mechanism.
