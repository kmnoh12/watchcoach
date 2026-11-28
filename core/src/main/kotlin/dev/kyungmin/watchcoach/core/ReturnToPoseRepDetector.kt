package dev.kyungmin.watchcoach.core

import kotlin.math.PI
import kotlin.math.acos
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Flexion/extension counter: leave the starting wrist tilt, then return to it.
 * Uses gravity-relative tilt only; it does not reconstruct a 3D path or joint angle.
 * 60° departure / 20° return are provisional motion hysteresis, not form criteria.
 */
internal class ReturnToPoseRepDetector(
    private val minimumRepMs: Long,
    /** Compare elevation from the forearm Y axis so pronation/supination around Y does not mask return to the starting angle. */
    private val pronationInvariant: Boolean = false,
) {
    private val filtered = DoubleArray(3)
    private val baselineSum = DoubleArray(3)
    private var baselineCount = 0
    private var baseline: DoubleArray? = null
    private var lastTimestampNs = 0L
    private var invalidGravitySinceNs = 0L
    private var waitForBottom = false
    private var departed = false
    private var startNs = 0L
    private var peakNs = 0L
    private var peakTilt = 0.0
    private var peakGyro = 0.0
    // Online 3D dominant rotation axis (SO(3)-invariant) learned from the set's own gyro covariance.
    // Projecting gravity perpendicular to this axis cancels cos(flare) shrinkage and out-of-plane
    // elbow-flare / grip-shift offsets without needing per-variant axes or thresholds.
    private val gyroCov = DoubleArray(9)
    private val rotationAxis = DoubleArray(3)
    private var axisReady = false

    val candidateStartNs: Long? get() = startNs.takeIf { it > 0L }

    fun reset() {
        baseline = null
        baselineCount = 0
        baselineSum.fill(0.0)
        lastTimestampNs = 0L
        invalidGravitySinceNs = 0L
        waitForBottom = false
        gyroCov.fill(0.0)
        rotationAxis.fill(0.0)
        axisReady = false
        resetCycle()
    }

    fun add(sample: SensorSample): ProfiledMotionRepEvent? {
        val t = sample.timestampNs
        val values = doubleArrayOf(sample.accelerationX.toDouble(), sample.accelerationY.toDouble(), sample.accelerationZ.toDouble())
        val gyro = doubleArrayOf(sample.gyroscopeX.toDouble(), sample.gyroscopeY.toDouble(), sample.gyroscopeZ.toDouble())
        if (t <= 0L || sample.sensorAccuracy == 0 || values.any { !it.isFinite() } || gyro.any { !it.isFinite() }) {
            resetCycle(); waitForBottom = true
            return null
        }
        if (lastTimestampNs != 0L && t <= lastTimestampNs) {
            resetCycle(); waitForBottom = true
            return null
        }
        val dt = if (lastTimestampNs == 0L) 0.0 else (t - lastTimestampNs) / 1e9
        lastTimestampNs = t
        if (baseline == null) {
            val norm = norm(values)
            if (norm !in 6.0..14.0) return null
            for (axis in 0..2) baselineSum[axis] += values[axis]
            if (++baselineCount < BASELINE_SAMPLES) return null
            for (axis in 0..2) filtered[axis] = baselineSum[axis] / baselineCount
            val mean = norm(filtered)
            baseline = DoubleArray(3) { filtered[it] / mean }
            return null
        }
        if (dt > 0.45) {
            resetCycle(); waitForBottom = true
            values.copyInto(filtered)
        } else {
            val alpha = 1.0 - exp(-dt / 0.15)
            for (axis in 0..2) filtered[axis] += alpha * (values[axis] - filtered[axis])
        }
        val magnitude = norm(filtered)
        if (magnitude !in 6.0..14.0) {
            // Tolerate brief dynamic acceleration, but do not bridge a sustained
            // loss of the gravity estimate. Match the existing 450ms sample-gap boundary.
            if (invalidGravitySinceNs == 0L) invalidGravitySinceNs = t
            if (t - invalidGravitySinceNs >= 450_000_000L) {
                resetCycle()
                waitForBottom = true
                return null
            }
            if (!pronationInvariant || magnitude < 1.5) return null
        } else {
            invalidGravitySinceNs = 0L
        }
        val reference = baseline!!
        val gyroRate = norm(gyro)
        if (!pronationInvariant && dt > 0.0 && dt <= 0.45 && gyroRate > AXIS_GYRO_FLOOR) {
            val mem = 1.0 - exp(-dt / AXIS_MEMORY_TAU_S)
            for (r in 0..2) {
                for (c in 0..2) {
                    gyroCov[r * 3 + c] = gyroCov[r * 3 + c] * (1.0 - mem) + gyro[r] * gyro[c] * mem
                }
            }
            if (!axisReady) {
                for (c in 0..2) rotationAxis[c] = gyro[c] / gyroRate
                axisReady = true
            } else {
                repeat(2) {
                    val nx = gyroCov[0] * rotationAxis[0] + gyroCov[1] * rotationAxis[1] + gyroCov[2] * rotationAxis[2]
                    val ny = gyroCov[3] * rotationAxis[0] + gyroCov[4] * rotationAxis[1] + gyroCov[5] * rotationAxis[2]
                    val nz = gyroCov[6] * rotationAxis[0] + gyroCov[7] * rotationAxis[1] + gyroCov[8] * rotationAxis[2]
                    val nn = sqrt(nx * nx + ny * ny + nz * nz)
                    if (nn > 1e-9) {
                        rotationAxis[0] = nx / nn
                        rotationAxis[1] = ny / nn
                        rotationAxis[2] = nz / nn
                    }
                }
            }
        }
        val tilt = if (pronationInvariant) {
            val uY = (filtered[1] / magnitude).coerceIn(-1.0, 1.0)
            val uR = sqrt((1.0 - uY * uY).coerceAtLeast(0.0))
            val bY = reference[1].coerceIn(-1.0, 1.0)
            val bR = sqrt((1.0 - bY * bY).coerceAtLeast(0.0))
            acos((uY * bY + uR * bR).coerceIn(-1.0, 1.0))
        } else {
            val ux = filtered[0] / magnitude
            val uy = filtered[1] / magnitude
            val uz = filtered[2] / magnitude
            val rawTilt = acos((ux * reference[0] + uy * reference[1] + uz * reference[2]).coerceIn(-1.0, 1.0))
            if (axisReady) {
                val ax = rotationAxis[0]; val ay = rotationAxis[1]; val az = rotationAxis[2]
                val uDot = ux * ax + uy * ay + uz * az
                val rDot = reference[0] * ax + reference[1] * ay + reference[2] * az
                val upx = ux - uDot * ax; val upy = uy - uDot * ay; val upz = uz - uDot * az
                val rpx = reference[0] - rDot * ax; val rpy = reference[1] - rDot * ay; val rpz = reference[2] - rDot * az
                val upn = sqrt(upx * upx + upy * upy + upz * upz)
                val rpn = sqrt(rpx * rpx + rpy * rpy + rpz * rpz)
                if (upn >= MIN_PLANE_PROJECTION && rpn >= MIN_PLANE_PROJECTION) {
                    val projTilt = acos(((upx * rpx + upy * rpy + upz * rpz) / (upn * rpn)).coerceIn(-1.0, 1.0))
                    minOf(projTilt, rawTilt * MAX_PROJECTION_GAIN)
                } else {
                    rawTilt
                }
            } else {
                rawTilt
            }
        }
        if (waitForBottom) {
            if (tilt <= RETURN_TILT) waitForBottom = false
            return null
        }
        if (tilt > RETURN_TILT && startNs == 0L) startNs = t
        if (tilt > peakTilt) { peakTilt = tilt; peakNs = t }
        peakGyro = max(peakGyro, norm(gyro))
        if (tilt >= DEPARTURE_TILT) departed = true
        if (tilt > RETURN_TILT) return null

        val durationMs = if (startNs == 0L) 0L else (t - startNs) / 1_000_000L
        val event = if (departed && durationMs >= minimumRepMs) {
            ProfiledMotionRepEvent(startNs, peakNs, t, durationMs, peakGyro, peakTilt * 2.0, 0.0,
                // Internal excursion score only; this is not an accuracy probability.
                (peakTilt / (PI / 2)).coerceIn(0.0, 1.0))
        } else null
        resetCycle()
        return event
    }

    private fun resetCycle() {
        departed = false; startNs = 0L; peakNs = 0L; peakTilt = 0.0; peakGyro = 0.0
    }

    private fun norm(v: DoubleArray) = sqrt(v.sumOf { it * it })

    companion object {
        private const val BASELINE_SAMPLES = 10
        private const val DEPARTURE_TILT = PI / 3
        private const val RETURN_TILT = PI / 9
        private const val AXIS_GYRO_FLOOR = 0.25
        private const val AXIS_MEMORY_TAU_S = 3.0
        private const val MIN_PLANE_PROJECTION = 0.40
        private const val MAX_PROJECTION_GAIN = 2.0
    }
}
