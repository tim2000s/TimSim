#!/usr/bin/env bash
# Rerun every study measurement against the current population, in one pass.
#
# The population was reseeded in August 2026 to make it reproducible from its seed, which
# regenerated all hundred subjects. Every figure measured before that describes bodies that no
# longer exist. This reruns each study's measurement unchanged, so that any movement is
# attributable to the population rather than to a change of method: the scripts that ran on
# physiological rather than titrated settings still do, because altering the design and the
# subjects at once would confound the two.
#
# Each step logs to docs/measurements/rerun/ and keeps going if one fails, since a missing
# bridge should not cost the rest of the pass.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/Users/timstreet/.venvs/boost-insilico/bin/python}"
LOGS="$REPO/docs/measurements/rerun"
# The older example scripts assume the package is pip-installed. It is not in this
# environment, so the repository goes on the path explicitly rather than editing each one.
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$LOGS"
cd "$REPO" || exit 1

run () {                       # run <label> <script> [args...]
  local label="$1"; shift
  local started; started=$(date +%s)
  printf '%s  START  %s\n' "$(date -u +%H:%M:%SZ)" "$label" | tee -a "$LOGS/pass.log"
  if "$PY" "$@" > "$LOGS/$label.log" 2>&1; then
    printf '%s  OK     %s  (%d min)\n' "$(date -u +%H:%M:%SZ)" "$label" \
      $(( ($(date +%s) - started) / 60 )) | tee -a "$LOGS/pass.log"
  else
    printf '%s  FAILED %s  (%d min)  %s\n' "$(date -u +%H:%M:%SZ)" "$label" \
      $(( ($(date +%s) - started) / 60 )) "$(tail -3 "$LOGS/$label.log" | tr '\n' ' ')" \
      | tee -a "$LOGS/pass.log"
  fi
}

printf '=== rerun started %s, population %s ===\n' "$(date -u +%FT%TZ)" \
  "$("$PY" -c "import sys;sys.path.insert(0,'.');from timsim.therapy import titrate;print(titrate.population_fingerprint())" 2>/dev/null | tail -1)" \
  | tee -a "$LOGS/pass.log"

# Cheap and load-bearing first, so a long run never blocks a quick answer.
run clamp              examples/hypoglycaemic_clamp.py
run production_low     examples/production_during_a_low.py
run capability         examples/capability_table.py
run meal_response      examples/meal_response.py
run two_benches        examples/two_benches.py
run hyperglycaemia_gap examples/hyperglycaemia_gap.py
run layer_ablation     examples/layer_ablation.py
run layer_ladder       examples/layer_ladder_by_controller.py --workers 10

printf '=== rerun finished %s ===\n' "$(date -u +%FT%TZ)" | tee -a "$LOGS/pass.log"
