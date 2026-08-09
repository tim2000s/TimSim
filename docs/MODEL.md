# What is underneath: the UVA/Padova simulator

Everything in this package sits on a physiological model it did not write, and most of the
arguments in the other documents turn on what that model does and does not contain. This is
a description of it, taken from the equations as implemented in simglucose rather than from
the papers, so that it matches what actually runs here.

## Provenance

The model is a meal simulation model of the glucose-insulin system, developed at the
University of Padova and the University of Virginia. Its lineage runs through Dalla Man,
Rizza and Cobelli's 2007 description of the meal model, the type 1 adaptation used for in
silico trials, and a population of virtual subjects fitted to triple-tracer meal studies.

In January 2008 the type 1 version was accepted by the US Food and Drug Administration as a
substitute for animal testing in the preclinical evaluation of closed-loop control
algorithms. That acceptance is narrow and worth stating precisely: it licenses the simulator
as a stage before a trial, not as a substitute for one. Every safety claim in this package
inherits that limit.

Three releases matter, and they are usually written S2008, S2013 and S2017.

| Release | What it added |
|---|---|
| S2008 | the base meal model, time-invariant parameters, no counterregulation, single-meal scope |
| S2013 | glucagon kinetics, secretion and action, and a risk-index term that deepens hypoglycaemia |
| S2017 | intraday insulin sensitivity variation, a dawn phenomenon, diurnal basal and carbohydrate ratio |

**simglucose implements S2008.** Its parameter table carries 62 columns, none of them
glucagon, and its equations contain no counterregulation and no risk term. S2013 and S2017
are licensed and are not redistributable, which is why this package works from S2008 and
adds what it can defend on top. `timsim/patient/varying.py` reimplements S2017's
sensitivity variation in mechanism rather than in detail, and records what it does not have.

## The state

Thirteen states, integrated on a one-minute grid. In simglucose's ordering:

| | State | Meaning | Unit |
|---|---|---|---|
| x0 | Qsto1 | glucose in the stomach, solid | mg |
| x1 | Qsto2 | glucose in the stomach, liquid | mg |
| x2 | Qgut | glucose in the intestine | mg |
| x3 | Gp | glucose in plasma | mg/kg |
| x4 | Gt | glucose in tissue | mg/kg |
| x5 | Ip | insulin in plasma | pmol/kg |
| x6 | X | insulin action on utilisation, remote compartment | pmol/L |
| x7 | I1 | insulin signal for production, first delay | pmol/L |
| x8 | Id | insulin signal for production, second delay | pmol/L |
| x9 | Il | insulin in the liver | pmol/kg |
| x10 | Isc1 | subcutaneous insulin, first compartment | pmol/kg |
| x11 | Isc2 | subcutaneous insulin, second compartment | pmol/kg |
| x12 | Gs | subcutaneous glucose | mg/kg |

Two inputs: carbohydrate in grams, and insulin in units per minute. One output that anything
outside the model can see, which is `Gs`, the subcutaneous glucose the sensor reads. `Gp` is
the plasma glucose, and this package reports it as `Result.bg` because a safety metric should
read the truth rather than a reading.

## The four subsystems

### Meal absorption

Carbohydrate enters the stomach as solid, liquefies, passes to the intestine and is absorbed
into plasma:

    dQsto1/dt = -kmax*Qsto1 + D
    dQsto2/dt =  kmax*Qsto1 - kgut*Qsto2
    dQgut/dt  =  kgut*Qsto2 - kabs*Qgut
    Ra        =  f*kabs*Qgut/BW

The distinctive part is `kgut`, the gastric emptying rate, which is not a constant. It falls
from `kmax` to `kmin` and back as the stomach empties, through a pair of hyperbolic tangents
whose breakpoints sit at fractions `b` and `d` of the total dose:

    kgut = kmin + (kmax-kmin)/2 * [ tanh(a*(Qsto - b*Dbar)) - tanh(c*(Qsto - d*Dbar)) + 2 ]

