#!/usr/bin/env bash
# The standalone measurements, run in waves rather than one after another.
#
# These twelve stages are independent of each other: none reads another's output, and the
# matrix and the tables they sit beside are already finished by the time this runs. Running
# them in sequence left most of the machine idle, because each stage parallelises across its
# own subjects and none of them has enough subjects to fill fourteen cores.
#
# Two separate inefficiencies were fixed together, and the smaller one was the staging. The
# larger was that `layer_ablation` and `hyperglycaemia_gap` called `simulate_cohort` without a
# worker count, so 60 and 136 twenty-eight-day runs each went through a single core. Both now
# take `--workers`, which changes no result: a subject's random stream comes from its name
# rather than from where it runs, which `simulate_cohort` documents and a test holds.
#
# Waves rather than one big pool, because the total worker budget has to stay near the core
# count. Oversubscribing costs more in cache contention than the extra processes return, and
# the bridged arms hold a node or JVM process per subject on top of their Python worker.
#
# Run after `rebuild_all.sh` has completed its derived tables, or on its own once a matrix and
# a titration store exist:
#
#     bash examples/standalone_parallel.sh
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/Users/timstreet/.venvs/boost-insilico/bin/python}"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
M="$REPO/docs/measurements"
LOGS="$M/rebuild"
mkdir -p "$LOGS"
cd "$REPO" || exit 1

say () { printf '%s  %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$LOGS/pipeline.log"; }

# One stage, in the background, reporting to the shared log when it finishes. A failure is
# reported and does not stop the others, since nothing here feeds anything else here.
bg () {
  local label="$1"; shift
  local t0
  t0=$(date +%s)
  say "START  $label"
  (
    if "$@" > "$LOGS/$label.log" 2>&1; then
      say "OK     $label ($(( ($(date +%s) - t0) / 60 )) min)"
    else
      say "FAILED $label ($(( ($(date +%s) - t0) / 60 )) min) — $(tail -3 "$LOGS/$label.log" | tr '\n' ' ')"
    fi
  ) &
}

wave () { say "--- wave $1 ---"; }

say "=== standalone measurements, in waves, $(sysctl -n hw.ncpu) cores ==="

# Wave 1. The cheap ones alongside the two that spend most of their time in short runs.
# `meal_response` runs two traces per subject per meal size and they are brief, so it fills
# its workers well; `capability` holds a bridge per subject and spends time in the pipe.
wave 1
bg clamp          "$PY" examples/hypoglycaemic_clamp.py
bg production_low "$PY" examples/production_during_a_low.py
bg meal_response  "$PY" examples/meal_response.py
bg capability     "$PY" examples/capability_table.py
wait
say "--- wave 1 done ---"

# Wave 2. The two that were serial, now parallel, with a bridged arm beside them.
wave 2
bg layer_ablation     "$PY" examples/layer_ablation.py --workers 5
bg hyperglycaemia_gap "$PY" examples/hyperglycaemia_gap.py --workers 5
bg two_benches        "$PY" examples/two_benches.py
wait
say "--- wave 2 done ---"

# Wave 3. The two longest, which are both bridge-bound, with the autosens pair filling the gaps.
wave 3
bg layer_ladder   "$PY" examples/layer_ladder_by_controller.py --workers 5
bg fit_control_iq "$PY" examples/fit_control_iq.py
bg autosens_on    "$PY" examples/oref_cohort.py --subjects 40 --days 28 --workers 2 \
                        --out "$M/oref_autosens_on.json"
bg autosens_off   "$PY" examples/oref_cohort.py --subjects 40 --days 28 --workers 2 \
                        --pin-autosens 1.0 --out "$M/oref_autosens_off.json"
wait
say "--- wave 3 done ---"

say "=== standalone measurements finished ==="
grep -c 'OK ' "$LOGS/pipeline.log" 2>/dev/null | xargs -I{} say "{} stages OK in this log"
grep 'FAILED' "$LOGS/pipeline.log" 2>/dev/null | while read -r l; do say "  $l"; done
