package dev.kyungmin.watchcoach.core

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Angle-invariant press counting and bench rack-end behavior (synthetic signals only). */
class AdaptivePressDetectorTest {
    private class BenchSim(
        exerciseId: String = "incline_bench",
        val target: Int = 9,
        val angle: Double = 30.0,
    ) {
        val d = ProfiledMotionRepDetector(ExerciseTrackingProfiles.resolve(exerciseId))
        val guard = PostTargetTempoGuard()
        val gate = SetEndGate()
        var k = 50
        val time: Double get() = k * 0.02
        val events = mutableListOf<Double>()
        val fast = mutableListOf<Double>()
        var closed: Double? = null

        init {
            d.beginCounting()
        }

        fun sample(a: Double) {
            val phi = angle * PI / 180.0
            val ns = k * 20_000_000L
            if (closed == null && gate.shouldEnd(
                    ns,
                    d.candidateStartNs,
                    d.maximumCycleNs,
                    if (d.rackSettled) 0L else SetEndGate.waitNs(events.size, target, 3_000_000_000L),
                    d.lastMotionNs,
                )
            ) {
                closed = time
            }
            val e = d.add(
                SensorSample(
                    ns,
                    (cos(phi) * a).toFloat(),
                    0f,
                    (9.80665 + sin(phi) * a).toFloat(),
                    0f,
                    0f,
                    0f,
                    3,
                ),
            )
            if (e != null && guard.accept(e.endTimestampNs, events.size, target) && gate.rep(e.endTimestampNs)) {
                events += time
            }
            if (d.rackSettled && fast.isEmpty()) fast += time
            k++
        }

        fun still(n: Int) {
            repeat(n) { sample(0.0) }
        }

        fun half(m: Double, n: Int) {
            val sec = 0.02 * n
            repeat(n) { sample(m * 2 * PI / (sec * sec) * sin(2 * PI * it / n)) }
        }

        fun rep() {
            half(-0.30, 55)
            half(0.30, 55)
        }

        fun start() {
            still(50)
            repeat(4) { rep() }
        }
    }

    @Test fun singlePressEngineCountsAcrossAllAngles() {
        for (exerciseId in listOf("chest_press", "machine_chest_press_plate", "flat_bench", "incline_bench")) {
            for (angle in listOf(-30.0, 0.0, 15.0, 30.0, 45.0, 60.0)) {
                val s = BenchSim(exerciseId = exerciseId, target = 6, angle = angle)
                s.still(50)
                repeat(6) { s.rep() }
                s.still(50)
                assertEquals(6, s.events.size, "$exerciseId angle=$angle")
            }
        }
    }

    @Test fun shortDropAtTargetClosesQuicklyWithoutExtraRep() {
        for (a in listOf(-30.0, 0.0, 15.0, 30.0, 45.0, 60.0)) {
            val s = BenchSim(target = 4, angle = a)
            s.start()
            s.still(25)
            s.half(-0.025, 17)
            val contact = s.time
            s.still(90)
            assertEquals(4, s.events.size, "angle=$a")
            assertNotNull(s.closed, "angle=$a")
            assertTrue(s.closed!! in contact..(contact + 1.5), "angle=$a closed=${s.closed} contact=$contact")
        }
    }

    @Test fun doubleContactRackImpactClosesFastBeforeTarget() {
        for (a in listOf(-30.0, 0.0, 15.0, 30.0, 45.0, 60.0)) {
            val s = BenchSim(target = 9, angle = a)
            s.start()
            s.sample(15.0)
            s.sample(-15.0)
            s.still(8)
            s.sample(15.0)
            s.sample(-15.0)
            val contact = s.time
            s.still(50)
            assertEquals(4, s.events.size, "angle=$a")
            assertTrue(s.fast.isNotEmpty(), "angle=$a events=${s.events} contact=$contact closed=${s.closed}")
            assertNotNull(s.closed, "angle=$a")
            assertTrue(s.closed!! in contact..(contact + 1.0), "angle=$a closed=${s.closed} contact=$contact")
        }
    }

    @Test fun shortDipBeforeTargetAllowsMidSetPauseAndResume() {
        for (a in listOf(-30.0, 0.0, 15.0, 30.0, 45.0, 60.0)) {
            for (hold in listOf(35, 75, 150)) {
                val s = BenchSim(target = 9, angle = a)
                s.start()
                s.still(35)
                s.half(-0.025, 17)
                s.still(hold)
                assertNull(s.closed, "angle=$a hold=$hold")
                assertEquals(4, s.events.size, "angle=$a hold=$hold")
                s.half(-0.275, 55)
                s.half(0.30, 55)
                s.still(50)
                assertNull(s.closed, "angle=$a hold=$hold")
                assertEquals(5, s.events.size, "angle=$a hold=$hold")
                assertTrue(s.fast.isEmpty(), "angle=$a hold=$hold")
            }
        }
    }

    @Test fun nonRackMovementsDoNotTriggerFalseRackClosureOrExtraRep() {
        // Opposite small stroke
        BenchSim().apply {
            start(); still(35); half(0.025, 17); still(90)
            assertEquals(4, events.size); assertTrue(fast.isEmpty()); assertNull(closed)
        }
        // Single knock while at lockout then continue
        BenchSim().apply {
            start(); sample(13.0); sample(-13.0); still(70); rep(); still(40)
            assertEquals(5, events.size); assertTrue(fast.isEmpty()); assertNull(closed)
        }
        // Half rep held at bottom
        BenchSim().apply {
            start(); still(35); half(-0.30, 55); still(80)
            assertEquals(4, events.size); assertTrue(fast.isEmpty()); assertNull(closed)
        }
        // Next rep past target
        BenchSim(target = 4).apply {
            start(); still(17); rep(); still(40)
            assertEquals(5, events.size); assertTrue(fast.isEmpty()); assertNull(closed)
        }
    }
}
