package dev.kyungmin.kcoach.phone

import dev.kyungmin.kcoach.core.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SetClockSessionTest {
    private val app get() = RuntimeEnvironment.getApplication()
    @org.junit.Before fun reset() {
        app.getSharedPreferences("workout-session", 0).edit().clear().commit()
        app.getSharedPreferences("ui-settings", 0).edit().putBoolean("manualAutoFinish", true).commit()
    }
    @org.junit.After fun restoreSetting() {
        app.getSharedPreferences("ui-settings", 0).edit().remove("manualAutoFinish").commit()
    }
    private fun snapshot() = WorkoutSnapshot(sessionId = "manual-clock", routineId = "r", exerciseIndex = 0, setIndex = 1,
        plannedSets = listOf(PlannedSetSnapshot(0, "leg_press", 0, 10, null, true, performedReps = 8,
            repSource = SetRepSource.MANUAL, completedDurationMs = 60_000, setId = "first", attemptId = "a"),
            PlannedSetSnapshot(0, "leg_press", 1, 10, null, false, setId = "second", attemptId = "b",
                workingStartedAtMs = 61_000, setTimerLimitMs = 70_000)), performedReps = mapOf("leg_press" to 8),
        phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0, paused = false, startedAtMs = 1000,
        pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0, lastCompletedSetKey = null, captureStates = emptyMap())
    private fun store() = SessionStore(app).also { assertTrue(it.saveActive(snapshot())) }
    @Test fun serviceControllerRestoresClockClaimsOnceAndSendsRest() {
        store()
        val sent = mutableListOf<String>()
        val controller = PhoneSessionController(SessionStore(app)) { _, payload -> sent += payload }
        assertNull(controller.advanceRest(130_999).getOrThrow())
        val done = controller.advanceRest(131_000).getOrThrow()!!
        assertEquals(SetRepSource.ESTIMATED, done.plannedSets[1].repSource)
        assertEquals("REST", WearSync.parse(sent.single())[1])
        assertNull(controller.advanceRest(131_001).getOrThrow())
        assertFalse(ProgressionPlanStore(app).logs(done, 1).single().sets[1].progressionEligible)
    }
    @Test fun manualInputWinsAndRecreationDoesNotResurrectDeadline() {
        val store = store()
        val command = ManualSetCommand("manual", "manual-clock", "leg_press", 1, "second", "b", 7, 0, ManualSetOperation.COMPLETE)
        assertEquals(ManualSetStatus.APPLIED, store.applyManualSet(command, 100_000).getOrThrow().ack.status)
        assertNull(SessionStore(app).advanceOtherSide(999_999).getOrThrow())
        val done = SessionStore(app).loadActive().getOrThrow()!!
        assertEquals(39_000L, done.plannedSets[1].completedDurationMs)
        assertEquals(SetRepSource.MANUAL, done.plannedSets[1].repSource)
    }
    @Test fun pausedClockAndAdjustmentSurviveRecreation() {
        val store = store()
        val command = WatchWorkoutControl("plus", WatchWorkoutAction.SET_ADJUST, "manual-clock", "second", "b", deltaSeconds = 10)
        assertEquals(command, WatchWorkoutControl.decode(command.encode()))
        assertEquals(WatchWorkoutControlStatus.APPLIED, store.applyWatchControl(command, 70_000).getOrThrow().ack.status)
        assertEquals(WatchWorkoutControlStatus.DUPLICATE, store.applyWatchControl(command, 71_000).getOrThrow().ack.status)
        store.setPaused("manual-clock", true, 71_000).getOrThrow()
        assertNull(SessionStore(app).advanceOtherSide(999_999).getOrThrow())
        SessionStore(app).setPaused("manual-clock", false, 101_000).getOrThrow()
        assertNull(SessionStore(app).advanceOtherSide(170_999).getOrThrow())
        assertNotNull(SessionStore(app).advanceOtherSide(171_000).getOrThrow())
    }
    @Test fun settingsOffAndStaleAdjustmentCannotEndOrChangeSet() {
        val store = store()
        app.getSharedPreferences("ui-settings", 0).edit().putBoolean("manualAutoFinish", false).commit()
        assertNull(store.advanceOtherSide(999_999).getOrThrow())
        assertEquals(WatchWorkoutControlStatus.STALE, store.applyWatchControl(
            WatchWorkoutControl("stale", WatchWorkoutAction.SET_ADJUST, "manual-clock", "second", "old", deltaSeconds = 10), 70_000).getOrThrow().ack.status)
    }
    @Test fun estimatedResultCanBeConfirmedAndThenCountsForProgression() {
        val store = store()
        val done = store.advanceOtherSide(131_000).getOrThrow()!!
        val finished = FinishedWorkoutStore(app)
        finished.finish(done, "레그프레스", 3)
        assertTrue(finished.confirmOther(done.sessionId, "second", "b", 6))
        val confirmed = finished.evidenceForSessions(setOf(done.sessionId)).single().snapshot
        assertEquals(6, confirmed.plannedSets[1].performedReps)
        assertEquals(SetRepSource.MANUAL, confirmed.plannedSets[1].repSource)
        assertTrue(ProgressionPlanStore(app).logs(confirmed, 1).single().sets[1].progressionEligible)
        assertFalse(finished.confirmOther(done.sessionId, "second", "b", 9))
    }
}