So a large meal empties more slowly in the middle of its absorption than a small one, which
is what the tracer data shows and what a linear compartment cannot reproduce. `f` is the
fraction of ingested glucose that reaches plasma, fixed at 0.9 across the published cohort.

### Glucose kinetics

Two compartments, plasma and tissue, exchanging at `k1` and `k2`:

    dGp/dt = max(EGP,0) + Ra - Uii - E - k1*Gp + k2*Gt
    dGt/dt = -Uid + k1*Gp - k2*Gt

with three sinks. `Uii` is insulin-independent utilisation, a constant `Fsnc` of 1 mg/kg/min,
which is roughly the brain. `E` is renal excretion, zero until plasma glucose passes the
threshold `ke2` and linear in `ke1` above it. `Uid` is insulin-dependent utilisation, and it
is the one that matters:

    Uid = (Vm0 + Vmx*X) * Gt / (Km0 + Gt)

Saturating in glucose and linear in insulin action. The saturation is why a given dose of
insulin does more work at a high glucose than at a low one: measured across the ten published
adults, one unit moves a settled subject 12.6 mg/dL from basal and 23.4 mg/dL from 300.

### Endogenous glucose production

    EGP = kp1 - kp2*Gp - kp3*Id,   floored at zero

Three terms, and the middle one is easy to overlook. `kp1` is the intercept, set by closure
so that production balances disposal at the subject's basal state. `kp3*Id` is insulin
suppressing the liver, acting through a doubly-delayed insulin signal rather than plasma
insulin directly, which is why hepatic suppression lags a bolus. And `-kp2*Gp` is glucose's
own negative feedback on production: as plasma glucose falls, the liver produces more.

That term is a hepatic autoregulation, and it is stronger than the people the model
represents. Measured on the published adults, production on crossing 54 mg/dL is 2.60
mg/kg/min against a basal of 2.36, so it rises. Rickels et al. measured 0.59 mg/kg/min in
long-standing type 1 diabetes at a 45 mg/dL clamp, flat against euglycaemia. This is why
adding counterregulation to this model would move it away from its own population rather
than towards it, and `docs/FIDELITY.md` sets out that argument in full.

### Insulin kinetics

Delivery enters the first subcutaneous compartment. From there insulin either reaches plasma
directly at `ka1` or passes to a second compartment at `kd` and reaches plasma at `ka2`:

    dIsc1/dt = u - (ka1+kd)*Isc1
    dIsc2/dt = kd*Isc1 - ka2*Isc2
    dIp/dt   = -(m2+m4)*Ip + m1*Il + ka1*Isc1 + ka2*Isc2
    dIl/dt   = -(m1+m30)*Il + m2*Ip

Plasma and liver exchange at `m1` and `m2`, with clearance `m4` peripherally and `m30`
hepatically. Two downstream signals are derived from plasma insulin concentration `I = Ip/Vi`:

    dX/dt  = -p2u*X + p2u*(I - Ib)          action on utilisation
    dI1/dt = -ki*(I1 - I)                   action on production, first delay
    dId/dt = -ki*(Id - I1)                  second delay

`X` drives `Uid`, `Id` suppresses `EGP`. The two delays are what give hepatic suppression a
slower onset than peripheral uptake.

### Subcutaneous glucose

    dGs/dt = -ksc*Gs + ksc*Gp

A single first-order lag. This is the whole interstitial model: no drift, no calibration
error, no compression. Everything a real sensor does beyond lagging is added by this package
in `timsim/sensor/realism.py`, and the difference matters because the lag alone understates
how long a severe low appears to last.

## The subjects

30 published virtual subjects in simglucose, ten each of adult, adolescent and child, as 62
columns of parameters. They are fitted individuals rather than samples from a distribution,
and the full simulator ships 300.

