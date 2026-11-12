package dev.kyungmin.kcoach.phone

import android.content.Context
import dev.kyungmin.kcoach.core.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class RecordManagementTest {
    private val app: Context get() = RuntimeEnvironment.getApplication()

    private fun finish(id: String) {
        val snapshot = WorkoutSnapshot(sessionId = id, routineId = "routine", exerciseIndex = 0, setIndex = 0,
            plannedSets = listOf(
                PlannedSetSnapshot(0, "dumbbell_curl", 0, 8, 10.0, true, exerciseName = "덤벨 컬", performedReps = 8, repSource = SetRepSource.MANUAL),
                PlannedSetSnapshot(0, "dumbbell_curl", 1, 8, 10.0, true, exerciseName = "덤벨 컬", performedReps = 8, repSource = SetRepSource.MANUAL)),
            performedReps = emptyMap(), phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0,
            paused = false, startedAtMs = 1000, pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0,
            lastCompletedSetKey = null, captureStates = emptyMap())
        FinishedWorkoutStore(app).finish(snapshot, "팔 루틴", 30)
    }

    @Test fun deleteRemovesTheRecordRowAndItsHistory() {
        finish("a"); finish("b")
        assertEquals(2, WorkoutLogStore(app).load().size)
        assertTrue(FinishedWorkoutStore(app).delete("a"))
        assertEquals(listOf("b"), WorkoutLogStore(app).load().map { it.sessionId })
        assertTrue(ExerciseHistoryStore(app).load().all.none { it.sessionId == "a" })
        assertTrue(ExerciseHistoryStore(app).load().all.any { it.sessionId == "b" })
        assertTrue(FinishedWorkoutStore(app).evidenceForSessions(setOf("a")).isEmpty())
    }

    @Test fun editedSetsAreProjectedAgainAndStayManual() {
        finish("a")
        val before = WorkoutLogStore(app).load().single()
        assertEquals(160, before.volumeKg)
        assertTrue(FinishedWorkoutStore(app).editSets("a", mapOf((0 to 0) to (20.0 to 10), (0 to 1) to (20.0 to 5))))
        val after = WorkoutLogStore(app).load().single()
        assertEquals(300, after.volumeKg)
        assertEquals(1, ExerciseHistoryStore(app).load().all.count { it.sessionId == "a" })
        val sets = FinishedWorkoutStore(app).evidenceForSessions(setOf("a")).single().snapshot.plannedSets
        assertEquals(listOf(10, 5), sets.map { it.performedReps })
        assertTrue(sets.all { it.repSource == SetRepSource.MANUAL })
    }
}
