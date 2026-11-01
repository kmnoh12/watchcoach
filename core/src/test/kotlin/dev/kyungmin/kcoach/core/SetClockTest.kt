package dev.kyungmin.kcoach.core

import kotlin.test.*

class SetClockTest {
    private fun initial(exercise: String = "leg_press") = WorkoutSnapshot(sessionId = "clock", routineId = "routine",
        exerciseIndex = 0, setIndex = 0, plannedSets = (0..2).map { PlannedSetSnapshot(0, exercise, it, 10, null, false,
            restSeconds = 0, setId = "set$it", attemptId = "attempt$it", identityRequired = true) }, performedReps = emptyMap(),
        phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0, paused = false, startedAtMs = 1000,
        pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0, lastCompletedSetKey = null, captureStates = emptyMap())
    private fun complete(s: WorkoutSnapshot, at: Long): WorkoutSnapshot {
        val set = WorkoutSessionReducer.nextPendingSet(s)!!
        return (WorkoutSessionReducer.completeSet(s, SetCompletionEvent(s.sessionId, set.exerciseId, set.setIndex, 8, at, 0,
            setId = set.setId, attemptId = set.attemptId, completedAtMs = at)) as SetCompletionResult.Applied).snapshot
    }
    private fun next(s: WorkoutSnapshot, at: Long) = SetClock.prepare(WorkoutSessionReducer.advanceAfterRest(s, at)!!, s, at, true)
    private fun second(duration: Long = 60_000): WorkoutSnapshot {
        val first = SetClock.prepare(initial(), null, 1000, true)
        return next(complete(first, 1000 + duration), 1000 + duration)
    }
    @Test fun firstSetWaitsAndSixtySecondFirstSetGivesSeventyThenEighty() {
        val first = SetClock.prepare(initial(), null, 1000, true)
        assertNull(SetClock.remainingMs(first, 999_999))
        val second = second()
        assertEquals(70_000L, SetClock.remainingMs(second, 61_000))
        assertNull(SetClock.autoComplete(second, 130_999, true))
        val done = SetClock.autoComplete(second, 131_000, true)!!
        assertEquals(70_000L, done.plannedSets[1].completedDurationMs)
        assertEquals(SetRepSource.ESTIMATED, done.plannedSets[1].repSource)
        assertEquals(10, done.plannedSets[1].performedReps)
        assertNull(SetClock.autoComplete(done, 131_001, true))
        assertEquals(80_000L, SetClock.remainingMs(next(done, 131_000), 131_000))
    }
    @Test fun deadlineCapsAtFiveMinutesButDurationKeepsActualValue() {
        val second = second(900_000)
        assertEquals(300_000L, second.plannedSets[1].setTimerLimitMs)
        assertEquals(900_000L, second.plannedSets[0].completedDurationMs)
    }
    @Test fun adjustmentsApplyOnlyToThisSetAndNextUsesActualCompletionTime() {
        val second = second()
        val adjusted = SetClock.adjust(second, 10, 61_000)!!
        assertEquals(80_000L, SetClock.remainingMs(adjusted, 61_000))
        assertEquals(second, SetClock.adjust(adjusted, -10, 61_000))
        // User finishes early despite the extended deadline.
        val third = next(complete(adjusted, 111_000), 111_000)
        assertEquals(60_000L, third.plannedSets[2].setTimerLimitMs)
        assertEquals(0L, third.plannedSets[2].setTimerAdjustmentMs)
        assertEquals(0L, SetClock.remainingMs(SetClock.adjust(second, -10, 125_000)!!, 125_000))
    }
    @Test fun pauseIsFrozenAcrossCodecAndResumeSubtractsPausedTime() {
        val paused = second().copy(paused = true, phase = WorkoutPhase.PAUSED, pausedSinceMs = 71_000)
        val restored = WorkoutSnapshotCodec.decode(WorkoutSnapshotCodec.encode(paused))
        assertEquals(paused, restored)
        assertEquals(60_000L, SetClock.remainingMs(restored, 999_999))
        assertNull(SetClock.autoComplete(restored, 999_999, true))
        val resumed = restored.copy(paused = false, phase = WorkoutPhase.WORKING, pausedSinceMs = 0, totalPausedMs = 30_000)
        assertNull(SetClock.autoComplete(resumed, 160_999, true))
        assertNotNull(SetClock.autoComplete(resumed, 161_000, true))
    }
    @Test fun explicitCompletionCancelsTimerAndDisabledClockCannotComplete() {
        assertNull(SetClock.autoComplete(complete(second(), 70_000), 999_999, true))
        assertNull(SetClock.autoComplete(second(), 999_999, false))
        assertNull(SetClock.remainingMs(SetClock.prepare(second(), second(), 61_000, false), 999_999))
    }
    @Test fun warmupsAndSensorSetsDoNotArmAndExerciseChangeResetsBaseline() {
        assertNull(SetClock.remainingMs(SetClock.prepare(initial().copy(plannedSets = initial().plannedSets.map {
            if (it.setIndex == 0) it.copy(completed = true, completedDurationMs = 60_000, setType = "WARMUP") else it
        }, setIndex = 1), null, 61_000, true), 61_000))
        assertNull(SetClock.remainingMs(SetClock.prepare(initial("barbell_biceps_curl"), null, 1000, true), 999_999))
        val changed = second().copy(plannedSets = second().plannedSets.map { if (it.setIndex == 1)
            it.copy(exerciseIndex = 1, exerciseId = "leg_press", workingStartedAtMs = 0, setTimerLimitMs = null) else it }, exerciseIndex = 1, setIndex = 1)
        assertNull(SetClock.remainingMs(SetClock.prepare(changed, null, 61_000, true), 61_000))
        val warm = second().copy(plannedSets = second().plannedSets.map { it.copy(setType = "WARMUP") })
        assertNull(SetClock.autoComplete(warm, 999_999, true))
    }
    @Test fun automaticAnalysisCannotConfirmAnUnknownManualCount() {
        val done = SetClock.autoComplete(second(), 131_000, true)!!
        assertEquals(done, WorkoutSessionReducer.confirmReps(done, "leg_press", 1, 0, "set1", "attempt1"))
    }
    @Test fun oppositeArmKeepsFifteenSecondsAndIgnoresManualSwitch() {
        val s = initial("one_arm_dumbbell_row").let { it.copy(plannedSets = it.plannedSets.map { set ->
            if (set.setIndex == 0) set.copy(unilateral = UnilateralProgress(UnilateralStage.OTHER_SIDE_WORKING, 8,
                SetRepSource.WATCH, firstSideDurationMs = 30_000, otherStartedAtMs = 1000)) else set }) }
        assertEquals(45_000L, SetClock.remainingMs(s, 1000, false))
        val adjusted = SetClock.adjust(s, 10, 1000, false)!!
        assertNull(SetClock.autoComplete(adjusted, 55_999, false))
        assertTrue(SetClock.autoComplete(adjusted, 56_000, false)!!.plannedSets.first().unilateral!!.estimated)
    }
}
