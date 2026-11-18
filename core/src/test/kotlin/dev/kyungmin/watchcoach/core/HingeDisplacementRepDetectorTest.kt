package dev.kyungmin.watchcoach.core

import java.util.Random
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals

/** Analytic height cycles (down and back up) fed through the production routing of the hinge lifts. */
class HingeDisplacementRepDetectorTest {
    private val g = 9.80665
    private val stepNs = 20_000_000L

    private fun stream(
        periodS: Double, reps: Int, travelM: Double, accelNoise: Double = 0.0, tiltDeg: Double = 0.0,
        gyroNoise: Double = 0.0, swayOnly: Boolean = false,
    ): Pair<List<SensorSample>, List<SensorSample>> {
        val random = Random(11)
        val tilt = Math.toRadians(tiltDeg)
        fun sample(t: Double, ns: Long, az: Double): SensorSample {
            // Up axis tilted by `tilt` about X: specific force (g + az) along it.
            val f = g + az
            return SensorSample(
                ns,
                (random.nextGaussian() * accelNoise).toFloat(),
                (f * sin(tilt) + random.nextGaussian() * accelNoise).toFloat(),
                (f * cos(tilt) + random.nextGaussian() * accelNoise).toFloat(),
                (random.nextGaussian() * gyroNoise).toFloat(), (random.nextGaussian() * gyroNoise).toFloat(), (random.nextGaussian() * gyroNoise).toFloat(),
                3,
            )
        }
        var ns = 1_000_000_000L
        val prep = (0 until 150).map { val s = sample(0.0, ns, 0.0); ns += stepNs; s }
        val work = ArrayList<SensorSample>()
        val w = 2 * PI / periodS
        val half = travelM / 2
        val total = ((reps * periodS + 8.0) * 50).toInt()
        for (i in 0 until total) {
            val t = i * 0.02
            val inRep = t < reps * periodS
            // height = half * cos(w t) - half: starts at the top (0), goes down by travel, returns.
            val az = if (inRep && !swayOnly) -half * w * w * cos(w * t) else if (swayOnly) -0.02 * w * w * cos(w * t) else 0.0
            work += sample(t, ns, az); ns += stepNs
        }
        return prep to work
    }

    private fun count(prep: List<SensorSample>, work: List<SensorSample>, id: String = "conventional_deadlift"): Int {
        val detector = ProfiledMotionRepDetector(ExerciseTrackingProfiles.resolve(id))
        detector.beginCounting()
        detector.prime(prep)
        val live = work.mapNotNull { detector.add(it) }
        return live.size + detector.finishAll().size
    }

    @Test fun tenRepsAtEveryTempoAndWatchLevelNoise() {
        for (period in listOf(2.1, 2.6, 3.25, 3.9)) for (noise in listOf(0.0, 0.05, 0.15)) {
            val (prep, work) = stream(period, 10, 0.4, accelNoise = noise, gyroNoise = noise / 5)
            assertEquals(10, count(prep, work), "period $period noise $noise")
        }
    }

    @Test fun startingTiltDoesNotChangeTheCount() {
        for (tilt in listOf(-15.0, 15.0)) {
            val (prep, work) = stream(3.25, 10, 0.4, accelNoise = 0.05, tiltDeg = tilt, gyroNoise = 0.01)
            assertEquals(10, count(prep, work), "tilt $tilt")
        }
    }

    @Test fun stillAndSmallSwayCountNothing() {
        for (id in listOf("conventional_deadlift", "sumo_deadlift", "romanian_deadlift_barbell")) {
            val (prep, still) = stream(3.0, 0, 0.0, accelNoise = 0.15, gyroNoise = 0.03)
            assertEquals(0, count(prep, still, id), "$id still")
            val (prep2, sway) = stream(2.5, 10, 0.0, accelNoise = 0.05, swayOnly = true)
            assertEquals(0, count(prep2, sway, id), "$id sway")
        }
    }
}
