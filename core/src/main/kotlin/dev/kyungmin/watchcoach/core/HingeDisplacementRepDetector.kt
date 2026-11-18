package dev.kyungmin.watchcoach.core

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Rep counter for deadlift/hinge lifts, where the wrist travels with the body.
 *
 * It does not look at how hard the wrist accelerates (that falls with the square of the tempo and sinks below any fixed floor
 * on a slow set). It estimates the wrist's height change in metres, which does not depend on tempo:
 *  1. a gravity direction tracked by a gyro-driven complementary filter (so a wrist that tilts with the torso still gives a
 *     true vertical axis),
 *  2. vertical linear acceleration = specific force along that axis minus a slow mean,
 *  3. two leaky integrators (about 0.04 Hz corner) to height,
 *  4. a zig-zag extremum tracker: an extreme counts only when the height moved at least [MIN_SWING_M] from the previous one.
 * The set's start pose is the counted extremum (back at the top again, or on the floor again); a rep is reported when the
 * lifter is back there, the other extremum is its turnaround. Extrema are confirmed when the height has moved back by
 * [FLIP_M] or has stood unbeaten for [SETTLE_NS], so the last rep of a set does not wait for another one.
 */
class HingeDisplacementRepDetector {
    companion object {
        private const val MIN_DT_S = 0.015
        private const val MAX_DT_S = 0.12
        private const val RESET_GAP_NS = 1_500_000_000L
        private const val INIT_SAMPLES = 40
        private const val GRAVITY_TAU_S = 3.0
        private const val BASELINE_TAU_S = 8.0
        private const val LEAK_TAU_S = 2.5
        private const val HEIGHT_LEAK_TAU_S = 2.5
        private const val SMOOTH_TAU_S = 0.25
        /** At rest the specific force is exactly gravity: a still wrist re-learns the baseline and zeroes the velocity. */
        private const val REST_S = 0.6
        private const val REST_ACCEL = 0.15
        private const val REST_SPEED = 0.03
        private const val REST_GYRO = 0.12
        private const val REST_TAU_S = 0.8
        /** A real swing of MIN_SWING_M takes at least this peak vertical speed; the slow relaxation of the leaky integrators never does. */
        private const val MIN_SWING_SPEED = 0.06
        private const val SPEED_MEMORY_S = 3.0
        private const val MIN_SWING_M = 0.12
        private const val FLIP_M = 0.08
        private const val SETTLE_NS = 450_000_000L
        private const val MIN_REP_NS = 900_000_000L
        private const val MAX_CYCLE_NS = 8_000_000_000L
        private const val GRAVITY_LOW = 6.0
        private const val GRAVITY_HIGH = 14.0
    }

    val maximumCycleNs: Long get() = MAX_CYCLE_NS

    private val up = DoubleArray(3)
    private var upReady = false
    private var initSamples = 0
    private val initSum = DoubleArray(3)
    private var baseline = 0.0
    private var baselineReady = false
    private var baselineSum = 0.0
    private var lastNs = 0L
    private var velocity = 0.0
    private var peakSpeed = 0.0
    private var lastTrackNs = 0L
    private var smoothF = 0.0
    private var smoothReady = false
    private var restS = 0.0
    private var height = 0.0

    // Zig-zag tracker. type: +1 searching a maximum, -1 searching a minimum, 0 start pose type not known yet.
    private var searching = 0
    private var startType = 0 // +1: the set starts and ends at the top of the height range, -1: at the bottom.
    private var runMaxD = 0.0
    private var runMaxNs = 0L
    private var runMinD = 0.0
    private var runMinNs = 0L
    private var lastExtremeD = 0.0
    private var lastExtremeNs = 0L
    private var previousCountedNs = 0L
    private var turnNs = 0L
    private var turnD = 0.0
    private var startedNs = 0L
    private var lastEndNs = Long.MIN_VALUE
    private val pending = ArrayDeque<ProfiledMotionRepEvent>()

    fun beginCounting() {
        up.fill(0.0); upReady = false; initSamples = 0; initSum.fill(0.0)
        baseline = 0.0; baselineReady = false; baselineSum = 0.0; baselineCount = 0
        smoothReady = false; restS = 0.0
        lastNs = 0L
        lastTrackNs = 0L
        clearDetection()
    }