Of the 62 columns, two are identifiers and 60 are parameters. Only 29 of those are
independent. Eleven are constant across the whole published cohort, including `f` at 0.9,
`Fsnc` at 1 and the renal threshold `ke2` at 339, and the remaining 20 are fixed exactly by
the model's own balance equations at the basal steady state: plasma glucose mass from concentration, tissue glucose from the glucose
balance, `Vm0` scaled so utilisation meets basal disposal, `u2ss` set to the infusion that
holds it, `kp1` set so production balances, and so on. `timsim/population/derive.py` writes
those relations out and reproduces all thirty published subjects from their free parameters
to a worst relative residual of 5e-12, which is what makes generating new subjects
tractable: sample 29 numbers, close the other 20, then screen.

Nine of the 20 are the initial state itself, which is the point. A published subject is
shipped sitting exactly at its own basal steady state, and the runner opens at that
subject's scheduled basal rather than at zero for the same reason.

A consequence worth carrying: a subject is a self-consistent steady state, and any change to
a parameter that does not re-close the others produces a person who drifts.

## What the model does not contain

No counterregulation of any kind in S2008. No glucagon. A subject going low here is defended
by carbohydrate, by insulin decaying, and by the `-kp2*Gp` term, and by nothing else.

No exercise, no illness, no alcohol, no stress. No infusion site behaviour: insulin delivered
is insulin absorbed, which is why `timsim/therapy/site.py` sits outside the equations as a
multiplier rather than inside them.

Time-invariant parameters in S2008. The same subject on the same day responds identically
every time, which is what this package's physiology layer exists to break.

The scope was a single meal. S2017's paper is titled for going from single meal to single
day, which is a fair indication of how far a 28-day run stretches the original design.

## Where this package attaches

Nothing here modifies the differential equations. The layers act on the model's inputs and
outputs, and on the parameters between steps:

| Layer | Where it acts |
|---|---|
| `physiology` | scales `Vmx` and `kp3` between steps, which is what S2017 varies |
| `behaviour` | supplies the carbohydrate input and decides what the algorithm is told about it |
| `sensor` | transforms the `Gs` output before anything sees it |
| `site` | multiplies the insulin input before it reaches `Isc1` |

The pump ceilings in `timsim/therapy/limits.py` sit in front of the insulin input, and the
controller sits outside the model entirely, as it does in simglucose's own composition:
`T1DSimEnv(patient, sensor, pump, scenario)` with the controller passed separately.

## References

Dalla Man C, Rizza RA, Cobelli C. Meal simulation model of the glucose-insulin system.
IEEE Transactions on Biomedical Engineering 2007;54(10):1740-1749.

Kovatchev BP, Breton M, Dalla Man C, Cobelli C. In silico preclinical trials: a proof of
concept in closed-loop control of type 1 diabetes. Journal of Diabetes Science and
Technology 2009;3(1):44-55.

Dalla Man C, Micheletto F, Lv D, Breton M, Kovatchev B, Cobelli C. The UVA/PADOVA type 1
diabetes simulator: new features. Journal of Diabetes Science and Technology
2014;8(1):26-34.

Visentin R, Campos-Nanez E, Schiavon M, Lv D, Vettoretti M, Breton M, Kovatchev BP, Dalla
Man C, Cobelli C. The UVA/Padova type 1 diabetes simulator goes from single meal to single
day. Journal of Diabetes Science and Technology 2018;12(2):273-281.

Visentin R, Dalla Man C, Kovatchev B, Cobelli C. The university of Virginia/Padova type 1
diabetes simulator matches the glucose traces of a clinical trial. Diabetes Technology and
Therapeutics 2014;16(7):428-434.

Rickels MR, Peleckis AJ, Markmann E, et al. Restoration of glucose counterregulation by
islet transplantation in long-standing type 1 diabetes. Diabetes 2015;64(5):1713-1718.

Xie J. simglucose: a type 1 diabetes simulator implemented in Python for reinforcement
learning purposes. https://github.com/jxx123/simglucose
