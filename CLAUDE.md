# TimSim

A person-in-the-loop layer over the UVA/Padova virtual patient in simglucose, plus a
generated population of 100 screened subjects. See `README.md` for what it does and
`docs/VALIDATION.md` for what any of it can be believed for.

## Writing style

This matters as much as the code. The documentation makes claims about a medical
simulator, and prose that reads as machine-generated undermines claims that are otherwise
carefully measured. Every rule below applies to README files, the docs directory, module
and function docstrings, comments, and commit messages. They apply equally to anything
written for the reader rather than for the repository: reports, papers, summaries and
notes shared outside it.

The register is scientific. Write as a methods and results section would be written: state
what was done, what was measured, and what follows, in the past tense for work done and the
present for what the code does. Quantities carry units and an interval where one exists. A
claim that cannot be traced to a measurement or a citation does not belong in the text, and
where something is a modelling choice rather than a finding, say so in the sentence that
makes it.

Stay calm. The tone is that of someone reporting a result they expect to be checked,
without enthusiasm and without hedging into vagueness. Negative results are reported in the
same voice as positive ones.

Do not use em-dashes or en-dashes in prose. Rewrite the sentence with a comma, a colon,
a full stop or brackets. En-dashes are fine inside numeric ranges in tables.

Do not bold text for emphasis in running prose. Bold belongs in table headers and nowhere
else. A sentence that needs bold to land needs rewriting.

Do not write in threes. Rule-of-three constructions are the strongest tell there is, in
lists, in clauses and in adjectives. Use two items or four, or restructure into a table or
separate sentences.

Do not use conditional-imperative constructions, meaning "if X then Y must happen" or "if
you do X, Y will follow". Say what happens, or say what to do, without the scaffolding.

Do not sensationalise. Avoid dramatic closing lines, avoid "the honest limit", avoid "that
is the point", avoid declaring something "exactly" the case. State the measurement and
stop.

Avoid the negative-parallel construction, meaning "not X, but Y" and "it is not that X, it
is that Y". Once in a document is tolerable; it appears constantly in generated text.

Plain British English. Explain why something is the way it is rather than what a line
does. Report uncertainty with an interval and a verdict, since a bare point estimate is
not a finding.

Vary sentence length. Generated prose settles into a rhythm of medium-length declaratives
of similar shape, and breaking that up does more for readability than any single rule
above.

## Working on this package

Run tests with `pytest -q` from the repository root. The suite takes about three minutes
and needs simglucose installed along with a generated population under
`timsim/population/params/`.

The run harness steps every five minutes, which is what real continuous glucose monitors
report on and what the open-source algorithms compute their deltas over. simglucose's
Dexcom model declares three minutes, so the sensor in use is `GuardianRT`, whose noise
parameters are identical. Changing that interval moves the whole fidelity table, so
anything that touches it needs `examples/layer_ablation.py` rerunning.

Sensor artefacts are inside the loop rather than applied afterwards. An algorithm sees the
compression lows and the jitter, and so does the simulated person. `Result.bg` carries no
sensor error and is what the safety metrics read.

`Result.bg` is not plasma glucose. simglucose exposes only `Gsub`, the subcutaneous
compartment divided by `Vg`, so `bg` is interstitial glucose without sensor error. It
differs from `Result.cgm` by the sensor model alone, and that difference is not small: the
sensor error has a standard deviation near 12 mg/dL, which fragments threshold crossings
rather than blurring them. The same runs give 100 excursions below 54 mg/dL on `bg` and 380
on `cgm`. Comparisons against trial data go on `cgm`, and `validation/compare.py` refuses
the other pairing.

Delivery passes through `timsim/therapy/limits.py` before it reaches the pump. Basal and
bolus are quantised to the nearest deliverable increment rather than rounded down, because
rounding down under-delivers on every cycle and pushes every subject off its steady state
in the same direction.

The load-bearing test is
`tests/test_population.py::test_closure_reproduces_every_published_subject`. It checks
that the steady-state relations in `population/derive.py` reproduce all thirty published
subjects. A failure there invalidates every generated subject.

The population is generated locally and is not committed, so nothing derived from the
published parameter tables is redistributed.

The bar for adding a mechanism is in `CONTRIBUTING.md`. The short version is that a new
layer comes with the statistic it is meant to move, the same statistic with the layer off,
and every other statistic as well.
