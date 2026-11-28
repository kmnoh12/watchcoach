package dev.kyungmin.watchcoach.core

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToLong
import kotlin.math.sqrt

/**
 * Haptic cue timing helpers and unified online cue scheduler.
 *
 * The cue fires [TRIM_BEFORE_COMPLETION_NS] (75 ms) before the predicted full return of a repetition,
 * bounded to `[0, MAX_CUE_DELAY_MS]` (900 ms). Counting is never modified.
 */
object RepCueDelay {
    const val FRACTION = 0.40
    const val MIN_MS = 150L
    const val MAX_MS = 600L
    private const val MAX_TURN_TO_EVENT_MS = 5_000.0

    const val ROW_RETURN_FRACTION = 0.85
    const val ROW_SMOOTHING_LAG_NS = 160_000_000L
    const val MIN_ROW_RETURN_NS = 400_000_000L
    const val MAX_ROW_RETURN_NS = 4_000_000_000L

    /** Global trim ahead of predicted 90% return completion (tunable for motor latency). */
    const val TRIM_BEFORE_COMPLETION_NS = 75_000_000L
    const val MAX_CUE_DELAY_MS = 900L
    const val MIN_LEARNED_RETURN_NS = 50_000_000L
    const val MAX_LEARNED_RETURN_NS = 2_500_000_000L

    fun delayMs(turnaroundNs: Long, eventEndNs: Long): Long {
        val sinceTopMs = (eventEndNs - turnaroundNs) / 1e6
        if (!sinceTopMs.isFinite() || sinceTopMs <= 0.0 || sinceTopMs > MAX_TURN_TO_EVENT_MS) return 0L
        return (FRACTION * sinceTopMs).toLong().coerceIn(MIN_MS, MAX_MS)
    }

    fun rowReturnDelayMs(peakNs: Long, emittedAtNs: Long, learnedReturnNs: Long): Long {
        if (learnedReturnNs <= MIN_ROW_RETURN_NS || learnedReturnNs >= MAX_ROW_RETURN_NS || emittedAtNs < peakNs) return 0L
        val targetCueNs = peakNs - ROW_SMOOTHING_LAG_NS + (ROW_RETURN_FRACTION * learnedReturnNs).roundToLong()
        return max(0L, ((targetCueNs - emittedAtNs) / 1_000_000.0).roundToLong())
    }

    /**
     * Unified cue delay: schedules `turnaroundNs + predictedReturnNs - TRIM_BEFORE_COMPLETION_NS`,
     * clamped to `[0, MAX_CUE_DELAY_MS]`. Never schedules in the past.
     */
    fun unifiedDelayMs(turnaroundNs: Long, emittedAtNs: Long, predictedReturnNs: Long): Long {
        if (predictedReturnNs <= 0L || emittedAtNs < turnaroundNs) return 0L
        val targetCueNs = turnaroundNs + predictedReturnNs - TRIM_BEFORE_COMPLETION_NS
        return ((targetCueNs - emittedAtNs) / 1_000_000.0).roundToLong().coerceIn(0L, MAX_CUE_DELAY_MS)
    }

    /**
     * Per-exercise stretch of the predicted 90% return so the cue lands near the real stop (the last 10% is a slow tail).
     * Measured on watch logs: machine_fly started at 1.27 (work/analysis-fly-cue-20261118) and was trimmed to 1.22
     * (~70 ms earlier) so buzz and phone count land just before full open instead of after stopping.
     */
    fun returnScale(exerciseId: String): Double = when (exerciseId) {
        "machine_fly" -> 1.22
        else -> 1.0
    }

    fun fallbackRatio(family: MotionFamily): Double = when (family) {
        MotionFamily.ARC_RETURN -> 0.72
        MotionFamily.FOREARM_ROTATION -> 0.80
        MotionFamily.TRANSLATION_PRESS_RETURN -> 0.55
        MotionFamily.PRESS_RETURN -> 0.85
        MotionFamily.FLEXION_EXTENSION -> 1.05
        MotionFamily.PULL_RETURN -> 1.15
        MotionFamily.MULTI_AXIS_RETURN -> 1.25
        MotionFamily.CYCLE_AXIS_RETURN -> 1.25
        MotionFamily.VERTICAL_PRESS_RETURN -> 1.38
        MotionFamily.UNOBSERVABLE_MANUAL -> 1.0
    }
}

