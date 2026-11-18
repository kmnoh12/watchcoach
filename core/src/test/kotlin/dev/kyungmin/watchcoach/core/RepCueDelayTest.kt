package dev.kyungmin.watchcoach.core

import kotlin.math.PI
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class RepCueDelayTest {
    private fun ms(v: Long) = v * 1_000_000L

    @Test
    fun delaysByTheFractionOfTimeSinceTheTop() = assertEquals(320L, RepCueDelay.delayMs(0L, ms(800)))

    @Test
    fun clampsFastAndSlowDescents() {
        assertEquals(RepCueDelay.MIN_MS, RepCueDelay.delayMs(0L, ms(200)))
        assertEquals(RepCueDelay.MAX_MS, RepCueDelay.delayMs(0L, ms(3_000)))
    }

    @Test
    fun invalidTimingFallsBackToImmediate() {
        assertEquals(0L, RepCueDelay.delayMs(ms(900), ms(800)))
        assertEquals(0L, RepCueDelay.delayMs(0L, ms(9_000)))
    }

    @Test
    fun rowReturnDelayUsesLearnedReturnDurationAndSmoothingLag() {
        // peak=1000ms, emitted=1320ms, learnedReturn=1200ms -> target = 1000 - 160 + 0.85*1200 = 1860ms -> delay = 540ms
        assertEquals(540L, RepCueDelay.rowReturnDelayMs(ms(1_000), ms(1_320), ms(1_200)))
        assertEquals(0L, RepCueDelay.rowReturnDelayMs(ms(1_000), ms(1_320), 0L))
        assertEquals(0L, RepCueDelay.rowReturnDelayMs(ms(1_000), ms(1_320), ms(5_000)))
    }

    @Test
    fun unifiedDelayTrimsBeforeCompletionAndRespectsBounds() {
        // turn=1000ms, predReturn=1500ms -> comp=2500ms, cue=2425ms; emitted=2100ms -> delay=325ms
        assertEquals(325L, RepCueDelay.unifiedDelayMs(ms(1_000), ms(2_100), ms(1_500)))
        // Upper bound clamped at MAX_CUE_DELAY_MS (900ms)
        assertEquals(RepCueDelay.MAX_CUE_DELAY_MS, RepCueDelay.unifiedDelayMs(ms(1_000), ms(1_200), ms(2_000)))
        // Past cue never returns negative delay
        assertEquals(0L, RepCueDelay.unifiedDelayMs(ms(1_000), ms(2_450), ms(1_500)))
        // Invalid timings fall back to 0
        assertEquals(0L, RepCueDelay.unifiedDelayMs(ms(1_000), ms(900), ms(1_500)))
        assertEquals(0L, RepCueDelay.unifiedDelayMs(ms(1_000), ms(1_500), 0L))
    }

    @Test
    fun unifiedSchedulerFallsBackOnFirstRepAndLearnsReturnDurationForLaterReps() {
        val scheduler = UnifiedCueScheduler(MotionFamily.MULTI_AXIS_RETURN)
        // First rep before any measurement: fallbackRatio(MULTI_AXIS_RETURN) = 1.25
        // turn=1000ms, emit=2000ms (sinceTurn=1000ms) -> predReturn=1250ms, cue=2175ms -> delay=175ms
        val firstEvent = ProfiledMotionRepEvent(ms(100), ms(1_000), ms(2_000), 1_900L, 1.5, 2.0, 0.2, 0.9)
        assertEquals(175L, scheduler.schedule(firstEvent, ms(2_000)))

        // Now feed two full rotational reps where return takes ~1400ms and emit happens at ~1000ms after turn
        scheduler.reset()
        val hz = 50
        val outMs = 1000L
        val retMs = 1400L
        var tMs = 0L
        val samples = mutableListOf<SensorSample>()
        // 400ms still lead-in
        repeat(20) {
            samples += SensorSample(ms(tMs), 0f, 0f, 9.8f, 0f, 0f, 0f, 3)
            tMs += 20L
        }
        val repEvents = mutableListOf<Pair<ProfiledMotionRepEvent, Long>>()
        repeat(2) {
            val repStart = tMs
            val outSteps = (outMs / 20L).toInt()
            for (i in 0 until outSteps) {
                val gx = (1.6 * sin(PI * i / outSteps)).toFloat()
                samples += SensorSample(ms(tMs), 0f, 0f, 9.8f, gx, 0f, 0f, 3)
                tMs += 20L
            }
            val turn = tMs
            val retSteps = (retMs / 20L).toInt()
            var emitAt = 0L
            for (i in 0 until retSteps) {
                val gx = (-1.15 * sin(PI * i / retSteps)).toFloat()
                samples += SensorSample(ms(tMs), 0f, 0f, 9.8f, gx, 0f, 0f, 3)
                if (i == (retSteps * 0.60).toInt()) emitAt = tMs
                tMs += 20L
            }
            // Brief 200ms rest between reps
            repeat(10) {
                samples += SensorSample(ms(tMs), 0f, 0f, 9.8f, 0f, 0f, 0f, 3)
                tMs += 20L
            }
            repEvents += ProfiledMotionRepEvent(ms(repStart), ms(turn), ms(emitAt), emitAt - repStart, 1.6, 2.0, 0.2, 0.9) to ms(emitAt)
        }

        var repIdx = 0
        val delays = mutableListOf<Long>()
        for (s in samples) {
            scheduler.observe(s)
            if (repIdx < repEvents.size && s.timestampNs >= repEvents[repIdx].second) {
                val (ev, emitNs) = repEvents[repIdx++]
                delays += scheduler.schedule(ev, emitNs)
            }
        }
        assertEquals(2, delays.size)
        val learned = scheduler.learnedReturnNs()
        assertNotNull(learned)
        // 90% return of a 1400ms half-sine return sits around 1113ms
        assertTrue(learned in ms(1_000)..ms(1_250), "learned=$learned")
        assertTrue(delays[1] in 100L..400L, "second rep delay=${delays[1]}")

        // Gap > 450ms resets learned state
        scheduler.observe(SensorSample(ms(tMs + 1_000L), 0f, 0f, 9.8f, 0f, 0f, 0f, 3))
        assertEquals(0, scheduler.measuredCount)
    }

    @Test
    fun unifiedSchedulerNeverSchedulesInThePastForReturnEndFamilies() {
        val scheduler = UnifiedCueScheduler(MotionFamily.TRANSLATION_PRESS_RETURN)
        val ev = ProfiledMotionRepEvent(ms(100), ms(1_000), ms(2_000), 1_900L, 1.0, 1.0, 0.0, 0.7)
        // fallbackRatio(TRANSLATION_PRESS_RETURN) = 0.55 -> pred=1550ms, cue=1475ms < emit=2000ms -> 0ms
        assertEquals(0L, scheduler.schedule(ev, ms(2_000)))
    }
}
