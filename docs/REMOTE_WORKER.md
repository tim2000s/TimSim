# Setting up a second machine to run part of a sweep

Written for a Windows desktop with an i7-8700, six cores and twelve threads, 16 GB. Nothing in
it is specific to that machine beyond the worker count at the end.

The work being split is the bench matrix: around 1,440 independent 28-day runs, each one a
single-threaded integration that shares nothing with the others. Splitting it is arithmetically
trivial. Splitting it *safely* is the part this document is mostly about, because a shard run
against a different population or an older commit merges into the total without anything
looking wrong.

## What this machine can and cannot contribute

It can run the Control-IQ, trend and basal-bolus arms, which need only Python and simglucose.

It can run the oref0 SMB arms only if node and the gathered oref source are present, which is
more work and is covered separately at the end.

Its graphics card is of no use. The workload is scipy integrating a stiff system forward in
time, step by step, in pure Python and numpy. There is no kernel to hand a GPU.

Expect roughly 40 per cent more throughput than the Mac alone: about 7 to 8 effective workers
at 140 to 150 seconds a run, against 12 at 95 seconds. A 1,440-run matrix goes from about 3.2
hours to about 2.3.

## 1. Python

Install Python 3.14 from python.org, ticking "Add python.exe to PATH". The version matters
more than it usually would: `requirements-lock.txt` pins pandas 3, which returns datetime
columns at a different resolution from pandas 2, and the trial data loader depends on it.

    py -3.14 --version

## 2. The repository

Clone it, or copy the folder across. Then, from inside it:

    py -3.14 -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements-lock.txt
    pip install -e .

The lock file is the environment every published figure was measured in, 29 pinned packages.
Install against it rather than `pyproject.toml` when the results are going to be combined with
results from another machine, because the merge refuses shards whose code does not match and
the pins are part of what "match" means.

`pip install -e .` matters. Several scripts import `timsim` with no path handling, so without
it they only run from a directory that happens to put the repository on `sys.path`.

Check it:

    py -c "import timsim, simglucose, numpy, pandas, scipy; print('ok')"

## 3. The population

The generated subjects are deliberately not committed, because they derive from the published
UVA/Padova parameter tables. Copy these four files from the Mac into
`timsim\population\params\`:

    vpop_params.csv          the subjects
    vpop_quest.csv           their settings and ages
    vpop_report.json         how they were generated
    titrated_settings.json   the titrated therapy settings

Do not regenerate them on the second machine. Generation is reproducible from its seed, so it
would produce the same subjects, but copying removes a whole class of doubt for the sake of
about 100 KB.

Confirm both machines agree:

    py -c "from timsim.therapy import titrate; print(titrate.population_fingerprint())"

The two must print the same sixteen characters. If they do not, stop: every subject name refers
to a different body on the two machines, and combining their results would be meaningless.

## 4. The reference data

Needed only for building cohorts and for comparisons against real people, not for running
simulations. If the shard is only running arms, and the cohorts file is copied across with the
population, the second machine does not need any of it.

    DCLP3            set DCLP3_DIR to the folder holding Data Files
    OpenAPS Commons  only for the Commons measurements, and it is 83 GB, so leave it

Copy `docs\measurements\cohorts.json` across as well. Both machines must build the same run
list from the same cohorts, which is what makes shard `i of n` a disjoint slice rather than an
overlapping guess.

## 5. Running a shard

On the Mac:

    python examples/bench_matrix.py --shard 1/2 --out docs/measurements/shard1.json

On the desktop:

    py examples\bench_matrix.py --shard 2/2 --out shard2.json

Slices are taken by position after the run list is built, so both machines must be at the same
commit with the same cohorts file. Set the worker count with the `WORKERS` environment
variable: **use 8 on this machine, not 12.** Six physical cores with hyperthreading gives
maybe 20 to 30 per cent over six threads for numeric work, and oversubscribing costs more in
cache contention than the extra threads return.

    set WORKERS=8

Memory is not a constraint. Each worker holds about 175 MB resident, so eight of them want
about 1.4 GB of the 16 available.

## 6. Combining

Copy the shard back, then:

    python examples/merge_shards.py docs/measurements/bench_matrix.json shard1.json shard2.json

The merge refuses rather than warns when the shards are not the same experiment. It checks the
population fingerprint, the titrated settings digest, the git commit, and whether either
working tree had uncommitted changes. It also refuses shards that share a run, which is what
happens when the two machines built different run lists.

The uncommitted-changes rule is the one most likely to bite during development, and it is
deliberate: two shards can share a commit and still be different programs if either had local
edits. `--allow-dirty` overrides it and prints a warning saying the result is not reproducible
from the repository alone.

## 7. Proving it before trusting it

Before splitting real work, run the *same* shard on both machines and compare:

    python examples/bench_matrix.py --shard 1/2 --out mac.json
    py examples\bench_matrix.py --shard 1/2 --out pc.json

Every completed run should agree to the bit, because a subject's random stream comes from
`subject_seed(name, seed)` rather than from the machine, the worker count, or the order runs
finish in. If they differ, something in the environment differs, and that is worth finding
before it is hidden inside a merged total.

## 8. The oref arms, if you want them

These need node and the gathered oref0 source, and `bridge/oref/build.sh` is a bash script that
copies files out of an AndroidAPS checkout. On Windows the practical options are to run it
under Git Bash or WSL, or to copy an already-built `bridge/oref/vendor` directory across from
the Mac.

The simplest split avoids this entirely: give the desktop the Control-IQ pairings, which need
no bridge at all, and keep the oref arms on the machine that already runs them.
