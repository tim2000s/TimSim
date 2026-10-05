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
| Dalla Man C, Micheletto F, Lv D, Breton M, Kovatchev B, Cobelli C. The UVA/Padova type 1 diabetes simulator: new features. *Journal of Diabetes Science and Technology* 2014;8(1):26–34. PMID 24876534 | Intraday and interday insulin sensitivity variation, and equation A10, which is the risk-modulated insulin action term | `patient/varying.py` | complete |
| Visentin R et al. Improving efficacy of inhaled technosphere insulin. *Diabetes Technology and Therapeutics* 2014;16(7):428–434 | Referenced in the S2013 lineage | `docs/MODEL.md` | complete |
| Visentin R, Dalla Man C, Kudva YC, Basu A, Cobelli C. Circadian variability of insulin sensitivity: physiological input for in silico artificial pancreas. *Diabetes Technology and Therapeutics* 2015;17(1):1–7 | The seven-class diurnal sensitivity model offered as an alternative to the common cosine, and the continuous glucose error grid comparison in which S2008 reads 40.7 per cent of hypoglycaemic values accurately against S2013's 85.9 | `patient/varying.py`, `si_pattern="visentin"` | complete |
| Hinshaw L, Dalla Man C, Nandy DK, Saad A, Bharucha AE, Levine JA, Rizza RA, Basu R, Carter RE, Cobelli C, Kudva YC, Basu A. Diurnal pattern of insulin action in type 1 diabetes: implications for a closed-loop system. *Diabetes* 2013;62(7):2223–2229. PMID 23447123 | Postprandial insulin sensitivity at breakfast, lunch and dinner in nineteen subjects, which the diurnal shape is set against | `patient/varying.py` | complete |
| Hinshaw L, Mallad A, Dalla Man C et al. Glucagon sensitivity and clearance in type 1 diabetes: insights from in vivo and in silico experiments. *American Journal of Physiology: Endocrinology and Metabolism* 2015;309(5):E474–E486. PMID 26152766 | Glucagon action parameters, and the separation of the glucagon and catecholamine arms of counterregulation by timescale | `patient/varying.py` | complete |

## Physiology the package calibrates against

| Reference | What it supplies | Where | Citation |
|---|---|---|---|
| Rickels MR et al. *Diabetes* 2015;64(5):1713–1718 | Endogenous glucose production of 0.59 ± 0.12 mg/kg/min at a hypoglycaemic clamp plateau in twelve people with long-standing type 1 diabetes and no glucagon response. The hepatic defence gain is fitted to this and to nothing else | `patient/varying.py`, `examples/calibrate_hypo_defence.py` | complete |
| Kovatchev BP, Cox DJ, Gonder-Frederick LA, Clarke W. Symmetrization of the blood glucose measurement scale and its applications. *Diabetes Care* 1997;20(11):1655–1658 | The Low Blood Glucose Risk Index: exponent 1.084, scale 1.509, threshold 60 mg/dL. Used both as a safety statistic and as S2013's risk function | `analysis/safety.py`, `patient/varying.py` | complete |

## Behaviour

The behaviour layer is the part with the least direct grounding, and these four are what it has.

| Reference | What it supplies | Where | Citation |
|---|---|---|---|
| Brazeau AS, Mircescu H, Desjardins K, Leroux C, Strychar I, Ekoé JM, Rabasa-Lhoret R. Carbohydrate counting accuracy and blood glucose variability in adults with type 1 diabetes. *Diabetes Research and Clinical Practice* 2013;99(1):19–23. PMID 23146371 | Carbohydrate counting error at 15 to 25 per cent of the meal | `person/behaviour.py` | complete |
| Meade LT, Rushton WE. Accuracy of carbohydrate counting in adults. *Clinical Diabetes* 2016;34(3):142–147. PMID 27621531 | A different quantity: error on a food-model portion test (82 per cent overestimated, by 40 per cent when they did), not error on real meals | `person/behaviour.py` | complete |
| Roversi C, Vettoretti M, Del Favero S, Facchinetti A, Sparacino G. Modeling carbohydrate counting error in type 1 diabetes management. *Diabetes Technology and Therapeutics* 2020;22(10):749–759 | Error in 692 real meals from 50 adults, measured against a dietitian's estimate; it grew with meal size and large meals were mostly underestimated | `person/behaviour.py` | complete |
| Savard V, Gingras V, Leroux C et al. Treatment of hypoglycemia in adult patients with type 1 diabetes: an observational study. *Canadian Journal of Diabetes* 2016;40(4):318–323. PMID 27373433 | Rescue carbohydrate in practice exceeding the fifteen gram rule, which is why the simulated helping is drawn rather than fixed | `person/behaviour.py` | complete |

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
| CLOSE-IT | The meal announcement comparison, and the only randomised population running the same algorithm family as the Commons. Time in range alone, as a mean and a standard deviation per arm: 69 ± 13 per cent announced and 66 ± 8 unannounced, adjusted difference -2.2 (95% CI -6.2 to 1.7), across 75 adults. Time below 70, time below 54, time above 180 and mean glucose are not reported for either arm, and there is no per-participant data | published summaries |

## The trial publications

The two datasets have papers, and the package cited neither. Both are now verified.

| Reference | What it is |
|---|---|
| Brown SA, Kovatchev BP, Raghinaru D et al. Six-month randomized, multicenter trial of closed-loop control in type 1 diabetes. *New England Journal of Medicine* 2019;381(18):1707–1717. PMID 31618560, ClinicalTrials.gov NCT03563313 | DCLP3, the trial the primary reference population comes from |
| Fabricius TW et al. Counterregulatory hormone and symptom responses to hypoglycaemia in people with type 1 diabetes, insulin-treated type 2 diabetes or without diabetes: the Hypo-RESOLVE hypoglycaemic clamp study. *Acta Diabetologica* 2024;61(5):623–633. PMID 38376580 | The measured glucagon response to hypoglycaemia in type 1 diabetes, 9.4 pmol/L (SE 0.8) across 47 participants against 30.6 (SE 4.7) in 16 controls at a 2.8 mmol/L clamp. Not yet used; it is the calibration target a secretion model would need |
| Wilkinson TJ et al. Study protocol for a randomised open-label clinical trial examining the safety and efficacy of the Android Artificial Pancreas System (AAPS). *BMJ Open* 2024;14(2):e078171 | CLOSE-IT, the protocol. The results exist as a conference presentation at ATTD 2025 and not as a paper, so every CLOSE-IT figure quoted here traces to an abstract. That is weaker provenance than any other reference in this table and the figures carry it |

## Corrections found while verifying

Three entries were wrong rather than merely incomplete, and the package repeats each of them at
the point where the mechanism is implemented.

Hinshaw et al. 2015 is in the *American Journal of Physiology: Endocrinology and Metabolism*,
not *Diabetes* as `patient/varying.py` states. It reports 29 participants and publishes glucagon
action parameters numerically, and it publishes no secretion model, which is consistent with what
the package says about the asymmetry it ships.

The Visentin reference behind the seven-class diurnal sensitivity model is the 2015 circadian
variability paper in *Diabetes Technology and Therapeutics*, with twenty subjects. It is
sometimes conflated with Visentin et al., One-day Bayesian cloning of type 1 diabetes subjects,
*IEEE Transactions on Biomedical Engineering* 2016;63(11):2416–2424, which is a different paper
about single-day cloning and is not what the diurnal classes come from.

Roversi et al. 2020 is Modeling carbohydrate counting error in type 1 diabetes management, not
the 2022 in silico trial by the same group in the *Journal of Diabetes Science and Technology*,
which builds on it.
