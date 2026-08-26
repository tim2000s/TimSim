#!/usr/bin/env bash
# Rebuild every measurement in the package from the current population, physiology and seeding.
#
# Three changes force it, each of which reaches every simulated minute.
#
# The hepatic defence gain was fitted on 34 adults and refitted on 150, where the answer moved
# from 0.20 to 0.05.
#
# Each stochastic component now draws from its own stream. A single shared generator made a
# component's draws depend on which other components ran, so switching a layer off changed the
# random month as well as the mechanism, and every ablation compared two different months.
#
# Titration and evaluation no longer share a seed. Settings were weakened until a subject
# cleared the hypoglycaemia floors on one month and were then scored on that same month, which
# reports a fitted quantity in sample. `timsim/seeds.py` holds them apart.
#
# The titration store is deleted rather than reused, and that is the subtle part. Its guard is a
# fingerprint of the population file, which has not changed, so the store would be accepted and
# every subject would carry settings fitted under the old physiology. Settings are titrated
# against a subject's own hypoglycaemia, and the defence gain is one of the things determining
# how much hypoglycaemia a subject has, so those settings are an output of the old constant.
#
# Previous outputs are archived rather than overwritten, so a figure quoted anywhere can still
# be traced to the run that produced it.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-/Users/timstreet/.venvs/boost-insilico/bin/python}"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
M="$REPO/docs/measurements"
LOGS="$M/rebuild"
ARCHIVE="$M/archive_pre_review"
PARAMS="$REPO/timsim/population/params"
mkdir -p "$LOGS" "$ARCHIVE"
cd "$REPO" || exit 1

WORKERS="${WORKERS:-12}"
COHORT_N="${COHORT_N:-90}"
REPLICATES="${REPLICATES:-3}"
export COHORT_N

