# TimSim: what it is, how it works, and what it is for

A person built on top of a metabolic model, so that an insulin delivery algorithm can be run
against something that eats without saying so, treats its own lows, and wears a sensor that
lies.

## What it is built on

The metabolic model is the UVA/Padova S2008 virtual patient, reached through simglucose. S2013
and S2017 are licensed and not redistributable, so everything here works from S2008 and adds
what it can defend from published sources. The population is 100 subjects generated locally
from the published parameter tables and screened for steady-state consistency; it is not
committed, so nothing derived from those tables is redistributed.

The load-bearing check on the generation is
`tests/test_population.py::test_closure_reproduces_every_published_subject`, which requires the
steady-state relations to reproduce all thirty published subjects. A failure there invalidates
every generated subject.

## The three parts, and why they are kept apart

A run contains a person, a rig and a controller, and keeping them separate is what makes any
result attributable.

The person is the metabolic model plus four layers. Physiology varies insulin sensitivity
through the day, from day to day and across runs of days, and defends glucose production
against insulin as glucose falls. Behaviour eats on a drawn schedule, announces imperfectly and
treats its own lows with a drawn helping. The sensor carries error, quantisation and compression
artefacts, inside the loop rather than applied afterwards, so an algorithm sees them and so does
the simulated person. The infusion site fails quietly and gets noticed late.

The rig is the sensor, the pump and the delivery limits, which sit between the person and the
algorithm and distort what each knows about the other. Delivery is quantised to the nearest
deliverable increment rather than rounded down, because rounding down under-delivers on every
cycle and pushes every subject off its steady state in the same direction.

The controller is whatever is dosing, and it is not part of the person. Four are available: an
open-loop regimen with meal boluses, a built-in correction loop, and two systems compiled from
their own source and driven across a process boundary, Boost through a JVM and oref0 SMB through
node. Neither gathered copy is redistributed.

## What the layers add, measured

Each layer is answerable to the statistic it was built to move, with the same statistic measured
with the layer off. The counterregulatory defence of glucose production is calibrated against a
stepped hyperinsulinaemic clamp reproduced in silico rather than against an outcome, because a
figure for glucose production is uninterpretable without the insulin it was read at: the same
model reports 1.28 mg/kg/min during spontaneous lows and 0.14 at a clamped 55 mg/dL plateau.
`examples/hypoglycaemic_clamp.py` runs the protocol.

Holding a controller fixed and varying the bench, both controllers tested move the same way:
mean glucose rises about 19 mg/dL, time above 180 mg/dL roughly doubles, variability rises and
delivered insulin rises. Three of those four move the population towards a real cohort's central
tendency and variability overshoots.

## Running something against it

Four rules, each of which cost a wrong answer to learn. They are set out with their measurements
in `docs/METHODS.md`.

Titrate the settings first. A subject's correction factor computed from its own model is not
what a real person carries, and handing an algorithm the derived value doubles its time below 70
mg/dL. `examples/titrate_cohort.py` weakens each subject until its own record clears the
consensus hypoglycaemia limits, basal before the correction factor, and
`therapy/titrate.py::profile_for` raises rather than falling back.

Match the target to the comparison, and the reference population to the algorithm. The target is
the largest configuration effect measured, worth 4.82 percentage points of time below 70 mg/dL
with an interval of 1.34. The two real references disagree by more than either differs from the
simulation.

Hold everything else and pair per subject. `analysis/cohort.py::paired_subjects` restricts a
comparison to the subjects completing every arm and raises rather than comparing arms over their
own survivors.

Report why runs ended. `Result.termination` records direction, day, glucose extremes, recent
insulin and whether the infusion site was still failing, because a completion count averages a
hypoglycaemia failure with a hyperglycaemia one.

## Configuring an algorithm the way its users are configured

An algorithm whose dosing is co-adapted with its user cannot be judged on factory defaults.
`controller/boost_autoconfig.py` ports that algorithm's own onboarding derivation, which sizes
every knob from a fortnight of the user's history. A subject has no history, so one is generated
by running a different loop for the same fortnight, which keeps the configuration from being
derived from the thing it configures. Configured that way rather than at defaults, that
algorithm delivers 10 U a day more and drops 5.3 points of time above 180 mg/dL.

## What the person can be told about a meal

`announcement` takes `always`, `some` or `never`. The middle one is what real records show and
is the default. The other two are experimental conditions: `always` is the lineage an algorithm's
configuration is derived from, and `never` is the condition meal-detecting algorithms claim to
handle. All three consume the person's generator identically, so they are one run under three
treatments.

Under every condition the true carbohydrate reaches the gut and the announced figure reaches the
algorithm, and the two differ by the estimate error, by every unannounced meal and by every
rescue helping. Nothing is pre-bolused and no user bolus exists, which is how a meal-detecting
algorithm is meant to be run.

## What it can be used for

A pre-clinical gate, in the sense the UVA/Padova simulator was accepted for in 2008: fix the
acceptance criteria before the run, run the cohort, and report whether anything trips them. That
substitutes for animal testing ahead of a trial and not for the trial.

Surfacing a failure mode is the stronger use, because a failure found this way is a
demonstration rather than an estimate.

Four things it cannot support. Certifying a system as safe, or pricing a settings change for an
individual. Any absolute outcome quoted without its settings provenance, its target and its
reference, since across four configurations of one unmodified algorithm time below 70 mg/dL
spans 2.75 to 7.61 per cent while two algorithms on a fixed configuration differ by 3.37. Any
claim resting on between-subject variation in sensor behaviour, which is far narrower than real
people's. And any claim about how hard a particular subject defends a low, since glucose
production at a hypoglycaemic plateau ranges from nothing to three times the human figure.

## Where the numbers come from

Real comparisons use the OpenAPS Data Commons, 221 users with a usable 28-day window, and the
DCLP3 trial, of which 40 per cent is held back unopened. `docs/CAPABILITY.md` sets out what the
simulator matches and what it does not, `docs/FIDELITY.md` the signature work, `docs/LADDER.md`
the layer attribution, and `docs/VALIDATION.md` what any of it can be believed for.
