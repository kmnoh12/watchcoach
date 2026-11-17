package dev.kyungmin.watchcoach.core

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class StartPrimingRepDetectorTest {
    private val stepNs = 20_000_000L

    private fun stillSamples(
        count: Int,
        startNs: Long = 1_000_000_000L,
        ax: Float = 0f,
        ay: Float = 0f,
        az: Float = 9.80665f,
        gx: Float = 0f,
        gy: Float = 0f,
        gz: Float = 0f,
        jitterGyro: Float = 0f,
    ): List<SensorSample> = (0 until count).map { i ->
        val sign = if (i % 2 == 0) 1f else -1f
        SensorSample(
            timestampNs = startNs + i * stepNs,
            accelerationX = ax,
            accelerationY = ay,
            accelerationZ = az,
            gyroscopeX = gx + sign * jitterGyro,
            gyroscopeY = gy - sign * jitterGyro * 0.5f,
            gyroscopeZ = gz + sign * jitterGyro * 0.25f,
            sensorAccuracy = 3,
        )
    }

    /**
     * Out-and-back rotational cycle on an oblique axis (pull/fly), starting immediately
     * at t=0 after the still hold (no post-buzz pause).
     */
    private fun immediateFlyOrPull(
        reps: Int,
        outS: Double = 0.75,
        retS: Double = 0.75,
        pauseS: Double = 0.15,
        amplitude: Double = 1.8,
        startNs: Long,
        gyroBias: FloatArray = floatArrayOf(0f, 0f, 0f),
        axis: DoubleArray = doubleArrayOf(0.45, -0.62, 0.64),
    ): List<SensorSample> {
        val out = ArrayList<SensorSample>()
        var t = startNs
        val hz = 50
        repeat(reps) {
            val outSamples = (outS * hz).toInt()
            for (i in 0 until outSamples) {
                val p = (i + 0.5) / outSamples
                val rate = amplitude * sin(PI * p)
                out += SensorSample(
                    t,
                    0f, 0f, 9.80665f,
                    (rate * axis[0] + gyroBias[0]).toFloat(),
                    (rate * axis[1] + gyroBias[1]).toFloat(),
                    (rate * axis[2] + gyroBias[2]).toFloat(),
                    3,
                )
                t += stepNs
            }
            val retSamples = (retS * hz).toInt()
            for (i in 0 until retSamples) {
                val p = (i + 0.5) / retSamples
                val rate = -amplitude * sin(PI * p)
                out += SensorSample(
                    t,
                    0f, 0f, 9.80665f,
                    (rate * axis[0] + gyroBias[0]).toFloat(),
                    (rate * axis[1] + gyroBias[1]).toFloat(),
                    (rate * axis[2] + gyroBias[2]).toFloat(),
                    3,
                )
                t += stepNs
            }
            repeat((pauseS * hz).toInt()) {
                out += SensorSample(t, 0f, 0f, 9.80665f, gyroBias[0], gyroBias[1], gyroBias[2], 3)
                t += stepNs
            }
        }
        repeat(100) {
            out += SensorSample(t, 0f, 0f, 9.80665f, gyroBias[0], gyroBias[1], gyroBias[2], 3)
            t += stepNs
        }
        return out
    }

    /**
     * Press-return cycle along a tilted gravity orientation with immediate start after prime.
     */
    private fun immediateChestPress(
        reps: Int,
        periodS: Double = 2.0,
        strokeM: Double = 0.35,
        startNs: Long,
        gravX: Float = 2.4f,
        gravY: Float = -3.1f,
        gravZ: Float = 8.98f,
    ): List<SensorSample> {
        val out = ArrayList<SensorSample>()
        var t = startNs
        val hz = 50
        val omega = 2.0 * PI / periodS
        val gNorm = kotlin.math.sqrt((gravX * gravX + gravY * gravY + gravZ * gravZ).toDouble())
        val ux = gravX / gNorm
        val uy = gravY / gNorm
        val uz = gravZ / gNorm
        val steps = (reps * periodS * hz).toInt()
        for (i in 0 until steps) {
            val sec = i.toDouble() / hz
            val accel = (strokeM / 2.0) * omega * omega * cos(omega * sec)
            val gyro = 0.35 * sin(omega * sec)
            out += SensorSample(
                t,
                (gravX + accel * ux).toFloat(),
                (gravY + accel * uy).toFloat(),
                (gravZ + accel * uz).toFloat(),
                gyro.toFloat(), 0f, 0f, 3,
            )
            t += stepNs
        }
        repeat(100) {
            out += SensorSample(t, gravX, gravY, gravZ, 0f, 0f, 0f, 3)
            t += stepNs
        }
        return out
    }

    @Test
    fun immediateReverseFlyAfterStillHoldCountsAllRepsWithoutFlippingPhase() {
        val profile = ExerciseTrackingProfiles.resolve("machine_reverse_fly")
        val detector = ProfiledMotionRepDetector(profile)
        val prime = stillSamples(60, startNs = 1_000_000_000L, jitterGyro = 0.22f)
        val activeStartNs = prime.last().timestampNs + stepNs
        val active = immediateFlyOrPull(reps = 5, startNs = activeStartNs)

        detector.beginCounting()
        detector.prime(prime)
        assertEquals(0L, detector.lastMotionNs, "prime must not update lastMotionNs")

        val events = active.mapNotNull { detector.add(it) } + detector.finishAll()
        assertEquals(5, events.size, "all 5 reps including the first immediate rep must count")

        // Verify phase is NOT flipped: rep 1 turnaround should sit near the first out->return reversal (~0.75 s),
        // and rep 1 end should be near the end of the return (~1.50 s), not at the next rep's lift peak.
        val firstOutPeakApprox = activeStartNs + 750_000_000L
        val firstReturnEndApprox = activeStartNs + 1_500_000_000L
        assertTrue(
            events.first().turnaroundTimestampNs <= firstOutPeakApprox + 250_000_000L,
            "turnaround must be near the first reversal, got ${(events.first().turnaroundTimestampNs - activeStartNs) / 1e6} ms",
        )
        assertTrue(
            events.first().endTimestampNs <= firstReturnEndApprox + 250_000_000L,
            "first rep must complete on the first return, got ${(events.first().endTimestampNs - activeStartNs) / 1e6} ms",
        )
    }

    @Test
    fun stillHoldJitterDoesNotFreezeExcursionAxisOrSign() {
        val profile = ExerciseTrackingProfiles.resolve("lat_pull_down")
        val detector = ProfiledMotionRepDetector(profile)
        // High-frequency jitter above minimumFeatureRate (0.14) but tiny excursion span (< minSpan).
        val prime = stillSamples(65, startNs = 1_000_000_000L, jitterGyro = 0.25f)
        val activeStartNs = prime.last().timestampNs + stepNs
        // Exercise happens on a completely different axis and negative direction from the jitter.
        val active = immediateFlyOrPull(
            reps = 4,
            startNs = activeStartNs,
            axis = doubleArrayOf(-0.2, 0.85, -0.49),
        )

        detector.beginCounting()
        detector.prime(prime)
        val events = active.mapNotNull { detector.add(it) } + detector.finishAll()
        assertEquals(4, events.size, "jitter during priming must not freeze a wrong axis or sign")
    }

    @Test
    fun immediateChestPressAfterStillHoldCountsAllRepsWithoutFlippingPhase() {
        val profile = ExerciseTrackingProfiles.resolve("chest_press")
        val detector = ProfiledMotionRepDetector(profile)
        val gravX = 2.4f
        val gravY = -3.1f
        val gravZ = 8.98f
        val prime = stillSamples(60, startNs = 1_000_000_000L, ax = gravX, ay = gravY, az = gravZ, jitterGyro = 0.10f)
        val activeStartNs = prime.last().timestampNs + stepNs
        val active = immediateChestPress(reps = 5, periodS = 2.0, strokeM = 0.35, startNs = activeStartNs, gravX = gravX, gravY = gravY, gravZ = gravZ)

        detector.beginCounting()
        detector.prime(prime)
        assertEquals(0L, detector.lastMotionNs)

        val events = active.mapNotNull { detector.add(it) } + detector.finishAll()
        assertEquals(5, events.size, "press-return must count all 5 immediate reps")
        // First rep should complete around 1.5-2.0 s after activeStartNs, not delayed to rep 2 or half-shifted.
        assertTrue(
            events.first().endTimestampNs <= activeStartNs + 2_100_000_000L,
            "first press rep ended too late (likely missed or phase-flipped): ${(events.first().endTimestampNs - activeStartNs) / 1e6} ms",
        )
    }

    @Test
    fun immediateLateralRaiseWithEarlyFirstLiftPeakCountsOnReturnWithoutHalfBeatShift() {
        val profile = ExerciseTrackingProfiles.resolve("dumbbell_lateral_raise")
        val detector = ProfiledMotionRepDetector(profile)
        val prime = stillSamples(60, startNs = 1_000_000_000L)
        val activeStartNs = prime.last().timestampNs + stepNs
        val axis = doubleArrayOf(0.40, 0.70, -0.59)
        val liftPeaks = mutableListOf<Long>()
        val returnPeaks = mutableListOf<Long>()
        val active = ArrayList<SensorSample>()
        var t = activeStartNs

        fun addWave(durationSteps: Int, peakGyro: Double, peakAccel: Double) {
            for (i in 0 until durationSteps) {
                val phase = (i + 0.5) / durationSteps
                val g = peakGyro * sin(PI * phase)
                val a = peakAccel * sin(2 * PI * phase)
                active += SensorSample(
                    t,
                    (a * axis[0]).toFloat(),
                    (a * axis[1]).toFloat(),
                    (9.80665 + a * axis[2]).toFloat(),
                    (g * axis[0]).toFloat(),
                    (g * axis[1]).toFloat(),
                    (g * axis[2]).toFloat(),
                    3,
                )
                t += stepNs
            }
        }

        // First lift peaks at ~0.24 s (12 samples at 50 Hz = 6 samples at 25 Hz < PEAK_HALF_WINDOW=8).
        // Without priming, this first lift peak is invisible and returnLobeDelivery flips the whole set.
        repeat(6) {
            liftPeaks += t + 12 * stepNs
            addWave(durationSteps = 24, peakGyro = 1.8, peakAccel = 1.6)
            repeat(6) { active += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); t += stepNs }
            returnPeaks += t + 22 * stepNs
            addWave(durationSteps = 45, peakGyro = -1.2, peakAccel = -1.1)
            repeat(15) { active += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); t += stepNs }
        }
        repeat(100) { active += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); t += stepNs }

        detector.beginCounting()
        detector.prime(prime)
        assertEquals(0L, detector.lastMotionNs)

        val events = active.mapNotNull { detector.add(it) } + detector.finishAll()
        assertEquals(6, events.size, "all 6 lateral raises including first early-peak rep must count")
        events.forEachIndexed { idx, event ->
            val nearest = (liftPeaks.map { it to "lift" } + returnPeaks.map { it to "return" })
                .minBy { abs(it.first - event.endTimestampNs) }
            assertEquals("return", nearest.second, "rep ${idx + 1} shifted to ${nearest.second} instead of return")
        }
    }

    @Test
    fun immediateCurlAfterTiltedStillHoldCountsFirstRep() {
        val profile = ExerciseTrackingProfiles.resolve("barbell_biceps_curl")
        val detector = ProfiledMotionRepDetector(profile)
        val prime = stillSamples(60, startNs = 1_000_000_000L, ax = 0f, ay = 0f, az = 9.80665f)
        val activeStartNs = prime.last().timestampNs + stepNs
        val active = ArrayList<SensorSample>()
        var t = activeStartNs
        val amplitude = 100.0 * PI / 180.0
        repeat(4) {
            for (i in 1..40) {
                val p = i / 40.0
                val angle = amplitude * (1 - cos(PI * p)) / 2
                val rate = amplitude * PI * sin(PI * p) / 1.6
                active += SensorSample(t, 0f, (9.80665 * sin(angle)).toFloat(), (9.80665 * cos(angle)).toFloat(), rate.toFloat(), 0f, 0f, 3)
                t += stepNs
            }
            for (i in 1..40) {
                val p = i / 40.0
                val angle = amplitude * (1 + cos(PI * p)) / 2
                val rate = -amplitude * PI * sin(PI * p) / 1.6
                active += SensorSample(t, 0f, (9.80665 * sin(angle)).toFloat(), (9.80665 * cos(angle)).toFloat(), rate.toFloat(), 0f, 0f, 3)
                t += stepNs
            }
            repeat(5) {
                active += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3)
                t += stepNs
            }
        }

        detector.beginCounting()
        detector.prime(prime)
        assertEquals(0L, detector.lastMotionNs)

        val events = active.mapNotNull { detector.add(it) } + detector.finishAll()
        assertEquals(4, events.size, "pose baseline primed from still hold must count all 4 immediate curls")
    }

    @Test
    fun tiltedStillHoldBaselineCountsImmediateCurlWhenUnprimedFails() {
        val profile = ExerciseTrackingProfiles.resolve("barbell_biceps_curl")
        val baseAngle = 40.0 * PI / 180.0
        val prime = stillSamples(
            60,
            startNs = 1_000_000_000L,
            ax = 0f,
            ay = (9.80665 * sin(baseAngle)).toFloat(),
            az = (9.80665 * cos(baseAngle)).toFloat(),
        )
        val activeStartNs = prime.last().timestampNs + stepNs
        val active = ArrayList<SensorSample>()
        var t = activeStartNs
        val sweep = 70.0 * PI / 180.0 // 40° -> 110° (> 60° departure from 40°, < 60° if baseline drifts to ~65°)
        repeat(4) {
            for (i in 1..40) {
                val p = i / 40.0
                val angle = baseAngle + sweep * (1 - cos(PI * p)) / 2
                val rate = sweep * PI * sin(PI * p) / 1.6
                active += SensorSample(t, 0f, (9.80665 * sin(angle)).toFloat(), (9.80665 * cos(angle)).toFloat(), rate.toFloat(), 0f, 0f, 3)
                t += stepNs
            }
            for (i in 1..40) {
                val p = i / 40.0
                val angle = baseAngle + sweep * (1 + cos(PI * p)) / 2
                val rate = -sweep * PI * sin(PI * p) / 1.6
                active += SensorSample(t, 0f, (9.80665 * sin(angle)).toFloat(), (9.80665 * cos(angle)).toFloat(), rate.toFloat(), 0f, 0f, 3)
                t += stepNs
            }
            repeat(5) {
                active += SensorSample(t, 0f, (9.80665 * sin(baseAngle)).toFloat(), (9.80665 * cos(baseAngle)).toFloat(), 0f, 0f, 0f, 3)
                t += stepNs
            }
        }

        val primed = ProfiledMotionRepDetector(profile)
        primed.beginCounting()
        primed.prime(prime)
        val primedEvents = active.mapNotNull { primed.add(it) } + primed.finishAll()
        assertEquals(4, primedEvents.size, "primed tilted still-hold baseline must count all 4 reps")
    }

    @Test
    fun slowDriftDuringStillHoldDoesNotEmitFakeExcursionRepOrLockWrongAxis() {
        val profile = ExerciseTrackingProfiles.resolve("machine_reverse_fly")
        val detector = ProfiledMotionRepDetector(profile)
        val prime = ArrayList<SensorSample>()
        var t = 1_000_000_000L
        // Slow 0.12 rad sway out and back on X during the 1.2s still hold (within gate limits).
        for (i in 0 until 60) {
            val rate = if (i in 10 until 50) 0.25 * sin(2 * PI * (i - 10) / 40.0) else 0.0
            prime += SensorSample(t, 0f, 0f, 9.80665f, rate.toFloat(), 0f, 0f, 3)
            t += stepNs
        }
        val activeStartNs = t
        val active = immediateFlyOrPull(
            reps = 4,
            startNs = activeStartNs,
            axis = doubleArrayOf(-0.2, 0.85, -0.49),
        )

        detector.beginCounting()
        detector.prime(prime)
        val events = active.mapNotNull { detector.add(it) } + detector.finishAll()
        assertEquals(4, events.size, "still-hold sway must not add a fake rep or lock a wrong axis")
        assertTrue(events.all { it.endTimestampNs >= activeStartNs }, "no rep may end inside the prime window")
    }

    @Test
    fun cycleAxisPrimeRejectsPrimeJitterAndPlateauPeaks() {
        // 1) Lateral raise (countOnReturn=true) with a brief 0.65 rad/s wrist jitter inside prime.
        val latProfile = ExerciseTrackingProfiles.resolve("dumbbell_lateral_raise")
        val latDetector = ProfiledMotionRepDetector(latProfile)
        val latPrime = stillSamples(60, startNs = 1_000_000_000L).mapIndexed { idx, s ->
            if (idx in 15..22) s.copy(gyroscopeX = 0.65f) else s
        }
        val latStartNs = latPrime.last().timestampNs + stepNs
        val axis = doubleArrayOf(0.40, 0.70, -0.59)
        val liftPeaks = mutableListOf<Long>()
        val returnPeaks = mutableListOf<Long>()
        val latActive = ArrayList<SensorSample>()
        var t = latStartNs
        fun addLatWave(durationSteps: Int, peakGyro: Double, peakAccel: Double) {
            for (i in 0 until durationSteps) {
                val phase = (i + 0.5) / durationSteps
                val g = peakGyro * sin(PI * phase)
                val a = peakAccel * sin(2 * PI * phase)
                latActive += SensorSample(
                    t,
                    (a * axis[0]).toFloat(),
                    (a * axis[1]).toFloat(),
                    (9.80665 + a * axis[2]).toFloat(),
                    (g * axis[0]).toFloat(),
                    (g * axis[1]).toFloat(),
                    (g * axis[2]).toFloat(),
                    3,
                )
                t += stepNs
            }
        }
        repeat(6) {
            liftPeaks += t + 12 * stepNs
            addLatWave(24, 1.8, 1.6)
            repeat(6) { latActive += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); t += stepNs }
            returnPeaks += t + 22 * stepNs
            addLatWave(45, -1.2, -1.1)
            repeat(15) { latActive += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); t += stepNs }
        }
        repeat(100) { latActive += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); t += stepNs }

        latDetector.beginCounting()
        latDetector.prime(latPrime)
        val latEvents = latActive.mapNotNull { latDetector.add(it) } + latDetector.finishAll()
        assertEquals(6, latEvents.size, "jitter during prime must not add or drop lateral raise reps")
        latEvents.forEachIndexed { idx, event ->
            val nearest = (liftPeaks.map { it to "lift" } + returnPeaks.map { it to "return" })
                .minBy { abs(it.first - event.endTimestampNs) }
            assertEquals("return", nearest.second, "rep ${idx + 1} flipped to ${nearest.second} due to prime jitter")
        }

        // 2) Asymmetric peaks with countOnReturn=false (dumbbell_triceps_extension): still prime plateau after mean subtraction must not emit a rep.
        val triProfile = ExerciseTrackingProfiles.resolve("dumbbell_triceps_extension")
        val triDetector = ProfiledMotionRepDetector(triProfile)
        val triPrime = stillSamples(60, startNs = 1_000_000_000L)
        val triStartNs = triPrime.last().timestampNs + stepNs
        val triActive = ArrayList<SensorSample>()
        var rt = triStartNs
        repeat(5) {
            for (i in 0 until 30) {
                val g = 2.0 * sin(PI * (i + 0.5) / 30)
                triActive += SensorSample(rt, 0f, 0f, 9.80665f, g.toFloat(), 0f, 0f, 3)
                rt += stepNs
            }
            for (i in 0 until 60) {
                val g = -0.35 * sin(PI * (i + 0.5) / 60)
                triActive += SensorSample(rt, 0f, 0f, 9.80665f, g.toFloat(), 0f, 0f, 3)
                rt += stepNs
            }
            repeat(20) { triActive += SensorSample(rt, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); rt += stepNs }
        }
        repeat(100) { triActive += SensorSample(rt, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); rt += stepNs }

        triDetector.beginCounting()
        triDetector.prime(triPrime)
        val triEvents = triActive.mapNotNull { triDetector.add(it) } + triDetector.finishAll()
        assertEquals(5, triEvents.size, "asymmetric triceps extension with still prime must count exactly 5 reps")
        assertTrue(triEvents.all { it.endTimestampNs >= triStartNs }, "no triceps rep may come from the prime plateau")
    }

    @Test
    fun emptyPrimeProducesBitIdenticalEventsAcrossAllDetectorEngines() {
        val cases = listOf(
            "machine_reverse_fly" to immediateFlyOrPull(5, startNs = 2_000_000_000L),
            "lat_pull_down" to immediateFlyOrPull(5, startNs = 2_000_000_000L),
            "chest_press" to immediateChestPress(5, startNs = 2_000_000_000L),
            "dumbbell_lateral_raise" to immediateFlyOrPull(5, outS = 0.8, retS = 1.0, startNs = 2_000_000_000L),
            "barbell_biceps_curl" to CurlCycleRegressionTest.curlSamples(4, 1.0, 1.0),
            "flat_bench" to immediateChestPress(5, periodS = 2.5, strokeM = 0.40, startNs = 2_000_000_000L),
        )
        for ((exerciseId, samples) in cases) {
            val profile = ExerciseTrackingProfiles.resolve(exerciseId)

            val baseline = ProfiledMotionRepDetector(profile)
            baseline.beginCounting()
            val baseEvents = samples.mapNotNull { baseline.add(it) } + baseline.finishAll()

            val withEmptyPrime = ProfiledMotionRepDetector(profile)
            withEmptyPrime.beginCounting()
            withEmptyPrime.prime(emptyList())
            val primedEvents = samples.mapNotNull { withEmptyPrime.add(it) } + withEmptyPrime.finishAll()

            assertEquals(baseEvents, primedEvents, "empty prime must be bit-identical for $exerciseId")
            assertEquals(baseline.lastMotionNs, withEmptyPrime.lastMotionNs, "lastMotionNs mismatch for $exerciseId")
        }
    }
}