say () { printf '%s  %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$LOGS/pipeline.log"; }

# The log is appended to across runs, so the summary at the end has to know where this one
# begins. Without that it greps the whole file, re-reports every historical failure as though
# it had just happened, and writes those lines back into the file it grepped, so each run
# nests the previous run's failure inside its own. A clean rebuild on 19 August 2026 signed
# off by reporting a failure from a run that had ended eleven hours earlier.
LOG_START=$(wc -l < "$LOGS/pipeline.log" 2>/dev/null || echo 0)
this_run () { tail -n "+$((LOG_START + 1))" "$LOGS/pipeline.log" 2>/dev/null; }

stage () {                     # stage <label> <command...>
  local label="$1"; shift
  local t0; t0=$(date +%s)
  say "START  $label"
  if "$@" > "$LOGS/$label.log" 2>&1; then
    say "OK     $label ($(( ($(date +%s) - t0) / 60 )) min)"
  else
    say "FAILED $label ($(( ($(date +%s) - t0) / 60 )) min) — $(tail -3 "$LOGS/$label.log" | tr '\n' ' ')"
    return 1
  fi
}

say "=== rebuild: defence gain $(grep -o 'HYPO_EGP_DEFENCE = [0-9.]*' timsim/patient/varying.py | awk '{print $3}'), titration seed $(grep -o '^TITRATION = [0-9]*' timsim/seeds.py | awk '{print $3}'), bench seed $(grep -o '^BENCH = [0-9]*' timsim/seeds.py | awk '{print $3}'), $WORKERS workers ==="

# Nothing may still be running against the old constant.
for p in meal_response bench_matrix titrate_cohort layer_ladder layer_ablation; do
  pkill -f "$p" 2>/dev/null && say "stopped a running $p"
done
sleep 3

# 1. Archive, so no stage can silently reuse an output fitted under the old gain.
for f in "$M"/*.json "$M"/*.txt; do
  case "$(basename "$f")" in
    # Real data only, already rebuilt, and nothing simulated feeds them. `commons_requirement`
    # is the reconstructed daily insulin the Commons cohort is matched on, and it moved when
    # the percentage-form temporary basals were recovered, so it has to survive to be matched
    # against rather than be rebuilt from a population it does not depend on.
    real_meals.json|real_meals_dia.json|commons_requirement.json) continue ;;
  esac
  [ -e "$f" ] && mv "$f" "$ARCHIVE/" 2>/dev/null
done
# The store moves aside only when it is about to be rebuilt. Under SKIP_TITRATION the whole point
# is to keep it, and moving it here left the guard below checking a file that no longer existed,
# which failed the run and destroyed the store the run was meant to preserve. It was recovered
# from the Drive copy. A guard that runs after the thing it guards has been deleted is not a guard.
if [ "${SKIP_TITRATION:-0}" != "1" ]; then
  [ -e "$PARAMS/titrated_settings.json" ] && mv "$PARAMS/titrated_settings.json" \
    "$ARCHIVE/titrated_settings_superseded.json"
fi

# The ladder does not write into "$M". It writes one file per rung into docs/ladder and skips
# any rung already there, so a loop over "$M" leaves twenty stale rungs in place and the stage
# reports complete in under a minute from measurements made under the previous configuration.
# That happened on 19 August 2026. The rungs are now stamped and the skip is guarded, so this
# is the second of two defences rather than the only one.
if [ -d "$REPO/docs/ladder" ] && [ -n "$(ls -A "$REPO/docs/ladder" 2>/dev/null)" ]; then
  mkdir -p "$ARCHIVE/ladder"
  mv "$REPO"/docs/ladder/*.json "$ARCHIVE/ladder/" 2>/dev/null
  say "archived $(ls -1 "$ARCHIVE/ladder" | wc -l | tr -d ' ') stale ladder rungs"
fi

# The arbiter has the same problem and one more: it was not in this script at all, so its six
# configurations were four days old and measured on a population that had since been
# regenerated, while `--table` read them against each other and printed a complete comparison.
# Its rows are now stamped and refused when they do not bind, and it runs below.
if ls "$REPO"/docs/arbiter_* >/dev/null 2>&1; then
  mkdir -p "$ARCHIVE/arbiter"
  mv "$REPO"/docs/arbiter_* "$ARCHIVE/arbiter/" 2>/dev/null
  say "archived $(ls -1 "$ARCHIVE/arbiter" | wc -l | tr -d ' ') stale arbiter outputs"
fi

# The layer ablation and the hyperglycaemia gap write into docs as well, one file per arm, and
# each reads its own files back to build a table. They were the last two families outside this
# step, so an arm could survive a rebuild that replaced its neighbours and the table combining
# them would say nothing. Both readers now refuse arms whose stamps do not agree, and both are
# archived here so the question does not arise. The named files are listed rather than globbed,
# because docs also holds older artefacts that no stage regenerates and that would be destroyed
# by a wildcard.
# `hypo`, `visentin` and `visentin1` are branches of the ablation rather than rungs of it, and
# `layer_ablation.py` run with no `--arm` measures the six rungs and not the three branches. So
# they were never rebuilt and never archived: the three files on disk are dated 7 and 8 August
# 2026, they carry a `loop` layer that no longer exists, and FIDELITY's Visentin comparison is
# read from them. Archiving them makes their absence visible instead of leaving four-month-old
# figures sitting beside current ones.
for f in all phys behav loop sens stock hypo visentin visentin1; do
  [ -e "$REPO/docs/$f.json" ] && { mkdir -p "$ARCHIVE/ablation"; \
    mv "$REPO/docs/$f.json" "$ARCHIVE/ablation/" 2>/dev/null; }
done
[ -d "$ARCHIVE/ablation" ] && say "archived $(ls -1 "$ARCHIVE/ablation" | wc -l | tr -d ' ') stale ablation arms"
if ls "$REPO"/docs/gap_*.json >/dev/null 2>&1; then
  mkdir -p "$ARCHIVE/gap"
  mv "$REPO"/docs/gap_*.json "$ARCHIVE/gap/" 2>/dev/null
  say "archived $(ls -1 "$ARCHIVE/gap" | wc -l | tr -d ' ') stale hyperglycaemia gap arms"
fi
say "archived previous outputs to $(basename "$ARCHIVE"); titration store cleared"

# 2. The real-data references, then the cohorts, then titration, in that order because each
#    reads the one before it. `commons_cohort` computes per-user outcomes from the export and
#    is population-independent, but `bench_tables` and `cohort_variation` read it, so it has to
#    exist before anything is scored. `build_cohorts` matches simulated subjects to those users
#    on the reconstructed daily requirement, which moved when the percentage-form temporary
#    basals were recovered, so cohort membership moves with it. Titration then runs over the
#    union of whatever cohorts that produced.
#
#    Ordering this wrong is quiet rather than loud: the run completes and the cohorts are the
#    ones matched to the superseded requirement.
stage commons_cohort "$PY" examples/commons_cohort.py || exit 1
stage cohorts "$PY" examples/build_cohorts.py || exit 1

# 3. Titration. Everything simulated downstream reads it, and it is itself an output of the
#    physiology, so it cannot be carried over.
# `SKIP_TITRATION=1` keeps the store on disk and rebuilds everything downstream against it.
#
# The default is to retitrate, and that default is right whenever the physiology has moved, since
# settings are an output of it and the population fingerprint cannot see the difference. It is
# wrong when the store is already current and something downstream is being rebuilt to match a
# published figure: retitrating then produces a different store for no reason, and every document
# quoting the old one describes a set of settings that no longer exists anywhere.
#
# The guard checks rather than trusts. Both fingerprints in the store must match what is on disk,
# which is exactly what `titrate.check_population` demands of any consumer, so a store that would
# be refused downstream cannot be carried past this point either.
if [ "${SKIP_TITRATION:-0}" = "1" ]; then
  if "$PY" - <<'CHECK'
import json, sys
sys.path.insert(0, ".")
from timsim.therapy import titrate
m = json.load(open(titrate.STORE))["meta"]
ok = (m.get("population") == titrate.population_fingerprint()
      and m.get("code") == titrate.code_fingerprint())
sys.exit(0 if ok else 1)
CHECK
  then
    say "SKIP   titrate (store matches the population and code on disk)"
  else
    say "FAILED titrate skip requested but the store does not match the population or code on disk"
    exit 1
  fi
else
  stage titrate "$PY" examples/titrate_cohort.py --cohort recorded --workers "$WORKERS" || exit 1
fi
stage replicate_plan "$PY" examples/cohort_replicates.py --plan-only \
      --n "$COHORT_N" --replicates "$REPLICATES" || exit 1
stage titrate_replicates "$PY" - <<'INNER' || exit 1
import json, os, subprocess, sys
repo = os.environ["PYTHONPATH"].split(":")[0]
sys.path.insert(0, repo)
from timsim.therapy import titrate
plan = json.load(open(os.path.join(repo, "docs", "measurements", "cohort_replicates_plan.json")))
todo = [s for s in plan.get("need_titration", []) if s not in set(titrate.titrated_subjects())]
print(f"{len(todo)} replicate subjects still need titrating")
if todo:
    args = [sys.executable, "examples/titrate_cohort.py", "--add", "--workers", "12"]
    for s in todo:
        args += ["--subject", s]
    sys.exit(subprocess.call(args))
INNER

# 3b. The fixed panels. The capability table, the ablation, the ladder, the hyperglycaemia
#     gap and the production measurement run on the first adults rather than on a matched
#     cohort, and they now read the titration store like everything else, so their subjects
#     must be in it. Titrating against the panel is not circular: titration runs under the
#     built-in trend loop, which is not among the systems the panels compare.
stage titrate_panel "$PY" - <<'INNER' || exit 1
import subprocess, sys, os
repo = os.environ["PYTHONPATH"].split(":")[0]
sys.path.insert(0, repo)
from timsim.therapy import titrate
panel = [f"adult#{i:03d}" for i in range(1, 41)]
todo = [s for s in panel if s not in set(titrate.titrated_subjects())]
print(f"{len(todo)} panel subjects still need titrating")
if todo:
    args = [sys.executable, "examples/titrate_cohort.py", "--add", "--workers", "12"]
    for s in todo:
        args += ["--subject", s]
    sys.exit(subprocess.call(args))
INNER

# 4. The matrix, which is the long pole and feeds the tables and the distance measurement.
stage bench_matrix env WORKERS="$WORKERS" "$PY" examples/bench_matrix.py || exit 1
# The group floor, in every cell the distance table reports rather than in one quoted for the
# rest. It is a property of the arm and the algorithm: measured on 20 August 2026 it ran 0.43,
# 0.53, 0.70 and 1.49 percentage points on time below 54 mg/dL across the four, so the single
# figure previously carried was too permissive by a factor of 2.8 in the worst of them. The
# cells do not even rank together across statistics, since the cell with the loosest floor on
# hypoglycaemia has the tightest of the four on mean glucose.
#
# The cohorts are chosen from the reference and the seed alone, so all four draw the same
# subjects and the plan titrated above covers every one of them. Four cells at 38 to 45 minutes,
# so about 2 h 45 m against the 40 minutes one cell used to cost.
stage replicates "$PY" examples/cohort_replicates.py --n "$COHORT_N" \
      --replicates "$REPLICATES" --workers "$WORKERS"
stage replicates_bare "$PY" examples/cohort_replicates.py --n "$COHORT_N" \
      --replicates "$REPLICATES" --workers "$WORKERS" --arm bare
stage replicates_oref "$PY" examples/cohort_replicates.py --n "$COHORT_N" \
      --replicates "$REPLICATES" --workers "$WORKERS" --controller oref
stage replicates_oref_bare "$PY" examples/cohort_replicates.py --n "$COHORT_N" \
      --replicates "$REPLICATES" --workers "$WORKERS" --controller oref --arm bare

# 5. Derived from the matrix, so cheap and safe to run in sequence.
stage cohort_variation "$PY" examples/cohort_variation.py
stage bench_tables "$PY" examples/bench_tables.py
cp "$LOGS/bench_tables.log" "$M/bench_tables.txt" 2>/dev/null
stage distance_to_real "$PY" examples/distance_to_real.py

# Also derived and also cheap, and absent from this script until 20 August 2026. `group_floor`
# reads the matrix and the distance table, `spread_ratio` reads the matrix, and
# `covariance_estimator` is parameter arithmetic over the population. All three were written
# after this script and none was added to it, so each would have carried figures from the
# previous population into the next rebuild while the files it reads were replaced underneath.
stage group_floor "$PY" examples/group_floor.py
stage spread_ratio "$PY" examples/spread_ratio.py
stage covariance_estimator "$PY" examples/covariance_estimator.py

# 6. The standalone measurements. Each is independent of the others, so a failure in one is
#    reported and the rest continue.
stage clamp "$PY" examples/hypoglycaemic_clamp.py
stage capability "$PY" examples/capability_table.py
stage layer_ablation "$PY" examples/layer_ablation.py
# The subject count is passed rather than defaulted, so a change to the default cannot silently
# change what a rebuild measures. Forty is set from what the ladder's statistic resolves, and the
# working is in the script. Twenty arms of forty subjects is 800 runs, near two and a half hours.
stage layer_ladder "$PY" examples/layer_ladder_by_controller.py --subjects 40 --workers "$WORKERS"
stage hyperglycaemia_gap "$PY" examples/hyperglycaemia_gap.py
stage production_low "$PY" examples/production_during_a_low.py
stage two_benches "$PY" examples/two_benches.py
stage fit_control_iq "$PY" examples/fit_control_iq.py
stage meal_response "$PY" examples/meal_response.py
stage autosens_on "$PY" examples/oref_cohort.py --subjects 40 --days 28 \
      --workers "$WORKERS" --out "$M/oref_autosens_on.json"
stage autosens_off "$PY" examples/oref_cohort.py --subjects 40 --days 28 \
      --workers "$WORKERS" --pin-autosens 1.0 --out "$M/oref_autosens_off.json"

# The classifier arbiter, which `docs/FIDELITY.md` reports a whole section from. Six full
# cohort runs at about half an hour each, so it goes last and is the one stage worth killing if
# the rest is needed sooner. It was omitted from this script until 19 August 2026, which is how
# its outputs came to be four days older than the population they were read against.
stage arbiter "$PY" examples/configuration_arbiter.py --subjects 34
stage arbiter_table "$PY" examples/configuration_arbiter.py --table

# Producers that had no stage here. `baseline_effects` and `capability_decomposition` were found
# outside the pipeline by the audit of 20 August 2026, which is why studies 09 and 14 could not be
# rebuilt from anything on disk. The rest are the model audit and the residual ledger, written
# between 22 and 24 August, whose outputs `docs/PADOVA_AUDIT.md` and `docs/DESIGN_ALIGNMENT.md`
# quote directly.
stage baseline_effects "$PY" examples/baseline_effects.py
stage capability_decomposition "$PY" examples/capability_decomposition.py
stage intake_clock "$PY" examples/intake_clock.py
stage day_profile env WORKERS="$WORKERS" "$PY" examples/day_profile.py --subjects 84 --workers "$WORKERS"
stage excursion_recovery "$PY" examples/excursion_recovery.py --subjects 40 --workers "$WORKERS"
stage glucose_effectiveness "$PY" examples/glucose_effectiveness.py --subjects 40 --workers "$WORKERS"
stage insulin_kinetics "$PY" examples/insulin_kinetics.py --subjects 40 --workers "$WORKERS"
stage liver_delay_fit "$PY" examples/liver_delay_fit.py --subjects 20
stage meal_with_bolus "$PY" examples/meal_with_bolus.py --subjects 40 --workers "$WORKERS"
stage controller_crosscheck "$PY" examples/controller_crosscheck.py --workers "$WORKERS"
stage combined_arms env WORKERS="$WORKERS" "$PY" examples/bench_matrix.py --benches combined \
      --out docs/measurements/validation.json
stage settings_sweep "$PY" examples/settings_sweep.py --cohort dclp3 --controller control-iq \
      --scales 1.0 1.5 2.0 2.5 --workers "$WORKERS"
stage engagement_arm "$PY" examples/engagement_arm.py --workers "$WORKERS"
stage validation_table "$PY" examples/validation_table.py

say "=== finished ==="
this_run | grep -c 'OK ' | xargs -I{} say "{} stages succeeded in this run"
failures=$(this_run | grep -c 'FAILED ')
if [ "$failures" -gt 0 ]; then
  say "$failures stages FAILED in this run:"
  this_run | grep 'FAILED ' | cut -c1-160 | while read -r l; do say "  $l"; done
else
  say "no stage failed in this run"
fi
