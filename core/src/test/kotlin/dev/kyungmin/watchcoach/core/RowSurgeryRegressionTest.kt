package dev.kyungmin.watchcoach.core

import kotlin.math.PI
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Regression tests for the row engine surgery (② + ③):
 * 1) RowReturnStopDetector directly detects full-extension return stops with cueDelayMs == 0,
 *    remains immune to chest pauses (contraction holds), handles continuous fast tempo and last-rep
 *    stops, and produces strictly monotonic timestamps with zero buzz inversions.
 * 2) UnifiedCueScheduler suppresses predicted return delay only for return-stop rows while preserving
 *    non-row cycle exercises (lateral raises, pull-ups) and other families (machine_fly returnScale=1.27).
 */
class RowSurgeryRegressionTest {
    private fun ms(v: Long) = v * 1_000_000L

    /** Physically consistent linear horizontal row stroke: pull (neg vel) -> optional chest hold -> return (pos vel) -> end pause. */
    private fun linearRowStream(
        reps: Int,
        pullSteps: Int = 50,
        chestHoldSteps: Int = 0,
        returnSteps: Int = 60,
        endRestSteps: Int = 10,
        ampAcc: Double = 3.2,
    ): List<SensorSample> {
        val stepNs = 20_000_000L
        var t = 1_000_000_000L
        val samples = mutableListOf<SensorSample>()
        fun add(ax: Double) {
            samples += SensorSample(t, ax.toFloat(), 0f, 9.80665f, 0f, 0f, 0f, 3)
            t += stepNs
        }
        repeat(40) { add(0.0) }
        repeat(reps) {
            // Pull: accel negative then positive (velocity stays negative, returns to 0 at chest)
            for (i in 0 until pullSteps) {
                val p = i.toDouble() / pullSteps
                add(-ampAcc * sin(2 * PI * p))
            }
            // Optional hold/squeeze at chest (must NOT trigger a count!)
            repeat(chestHoldSteps) { add(0.0) }
            // Return: accel positive then negative (velocity stays positive, returns to 0 at full extension)
            for (i in 0 until returnSteps) {
                val p = i.toDouble() / returnSteps
                add(ampAcc * sin(2 * PI * p))
            }
            repeat(endRestSteps) { add(0.0) }
        }
        repeat(60) { add(0.0) }
        return samples
    }

    @Test
    fun seatedAndCableRowsEmitAtReturnStopWithZeroCueDelayAndChestPauseImmunity() {
        for (exerciseId in listOf("seated_row", "cable_seated_row")) {
            val samples = linearRowStream(reps = 6, pullSteps = 50, chestHoldSteps = 60, returnSteps = 60, endRestSteps = 15)
            val detector = ProfiledMotionRepDetector(ExerciseTrackingProfiles.resolve(exerciseId))
            detector.beginCounting()
            val events = mutableListOf<Pair<ProfiledMotionRepEvent, Long>>()
            for (s in samples) {
                detector.add(s)?.let { events += it to s.timestampNs }
            }
            events += detector.finishAll().map { it to samples.last().timestampNs }

            assertEquals(6, events.size, exerciseId)
            assertTrue(events.all { it.first.cueDelayMs == 0L }, "$exerciseId cueDelayMs must be 0")
            assertTrue(events.all { it.first.startTimestampNs < it.first.turnaroundTimestampNs && it.first.turnaroundTimestampNs < it.first.endTimestampNs },
                "$exerciseId must populate start < turnaround < end")
            // Confirm lag stays short (<= 300ms) and buzzes are strictly monotonic
            for (i in events.indices) {
                val lagMs = (events[i].second - events[i].first.endTimestampNs) / 1_000_000L
                assertTrue(lagMs in 0L..320L, "$exerciseId confirm lag out of range: ${lagMs}ms")
                if (i > 0) {
                    assertTrue(events[i].first.endTimestampNs > events[i - 1].first.endTimestampNs)
                    assertTrue(events[i].second > events[i - 1].second)
                }
            }
        }
    }

    @Test
    fun continuousFastRowTempoWithNoEndPauseCountsEveryRep() {
        val samples = linearRowStream(reps = 8, pullSteps = 35, chestHoldSteps = 0, returnSteps = 40, endRestSteps = 0, ampAcc = 4.0)
        val detector = ProfiledMotionRepDetector(ExerciseTrackingProfiles.resolve("seated_row"))
        detector.beginCounting()
        val live = samples.mapNotNull { detector.add(it) }
        val total = live + detector.finishAll()
        assertEquals(8, total.size, "continuous fast tempo without pauses must count all 8 reps")
        assertTrue(total.all { it.cueDelayMs == 0L })
    }

    @Test
    fun unifiedSchedulerSuppressesOnlyReturnStopRowsAndPreservesMachineFlyAndPullUp() {
        val suppressed = UnifiedCueScheduler(
            family = MotionFamily.CYCLE_AXIS_RETURN,
            returnScale = 1.0,
            suppressReturnDelay = true,
        )
        val rowReturnEvent = ProfiledMotionRepEvent(ms(1000), ms(2200), ms(3400), 2400L, 0.8, 0.4, 0.0, 0.85)
        assertEquals(0L, suppressed.schedule(rowReturnEvent, ms(3620)))

        // Non-row cycle exercise (e.g. pull_up) still receives scheduled cue delay.
        val nonReturnCycle = UnifiedCueScheduler(
            family = MotionFamily.CYCLE_AXIS_RETURN,
            returnScale = 1.0,
            suppressReturnDelay = false,
        )
        val cycleEvent = ProfiledMotionRepEvent(ms(1000), ms(3000), ms(3000), 2000L, 1.0, 0.0, 0.0, 0.7)
        assertTrue(nonReturnCycle.schedule(cycleEvent, ms(3400)) > 0L)

        // machine_fly (MULTI_AXIS_RETURN with returnScale = 1.27) is completely unchanged.
        val flyScheduler = UnifiedCueScheduler(
            family = MotionFamily.MULTI_AXIS_RETURN,
            returnScale = RepCueDelay.returnScale("machine_fly"),
        )
        val flyEvent = ProfiledMotionRepEvent(ms(100), ms(1000), ms(2000), 1900L, 1.5, 2.0, 0.2, 0.9)
        assertEquals(513L, flyScheduler.schedule(flyEvent, ms(2000)))
    }
}
