# How closely does this match real data, and where does it fail

This is level 3 of the six in [VALIDATION.md](VALIDATION.md), and on its own it is the
weakest of them. Matching the marginal statistics of real data says nothing about whether
the response to an intervention is right. Read it alongside levels 4 and 5, which are what
a controller comparison actually rests on.

## The measurement

Eleven statistics, computed identically on simulator output and on real continuous glucose
data. The real reference is the envelope across four cohorts of closed-loop users, 192
people, taken as the minimum and maximum of the four cohort medians. Each simulator figure
is the median across the first ten adult subjects, run for 28 days.

Each column adds one mechanism to the column before it, so a movement is attributable to a
named cause rather than to the bundle.

| Signature | Real range | stock 2008 | +physiology | +behaviour | +loop | +sensor | In range |
|---|---|---|---|---|---|---|---|
| Glucose variability (CV%) | 29.5–34.3 | 30.7 | 31.5 | 39.5 | 33.1 | 33.2 | yes |
| Rise tail P(ΔBG>10/5min) % | 3.7–6.6 | 2.7 | 2.6 | 3.7 | 4.2 | 5.1 | yes |
| Autocorrelation @30min | 0.78–0.87 | 0.91 | 0.92 | 0.92 | 0.86 | 0.85 | yes |
| Autocorrelation @60min | 0.50–0.68 | 0.77 | 0.79 | 0.79 | 0.59 | 0.59 | yes |
| Outcome SD @stuck-high (mg/dL) | 26.5–33.5 | 21.2 | 20.6 | 23.1 | 25.5 | 25.5 | marginal |
| Diurnal amplitude (mg/dL) | 34.7–56.3 | 82.0 | 73.7 | 54.3 | 49.0 | 49.5 | yes |
| Hypo recovery to 100 (min) | 50–59 | 106 | 108 | 68 | 63 | 60.0 | marginal |
| Hypo rebound >180 % | 23.2–28.4 | 0.0 | 26.8 | 51.3 | 64.8 | 58.5 | no |
| Compression lows /30d | 1.9–5.3 | 0.0 | 0.0 | 0.5 | 0.5 | 5.4 | yes |
| Sensor jitter (mg/dL) | 4.5–6.7 | 2.4 | 2.4 | 2.4 | 2.4 | 5.3 | yes |
| ISF drift (weekly %CV) | 8.2–21.7 | 0.0 | 0.0 | 14.5 | 4.0 | 4.0 | no |

One of eleven for the bare subjects, seven of eleven with all four layers, plus two that
miss by a hair: outcome spread at 25.5 against a padded lower bound of 25.8, and hypo
recovery at 60.0 against 59.9. Those two are called marginal rather than counted, but they
are a fraction of a unit away and should not be read as failures.

Reproduce with `python examples/layer_ablation.py`, about an hour serially; `--arm` runs one
column so the five can go in parallel. Raw output in `docs/*.json`.

## Reading it

The layers do different work and the split is clean.

The physiology layer moves the physiology-linked statistics and nothing else. Variability
edges up, the diurnal amplitude comes down from a very high 82 towards the real range, and
hypoglycaemia rebound appears for the first time at 26.8%, inside the real range, because
varying sensitivity produces lows the fixed-parameter subjects never had. The disturbance
statistics do not move at all. That is the measured version of a general point worth
internalising before reaching for a more refined model: refining the differential equations
fixes the statistics that depend on the differential equations.

The behaviour layer supplies the disturbances. Rescue carbohydrate takes hypoglycaemia
recovery from 108 minutes to 68 against a real 50 to 59. An adapting setting takes drift
from a structural zero to 14.5%, inside the real range. Unannounced meals take the rise
tail from 2.6 to 3.7, into range, and this time it is genuinely the meals: the sensor layer
adds a further 0.9 on top, but the crossing happens before the sensor is involved.

The loop layer supplies the damping. Every added disturbance had left both autocorrelations
above the real range, because nothing was correcting anything, and continuous correction
brings both inside: 0.92 to 0.86 at thirty minutes and 0.79 to 0.59 at sixty. Variability
settles from an overshoot of 39.5 to 33.1 rather than running away. This was missing from
the comparison rather than from the model: every real cohort here is running automated
insulin delivery, and the simulated person was on open-loop basal-bolus.

