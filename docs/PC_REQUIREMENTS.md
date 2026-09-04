# Requirements for a second machine running part of a sweep

The work being divided is the bench matrix, around 1,440 independent 28-day simulation runs. Each
run is a single-threaded numerical integration sharing nothing with the others, so dividing them is
arithmetically trivial. Dividing them safely is the part that needs care, because a shard produced
against a different population or an older commit merges into the total without anything looking
wrong.

This document lists what the machine must have. The procedure for using it is in `REMOTE_WORKER.md`.

## Hardware

| | Requirement | Note |
|---|---|---|
| Processor | six physical cores or more | the reference machine is an i7-8700, six cores and twelve threads |
| Memory | 4 GB free, 16 GB comfortable | each worker holds about 175 MB resident, so eight want roughly 1.4 GB |
| Disk | about 2 GB | the repository, a virtual environment and the shard output |
| Graphics | none | see below |

The graphics card contributes nothing. The workload is scipy integrating a stiff system forward in
time, step by step, in Python and numpy, and there is no kernel to hand to a GPU. A machine chosen
for this work should be chosen on cores and clock speed.

Set the worker count below the thread count. On six physical cores with hyperthreading, use eight
workers rather than twelve: the extra threads return maybe 20 to 30 per cent on numeric work, and
oversubscribing costs more in cache contention than it returns. The count is set through the
`WORKERS` environment variable.

An i7-8700 of this shape adds roughly 40 per cent throughput to the existing Mac, about 7 to 8
effective workers at 140 to 150 seconds a run against 12 at 95 seconds, which takes a 1,440-run
matrix from about 3.2 hours to about 2.3.

## Software

Python 3.14, installed from python.org with "Add python.exe to PATH" ticked. The version matters
more than it usually would, because `requirements-lock.txt` pins pandas 3, which returns datetime
columns at a different resolution from pandas 2, and the trial data loader depends on that
resolution.

The environment is installed from `requirements-lock.txt`, which is the 29 pinned packages every
published figure was measured in, rather than from `pyproject.toml`. Results that will be combined
across machines have to come from matching environments, because the merge step refuses shards whose
code does not match and the pins are part of what matching means. The package must then be installed
in editable form, because several scripts import `timsim` with no path handling and would otherwise
run only from a directory that happens to put the repository on `sys.path`.

Node and the gathered source of the OpenAPS reference algorithm, oref0, are needed only for the
oref arms. `bridge/oref/build.sh` is a
bash script that copies files out of an AndroidAPS checkout, so on Windows it wants Git Bash or WSL,
or an already-built `bridge/oref/vendor` directory copied across. The simplest division of work
avoids this: give the second machine the Control-IQ pairings, which need no bridge, and keep the
oref arms where they already run.

## Data to copy across

The generated subjects are deliberately not committed, because they derive from the published
UVA/Padova parameter tables. Four files go into `timsim\population\params\`.

| File | Contents |
|---|---|
| `vpop_params.csv` | the subjects |
| `vpop_quest.csv` | their settings and ages |
| `vpop_report.json` | how they were generated |
| `titrated_settings.json` | the titrated therapy settings |

Copy them rather than regenerating them. Generation is reproducible from its seed and would produce
the same subjects, but copying removes a class of doubt for about 100 KB. `docs\measurements\
cohorts.json` goes across as well, because both machines must build the same run list from the same
cohorts for shard `i of n` to be a disjoint slice rather than an overlapping guess.

Reference data is needed only for building cohorts and comparing against real people, not for
running simulations. A machine that only runs arms, with the cohorts file copied across, needs none
of it. The OpenAPS Commons is 83 GB and should be left where it is.

## The checks that make a shard trustworthy

Two fingerprints have to agree before any work is divided. `population_fingerprint()` prints sixteen
characters that must match on both machines; if they differ, every subject name refers to a
different simulated body and combining the results would be meaningless. The merge step then checks
the population fingerprint, the titrated settings digest, the git commit, and whether either working
tree had uncommitted changes, and refuses rather than warns when they disagree.

The uncommitted-changes rule is the one most likely to bite, and it is deliberate: two shards can
share a commit and still be different programs if either had local edits. It can be overridden, at
the cost of a result that is not reproducible from the repository alone.

Before dividing real work, run the same shard on both machines and compare. Every completed run
should agree exactly, because a subject's random stream comes from `subject_seed(name, seed)` rather
than from the machine, the worker count or the order in which runs finish. A difference means
something in the environment differs, and it is worth finding before it is hidden inside a merged
total.
