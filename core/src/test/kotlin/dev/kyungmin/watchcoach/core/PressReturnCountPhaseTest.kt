package dev.kyungmin.watchcoach.core

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** A press counts once the handles are back at the chest, whichever way the first second of the set moved. */
class PressReturnCountPhaseTest {
    private val periodS = 2.4
    private val reps = 10

    /**
     * Hand travels 35 cm along the forearm and back, starting and ending at the chest.
     * [handwardX] is the watch X sign toward the hand; [sidewaysLead] adds a sideways settle before the first push.
     */
    private fun pressSet(handwardX: Int, sidewaysLead: Boolean): Pair<List<SensorSample>, Long> {
        val stepNs = 20_000_000L
        var t = 1_000_000_000L
        val out = ArrayList<SensorSample>()
        repeat(50) { out += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); t += stepNs }
        if (sidewaysLead) {
            for (i in 0 until 40) {
                val p = i / 40.0
                // A small settle; the old first-second sign rule counted this set at extension.
                val ay = 0.3 * sin(2 * PI * p)
                out += SensorSample(t, 0f, ay.toFloat(), 9.80665f, 0f, 0f, (0.3 * sin(2 * PI * p)).toFloat(), 3); t += stepNs
            }
        }
        val firstPushNs = t
        val w = 2 * PI / periodS
        val n = (reps * periodS / 0.02).toInt()
        for (i in 0 until n) {
            val s = i * 0.02
            val ax = handwardX * 0.35 / 2 * w * w * cos(w * s)
            val gx = 0.4 * sin(w * s)
            out += SensorSample(t, ax.toFloat(), 0f, 9.80665f, gx.toFloat(), 0f, 0f, 3); t += stepNs
        }
        repeat(150) { out += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3); t += stepNs }
        return out to firstPushNs
    }

    private fun assertCountsAtChest(handwardX: Int, sidewaysLead: Boolean) {
        val (samples, firstPushNs) = pressSet(handwardX, sidewaysLead)
        val profile = ExerciseTrackingProfiles.resolve("machine_chest_press_plate")
        assertEquals(MotionFamily.PRESS_RETURN, profile.family)
        val detector = ProfiledMotionRepDetector(profile, handwardX)
        detector.beginCounting()
        val events = samples.mapNotNull { detector.add(it) } + detector.finishAll()
        assertTrue(events.size in reps - 1..reps, "counted ${events.size}")
        events.forEach { e ->
            val cycles = (e.endTimestampNs - firstPushNs) / 1e9 / periodS
            val fromChest = abs(cycles - Math.round(cycles))
            assertTrue(fromChest <= 0.2, "rep ended ${"%.2f".format(cycles)} cycles in: not back at the chest")
            assertFalse(abs(cycles - Math.floor(cycles) - 0.5) < 0.2, "counted at full extension")
        }
    }

    @Test fun pushFirstStartCountsAtTheChestNotAtExtension() = assertCountsAtChest(handwardX = 1, sidewaysLead = false)

    @Test fun sidewaysSettleBeforeTheFirstPushStillCountsAtTheChest() = assertCountsAtChest(handwardX = 1, sidewaysLead = true)

    @Test fun watchWornTheOtherWayRoundUsesItsOwnHandwardAxis() = assertCountsAtChest(handwardX = -1, sidewaysLead = false)

    @Test fun forearmAxisFollowsWristSideAndDisplayRotation() {
        assertEquals(1, ForearmAxis.handwardX("LEFT", false))
        assertEquals(-1, ForearmAxis.handwardX("RIGHT", false))
        assertEquals(-1, ForearmAxis.handwardX("LEFT", true))
        assertEquals(1, ForearmAxis.handwardX(null, false))
        assertEquals(-1, ForearmAxis.decode("-1"))
        assertEquals(1, ForearmAxis.decode(null))
        assertEquals(1, ForearmAxis.decode("garbage"))
    }

    @Test fun replayOnlyOverrulesTheWatchWhenTheWatchClearlyFailed() {
        assertTrue(PhoneRepAnalyzer.replayMayConfirm(null, 10))
        assertTrue(PhoneRepAnalyzer.replayMayConfirm(10, 10))
        assertFalse(PhoneRepAnalyzer.replayMayConfirm(12, 11), "one rep apart keeps the watch")
        assertFalse(PhoneRepAnalyzer.replayMayConfirm(12, 9), "three apart keeps the watch")
        assertTrue(PhoneRepAnalyzer.replayMayConfirm(4, 10))
        assertTrue(PhoneRepAnalyzer.replayMayConfirm(1, 12))
        assertTrue(PhoneRepAnalyzer.replayMayConfirm(0, 3))
    }
}
