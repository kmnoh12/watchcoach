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
class UnilateralSessionTest {
    private val app get() = RuntimeEnvironment.getApplication()
    private fun initial() = WorkoutSnapshot(sessionId = "s", routineId = "r", exerciseIndex = 0, setIndex = 0,
        plannedSets = listOf(PlannedSetSnapshot(0, "one_arm_dumbbell_row", 0, 10, 20.0, false,
            restSeconds = 60, setId = "set", attemptId = "a", identityRequired = true)),
        performedReps = emptyMap(), phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0,
        paused = false, startedAtMs = 1, pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0,
        lastCompletedSetKey = null, captureStates = emptyMap())
    private fun completion() = WearSync.liveState("s", "one_arm_dumbbell_row", "원암 덤벨 로우", 0, 12, 10,
        20.0, 80, "SET_COMPLETE", false, completionId = "completion", setId = "set", attemptId = "a")
    private fun command(action: WatchWorkoutAction, id: String = action.name, reps: Int = -1) =
        WatchWorkoutControl(id, action, "s", "set", "a", reps = reps)

    @Test fun autoCompletionSendsHoldInsteadOfRestAndSurvivesStoreRecreation() {
        val store = SessionStore(app); assertTrue(store.saveActive(initial()))
        val sent = mutableListOf<Pair<String, String>>()
        PhoneSessionController(store) { path, payload -> sent += path to payload }.receiveCompletion(completion(), 1_000).getOrThrow()
        val snapshot = SessionStore(app).loadActive().getOrThrow()!!
        assertFalse(snapshot.plannedSets.single().completed)
        assertEquals(0L, snapshot.restEndAtMs)
        val sync = WearSync.parse(sent.single { it.first == WearSync.PATH_COMMAND }.second)
        assertEquals("SYNC", sync[1])
        assertEquals(UnilateralStage.OTHER_SIDE_WORKING, UnilateralProgress.decode(sync[24])!!.stage)
        assertTrue(sent.any { it.first == WearSync.PATH_SET_ACK })
        assertNull(store.advanceAfterRest(999_999).getOrThrow())
        assertEquals(UnilateralStage.OTHER_SIDE_WORKING, restoreWorkoutRoutine(snapshot, null).exercises[0].sets[0].unilateral!!.stage)
    }
    @Test fun manualCompletionAlsoHoldsAndSecondManualCompletionRecordsActualOppositeCount() {
        val store = SessionStore(app); assertTrue(store.saveActive(initial()))
        fun manual(id: String, count: Int) = store.applyManualSet(ManualSetCommand(id, "s", "one_arm_dumbbell_row", 0,
            "set", "a", count, store.manualSetRevision("s", "set", "a").getOrThrow()!!, ManualSetOperation.COMPLETE), 1_000).getOrThrow()
        val first = manual("first", 12)
        assertFalse(first.restStarted)
        assertEquals(ManualSetStatus.APPLIED, first.ack.status)
        assertEquals(WatchWorkoutControlStatus.DUPLICATE, store.applyWatchControl(command(WatchWorkoutAction.START_OTHER_SIDE), 2_000).getOrThrow().ack.status)
        val final = manual("other", 9)
        assertTrue(final.restStarted)
        assertEquals(9, final.snapshot!!.plannedSets.single().unilateral!!.otherReps)
        assertEquals(12, final.snapshot!!.plannedSets.single().performedReps)
        assertEquals(ManualSetStatus.DUPLICATE, store.applyManualSet(ManualSetCommand("first", "s", "one_arm_dumbbell_row", 0,
            "set", "a", 12, 0, ManualSetOperation.COMPLETE), 9_000).getOrThrow().ack.status)
        assertEquals(9, store.loadActive().getOrThrow()!!.plannedSets.single().unilateral!!.otherReps)
    }
    @Test fun phoneAndWatchActionsShareReceiptsAndNeverDoubleCompleteOrRestartRest() {
        val store = SessionStore(app); assertTrue(store.saveActive(initial()))
        val sent = mutableListOf<String>()
        val controller = PhoneSessionController(store) { _, payload -> sent += payload }
        controller.receiveCompletion(completion(), 1_000).getOrThrow()
        val before = store.loadActive().getOrThrow()!!.restRev
        val start = command(WatchWorkoutAction.START_OTHER_SIDE)
        assertEquals(start, WatchWorkoutControl.decode(start.encode()))
        assertEquals(WatchWorkoutControlStatus.DUPLICATE, store.applyWatchControl(start, 2_000).getOrThrow().ack.status)
        assertEquals(before, store.loadActive().getOrThrow()!!.restRev)
        controller.receiveCompletion(completion(), 3_000).getOrThrow()
        assertEquals(UnilateralStage.OTHER_SIDE_WORKING, store.loadActive().getOrThrow()!!.plannedSets.single().unilateral!!.stage)
        val done = command(WatchWorkoutAction.COMPLETE_OTHER_SIDE, reps = 8)
        assertEquals(done, WatchWorkoutControl.decode(done.encode()))
        val result = store.applyWatchControl(done, 4_000).getOrThrow()
        assertEquals(64_000L, result.snapshot!!.restEndAtMs)
        assertEquals(8, result.snapshot!!.plannedSets.single().unilateral!!.otherReps)
        assertEquals(WatchWorkoutControlStatus.DUPLICATE, store.applyWatchControl(done, 99_000).getOrThrow().ack.status)
        assertEquals(64_000L, store.loadActive().getOrThrow()!!.restEndAtMs)
        val stale = start.copy(commandId = "old", attemptId = "old")
        assertEquals(WatchWorkoutControlStatus.REJECTED, store.applyWatchControl(stale, 99_000).getOrThrow().ack.status)
    }
    @Test fun watchSuggestedCompletionIsEstimatedUntilPhoneConfirms() {
        val store = SessionStore(app); assertTrue(store.saveActive(initial()))
        PhoneSessionController(store) { _, _ -> }.receiveCompletion(completion(), 1_000).getOrThrow()
        val request = command(WatchWorkoutAction.COMPLETE_OTHER_SIDE)
        val result = store.applyWatchControl(request, 4_000).getOrThrow()
        val set = result.snapshot!!.plannedSets.single()
        assertEquals(UnilateralStage.BOTH_COMPLETE, set.unilateral!!.stage)
        assertEquals(12, set.unilateral!!.otherReps)
        assertEquals(SetRepSource.ESTIMATED, set.unilateral!!.otherRepSource)
        assertEquals(64_000L, result.snapshot!!.restEndAtMs)
        assertEquals(WatchWorkoutControlStatus.DUPLICATE, store.applyWatchControl(request, 5_000).getOrThrow().ack.status)
        val finished = FinishedWorkoutStore(app)
        finished.finish(result.snapshot!!, "원암", 3)
        assertTrue(finished.confirmOther("s", "set", "a", 9))
        val confirmed = finished.evidenceForSessions(setOf("s")).single().snapshot.plannedSets.single()
        assertEquals(9, confirmed.unilateral!!.otherReps)
        assertEquals(SetRepSource.MANUAL, confirmed.unilateral!!.otherRepSource)
    }