/**
 * Online causal cue scheduler shared across all motion families.
 *
 * Tracks a bias-rejected gyro position signal to measure each completed repetition's
 * turnaround-to-90%-return duration within the current set, and predicts future completions
 * using the median of recent measured repetitions (falling back to a family ratio on rep 1).
 */
class UnifiedCueScheduler(
    private val family: MotionFamily,
    private val returnScale: Double = 1.0,
    /**
     * Suppresses predicted return delay when the underlying detector already detects and emits at
     * the physical return-end stop (`RowReturnStopDetector` for rowing exercises). Non-row
     * `CYCLE_AXIS_RETURN` exercises (lateral/front raises, straight-arm pulldowns, pull-ups, squats),
     * `MULTI_AXIS_RETURN` (`machine_fly` with `returnScale = 1.22`), and `PULL_RETURN` stay unchanged.
     */
    private val suppressReturnDelay: Boolean = false,
) {
    private data class Point(val t: Long, val theta: DoubleArray, val gPos: DoubleArray)
    private data class PendingReturn(
        val repIndex: Int,
        val turnaroundNs: Long,
        val emittedNs: Long,
        val axis: DoubleArray,
        val outSign: Double,
        val baseNs: Long,
        val baseRaw: Double,
        val slope: Double,
        val threshold: Double,
        val amplitude: Double,
        var minSeen: Double,
        var prevTs: Long,
        var prevVal: Double,
        val minPeakNs: Long,
        val deadlineNs: Long,
    )

    private var lastNs = 0L
    private val gBias = DoubleArray(3)
    private val theta = DoubleArray(3)
    private val gPos = DoubleArray(3)
    private val gBiasFast = DoubleArray(3)
    private val buffer = ArrayDeque<Point>()

    private val learnedReturns = ArrayList<Pair<Int, Long>>()
    private val learnedRatios = ArrayList<Pair<Int, Double>>()
    private var pending: PendingReturn? = null
    private var lastTurnaroundNs = 0L
    private var prevBaseTheta: DoubleArray? = null
    private var prevBaseNs = 0L
    private val driftVec = DoubleArray(3)
    private var repCount = 0

    val measuredCount: Int get() = learnedReturns.size

    fun reset() {
        lastNs = 0L
        gBias.fill(0.0)
        theta.fill(0.0)
        gPos.fill(0.0)
        gBiasFast.fill(0.0)
        buffer.clear()
        learnedReturns.clear()
        learnedRatios.clear()
        pending = null
        lastTurnaroundNs = 0L
        prevBaseTheta = null
        prevBaseNs = 0L
        driftVec.fill(0.0)
        repCount = 0
    }

    fun observe(sample: SensorSample) {
        val t = sample.timestampNs
        val gx = sample.gyroscopeX.toDouble()
        val gy = sample.gyroscopeY.toDouble()
        val gz = sample.gyroscopeZ.toDouble()
        if (sample.sensorAccuracy == 0 || t < 0L || !gx.isFinite() || !gy.isFinite() || !gz.isFinite()) {
            reset()
            return
        }
        if (lastNs > 0L && t <= lastNs) return
        if (lastNs > 0L && t - lastNs > MAX_GAP_NS) reset()
        val dt = if (lastNs == 0L) 0.02 else (t - lastNs) / 1e9
        lastNs = t

        val g = doubleArrayOf(gx, gy, gz)
        val gMag = sqrt(gx * gx + gy * gy + gz * gz)
        if (gMag < ZUPT_GYRO_FLOOR) {
            val bz = 1.0 - exp(-dt / ZUPT_BIAS_TAU_S)
            for (c in 0..2) gBias[c] += (g[c] - gBias[c]) * bz
        }
        val baFast = 1.0 - exp(-dt / FAST_BIAS_TAU_S)
        val gDecay = exp(-dt / GPOS_DECAY_TAU_S)
        for (c in 0..2) {
            theta[c] += (g[c] - gBias[c]) * dt
            gBiasFast[c] += (g[c] - gBiasFast[c]) * baFast
            gPos[c] = gPos[c] * gDecay + (g[c] - gBiasFast[c]) * dt
        }
        buffer.addLast(Point(t, theta.copyOf(), gPos.copyOf()))
        while (buffer.size > MAX_BUFFER_POINTS || (buffer.isNotEmpty() && buffer.first().t < t - BUFFER_WINDOW_NS)) {
            buffer.removeFirst()
        }
        resolvePending(t)
    }

    fun schedule(event: ProfiledMotionRepEvent, emittedAtNs: Long): Long {
        val turnNs = event.turnaroundTimestampNs
        val isCycle = event.endTimestampNs == turnNs
        if (suppressReturnDelay) {
            return 0L
        }
        if (turnNs < lastTurnaroundNs) {
            learnedReturns.clear()
            learnedRatios.clear()
            pending = null
            lastTurnaroundNs = 0L
            prevBaseTheta = null
            prevBaseNs = 0L
            driftVec.fill(0.0)
            repCount = 0
        }
        val repIdx = repCount++
        val sinceTurn = max(0L, emittedAtNs - turnNs)
        val predReturnNs = (predictReturnNs(isCycle, sinceTurn) * returnScale).roundToLong()
        val delayMs = RepCueDelay.unifiedDelayMs(turnNs, emittedAtNs, predReturnNs)

        pending = null
        if (family !in LINEAR_PRESS_FAMILIES) {
            measureRepReturn(repIdx, event, emittedAtNs, isCycle, sinceTurn)
        }
        lastTurnaroundNs = turnNs
        return delayMs
    }

    fun learnedReturnNs(): Long? {
        val rets = recentValues(learnedReturns, 3)
        if (rets.isEmpty()) return null
        val sorted = rets.sorted()
        val mid = sorted.size / 2
        return if (sorted.size % 2 == 1) sorted[mid] else (sorted[mid - 1] + sorted[mid]) / 2L
    }

    private fun predictReturnNs(isCycle: Boolean, sinceTurnNs: Long): Long {
        val rats = recentValues(learnedRatios, 4)
        if (!isCycle && rats.isNotEmpty()) {
            val sorted = rats.sorted()
            val mid = sorted.size / 2
            val medRatio = if (sorted.size % 2 == 1) sorted[mid] else (sorted[mid - 1] + sorted[mid]) / 2.0
            return (sinceTurnNs * medRatio).roundToLong()
        }
        learnedReturnNs()?.let { return it }
        return (sinceTurnNs * RepCueDelay.fallbackRatio(family)).roundToLong()
    }

    private fun resolvePending(tNs: Long) {
        val p = pending ?: return
        if (tNs > p.deadlineNs) {
            pending = null
            return
        }
        if (tNs <= p.minPeakNs) return
        val rawProj = (0..2).sumOf { theta[it] * p.axis[it] }
        val value = p.outSign * (rawProj - (p.baseRaw + p.slope * ((tNs - p.baseNs) / 1e9)))
        if (value <= p.threshold) {
            val compNs = interpolateCrossing(p.prevTs, p.prevVal, tNs, value, p.threshold)
            recordMeasurement(p.repIndex, compNs - p.turnaroundNs, p.emittedNs - p.turnaroundNs)
            pending = null
            return
        }
        if (value > p.minSeen + REVERSAL_ABORT_FRACTION * p.amplitude) {
            pending = null
            return
        }
        if (value < p.minSeen) p.minSeen = value
        p.prevTs = tNs
        p.prevVal = value
    }

    private fun measureRepReturn(
        repIdx: Int,
        event: ProfiledMotionRepEvent,
        emittedAtNs: Long,
        isCycle: Boolean,
        sinceTurnNs: Long,
    ) {
        val pts = buffer.toList()
        if (pts.size < 20) return
        val axis = principalAxis(pts)
        val n = pts.size
        val rawProj = DoubleArray(n) { i -> (0..2).sumOf { c -> pts[i].theta[c] * axis[c] } }
        val gpProj = DoubleArray(n) { i -> (0..2).sumOf { c -> pts[i].gPos[c] * axis[c] } }
        val prevT = if (lastTurnaroundNs > 0L) lastTurnaroundNs else pts.first().t
        val loNs = if (isCycle) {
            max(if (lastTurnaroundNs > 0L) prevT + 200_000_000L else pts.first().t, event.turnaroundTimestampNs - 1_500_000_000L)
        } else {
            max(if (lastTurnaroundNs > 0L) prevT + 200_000_000L else pts.first().t, event.startTimestampNs)
        }
        val cands = pts.indices.filter { pts[it].t in loNs..emittedAtNs }
        if (cands.size < 3) return

        val outSign = determinePolarity(pts, rawProj, gpProj, cands, isCycle, prevT, event)
        var slopeAxis = (0..2).sumOf { driftVec[it] * axis[it] }
        val t0 = pts.first().t
        val peakI = cands.maxByOrNull { i -> outSign * (rawProj[i] - slopeAxis * ((pts[i].t - t0) / 1e9)) } ?: return

        val sLoNs = max(
            pts.first().t,
            max(
                if (lastTurnaroundNs > 0L) prevT else pts.first().t,
                if (isCycle) pts[peakI].t - 2_500_000_000L else event.startTimestampNs - 600_000_000L,
            ),
        )
        val baseCands = (0 until peakI).filter { pts[it].t >= sLoNs }
        if (baseCands.isEmpty()) return
        val baseI = baseCands.minByOrNull { i -> outSign * (rawProj[i] - slopeAxis * ((pts[i].t - t0) / 1e9)) } ?: return
        val baseNs = pts[baseI].t
        val baseTheta = pts[baseI].theta
        prevBaseTheta?.let { prevTheta ->
            val dtB = baseNs - prevBaseNs
            if (dtB in 500_000_000L..8_000_000_000L) {
                val dtSec = dtB / 1e9
                for (c in 0..2) {
                    val obsDrift = ((baseTheta[c] - prevTheta[c]) / dtSec).coerceIn(-0.1, 0.1)
                    driftVec[c] = 0.5 * driftVec[c] + 0.5 * obsDrift
                }
                slopeAxis = (0..2).sumOf { driftVec[it] * axis[it] }
            }
        }
        prevBaseTheta = baseTheta.copyOf()
        prevBaseNs = baseNs

        val baseRaw = rawProj[baseI]
        val amp = outSign * (rawProj[peakI] - (baseRaw + slopeAxis * ((pts[peakI].t - baseNs) / 1e9)))
        val minAmp = if (family in HIGH_AMPLITUDE_THRESHOLD_FAMILIES) 0.35 else 0.25
        if (amp < minAmp) return

        val thr = 0.10 * amp
        var foundNs: Long? = null
        var minSeen = amp
        var prevVal = amp
        var prevTs = pts[peakI].t
        for (i in (peakI + 1) until n) {
            val valAtI = outSign * (rawProj[i] - (baseRaw + slopeAxis * ((pts[i].t - baseNs) / 1e9)))
            if (valAtI <= thr) {
                foundNs = interpolateCrossing(prevTs, prevVal, pts[i].t, valAtI, thr)
                break
            }
            if (valAtI < minSeen) minSeen = valAtI
            if (valAtI > minSeen + REVERSAL_ABORT_FRACTION * amp) break
            prevVal = valAtI
            prevTs = pts[i].t
        }
        if (foundNs != null) {
            recordMeasurement(repIdx, foundNs - event.turnaroundTimestampNs, sinceTurnNs)
        } else if (minSeen > thr && prevVal <= minSeen + REVERSAL_ABORT_FRACTION * amp) {
            pending = PendingReturn(
                repIndex = repIdx,
                turnaroundNs = event.turnaroundTimestampNs,
                emittedNs = emittedAtNs,
                axis = axis,
                outSign = outSign,
                baseNs = baseNs,
                baseRaw = baseRaw,
                slope = slopeAxis,
                threshold = thr,
                amplitude = amp,
                minSeen = minSeen,
                prevTs = prevTs,
                prevVal = prevVal,
                minPeakNs = pts[peakI].t,
                deadlineNs = emittedAtNs + PENDING_TIMEOUT_NS,
            )
        }
    }

    private fun determinePolarity(
        pts: List<Point>,
        rawProj: DoubleArray,
        gpProj: DoubleArray,
        cands: List<Int>,
        isCycle: Boolean,
        prevT: Long,
        event: ProfiledMotionRepEvent,
    ): Double {
        if (!isCycle) {
            val lo = max(pts.first().t, max(prevT, event.startTimestampNs - 600_000_000L))
            val hi = max(event.startTimestampNs, event.turnaroundTimestampNs)
            val pre = pts.indices.filter { pts[it].t in lo..hi }
            val p0 = if (pre.isNotEmpty()) {
                val k = max(1, pre.size / 3)
                pre.take(k).sumOf { rawProj[it] } / k
            } else {
                rawProj[cands.first()]
            }
            val posAmp = cands.maxOf { rawProj[it] - p0 }
            val negAmp = cands.maxOf { p0 - rawProj[it] }
            return if (posAmp >= negAmp) 1.0 else -1.0
        }
        val sorted = gpProj.sorted()
        val med = sorted[sorted.size / 2]
        val p95 = sorted[(0.95 * (sorted.size - 1)).toInt()]
        val p05 = sorted[(0.05 * (sorted.size - 1)).toInt()]
        return if (p95 - med >= med - p05) 1.0 else -1.0
    }

    private fun principalAxis(pts: List<Point>): DoubleArray {
        val n = pts.size
        val mean = DoubleArray(3) { c -> pts.sumOf { it.gPos[c] } / n }
        val cov = Array(3) { DoubleArray(3) }
        for (p in pts) {
            for (a in 0..2) for (b in a..2) cov[a][b] += (p.gPos[a] - mean[a]) * (p.gPos[b] - mean[b])
        }
        for (a in 0..2) for (b in 0 until a) cov[a][b] = cov[b][a]
        var v = doubleArrayOf(1.0, 0.7, 0.3)
        repeat(24) {
            val w = DoubleArray(3) { a -> (0..2).sumOf { b -> cov[a][b] * v[b] } }
            val nm = sqrt(w.sumOf { it * it }).coerceAtLeast(1e-12)
            v = DoubleArray(3) { w[it] / nm }
        }
        return v
    }

    private fun interpolateCrossing(t0: Long, v0: Double, t1: Long, v1: Double, thr: Double): Long {
        if (v0 <= thr || v0 <= v1) return t1
        val frac = ((v0 - thr) / (v0 - v1)).coerceIn(0.0, 1.0)
        return t0 + ((t1 - t0) * frac).roundToLong()
    }

    private fun recordMeasurement(repIdx: Int, durationNs: Long, emitSinceTurnNs: Long) {
        if (durationNs !in RepCueDelay.MIN_LEARNED_RETURN_NS..RepCueDelay.MAX_LEARNED_RETURN_NS) return
        learnedReturns.add(repIdx to durationNs)
        if (emitSinceTurnNs >= 200_000_000L) {
            val ratio = durationNs.toDouble() / emitSinceTurnNs
            if (ratio in 0.3..3.0) learnedRatios.add(repIdx to ratio)
        }
    }

    private fun <T> recentValues(items: List<Pair<Int, T>>, maxLen: Int): List<T> {
        val hasTwoLater = items.count { it.first > 0 } >= 2
        val filtered = if (hasTwoLater) items.filter { it.first > 0 } else items
        return filtered.takeLast(maxLen).map { it.second }
    }

    companion object {
        private const val MAX_GAP_NS = 450_000_000L
        private const val ZUPT_GYRO_FLOOR = 0.20
        private const val ZUPT_BIAS_TAU_S = 1.0
        private const val FAST_BIAS_TAU_S = 1.5
        private const val GPOS_DECAY_TAU_S = 6.0
        private const val MAX_BUFFER_POINTS = 800
        private const val BUFFER_WINDOW_NS = 12_000_000_000L
        private const val PENDING_TIMEOUT_NS = 1_200_000_000L
        private const val REVERSAL_ABORT_FRACTION = 0.15

        private val LINEAR_PRESS_FAMILIES = setOf(
            MotionFamily.TRANSLATION_PRESS_RETURN,
            MotionFamily.PRESS_RETURN,
        )
        private val HIGH_AMPLITUDE_THRESHOLD_FAMILIES = setOf(
            MotionFamily.VERTICAL_PRESS_RETURN,
            MotionFamily.ARC_RETURN,
            MotionFamily.FOREARM_ROTATION,
        )
    }
}
