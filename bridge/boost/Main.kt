package timsim.bridge

import app.aaps.plugins.aps.openAPSBoostV5.DetermineBasalBoostV5
import app.aaps.plugins.aps.openAPSBoostV5.MealHypothesis
import app.aaps.plugins.aps.openAPSBoostV5.MealHypothesisState
import app.aaps.plugins.aps.openAPSBoostV5.V5Inputs
import app.aaps.plugins.aps.openAPSBoostV5.V5PersistedState

/**
 * A line protocol over the real Boost decision code.
 *
 * The point of this is what it does not contain. There is no reimplementation here: the five
 * decision files and the orchestrator are compiled from the AndroidAPS working tree and
 * `decide` is called directly, so nothing can drift between this and what ships. The Python
 * port it replaces reproduced the logged dose to 0.0000 U and still agreed with the logged
 * state machine only 70.9% of the time, reaching RECOVERING on 0.6% of real inputs against a
 * logged 5.8%. Every comparison then needed a control run to subtract that.
 *
 * The protocol is positional and whitespace separated rather than JSON, because a 28-day run
 * for one subject is 8,064 cycles and a hundred subjects is over 800,000 round trips. Field
 * order is fixed by [FIELDS] and asserted on the Python side.
 *
 * State is held here rather than passed across, one session per subject, because
 * `V5PersistedState` is what the plugin keeps in its own store between cycles and marshalling
 * it each way would be another place for the two sides to disagree.
 *
 * Two inputs are deliberately absent. `riskAtProjectedIob` is a model callback and is passed
 * as null, which disables `postActionRiskCheck`, and the ML fields are null because no model
 * runs here. Both match how the algorithm behaves when its models are unavailable, which is a
 * real operating mode, and both are reported in the output so a run cannot quietly be read as
 * though the models were present.
 */
private val FIELDS = listOf(
    "delta", "shortAvgDelta", "deltaAccl", "bg", "eventualBg", "targetBg", "maxDelta",
    "minGuardBg", "minGuardThreshold", "d0", "d1", "d2",
    "iob", "maxIob", "baseInsulinReq", "roundSmbTo", "enableSmbPreChecks",
    "mlHypoRisk", "mlMealLikely", "recentLowBg", "cumulativeRise30min", "hour",
    "exerciseActive", "inPostExerciseWindow", "asleep", "fastCarbConfirmEnabled",
    "sensorQualityOk", "profileSwitched", "pumpDisconnected", "loopSuspended",
    "timeJumpMinutes", "aggressionUserKnob", "hypoCautionUserKnob", "sensitivityUserKnob",
    "confirmedCapU", "committedCapU",
)

private const val MISSING = -99999.0

private fun optional(v: Double): Double? = if (v == MISSING) null else v

fun main() {
    // The orchestrator takes a logger and marks it unused, so an empty implementation of
    // the stub interface satisfies the constructor without introducing behaviour.
    // The constructor dropped its aapsLogger parameter between Boost-V6 and the V7 line.
    val engine = DetermineBasalBoostV5()
    var persisted = V5PersistedState()
    val out = java.io.PrintWriter(java.io.BufferedWriter(java.io.OutputStreamWriter(System.out)))

    System.`in`.bufferedReader().forEachLine { line ->
        val t = line.trim()
        if (t.isEmpty()) return@forEachLine
        if (t == "FIELDS") { out.println(FIELDS.joinToString(" ")); out.flush(); return@forEachLine }
        if (t == "RESET") { persisted = V5PersistedState(); out.println("ok"); out.flush(); return@forEachLine }
        if (t == "QUIT") { out.flush(); kotlin.system.exitProcess(0) }

        val f = t.split(Regex("\\s+")).map { it.toDouble() }
        require(f.size == FIELDS.size) { "expected ${FIELDS.size} fields, got ${f.size}" }
        var i = 0
        fun next() = f[i++]
        fun flag() = f[i++] != 0.0

        val inputs = V5Inputs(
            delta = next(), shortAvgDelta = next(), deltaAccl = next(), bg = next(),
            eventualBg = next(), targetBg = next(), maxDelta = next(),
            minGuardBg = next(), minGuardThreshold = next(),
            deltaHistory = listOf(next(), next(), next()),
            iob = next(), maxIob = next(), baseInsulinReq = next(), roundSmbTo = next(),
            enableSmbPreChecks = flag(),
            mlHypoRisk = optional(next()), mlMealLikely = optional(next()),
            recentLowBg = next(), cumulativeRise30min = next(), hour = next().toInt(),
            exerciseActive = flag(), inPostExerciseWindow = flag(), asleep = flag(),
            fastCarbConfirmEnabled = flag(), sensorQualityOk = flag(),
            profileSwitched = flag(), pumpDisconnected = flag(), loopSuspended = flag(),
            timeJumpMinutes = next(),
            aggressionUserKnob = next(), hypoCautionUserKnob = next(),
            sensitivityUserKnob = next(),
            confirmedCapU = next(), committedCapU = next(),
        )

        val d = engine.decide(inputs, persisted)
        persisted = d.newPersistedState
        val r = d.phase3.reductions
        out.println(
            listOf(
                d.finalDose, d.score, d.mealHypothesis.ordinal, d.mealHypothesisAge,
                if (d.stateReset) 1 else 0, d.aggressionBudget.budget, d.actionMultiplier,
                d.insulinToDeliver,
                if (r.hardGateFired != null) 1 else 0,
                if (r.maxIobClampApplied) 1 else 0,
                r.iobHeadroomBrake, r.postActionRiskCheck, r.decelerationBrake,
                r.sensorQualityCheck, if (r.dynamicSpikeCapped) 1 else 0,
                if (d.mlWeightsRenormalized) 1 else 0,
            ).joinToString(" ")
        )
        out.flush()
    }
    out.flush()
}

/** The state order, so the Python side can name what the ordinal means without guessing. */
@Suppress("unused")
val STATE_ORDER: List<String> = MealHypothesis.entries.map { it.name }