    @Test fun phoneFacadeFinishesOnlyFirstArmAndKeepsOppositeCountUnknown() {
        val store = SessionStore(app); assertTrue(store.saveActive(initial()))
        val controller = PhoneSessionController(store) { _, _ -> }
        controller.receiveCompletion(completion(), 1_000).getOrThrow()
        val result = controller.unilateralAction("s", "set", "a", UnilateralAction.FINISH_WATCH_SIDE_ONLY, 5_000).getOrThrow()
        assertEquals(WatchWorkoutControlStatus.APPLIED, result.ack.status)
        assertEquals(UnilateralStage.WATCH_SIDE_ONLY, result.snapshot!!.plannedSets.single().unilateral!!.stage)
        assertNull(result.snapshot!!.plannedSets.single().unilateral!!.otherReps)
    }

    private fun timedController(): PhoneSessionController {
        OneArmSetting.setEnabled(app, false)
        val store = SessionStore(app)
        assertTrue(store.saveActive(initial()))
        return PhoneSessionController(store) { _, _ -> }.also {
            it.receiveCompletion(completion() + "|30000", 1_000).getOrThrow()
        }
    }
    @Test fun timedOppositeSideRestoresRemainingTimeAndStartsOneRestAfterPause() {
        val controller = timedController()
        assertNull(controller.advanceRest(45_999).getOrThrow())
        SessionStore(app).setPaused("s", true, 11_000).getOrThrow()
        assertNull(controller.advanceRest(100_000).getOrThrow())
        SessionStore(app).setPaused("s", false, 31_000).getOrThrow()
        val restored = PhoneSessionController(SessionStore(app)) { _, _ -> }
        assertNull(restored.advanceRest(65_999).getOrThrow())
        val done = restored.advanceRest(66_000).getOrThrow()!!
        assertEquals(126_000, done.restEndAtMs)
        assertTrue(done.plannedSets.single().unilateral!!.estimated)
        assertNull(restored.advanceRest(66_001).getOrThrow())
        assertFalse(ProgressionPlanStore(app).logs(done, 1).single().sets.single().progressionEligible)
    }
    @Test fun explicitInputBeforeTimeoutWinsAndFinishedCorrectionPreservesMeasuredSide() {
        val controller = timedController()
        val manual = controller.unilateralAction("s", "set", "a", UnilateralAction.COMPLETE_OTHER_SIDE, 40_000, 8).getOrThrow().snapshot!!
        assertFalse(manual.plannedSets.single().unilateral!!.estimated)
        assertNull(controller.advanceRest(46_000).getOrThrow())
    }
    @Test fun finishedEstimatedCorrectionPreservesMeasuredSide() {
        val timed = timedController().advanceRest(46_000).getOrThrow()!!
        val finished = FinishedWorkoutStore(app)
        finished.finish(timed, "원암", 1)
        assertTrue(finished.confirmOther("s", "set", "a", 9))
        val corrected = finished.evidenceForSessions(setOf("s")).single().snapshot
        assertEquals(12, corrected.plannedSets.single().performedReps)
        assertEquals(12, corrected.plannedSets.single().unilateral!!.watchReps)
        assertEquals(9, corrected.plannedSets.single().unilateral!!.otherReps)
        assertEquals(SetRepSource.MANUAL, corrected.plannedSets.single().unilateral!!.otherRepSource)
        assertTrue(ProgressionPlanStore(app).logs(corrected, 1).single().sets.single().progressionEligible)
        assertFalse(finished.confirmOther("s", "set", "a", 7))
    }
    @Test fun oneArmOnlySettingAndUnknownLegacyDurationNeverArmTimer() {
        OneArmSetting.setEnabled(app, true)
        val store = SessionStore(app); assertTrue(store.saveActive(initial()))
        val controller = PhoneSessionController(store) { _, _ -> }
        controller.receiveCompletion(completion() + "|30000", 1_000).getOrThrow()
        assertEquals(UnilateralStage.WATCH_SIDE_ONLY, store.loadActive().getOrThrow()!!.plannedSets.single().unilateral!!.stage)
        assertNull(store.advanceOtherSide(999_999).getOrThrow())
    }
    @Test fun unknownLegacyDurationNeverArmsTimer() {
        val controller = PhoneSessionController(SessionStore(app)) { _, _ -> }
        OneArmSetting.setEnabled(app, false)
        assertTrue(SessionStore(app).saveActive(initial()))
        controller.receiveCompletion(completion(), 1_000).getOrThrow()
        assertNull(SessionStore(app).advanceOtherSide(999_999).getOrThrow())
    }

}
