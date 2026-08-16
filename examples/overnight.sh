#!/usr/bin/env bash
# Everything the larger population needs, start to finish, without supervision.
#
# The stages are ordered by dependency and each one is skipped if its output already exists,
# so the pipeline can be rerun after an interruption without repeating hours of work. A stage
# that fails stops the pipeline rather than letting the next one run on missing input, which
# is the failure this sequence is most exposed to: a cohort built against one population and
# titrated against another produces numbers that look fine and mean nothing.
#
# The gate is the append-only check. If growing the population did not preserve the subjects
# already measured, everything downstream is a different experiment and the pipeline stops.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/Users/timstreet/.venvs/boost-insilico/bin/python}"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
LOGS="$REPO/docs/measurements/overnight"
M="$REPO/docs/measurements"
mkdir -p "$LOGS"
cd "$REPO" || exit 1

COHORT_N="${COHORT_N:-90}"
REPLICATES="${REPLICATES:-3}"
WORKERS="${WORKERS:-12}"
export COHORT_N

say () { printf '%s  %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$LOGS/pipeline.log"; }

stage () {                     # stage <label> <output-to-skip-on> <command...>
  local label="$1" guard="$2"; shift 2
  if [ -n "$guard" ] && [ -e "$guard" ]; then
    say "SKIP   $label (already have $(basename "$guard"))"
    return 0
  fi
  local t0; t0=$(date +%s)
  say "START  $label"
  if "$@" > "$LOGS/$label.log" 2>&1; then
    say "OK     $label ($(( ($(date +%s) - t0) / 60 )) min)"
  else
    say "FAILED $label ($(( ($(date +%s) - t0) / 60 )) min) — $(tail -2 "$LOGS/$label.log" | tr '\n' ' ')"
    say "pipeline stopped"
    exit 1
  fi
}

say "=== overnight run, cohorts of $COHORT_N, $REPLICATES replicates, $WORKERS workers ==="

# 1. Wait for the population, then check growing it preserved what was already measured.
while pgrep -f grow_population.py > /dev/null; do sleep 30; done
stage append_check "" "$PY" examples/check_append.py
if ! grep -q "APPEND-ONLY" "$LOGS/append_check.log"; then
  say "the grown population does not contain the old one; stopping before anything is built on it"
  exit 1
fi

# 2. Cohorts, and the replicate plan, both against the population now on disk.
stage cohorts "" "$PY" examples/build_cohorts.py
stage replicate_plan "" "$PY" examples/cohort_replicates.py --plan-only \
      --n "$COHORT_N" --replicates "$REPLICATES"

# 3. Titration. The long pole: parallel across subjects, sequential within one, since a
#    subject's ladder stops at the weakest setting that clears its floors.
stage titrate "" "$PY" examples/titrate_cohort.py --cohort recorded --workers "$WORKERS"
stage titrate_replicates "" "$PY" - <<'INNER'
import json, os, subprocess, sys
sys.path.insert(0, os.environ["PYTHONPATH"].split(":")[0])
from timsim.therapy import titrate
plan = json.load(open(os.path.join(os.environ["PYTHONPATH"].split(":")[0],
                                   "docs", "measurements", "cohort_replicates.json")))
todo = [s for s in plan.get("need_titration", []) if s not in set(titrate.titrated_subjects())]
print(f"{len(todo)} replicate subjects still need titrating")
if todo:
    args = [sys.executable, "examples/titrate_cohort.py", "--add", "--workers", "12"]
    for s in todo:
        args += ["--subject", s]
    sys.exit(subprocess.call(args))
INNER

# 4. The arms themselves.
stage bench_matrix "" env WORKERS="$WORKERS" "$PY" examples/bench_matrix.py
stage replicates "" "$PY" examples/cohort_replicates.py --n "$COHORT_N" \
      --replicates "$REPLICATES" --workers "$WORKERS"

# 5. What the arms are read against, and the tables.
stage cohort_variation "" "$PY" examples/cohort_variation.py
stage bench_tables "" "$PY" examples/bench_tables.py
cp "$LOGS/bench_tables.log" "$M/bench_tables.txt" 2>/dev/null

say "=== finished ==="
say "cohorts of $COHORT_N; read $M/bench_tables.txt, cohort_variation.json, cohort_replicates.json"
