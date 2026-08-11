#!/bin/sh
# Compile the real Boost decision code into a bridge jar.
#
# The five decision files and the orchestrator are compiled straight from the AndroidAPS
# working tree rather than copied, so there is no second copy to drift. Point BOOST_SRC at a
# different checkout to test a different version; the gate's design fingerprint should record
# which one was used.
set -e
JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}"
export JAVA_HOME
BOOST_SRC="${BOOST_SRC:-$HOME/StudioProjects/Boost-V6}"
V5="$BOOST_SRC/plugins/aps/src/main/kotlin/app/aaps/plugins/aps/openAPSBoostV5"
HERE="$(cd "$(dirname "$0")" && pwd)"

test -d "$V5" || { echo "no Boost source at $V5; set BOOST_SRC" >&2; exit 1; }

kotlinc \
  "$V5/MealHypothesis.kt" \
  "$V5/MealSignalScore.kt" \
  "$V5/AggressionBudget.kt" \
  "$V5/MealActionMultiplier.kt" \
  "$V5/SafetyGates.kt" \
  "$V5/DetermineBasalBoostV5.kt" \
  "$HERE/stub/app/aaps/core/interfaces/logging/AAPSLogger.kt" \
  "$HERE/stub/javax/inject/Annotations.kt" \
  "$HERE/Main.kt" \
  -include-runtime -d "$HERE/boost-bridge.jar" -nowarn

echo "built $HERE/boost-bridge.jar from $BOOST_SRC"
