#!/usr/bin/env bash
# The study measurements that do not read the titration store, so they can run while the main
# pipeline is titrating. Every one of them has to be redone on the grown population anyway.
#
# Deliberately narrow parallelism: the pipeline is using twelve of fourteen cores, and the
# point of this is to use what is left rather than to compete for what is not.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/Users/timstreet/.venvs/boost-insilico/bin/python}"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
LOGS="$REPO/docs/measurements/rerun600"
mkdir -p "$LOGS"; cd "$REPO" || exit 1

say () { printf '%s  %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$LOGS/pass.log"; }
run () {
  local label="$1"; shift
  local t0; t0=$(date +%s)
  say "START  $label"
  if "$@" > "$LOGS/$label.log" 2>&1; then
    say "OK     $label ($(( ($(date +%s) - t0) / 60 )) min)"
  else
    say "FAILED $label ($(( ($(date +%s) - t0) / 60 )) min) $(tail -2 "$LOGS/$label.log" | tr '\n' ' ')"
  fi
}

say "=== studies not needing titrated settings, population $($PY -c "import sys;sys.path.insert(0,'.');from timsim.therapy import titrate;print(titrate.population_fingerprint())" 2>/dev/null | tail -1) ==="
run production_low     "$PY" examples/production_during_a_low.py
run capability         "$PY" examples/capability_table.py
run hyperglycaemia_gap "$PY" examples/hyperglycaemia_gap.py
run layer_ablation     "$PY" examples/layer_ablation.py
run layer_ladder       "$PY" examples/layer_ladder_by_controller.py --workers 2
say "=== finished ==="
