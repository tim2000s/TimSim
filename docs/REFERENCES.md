# References

Every published source this package draws a number, a mechanism or a threshold from, with what
it is used for and where it enters the code. Assembled from the citations in the source and the
documentation, so it records what the package actually rests on rather than a reading list.

The completeness column is there because several sources are cited by author and year alone.
Those need checking against the originals before they go into anything for publication, and the
gap is marked rather than filled from memory.

## The model lineage

The simulator underneath is the UVA/Padova type 1 patient as implemented by simglucose, which is
the 2008 release. Two later releases are licensed and not redistributable, so what this package
implements of them is a mechanism rather than a version, and `patient/varying.py` says so at the
point where each one enters.

| Reference | What it supplies | Where | Citation |
|---|---|---|---|
| Dalla Man C, Rizza RA, Cobelli C. Meal simulation model of the glucose-insulin system. *IEEE Transactions on Biomedical Engineering* 2007;54(10):1740–1749 | The meal model every simulated minute runs on, and the balance equations `population/derive.py` closes new subjects against | `population/derive.py` | complete |
| Kovatchev BP, Breton M, Dalla Man C, Cobelli C. In silico preclinical trials: a proof of concept in closed-loop control of type 1 diabetes. *Journal of Diabetes Science and Technology* 2009;3(1):44–55 | The simulator as a preclinical instrument, and its acceptance by the US Food and Drug Administration in January 2008 as a substitute for animal trials | `docs/MODEL.md` | complete |
| Dalla Man C et al. The UVA/Padova type 1 diabetes simulator: new features. *Journal of Diabetes Science and Technology* 2014 | Intraday and interday insulin sensitivity variation, and equation A10, which is the risk-modulated insulin action term | `patient/varying.py` | volume and pages missing |
| Visentin R et al. Improving efficacy of inhaled technosphere insulin. *Diabetes Technology and Therapeutics* 2014;16(7):428–434 | Referenced in the S2013 lineage | `docs/MODEL.md` | complete |
| Visentin R, Dalla Man C, Cobelli C. One-day Bayesian cloning of type 1 diabetes subjects. 2015 | The seven-class diurnal sensitivity model offered as an alternative to the common cosine, and the continuous glucose error grid comparison in which S2008 reads 40.7 per cent of hypoglycaemic values accurately against S2013's 85.9 | `patient/varying.py`, `si_pattern="visentin"` | journal and pages missing |
| Hinshaw L et al. *Diabetes* 2013 | Postprandial insulin sensitivity at breakfast, lunch and dinner in nineteen subjects, which the diurnal shape is set against | `patient/varying.py` | volume and pages missing |
| Hinshaw L et al. *Diabetes* 2015 | Glucagon action parameters, and the separation of the glucagon and catecholamine arms of counterregulation by timescale | `patient/varying.py` | volume and pages missing |

## Physiology the package calibrates against

| Reference | What it supplies | Where | Citation |
|---|---|---|---|
| Rickels MR et al. *Diabetes* 2015;64(5):1713–1718 | Endogenous glucose production of 0.59 ± 0.12 mg/kg/min at a hypoglycaemic clamp plateau in twelve people with long-standing type 1 diabetes and no glucagon response. The hepatic defence gain is fitted to this and to nothing else | `patient/varying.py`, `examples/calibrate_hypo_defence.py` | complete |
| Kovatchev BP et al. Symmetrization of the blood glucose measurement scale and its applications. *Diabetes Care* 1997 | The Low Blood Glucose Risk Index: exponent 1.084, scale 1.509, threshold 60 mg/dL. Used both as a safety statistic and as S2013's risk function | `analysis/safety.py`, `patient/varying.py` | volume and pages missing |

## Behaviour

The behaviour layer is the part with the least direct grounding, and these four are what it has.

| Reference | What it supplies | Where | Citation |
|---|---|---|---|
| Brazeau AS et al. Carbohydrate counting accuracy and blood glucose variability in adults with type 1 diabetes. 2013 | Carbohydrate counting error at 15 to 25 per cent of the meal | `person/behaviour.py` | journal and pages missing |
| Meade LT, Rushton WE. Accuracy of carbohydrate counting. 2016 | The same quantity, independently | `person/behaviour.py` | journal and pages missing |
| Roversi C et al. 2020 | A comparable spread inferred from continuous glucose data rather than from logs | `person/behaviour.py` | journal and pages missing |
| Savard V et al. 2016 | Rescue carbohydrate in practice exceeding the fifteen gram rule, which is why the simulated helping is drawn rather than fixed | `person/behaviour.py` | journal and pages missing |

## Clinical targets

| Reference | What it supplies | Where | Citation |
|---|---|---|---|
| Battelino T et al. Clinical targets for continuous glucose monitoring data interpretation: recommendations from the international consensus on time in range. *Diabetes Care* 2019;42(8):1593–1603 | Time below 54 mg/dL under 1 per cent and below 70 under 4, which are the gates titration acts on and the criteria the safety gate scores | `therapy/titrate.py`, `validation/gate.py` | complete |

## Reference populations

These are datasets rather than papers, and each is used at the level of individual records
rather than published summaries, except CLOSE-IT.

| Source | What it supplies | Access |
|---|---|---|
| DCLP3, the third international diabetes closed loop trial | 112 closed-loop participants running Control-IQ, split into a calibration half of 67 and a sealed held-out half. The primary reference for time in range, hypoglycaemia, the hour-by-hour hyperglycaemia profile, and the recorded pump settings that give a real correction factor median of 40.0 mg/dL per unit | requested from the trial group; `DCLP3_DIR` |
| OpenAPS Data Commons, April 2026 export | 240 user directories, of which 131 carry a readable glucose series, 103 hold a 28-day window at adequate coverage, and 71 of those also hold pump records. Supplies the oref-family reference population, the real uncovered meal responses, and the reconstructed daily insulin requirement cohorts are matched on | requested from the Commons |
| CLOSE-IT | The meal announcement comparison. Published summaries only, since the trial releases no per-participant data, so it supports a mean and a standard deviation and no per-person spread | published summaries |

## What needs completing before publication

Nine of the sixteen entries above are missing a journal, a volume or a page range. They are
marked in place, and they should be completed against the originals rather than from memory.

One gap is larger than a missing page number. DCLP3 is referenced throughout the package as a
dataset and its trial publication is cited nowhere in the source, although it is the primary
reference population for the whole validation argument. The paper is Brown SA et al., Six-month
randomized, multicenter trial of closed-loop control in type 1 diabetes, *New England Journal of
Medicine* 2019;381(18):1707–1717, and that reference has not been verified against the original
here. Any paper drawing on this work should cite the trial rather than only the data.
