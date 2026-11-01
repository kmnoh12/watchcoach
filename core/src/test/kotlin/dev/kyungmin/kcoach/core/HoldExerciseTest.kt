package dev.kyungmin.kcoach.core

import kotlin.test.*

class HoldExerciseTest {
    private fun snapshot() = WorkoutSnapshot(sessionId = "hold", routineId = "r", exerciseIndex = 0, setIndex = 0,
        plannedSets = listOf(PlannedSetSnapshot(0, "plate_pinch", 0, 0, 40.0, false, restSeconds = 0,
            setId = "s", attemptId = "a", targetDurationSeconds = 30)), performedReps = emptyMap(),
        phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0, paused = false,
        startedAtMs = 1000, pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0, lastCompletedSetKey = null, captureStates = emptyMap())
    @Test fun staticClassificationAndManualOnlyStopwatch() {
        assertEquals(setOf("plank", "side_plank", "hollow_hold", "plate_pinch"), HoldExercise.catalogIds)
        assertEquals(ExerciseKind.RESISTANCE, HoldExercise.kind("dead_bug"))
        val s = SetClock.prepare(snapshot(), null, 1000, true)
        assertEquals(0L, SetClock.holdElapsedMs(s, 1000))
        assertEquals(45_000L, SetClock.holdElapsedMs(s, 46_000))
        assertNull(s.plannedSets.single().setTimerLimitMs)
        assertNull(SetClock.remainingMs(s, 99_000))
        assertNull(SetClock.autoComplete(s, 999_000, true))
        assertNull(SetClock.adjust(s, 10, 3000))
    }
    @Test fun manualCompletionSavesActiveSecondsAndWireRoundTrips() {
        val s = SetClock.prepare(snapshot(), null, 1000, false).copy(totalPausedMs = 10_000)
        val done = (WorkoutSessionReducer.completeSet(s, SetCompletionEvent("hold", "plate_pinch", 0, 99, 56_000, 0,
            setId = "s", attemptId = "a", completedAtMs = 56_000)) as SetCompletionResult.Applied).snapshot
        assertEquals(45, done.plannedSets.single().durationSeconds)
        assertEquals(0, done.plannedSets.single().performedReps)
        assertEquals("40kg × 0:45", HoldExercise.record(done.plannedSets.single()))
        assertEquals(done, WorkoutSnapshotCodec.decode(WorkoutSnapshotCodec.encode(done)))
        val wire = WearSync.parse(WearSync.withSetClock("2|SET", s, 56_000, false))
        assertEquals("HOLD", wire[28]); assertEquals("30", wire[29]); assertEquals("11000", wire[30])
        assertEquals("", wire[25])
        val paused = s.copy(paused = true, pausedSinceMs = 56_000)
        assertEquals(45_000L, SetClock.holdElapsedMs(paused, 999_000))
        assertEquals("45000", WearSync.parse(WearSync.withSetClock("2|PAUSE", paused, 999_000))[30])
    }
    @Test fun historyKeepsLegacyRepsAndHoldSecondsSeparate() {
        val old = ExerciseHistoryCodec.decode("plate_pinch\t1\t40:12").single()
        assertNull(old.sets.single().durationSeconds); assertEquals(12, old.totalReps)
        val hold = old.copy(sets = listOf(LoggedSet(40.0, 0, durationSeconds = 45, targetDurationSeconds = 30)))
        assertEquals(hold, ExerciseHistoryCodec.decode(ExerciseHistoryCodec.encode(listOf(hold))).single())
        assertEquals(0.0, hold.volumeKg); assertEquals(0, hold.totalReps)
        assertEquals(35, HoldExercise.nextTarget(hold.sets, 30))
        assertEquals(30, HoldExercise.nextTarget(hold.sets + LoggedSet(null, 0, durationSeconds = 20, targetDurationSeconds = 30), 30))
    }
    @Test fun versionNineHoldNamedRecordKeepsOriginalRepetitions() {
        val encoded = java.util.Base64.getUrlDecoder().decode(WorkoutSnapshotCodec.encode(snapshot().copy(
            plannedSets = listOf(snapshot().plannedSets.single().copy(targetReps = 12, completed = true, performedReps = 12)))))
        val kindOffset = encoded.toList().windowed(4).indexOf("HOLD".toByteArray().toList())
        assertTrue(kindOffset > 0)
        val legacy = encoded.take(kindOffset - 4).toByteArray() + encoded.drop(kindOffset + 12).toByteArray()
        java.nio.ByteBuffer.wrap(legacy).putInt(4, 9)
        val set = WorkoutSnapshotCodec.decode(java.util.Base64.getUrlEncoder().encodeToString(legacy)).plannedSets.single()
        assertEquals(ExerciseKind.RESISTANCE, set.exerciseKind)
        assertEquals(12, set.performedReps); assertNull(set.durationSeconds)
    }

}
