package dev.kyungmin.watchcoach.core

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Causal return-stop repetition detector for rowing exercises (`seated_row`, `cable_seated_row`,
 * barbell/dumbbell/machine/cable row variants).
 *
 * Instead of firing at a contraction/deceleration peak plus a predicted return delay (which fails
 * across grips and tempos), this detector tracks the wrist's 3D linear velocity in a gyro-stabilized
 * world frame:
 *  1. Maintains a body-to-world rotation matrix via gyro integration with complementary gravity
 *     alignment so forearm rotation (normal grip, protruding horizontal grip, low undergrip) does
 *     not corrupt linear acceleration.
 *  2. Removes gravity and slow bias, then leaky-integrates into zero-centered 3D velocity with
 *     zero-velocity updates (ZUPT) during genuine stillness so last-rep stops confirm cleanly.
 *  3. Projects velocity onto the sign-continuous dominant 3D motion axis and tracks the ordered
 *     sequence: pull lobe -> chest turnaround -> return lobe -> return stop (velocity drops to
 *     near-zero and holds for [STOP_CONFIRM_NS] or reverses cleanly into the next pull).
 *
 * A chest pause (hold at max contraction) stays in [State.WAIT_RETURN] because no return lobe has
 * occurred yet, so it never triggers prematurely. Every accepted event carries `start < turnaround < end`
 * at the physical return end and `cueDelayMs = 0L`.
 *
 * For physically non-inertial synthetic test streams (e.g., pure gyro rotation with frozen gravity),
 * delegates transparently to the timestamp-consensus [CycleAxisRepDetector] fallback.
 */
