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
class ExerciseRecordOverviewTest {
    @Test fun countsActualCompletedValuesAndKeepsTimeSeparate() {
        val history = ExerciseHistory(listOf(
            ExerciseLog("curl", 3, listOf(LoggedSet(20.0, 8, targetReps = 10), LoggedSet(20.0, 10, completed = false), LoggedSet(20.0, 10, repsEntered = false))),
            ExerciseLog("curl", 2, listOf(LoggedSet(15.0, 12))),
            ExerciseLog("plank", 3, listOf(LoggedSet(null, 0, durationSeconds = 42, targetDurationSeconds = 60)))))
        val reps = ExerciseRecordOverview.from(history, "curl", false)
        assertTrue(reps.stats.contains("2세트" to "완료 세트"))
        assertTrue(reps.stats.contains("20회" to "수행 횟수"))
        assertTrue(reps.records.first().second.contains("20kg × 8회"))
        assertFalse(reps.records.first().second.contains("10회"))
        val time = ExerciseRecordOverview.from(history, "plank", true)
        assertTrue(time.stats.contains(HoldExercise.time(42) to "누적 시간"))
        assertTrue(time.records.first().second.contains(HoldExercise.time(42)))
        assertTrue(ExerciseRecordOverview.from(history, "unknown", false).stats.contains("0세트" to "완료 세트"))
    }

    @Test fun finishedEvidenceDoesNotDoubleCountItsProjectedCacheOrDropRepeatedExercises() {
        val app = RuntimeEnvironment.getApplication()
        val sets = (0..1).map { index -> PlannedSetSnapshot(index, "curl", 0, 10, 20.0, true,
            performedReps = 8, repSource = SetRepSource.MANUAL, setId = "set-$index", attemptId = "a") }
        val snapshot = WorkoutSnapshot(sessionId = "session", routineId = "routine", exerciseIndex = 1, setIndex = 0,
            plannedSets = sets, performedReps = mapOf("curl" to 16), phase = WorkoutPhase.WORKING,
            restEndAtMs = 0, pausedRestRemainingMs = 0, paused = false, startedAtMs = 1,
            pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0, lastCompletedSetKey = null, captureStates = emptyMap())
        val store = FinishedWorkoutStore(app)
        store.finish(snapshot, "운동", 3)
        ExerciseHistoryStore(app).add(ExerciseLog("curl", -1, listOf(LoggedSet(10.0, 5))))
        val history = store.historyForRecords()
        assertEquals(2, history.all.count { it.sessionId == "session" })
        assertEquals(3, history.all.size)
        assertTrue(ExerciseRecordOverview.from(history, "curl", false).stats.contains("21회" to "수행 횟수"))
    }
}
