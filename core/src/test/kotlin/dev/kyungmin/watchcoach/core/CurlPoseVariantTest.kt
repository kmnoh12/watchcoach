package dev.kyungmin.watchcoach.core

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.test.Test
import kotlin.test.assertEquals

/** Synthetic pose-variant invariance for curls and pushdowns (grip rotation, elbow flare, dynamic spread). */
class CurlPoseVariantTest {
    private fun rotateVec(v: DoubleArray, axis: DoubleArray, rad: Double): DoubleArray {
        val c = cos(rad)
        val s = sin(rad)
        val dot = axis[0] * v[0] + axis[1] * v[1] + axis[2] * v[2]
        return doubleArrayOf(
            v[0] * c + (axis[1] * v[2] - axis[2] * v[1]) * s + axis[0] * dot * (1 - c),
            v[1] * c + (axis[2] * v[0] - axis[0] * v[2]) * s + axis[1] * dot * (1 - c),
            v[2] * c + (axis[0] * v[1] - axis[1] * v[0]) * s + axis[2] * dot * (1 - c),
        )
    }

    /**
     * Synthesizes a flexion/extension set (e.g. cable pushdown or rope hammer curl) where the elbow
     * is flared out of the vertical plane by [flareDeg] (shrinking raw gravity tilt by cos(flareDeg))
     * and the wrist grip is rotated by [gripDeg].
     */
    private fun variantSamples(
        reps: Int,
        amplitudeDeg: Double,
        flareDeg: Double,
        gripDeg: Double,
        upS: Double = 1.0,
        downS: Double = 1.0,
    ): List<SensorSample> {
        val amp = amplitudeDeg * PI / 180.0
        val phi = flareDeg * PI / 180.0
        val gripRad = gripDeg * PI / 180.0
        val gripAxis = doubleArrayOf(0.4, 0.8, 0.4472135955).let { a ->
            val n = sqrt(a.sumOf { it * it })
            doubleArrayOf(a[0] / n, a[1] / n, a[2] / n)
        }
        var t = 1_000_000_000L
        val out = ArrayList<SensorSample>()
        fun emit(alpha: Double, rate: Double) {
            // Hinge axis is +X; gravity is tilted toward +X by flare angle phi.
            val g0 = doubleArrayOf(
                9.80665 * sin(phi),
                9.80665 * cos(phi) * sin(alpha),
                9.80665 * cos(phi) * cos(alpha),
            )
            val w0 = doubleArrayOf(rate, 0.0, 0.0)
            val g = rotateVec(g0, gripAxis, gripRad)
            val w = rotateVec(w0, gripAxis, gripRad)
            out += SensorSample(
                t,
                g[0].toFloat(), g[1].toFloat(), g[2].toFloat(),
                w[0].toFloat(), w[1].toFloat(), w[2].toFloat(),
                sensorAccuracy = 3,
            )
            t += 20_000_000L
        }
        repeat(25) { emit(0.0, 0.0) }
        repeat(reps) {
            val upSteps = (upS * 50).toInt()
            for (i in 1..upSteps) {
                val p = i.toDouble() / upSteps
                emit(amp * (1 - cos(PI * p)) / 2, amp * PI * sin(PI * p) / (2 * upS))
            }
            val downSteps = (downS * 50).toInt()
            for (i in 1..downSteps) {
                val p = i.toDouble() / downSteps
                emit(amp * (1 + cos(PI * p)) / 2, -amp * PI * sin(PI * p) / (2 * downS))
            }
        }
        repeat(25) { emit(0.0, 0.0) }
        return out
    }

    private fun count(exerciseId: String, samples: List<SensorSample>): Int {
        val d = ProfiledMotionRepDetector(ExerciseTrackingProfiles.resolve(exerciseId))
        d.beginCounting()
        return samples.count { d.add(it) != null } + if (d.finish() != null) 1 else 0
    }

    @Test fun pushdownAndHammerCurlCountAcrossElbowFlareAndGripRotations() {
        for (exerciseId in listOf("cable_pushdown", "rope_hammer_curl", "rope_extension", "cable_curl")) {
            for (flare in listOf(-40.0, -30.0, -20.0, 0.0, 20.0, 30.0, 40.0)) {
                for (grip in listOf(-40.0, 0.0, 40.0)) {
                    // 75-degree arc: at 40 deg flare, raw 3D gravity tilt shrinks to 55.6 deg (< 60 deg),
                    // which failed the old unprojected gravity-tilt threshold.
                    val samples = variantSamples(reps = 8, amplitudeDeg = 75.0, flareDeg = flare, gripDeg = grip)
                    assertEquals(8, count(exerciseId, samples), "$exerciseId flare=$flare grip=$grip")
                }
            }
        }
    }

    @Test fun flaredRopeHammerCurlWithPostSetupElbowShiftStillCountsEveryRep() {
        // Simulates starting setup at 0 deg flare, then flaring elbows 25 deg outward during working reps.
        val setup = variantSamples(reps = 0, amplitudeDeg = 85.0, flareDeg = 0.0, gripDeg = 15.0).take(25)
        val working = variantSamples(reps = 10, amplitudeDeg = 85.0, flareDeg = 25.0, gripDeg = 15.0).drop(25)
        var t = 1_000_000_000L
        val combined = (setup + working).map { s -> s.copy(timestampNs = t).also { t += 20_000_000L } }
        assertEquals(10, count("rope_hammer_curl", combined))
        assertEquals(10, count("cable_pushdown", combined))
    }

    @Test fun horizontalGyroShakeWithoutGravityChangeStillCountsZero() {
        val d = ProfiledMotionRepDetector(ExerciseTrackingProfiles.resolve("cable_pushdown"))
        d.beginCounting()
        var t = 1_000_000_000L
        var count = 0
        repeat(5) {
            for (rate in listOf(2.0f, 0f, -2.0f, 0f)) {
                repeat(15) {
                    if (d.add(SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, rate, 3)) != null) count++
                    t += 20_000_000L
                }
            }
        }
        assertEquals(0, count)
    }
}
