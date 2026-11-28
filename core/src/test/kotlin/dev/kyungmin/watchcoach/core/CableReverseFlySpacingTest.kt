package dev.kyungmin.watchcoach.core

import kotlin.math.PI
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CableReverseFlySpacingTest {
    @Test fun fasterReturnsAfterPauseStillCountOncePerRoundTrip() {
        val detector = ProfiledMotionRepDetector(ExerciseTrackingProfiles.resolve("crossover_reverse_fly"))
        var t = 1_000_000_000L
        val events = mutableListOf<ProfiledMotionRepEvent>()
        fun feed(rate: Double) {
            detector.add(SensorSample(t, 0f, 0f, 9.81f,
                (.36 * rate).toFloat(), (.48 * rate).toFloat(), (.80 * rate).toFloat(), 3))?.let(events::add)
            t += 20_000_000L
        }
        repeat(35) { feed(0.0) }
        // Two slower, equal-travel round trips, a pause, then six at a faster pace.
        repeat(8) { rep ->
            val frames = if (rep < 2) 120 else 80
            val start = t
            repeat(frames) { i -> feed((160.0 / frames) * sin(2 * PI * i / frames)) }
            repeat(if (rep == 1) 60 else 8) { feed(0.0) }
            assertEquals(rep + 1, events.size, "round trip #${rep + 1}")
            // A hit at the outward peak would pass a count-only test, but is half a cycle early.
            assertTrue(events.last().endTimestampNs in (start + frames * 10_000_000L)..t)
        }
        repeat(100) { feed(0.0) }
        assertEquals(8, events.size)
        assertTrue(detector.finishAll().isEmpty())
    }
}