The sensor layer closes the two sensor statistics, as it is the only layer that can.

## The three that did not come right

They are reported rather than tuned away, which matters, because fitting a parameter to a
statistic turns that row from a test into a restatement.

**Hypoglycaemia rebound overshoots badly**, 58.5% against a real 23 to 28, and it gets
worse when the loop is added rather than better. The assumption that a person takes a
second helping on 35% of rescues is too aggressive for what these cohorts do. Read as a
measurement rather than a failure, it says real closed-loop users over-treat less, or are
mopped up more, than the standard clinical account of over-treatment implies. One parameter
would close this row and it has deliberately not been touched. The practical consequence:
an algorithm judged here on how it handles rebound highs is being judged on a harsher world
than the real one.

**Sensitivity drift falls below range** once the loop is added, 14.5% to 4.0% against a
real 8.2 to 21.7. The loop holds glucose closer to target, so the weekly adaptation has
less error to chase. Real drift is partly physiological rather than purely a response to
outcomes, and this adapter only responds to outcomes.

**Outcome spread at stuck-high** is the one that matters, and it is now close. It moved from
21.2 to 25.5 mg/dL against a real 26.5 to 33.5, having sat at 21.0 before the therapy
settings were corrected. Most of that improvement came from a fix found at level 2 rather
than from anything aimed at this statistic. It is now a fraction outside rather than
comfortably outside, which is a change of degree and not of kind: the spread of where
glucose ends up half an hour after a stuck high is precisely the quantity a dosing decision
bets on, and the simulator is still on the confident side of real. Treat this as improved
and unresolved.

## Survival

simglucose ends an episode when blood glucose falls below 10 mg/dL, so a truncated series
means the virtual subject did not survive. This is easy to miss, because the analysis is
handed whatever series it is given, and any comparison that silently drops incomplete runs
is conditioning on survival.

In the table above the physiology layer alone loses **three of ten subjects** over 28 days.
Every other arm completes ten of ten. The reason is not subtle: varying insulin sensitivity
produces days on which the subject needs much less insulin than it is getting, and a virtual
patient with no carbohydrate to eat and no loop to withdraw insulin has nothing to stop the
resulting low. Adding either the behaviour layer or the loop restores full survival.

That is worth stating as a finding rather than a footnote. A more refined physiology made
the population less survivable, and only the person and the loop made it viable again.

`Result.completed` records this per subject and `examples/fidelity_check.py` reports it.

## What changed these numbers, and why that is the point

An earlier version of this table was materially worse: three fewer statistics in range, and
outcome spread at 21.0 rather than 25.5. Two defects were behind it, and neither was
visible at this level.

The first was found at level 2. Carbohydrate ratios and correction factors were drawn from
the published cohort's distribution conditioned on body weight and basal rate. The published
subjects respond at 1.10 times their stated correction factor; the generated ones came out
at 0.63, so every generated subject was being dosed on somebody else's settings on every
cycle of every run. Settings are now measured from each subject's own model.

The second was found by a level 1 check that was itself wrong twice before it was right.
Every run opened with a zero-insulin step, inherited from simglucose's own examples, which
kicked each subject off the steady state its parameters were closed at and left a slow ring
through the first days. Runs now open at the subject's own basal, and a quiet subject holds
its fasting glucose to within 0.02 mg/dL over four days.

Neither would have been caught by looking at this table. That is the argument for the
graded structure in [VALIDATION.md](VALIDATION.md): distributional fidelity is a
consequence of getting the mechanics right, not a substitute for checking them.

## What the population does and does not add

The 100 subjects are drawn from the joint distribution of the 30 published subjects, so
they are a resampling of that cohort rather than new clinical data. They inherit whatever
the published cohort does not represent, and they carry no independent information about
human variability.

What they add is resolution, and it is quantified at level 5: the design resolves about 1.8
percentage points of time in range across 34 adults and about 1.0 across all 100.

## Provenance of the parameters

No parameter in the behaviour layer was fitted to any statistic in the table above.
Announcement rates, carbohydrate-counting error and rescue-treatment sizes are clinical
literature figures or explicit modelling choices, recorded with their reasoning in
`timsim/person/behaviour.py`. The sensor layer's two parameters were fitted, on a different
cohort from the one they are evaluated against, and that is stated in
`timsim/sensor/realism.py`.