    private fun clearDetection() {
        velocity = 0.0; height = 0.0; peakSpeed = 0.0
        searching = 0; startType = 0
        runMaxD = 0.0; runMinD = 0.0; runMaxNs = lastNs; runMinNs = lastNs
        lastExtremeD = 0.0; lastExtremeNs = lastNs
        previousCountedNs = lastNs; turnNs = 0L; turnD = 0.0; startedNs = lastNs
        lastEndNs = Long.MIN_VALUE
        pending.clear()
    }

    /** Preparation samples teach the gravity axis and the resting specific force; their motion is never counted. */
    fun prime(samples: Iterable<SensorSample>) {
        for (s in samples) add(s)
        clearDetection()
    }

    fun add(sample: SensorSample): ProfiledMotionRepEvent? {
        process(sample)
        return pending.removeFirstOrNull()
    }

    fun finishAll(): List<ProfiledMotionRepEvent> {
        if (lastNs != 0L) settle(lastNs + SETTLE_NS)
        val rest = pending.toList(); pending.clear()
        return rest
    }

    private fun process(sample: SensorSample) {
        if (sample.sensorAccuracy == 0) return
        val t = sample.timestampNs
        val a = doubleArrayOf(sample.accelerationX.toDouble(), sample.accelerationY.toDouble(), sample.accelerationZ.toDouble())
        val w = doubleArrayOf(sample.gyroscopeX.toDouble(), sample.gyroscopeY.toDouble(), sample.gyroscopeZ.toDouble())
        if (t < 0 || a.any { !it.isFinite() } || w.any { !it.isFinite() }) return
        if (lastNs != 0L) {
            if (t <= lastNs) return
            if (t - lastNs > RESET_GAP_NS) beginCounting()
        }
        val dt = if (lastNs == 0L) 0.0 else ((t - lastNs) / 1e9)
        if (lastNs != 0L && dt < MIN_DT_S) return
        val step = dt.coerceAtMost(MAX_DT_S)
        val firstSample = lastNs == 0L
        lastNs = t
        val norm = sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
        if (!upReady) {
            if (norm in GRAVITY_LOW..GRAVITY_HIGH) {
                for (c in 0..2) initSum[c] += a[c] / norm
                initSamples++
                val n = sqrt(initSum.sumOf { it * it })
                for (c in 0..2) up[c] = initSum[c] / n
                if (initSamples >= INIT_SAMPLES) upReady = true
            }
            if (!upReady) { if (firstSample) { startedNs = t; runMaxNs = t; runMinNs = t; lastExtremeNs = t; previousCountedNs = t }; return }
        } else if (step > 0.0) {
            rotateGravity(w, step)
            if (norm in GRAVITY_LOW..GRAVITY_HIGH) {
                val k = (step / GRAVITY_TAU_S).coerceAtMost(0.5)
                for (c in 0..2) up[c] += (a[c] / norm - up[c]) * k
                val n = sqrt(up.sumOf { it * it })
                for (c in 0..2) up[c] /= n
            }
        }
        val f = a[0] * up[0] + a[1] * up[1] + a[2] * up[2]
        if (!baselineReady) {
            baselineSum += f; baseline = baselineSum / (++baselineCount)
            if (baselineCount >= INIT_SAMPLES) baselineReady = true
            if (!baselineReady || step <= 0.0) { markOrigin(t); return }
        } else if (step > 0.0) {
            baseline += (f - baseline) * (step / BASELINE_TAU_S).coerceAtMost(0.5)
        }
        if (step <= 0.0) { markOrigin(t); return }
        if (!smoothReady) { smoothF = f; smoothReady = true } else smoothF += (f - smoothF) * (step / SMOOTH_TAU_S).coerceAtMost(1.0)
        val gyroMag = sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2])
        if (abs(smoothF - baseline) < REST_ACCEL && abs(velocity) < REST_SPEED && gyroMag < REST_GYRO) restS += step else restS = 0.0
        if (restS >= REST_S) {
            baseline += (smoothF - baseline) * (step / REST_TAU_S).coerceAtMost(1.0)
            velocity = 0.0
        }
        val az = f - baseline
        velocity += (az - velocity / LEAK_TAU_S) * step
        height += (velocity - height / HEIGHT_LEAK_TAU_S) * step
        track(t)
    }

    private var baselineCount = 0

    private fun markOrigin(t: Long) {
        // Counting starts from rest: the height origin is the start pose, whatever happens during initialisation.
        velocity = 0.0; height = 0.0; peakSpeed = 0.0
        runMaxD = 0.0; runMinD = 0.0; runMaxNs = t; runMinNs = t
        lastExtremeD = 0.0; lastExtremeNs = t; previousCountedNs = t; startedNs = t
    }

    private fun rotateGravity(w: DoubleArray, dt: Double) {
        val mag = sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2])
        val theta = mag * dt
        if (theta < 1e-9) return
        val k = doubleArrayOf(w[0] / mag, w[1] / mag, w[2] / mag)
        val c = cos(theta); val s = sin(theta)
        val cross = doubleArrayOf(k[1] * up[2] - k[2] * up[1], k[2] * up[0] - k[0] * up[2], k[0] * up[1] - k[1] * up[0])
        val dot = k[0] * up[0] + k[1] * up[1] + k[2] * up[2]
        for (i in 0..2) up[i] = up[i] * c - cross[i] * s + k[i] * dot * (1 - c)
    }

    private fun track(t: Long) {
        val d = height
        peakSpeed = maxOf(abs(velocity), peakSpeed * exp(-(t - lastTrackNs) / 1e9 / SPEED_MEMORY_S))
        lastTrackNs = t
        if (d >= runMaxD) { runMaxD = d; runMaxNs = t }
        if (d <= runMinD) { runMinD = d; runMinNs = t }
        when (searching) {
            0 -> if (peakSpeed >= MIN_SWING_SPEED) {
                // The start pose is an extreme of its own: the first swing of at least MIN_SWING_M tells which one.
                if (runMaxD - d >= MIN_SWING_M && runMaxD - d >= d - runMinD) {
                    startType = 1; searching = -1; lastExtremeD = 0.0; lastExtremeNs = startedNs
                    runMinD = d; runMinNs = t
                } else if (d - runMinD >= MIN_SWING_M) {
                    startType = -1; searching = 1; lastExtremeD = 0.0; lastExtremeNs = startedNs
                    runMaxD = d; runMaxNs = t
                }
            }
            else -> confirm(t, d)
        }
    }

    private fun confirm(t: Long, d: Double) {
        val low = searching < 0
        val candD = if (low) runMinD else runMaxD
        val candNs = if (low) runMinNs else runMaxNs
        val swing = abs(candD - lastExtremeD)
        if (swing < MIN_SWING_M || peakSpeed < MIN_SWING_SPEED) return
        val retraced = if (low) d - candD else candD - d
        if (retraced >= FLIP_M || t - candNs >= SETTLE_NS) accept(candNs, candD, low)
    }

    private fun accept(candNs: Long, candD: Double, low: Boolean) {
        val type = if (low) -1 else 1
        if (type == startType) {
            if (candNs - previousCountedNs >= MIN_REP_NS && candNs > lastEndNs) {
                val peak = abs(turnD - candD)
                val turn = if (turnNs in (previousCountedNs + 1) until candNs) turnNs else (previousCountedNs + candNs) / 2
                pending.addLast(ProfiledMotionRepEvent(
                    previousCountedNs, turn, candNs, (candNs - previousCountedNs) / 1_000_000L,
                    peak, peak, 0.0, 0.7,
                ))
                lastEndNs = candNs
                previousCountedNs = candNs
            }
        } else {
            turnNs = candNs; turnD = candD
        }
        lastExtremeD = candD; lastExtremeNs = candNs
        searching = -searching
        // The next extreme is searched from the confirmed one onwards.
        runMaxD = height; runMaxNs = lastNs; runMinD = height; runMinNs = lastNs
    }

    private fun settle(now: Long) {
        if (searching != 0) confirm(now, height)
    }
}