class RowReturnStopDetector(
    private val dynOnly: Boolean = false,
) {
    companion object {
        private const val MIN_DT_S = 0.008
        private const val MAX_DT_S = 0.12
        private const val RESET_GAP_NS = 1_500_000_000L
        private const val MAX_CYCLE_NS = 7_000_000_000L

        private const val GRAVITY_NOMINAL = 9.80665
        private const val GRAVITY_CORR_BAND = 1.8
        private const val GRAVITY_LOW = 6.0
        private const val GRAVITY_HIGH = 14.0
        private const val WARMUP_ACCEL_S = 0.6
        private const val WARMUP_VB_S = 1.2
        private const val KP_WARMUP = 2.0
        private const val KP_STEADY = 0.5
        private const val TAU_BASE_WARMUP_S = 0.6
        private const val TAU_BASE_STEADY_S = 3.0
        private const val TAU_VEL_S = 3.0
        private const val TAU_VBASE_WARMUP_S = 1.2
        private const val TAU_VBASE_STEADY_S = 4.8
        private const val TAU_COV_S = 8.0

        // ZUPT during stillness so the final rep's velocity settles promptly to zero.
        private const val REST_FAST_TAU_S = 0.20
        private const val REST_ACCEL_DEV_FLOOR = 0.15
        private const val REST_GYRO_FLOOR = 0.15
        private const val REST_ZUPT_S = 0.22
        private const val REST_DECAY_TAU_S = 0.12

        // State-machine thresholds (world-frame linear velocity along principal axis, m/s & m).
        private const val LOCK_MIN_VEL = 0.20
        private const val LOCK_MIN_DISP = 0.045
        private const val MIN_VEL = 0.18
        private const val MIN_DISP = 0.045
        private const val ADAPT_VEL_FRAC = 0.46
        private const val ADAPT_DISP_FRAC = 0.46
        private const val STOP_VEL_FRAC = 0.06
        private const val REVERSAL_VEL_FRAC = -0.10
        private const val STOP_CONFIRM_NS = 220_000_000L
        private const val MIN_REP_SEP_NS = 950_000_000L
        private const val ADAPTIVE_PERIOD_FRAC = 0.55
        private const val MAX_ADAPTIVE_SEP_NS = 1_350_000_000L
        private const val MAX_PERIOD_GAP_NS = 4_500_000_000L
        private const val RECENT_WINDOW = 5

        // Synthetic non-inertial fallback guard (real IMU captures always have body dynamic accel
        // and consistent gravity rotation; gyro-only or frozen-gravity unit tests do not).
        private const val BODY_DYN_ACTIVATE_FLOOR = 0.45
        private const val GRAVITY_CONSISTENCY_MIN_DOT = 0.80
        private const val GRAVITY_MISMATCH_S = 0.35
    }

    private enum class State { WAIT_PULL, IN_PULL, WAIT_RETURN, IN_RETURN }

    val maximumCycleNs: Long get() = MAX_CYCLE_NS

    private val fallback = CycleAxisRepDetector(countOnReturn = true, phaseKernel = false, dynOnly = dynOnly)

    // Orientation R (3x3 row-major: maps body vector -> world vector; row 2 is world +Z / up).
    private val rot = DoubleArray(9)
    private var rotReady = false
    private val aBase = DoubleArray(3)
    private val aFastLpf = DoubleArray(3)
    private val bodyAccLpf = DoubleArray(3)
    private var bodyDynPeak = 0.0
    private var gravityMismatchS = 0.0
    private var useFallback = false

    private val vW = DoubleArray(3)
    private val vBase = DoubleArray(3)
    private val cov = DoubleArray(9)
    private var axis: DoubleArray? = null

    private var lastNs = 0L
    private var elapsedS = 0.0
    private var activeElapsedS = 0.0
    private var restS = 0.0
    private var primeEndNs = Long.MIN_VALUE

    private var pullSign = 0
    private var lobeSign = 0
    private var lobePeak = 0.0
    private var lobeDisp = 0.0
    private var lobeStartNs = 0L

    private var state = State.WAIT_PULL
    private var pullStartNs = 0L
    private var pullPeak = 0.0
    private var pullDisp = 0.0
    private var turnNs = 0L
    private var retPeak = 0.0
    private var retDisp = 0.0
    private var stopCandNs = -1L
    private var prevStopNs = Long.MIN_VALUE

    private val recentPeaks = ArrayDeque<Double>()
    private val recentDisps = ArrayDeque<Double>()
    private val recentPeriods = ArrayDeque<Long>()

    fun beginCounting() {
        fallback.beginCounting()
        rotReady = false
        rot.fill(0.0); rot[0] = 1.0; rot[4] = 1.0; rot[8] = 1.0
        aBase.fill(0.0)
        aFastLpf.fill(0.0)
        bodyAccLpf.fill(0.0)
        bodyDynPeak = 0.0
        gravityMismatchS = 0.0
        useFallback = false
        lastNs = 0L
        elapsedS = 0.0
        primeEndNs = Long.MIN_VALUE
        clearMotionState()
    }

    private fun clearMotionState() {
        vW.fill(0.0)
        vBase.fill(0.0)
        cov.fill(0.0)
        axis = null
        activeElapsedS = 0.0
        restS = 0.0
        pullSign = 0
        lobeSign = 0
        lobePeak = 0.0
        lobeDisp = 0.0
        lobeStartNs = 0L
        state = State.WAIT_PULL
        pullStartNs = 0L
        pullPeak = 0.0
        pullDisp = 0.0
        turnNs = 0L
        retPeak = 0.0
        retDisp = 0.0
        stopCandNs = -1L
        prevStopNs = Long.MIN_VALUE
        recentPeaks.clear()
        recentDisps.clear()
        recentPeriods.clear()
    }

    /** Warms up gravity orientation and baselines during stationary prep without emitting reps. */
    fun prime(samples: Iterable<SensorSample>) {
        val list = samples.toList()
        if (list.isEmpty()) return
        fallback.prime(list)
        var lastPrimed = Long.MIN_VALUE
        for (s in list) {
            if (s.timestampNs > lastPrimed) lastPrimed = s.timestampNs
            updateOrientation(s, priming = true)
        }
        primeEndNs = lastPrimed
        bodyDynPeak = 0.0
        gravityMismatchS = 0.0
        useFallback = false
        clearMotionState()
    }

    fun add(sample: SensorSample): ProfiledMotionRepEvent? {
        val fbEvent = fallback.add(sample)
        val t = sample.timestampNs
        if (sample.sensorAccuracy == 0 || t < 0L ||
            !sample.accelerationX.isFinite() || !sample.accelerationY.isFinite() || !sample.accelerationZ.isFinite() ||
            !sample.gyroscopeX.isFinite() || !sample.gyroscopeY.isFinite() || !sample.gyroscopeZ.isFinite()
        ) {
            return if (useFallback) fbEvent?.copy(cueDelayMs = 0L) else null
        }
        if (lastNs != 0L && t <= lastNs) return null
        if (lastNs != 0L && t - lastNs > RESET_GAP_NS) {
            rotReady = false
            elapsedS = 0.0
            bodyDynPeak = 0.0
            gravityMismatchS = 0.0
            clearMotionState()
        }

        val primaryEvent = processSample(sample)
        if (useFallback) return fbEvent?.copy(cueDelayMs = 0L)
        // Only emit gyro-only fallback if no real body linear acceleration has appeared at all.
        if (bodyDynPeak < BODY_DYN_ACTIVATE_FLOOR) return fbEvent?.copy(cueDelayMs = 0L)
        return primaryEvent
    }

    fun finishAll(): List<ProfiledMotionRepEvent> {
        val fbRest = fallback.finishAll().map { it.copy(cueDelayMs = 0L) }
        if (useFallback || bodyDynPeak < BODY_DYN_ACTIVATE_FLOOR) return fbRest
        if (state == State.IN_RETURN && stopCandNs > 0L && lastNs > 0L) {
            val ev = tryEmitRep(stopCandNs, lastNs)
            state = State.WAIT_PULL
            stopCandNs = -1L
            return listOfNotNull(ev)
        }
        return emptyList()
    }

    private fun updateOrientation(sample: SensorSample, priming: Boolean): Double {
        val t = sample.timestampNs
        val ax = sample.accelerationX.toDouble()
        val ay = sample.accelerationY.toDouble()
        val az = sample.accelerationZ.toDouble()
        val gx = sample.gyroscopeX.toDouble()
        val gy = sample.gyroscopeY.toDouble()
        val gz = sample.gyroscopeZ.toDouble()

        val dt = if (lastNs == 0L) 0.0 else (t - lastNs) / 1e9
        if (lastNs != 0L && dt < MIN_DT_S) return -1.0
        val step = dt.coerceIn(0.0, MAX_DT_S)
        lastNs = t
        elapsedS += step

        val aNorm = sqrt(ax * ax + ay * ay + az * az)
        if (!rotReady) {
            val ux: Double; val uy: Double; val uz: Double
            if (aNorm > 1e-6) { ux = ax / aNorm; uy = ay / aNorm; uz = az / aNorm }
            else { ux = 0.0; uy = 0.0; uz = 1.0 }
            // World frame: row 2 = up, row 0 = device X orthogonalized to up, row 1 = up x row0
            var exx = 1.0 - ux * ux; var exy = -ux * uy; var exz = -ux * uz
            var exn = sqrt(exx * exx + exy * exy + exz * exz)
            if (exn < 1e-4) {
                exx = -uy * ux; exy = 1.0 - uy * uy; exz = -uy * uz
                exn = sqrt(exx * exx + exy * exy + exz * exz).coerceAtLeast(1e-9)
            }
            exx /= exn; exy /= exn; exz /= exn
            val eyx = uy * exz - uz * exy
            val eyy = uz * exx - ux * exz
            val eyz = ux * exy - uy * exx
            rot[0] = exx; rot[1] = exy; rot[2] = exz
            rot[3] = eyx; rot[4] = eyy; rot[5] = eyz
            rot[6] = ux;  rot[7] = uy;  rot[8] = uz
            rotReady = true
            aBase[0] = rot[0] * ax + rot[1] * ay + rot[2] * az
            aBase[1] = rot[3] * ax + rot[4] * ay + rot[5] * az
            aBase[2] = rot[6] * ax + rot[7] * ay + rot[8] * az
            aFastLpf[0] = ax; aFastLpf[1] = ay; aFastLpf[2] = az
            bodyAccLpf[0] = ax; bodyAccLpf[1] = ay; bodyAccLpf[2] = az
            return 0.0
        }

        if (step > 0.0) {
            // Complementary gyro integration + gentle gravity tilt alignment (only when |a| is near 1g so linear accel doesn't tilt R)
            var cx = 0.0; var cy = 0.0; var cz = 0.0
            if (abs(aNorm - GRAVITY_NOMINAL) <= GRAVITY_CORR_BAND) {
                val invN = 1.0 / aNorm
                val aux = ax * invN; val auy = ay * invN; val auz = az * invN
                // World +Z expressed in body frame is row 2 of R (since R^T * [0,0,1] = row 2).
                val gbx = rot[6]; val gby = rot[7]; val gbz = rot[8]
                val kp = if (elapsedS < WARMUP_ACCEL_S) KP_WARMUP else KP_STEADY
                cx = (auy * gbz - auz * gby) * kp
                cy = (auz * gbx - aux * gbz) * kp
                cz = (aux * gby - auy * gbx) * kp
            }
            applyBodyRotation((gx + cx) * step, (gy + cy) * step, (gz + cz) * step)

            // Track body-frame LPF acceleration to measure real body dynamic acceleration & gravity consistency.
            val alphaLpf = 1.0 - exp(-step / 1.5)
            bodyAccLpf[0] += (ax - bodyAccLpf[0]) * alphaLpf
            bodyAccLpf[1] += (ay - bodyAccLpf[1]) * alphaLpf
            bodyAccLpf[2] += (az - bodyAccLpf[2]) * alphaLpf
            if (!priming) {
                val dx = ax - bodyAccLpf[0]; val dy = ay - bodyAccLpf[1]; val dz = az - bodyAccLpf[2]
                val bDyn = sqrt(dx * dx + dy * dy + dz * dz)
                if (bDyn > bodyDynPeak) bodyDynPeak = bDyn
                val lpfNorm = sqrt(bodyAccLpf[0] * bodyAccLpf[0] + bodyAccLpf[1] * bodyAccLpf[1] + bodyAccLpf[2] * bodyAccLpf[2])
                if (lpfNorm in GRAVITY_LOW..GRAVITY_HIGH) {
                    val dotG = (bodyAccLpf[0] * rot[6] + bodyAccLpf[1] * rot[7] + bodyAccLpf[2] * rot[8]) / lpfNorm
                    if (dotG < GRAVITY_CONSISTENCY_MIN_DOT) {
                        gravityMismatchS += step
                        if (gravityMismatchS >= GRAVITY_MISMATCH_S) useFallback = true
                    } else {
                        gravityMismatchS = max(0.0, gravityMismatchS - step)
                    }
                }
            }

            // World-frame acceleration & slow baseline removal
            val awx = rot[0] * ax + rot[1] * ay + rot[2] * az
            val awy = rot[3] * ax + rot[4] * ay + rot[5] * az
            val awz = rot[6] * ax + rot[7] * ay + rot[8] * az
            val tb = if (elapsedS < WARMUP_ACCEL_S) TAU_BASE_WARMUP_S else TAU_BASE_STEADY_S
            val alphaB = 1.0 - exp(-step / tb)
            aBase[0] += (awx - aBase[0]) * alphaB
            aBase[1] += (awy - aBase[1]) * alphaB
            aBase[2] += (awz - aBase[2]) * alphaB
        }
        return step
    }

    private fun processSample(sample: SensorSample): ProfiledMotionRepEvent? {
        val step = updateOrientation(sample, priming = false)
        if (step <= 0.0 || useFallback) return null

        val t = sample.timestampNs
        if (t <= primeEndNs) return null
        activeElapsedS += step

        val ax = sample.accelerationX.toDouble()
        val ay = sample.accelerationY.toDouble()
        val az = sample.accelerationZ.toDouble()
        val awx = rot[0] * ax + rot[1] * ay + rot[2] * az
        val awy = rot[3] * ax + rot[4] * ay + rot[5] * az
        val awz = rot[6] * ax + rot[7] * ay + rot[8] * az
        // Measure stillness in body frame so gentle complementary tilt relaxation never delays ZUPT.
        val alphaFast = 1.0 - exp(-step / REST_FAST_TAU_S)
        aFastLpf[0] += (ax - aFastLpf[0]) * alphaFast
        aFastLpf[1] += (ay - aFastLpf[1]) * alphaFast
        aFastLpf[2] += (az - aFastLpf[2]) * alphaFast
        val devx = ax - aFastLpf[0]; val devy = ay - aFastLpf[1]; val devz = az - aFastLpf[2]
        val fastDev = sqrt(devx * devx + devy * devy + devz * devz)
        val gyroMag = sqrt(
            sample.gyroscopeX.toDouble() * sample.gyroscopeX +
                sample.gyroscopeY.toDouble() * sample.gyroscopeY +
                sample.gyroscopeZ.toDouble() * sample.gyroscopeZ,
        )
        if (fastDev < REST_ACCEL_DEV_FLOOR && gyroMag < REST_GYRO_FLOOR) restS += step else restS = 0.0
        if (restS >= REST_ZUPT_S) {
            val kBase = 1.0 - exp(-step / REST_DECAY_TAU_S)
            aBase[0] += (awx - aBase[0]) * kBase
            aBase[1] += (awy - aBase[1]) * kBase
            aBase[2] += (awz - aBase[2]) * kBase
        }
        val adx = awx - aBase[0]
        val ady = awy - aBase[1]
        val adz = awz - aBase[2]

        val decayV = exp(-step / TAU_VEL_S)
        vW[0] = vW[0] * decayV + adx * step
        vW[1] = vW[1] * decayV + ady * step
        vW[2] = vW[2] * decayV + adz * step

        if (restS >= REST_ZUPT_S) {
            val kZupt = 1.0 - exp(-step / REST_DECAY_TAU_S)
            for (c in 0..2) vW[c] += (vBase[c] - vW[c]) * kZupt
        }

        val tvb = if (activeElapsedS < WARMUP_VB_S) TAU_VBASE_WARMUP_S else TAU_VBASE_STEADY_S
        val alphaVb = 1.0 - exp(-step / tvb)
        for (c in 0..2) vBase[c] += (vW[c] - vBase[c]) * alphaVb

        val vcx = vW[0] - vBase[0]
        val vcy = vW[1] - vBase[1]
        val vcz = vW[2] - vBase[2]

        val decayC = exp(-step / TAU_COV_S)
        cov[0] = cov[0] * decayC + vcx * vcx * step
        cov[1] = cov[1] * decayC + vcx * vcy * step
        cov[2] = cov[2] * decayC + vcx * vcz * step
        cov[3] = cov[1]
        cov[4] = cov[4] * decayC + vcy * vcy * step
        cov[5] = cov[5] * decayC + vcy * vcz * step
        cov[6] = cov[2]
        cov[7] = cov[5]
        cov[8] = cov[8] * decayC + vcz * vcz * step

        val trace = cov[0] + cov[4] + cov[8]
        if (trace > 1e-5) {
            axis = dominantAxis(cov, axis)
        }
        val u = axis ?: return null
        val vr = vcx * u[0] + vcy * u[1] + vcz * u[2]

        // Lock pull direction on the first substantial velocity stroke from rest.
        if (pullSign == 0) {
            val s = if (vr >= 0.0) 1 else -1
            if (abs(vr) < 0.05) {
                lobeSign = 0; lobePeak = 0.0; lobeDisp = 0.0; lobeStartNs = 0L
            } else if (s != lobeSign) {
                lobeSign = s; lobePeak = abs(vr); lobeDisp = abs(vr) * step; lobeStartNs = t
            } else {
                if (abs(vr) > lobePeak) lobePeak = abs(vr)
                lobeDisp += abs(vr) * step
                if (lobePeak >= LOCK_MIN_VEL && lobeDisp >= LOCK_MIN_DISP) {
                    pullSign = lobeSign
                    state = State.IN_PULL
                    pullStartNs = if (lobeStartNs > 0L) lobeStartNs else t
                    pullPeak = lobePeak
                    pullDisp = lobeDisp
                }
            }
            return null
        }

        // Oriented velocity: vs < 0 = PULL toward chest, vs > 0 = RETURN toward full extension.
        val vs = -pullSign * vr
        val effV = if (recentPeaks.size < 2) MIN_VEL else max(MIN_VEL, ADAPT_VEL_FRAC * medianOf(recentPeaks))
        val effD = if (recentDisps.size < 2) MIN_DISP else max(MIN_DISP, ADAPT_DISP_FRAC * medianOf(recentDisps))

        when (state) {
            State.WAIT_PULL -> {
                if (vs < -0.5 * effV) {
                    state = State.IN_PULL
                    pullStartNs = t
                    pullPeak = -vs
                    pullDisp = -vs * step
                }
            }
            State.IN_PULL -> {
                if (vs < 0.0) {
                    if (-vs > pullPeak) pullPeak = -vs
                    pullDisp += -vs * step
                } else {
                    if (pullPeak >= effV && pullDisp >= effD) {
                        state = State.WAIT_RETURN
                        turnNs = t
                        retPeak = vs
                        retDisp = vs * step
                        stopCandNs = -1L
                        if (retPeak >= 0.50 * effV && retDisp >= 0.30 * effD) {
                            state = State.IN_RETURN
                        }
                    } else {
                        state = State.WAIT_PULL
                    }
                }
            }
            State.WAIT_RETURN -> {
                // Chest pause stays here with vs ~ 0 and never emits until a real return lobe occurs.
                if (vs > 0.0) {
                    if (vs > retPeak) retPeak = vs
                    retDisp += vs * step
                    if (retPeak >= 0.50 * effV && retDisp >= 0.35 * effD) {
                        state = State.IN_RETURN
                    }
                } else if (vs < -effV) {
                    state = State.IN_PULL
                    if (-vs > pullPeak) pullPeak = -vs
                    pullDisp += -vs * step
                }
            }
            State.IN_RETURN -> {
                if (vs > 0.0) {
                    if (vs > retPeak) {
                        retPeak = vs
                        stopCandNs = -1L
                    }
                    retDisp += vs * step
                }
                val stopThr = STOP_VEL_FRAC * retPeak
                if (vs <= stopThr && retPeak >= 0.50 * effV && retDisp >= 0.40 * effD) {
                    if (stopCandNs < 0L) stopCandNs = t
                    val reversedIntoNextPull = vs <= REVERSAL_VEL_FRAC * retPeak
                    val settledAtStop = t - stopCandNs >= STOP_CONFIRM_NS
                    if (reversedIntoNextPull || settledAtStop) {
                        val event = tryEmitRep(stopCandNs, t)
                        stopCandNs = -1L
                        if (vs < -0.4 * effV) {
                            state = State.IN_PULL
                            pullStartNs = t
                            pullPeak = -vs
                            pullDisp = -vs * step
                        } else {
                            state = State.WAIT_PULL
                        }
                        return event
                    }
                } else if (vs > max(stopThr * 1.5, 0.18 * retPeak)) {
                    stopCandNs = -1L
                }
            }
        }
        return null
    }

    private fun tryEmitRep(stopNs: Long, emittedNs: Long): ProfiledMotionRepEvent? {
        var minSepNs = MIN_REP_SEP_NS
        if (recentPeriods.isNotEmpty()) {
            val med = medianLong(recentPeriods)
            minSepNs = max(minSepNs, (med * ADAPTIVE_PERIOD_FRAC).toLong().coerceAtMost(MAX_ADAPTIVE_SEP_NS))
        }
        if (prevStopNs != Long.MIN_VALUE && stopNs - prevStopNs < minSepNs) return null

        val startNs = if (pullStartNs in 1L until stopNs) pullStartNs else {
            if (prevStopNs != Long.MIN_VALUE && prevStopNs < stopNs) prevStopNs else (stopNs - 1_500_000_000L).coerceAtLeast(0L)
        }
        val safeTurnNs = if (turnNs in (startNs + 1L) until stopNs) turnNs else (startNs + stopNs) / 2L
        val durMs = ((stopNs - startNs) / 1_000_000L).coerceAtLeast(1L)

        if (prevStopNs != Long.MIN_VALUE) {
            val gap = stopNs - prevStopNs
            if (gap in 800_000_000L..MAX_PERIOD_GAP_NS) {
                if (recentPeriods.size >= RECENT_WINDOW) recentPeriods.removeFirst()
                recentPeriods.addLast(gap)
            }
        }
        prevStopNs = stopNs
        if (recentPeaks.size >= RECENT_WINDOW) recentPeaks.removeFirst()
        recentPeaks.addLast(min(pullPeak, retPeak))
        if (recentDisps.size >= RECENT_WINDOW) recentDisps.removeFirst()
        recentDisps.addLast(min(pullDisp, retDisp))

        return ProfiledMotionRepEvent(
            startTimestampNs = startNs,
            turnaroundTimestampNs = safeTurnNs,
            endTimestampNs = stopNs,
            durationMs = durMs,
            peakMotionRate = max(pullPeak, retPeak),
            motionDisplacement = pullDisp + retDisp,
            trajectorySpread = 0.0,
            confidence = 0.85,
            cueDelayMs = 0L,
        )
    }

    /** Right-multiplies R by exp([rx, ry, rz]_x) (Rodrigues formula) and re-orthonormalizes rows. */
    private fun applyBodyRotation(rx: Double, ry: Double, rz: Double) {
        val ang = sqrt(rx * rx + ry * ry + rz * rz)
        if (ang < 1e-9) return
        val kx = rx / ang; val ky = ry / ang; val kz = rz / ang
        val c = cos(ang); val s = sin(ang); val omc = 1.0 - c

        val d00 = c + kx * kx * omc
        val d01 = kx * ky * omc - kz * s
        val d02 = kx * kz * omc + ky * s
        val d10 = ky * kx * omc + kz * s
        val d11 = c + ky * ky * omc
        val d12 = ky * kz * omc - kx * s
        val d20 = kz * kx * omc - ky * s
        val d21 = kz * ky * omc + kx * s
        val d22 = c + kz * kz * omc

        val r00 = rot[0] * d00 + rot[1] * d10 + rot[2] * d20
        val r01 = rot[0] * d01 + rot[1] * d11 + rot[2] * d21
        val r02 = rot[0] * d02 + rot[1] * d12 + rot[2] * d22
        val r10 = rot[3] * d00 + rot[4] * d10 + rot[5] * d20
        val r11 = rot[3] * d01 + rot[4] * d11 + rot[5] * d21
        val r12 = rot[3] * d02 + rot[4] * d12 + rot[5] * d22
        val r20 = rot[6] * d00 + rot[7] * d10 + rot[8] * d20
        val r21 = rot[6] * d01 + rot[7] * d11 + rot[8] * d21
        val r22 = rot[6] * d02 + rot[7] * d12 + rot[8] * d22

        // Re-orthonormalize (keep row 2 = up exact, row 0 orthogonal, row 1 = row2 x row0)
        val n2 = sqrt(r20 * r20 + r21 * r21 + r22 * r22).coerceAtLeast(1e-12)
        val u20 = r20 / n2; val u21 = r21 / n2; val u22 = r22 / n2
        val dot02 = r00 * u20 + r01 * u21 + r02 * u22
        var u00 = r00 - dot02 * u20; var u01 = r01 - dot02 * u21; var u02 = r02 - dot02 * u22
        val n0 = sqrt(u00 * u00 + u01 * u01 + u02 * u02).coerceAtLeast(1e-12)
        u00 /= n0; u01 /= n0; u02 /= n0
        val u10 = u21 * u02 - u22 * u01
        val u11 = u22 * u00 - u20 * u02
        val u12 = u20 * u01 - u21 * u00

        rot[0] = u00; rot[1] = u01; rot[2] = u02
        rot[3] = u10; rot[4] = u11; rot[5] = u12
        rot[6] = u20; rot[7] = u21; rot[8] = u22
    }

    /** Dominant eigenvector of 3x3 symmetric PSD matrix with sign continuity against [prev]. */
    private fun dominantAxis(m: DoubleArray, prev: DoubleArray?): DoubleArray {
        var vx = prev?.get(0) ?: 1.0
        var vy = prev?.get(1) ?: 0.7
        var vz = prev?.get(2) ?: 0.3
        repeat(16) {
            val wx = m[0] * vx + m[1] * vy + m[2] * vz
            val wy = m[3] * vx + m[4] * vy + m[5] * vz
            val wz = m[6] * vx + m[7] * vy + m[8] * vz
            val norm = sqrt(wx * wx + wy * wy + wz * wz)
            if (norm < 1e-12) return prev ?: doubleArrayOf(1.0, 0.0, 0.0)
            vx = wx / norm; vy = wy / norm; vz = wz / norm
        }
        if (prev != null && vx * prev[0] + vy * prev[1] + vz * prev[2] < 0.0) {
            vx = -vx; vy = -vy; vz = -vz
        }
        return doubleArrayOf(vx, vy, vz)
    }

    private fun medianOf(values: Collection<Double>): Double {
        val s = values.sorted()
        val mid = s.size / 2
        return if (s.size % 2 == 1) s[mid] else (s[mid - 1] + s[mid]) / 2.0
    }

    private fun medianLong(values: Collection<Long>): Long {
        val s = values.sorted()
        val mid = s.size / 2
        return if (s.size % 2 == 1) s[mid] else (s[mid - 1] + s[mid]) / 2L
    }
}
