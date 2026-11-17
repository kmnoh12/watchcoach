package dev.kyungmin.watchcoach.core

import kotlin.test.Test
import kotlin.test.assertEquals

class HeartRateGuardTest {
    private val sec = 1_000_000_000L

    private fun feed(guard: HeartRateGuard, fromSec: Int, toSec: Int, bpm: Int) =
        (fromSec..toSec).map { guard.offer(it * sec, bpm) }

    @Test fun normalReadingsAreAcceptedAndFollowTheTrend() {
        val g = HeartRateGuard()
        feed(g, 0, 5, 110)
        val r = g.offer(6 * sec, 118)
        assertEquals(HeartRateGuard.Verdict.ACCEPTED, r.verdict)
        assertEquals(118, r.stableBpm)
    }

    @Test fun suddenHalvedReadingIsHeldAtTheLastStableValue() {
        val g = HeartRateGuard()
        feed(g, 0, 10, 112)
        val r = g.offer(11 * sec, 56)
        assertEquals(HeartRateGuard.Verdict.SUSPECT, r.verdict)
        assertEquals(112, r.stableBpm)
    }

    @Test fun persistentHalvedReadingAsksForASensorRestartOnce() {
        val g = HeartRateGuard()
        feed(g, 0, 10, 112)
        val results = (11..22).map { g.offer(it * sec, 55) }
        assertEquals(1, results.count { it.verdict == HeartRateGuard.Verdict.RESTART_SENSOR })
        assertEquals(true, results.all { it.stableBpm == 112 })
    }

    @Test fun afterARestartTheNextReadingIsTrusted() {
        val g = HeartRateGuard()
        feed(g, 0, 10, 112)
        (11..20).forEach { g.offer(it * sec, 55) }
        val r = g.offer(21 * sec, 110)
        assertEquals(HeartRateGuard.Verdict.ACCEPTED, r.verdict)
        assertEquals(110, r.stableBpm)
    }

    @Test fun lowRestingHeartRateIsNotTreatedAsAGlitch() {
        val g = HeartRateGuard()
        feed(g, 0, 10, 72)
        val r = g.offer(11 * sec, 50)
        assertEquals(HeartRateGuard.Verdict.ACCEPTED, r.verdict)
        assertEquals(50, r.stableBpm)
    }

    @Test fun realRecoveryDropsGraduallyAreAccepted() {
        val g = HeartRateGuard()
        var bpm = 150
        val verdicts = (0..30).map { t -> bpm = (bpm - 2).coerceAtLeast(95); g.offer(t * sec, bpm).verdict }
        assertEquals(true, verdicts.all { it == HeartRateGuard.Verdict.ACCEPTED })
    }

    @Test fun outOfRangeReadingsAreSuspect() {
        val g = HeartRateGuard()
        feed(g, 0, 3, 100)
        assertEquals(HeartRateGuard.Verdict.SUSPECT, g.offer(4 * sec, 0).verdict)
        assertEquals(HeartRateGuard.Verdict.SUSPECT, g.offer(5 * sec, 300).verdict)
    }
}

class HeartDisplayGateTest {
    @Test fun firstValueShowsAtOnceThenHoldsForTheInterval() {
        val gate = HeartDisplayGate(10_000L, 5_000L)
        assertEquals(110, gate.offer(0, 110, working = true))
        assertEquals(110, gate.offer(4_000, 120, working = true))
        assertEquals(110, gate.offer(9_000, 130, working = true))
    }

    @Test fun refreshShowsTheMedianOfWhatArrived() {
        val gate = HeartDisplayGate(10_000L, 5_000L)
        gate.offer(0, 100, working = true)
        listOf(120, 124, 126, 128).forEachIndexed { i, v -> gate.offer(2_000L + i * 2_000L, v, working = true) }
        assertEquals(126, gate.offer(10_000, 130, working = true)) // median of 120,124,126,128,130
    }

    @Test fun restingRefreshesEveryFiveSeconds() {
        val gate = HeartDisplayGate(10_000L, 5_000L)
        gate.offer(0, 130, working = false)
        assertEquals(130, gate.offer(4_000, 120, working = false))
        assertEquals(119, gate.offer(5_000, 118, working = false)) // median of the 120 and 118 that arrived since
    }

    @Test fun noReadingClearsTheDisplay() {
        val gate = HeartDisplayGate()
        gate.offer(0, 100, working = true)
        assertEquals(0, gate.offer(1_000, 0, working = true))
        assertEquals(95, gate.offer(2_000, 95, working = true))
    }
}
