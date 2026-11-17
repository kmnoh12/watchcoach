package dev.kyungmin.watchcoach.phone

import dev.kyungmin.watchcoach.core.*
import dev.kyungmin.watchcoach.phone.ui.loadResultPresentation
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ResultHistoryCarryoverTest {
    private val context get() = RuntimeEnvironment.getApplication()

    @Before fun clear() {
        listOf("finished-workouts", "exercise-history", "workout-log", "progression-plans").forEach {
            context.getSharedPreferences(it, 0).edit().clear().commit()
        }
    }

    private fun set(id: String, reps: Int, index: Int = 0) = PlannedSetSnapshot(
        index, id, 0, 8, 40.0, true, performedReps = reps, equipment = "바벨", family = "flat",
        gripType = "노멀", exerciseName = id, repSource = SetRepSource.MANUAL)

    private fun record(id: String, time: Long, sets: List<PlannedSetSnapshot>, routine: String = "routine"): WorkoutSnapshot {
        val snapshot = WorkoutSnapshot(sessionId = id, routineId = routine, exerciseIndex = 0, setIndex = 0,
            plannedSets = sets.mapIndexed { i, set -> set.copy(setId = "$id-$i", attemptId = "attempt") }, performedReps = emptyMap(),
            phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0, paused = false,
            startedAtMs = time, pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0,
            lastCompletedSetKey = null, captureStates = emptyMap())
        FinishedWorkoutStore(context).finish(snapshot, "루틴", 1)
        return snapshot
    }

    @Test fun resultUsesOlderAndOtherRoutineHistoryPerExerciseAndLabelsOnlyNewExercisesFirst() {
        record("older", 1000, listOf(set("press", 7)))
        record("other", 2000, listOf(set("press", 8)), "other-routine")
        record("immediate", 3000, listOf(set("curl", 8)))
        record("current", 4000, listOf(set("press", 9), set("curl", 9, 1), set("new", 8, 2)))
        val rows = loadResultPresentation(context, "current").exercises.associateBy { it.exerciseId }
        assertNotEquals("첫 기록", rows.getValue("press").delta)
        assertEquals("40kg × 8회", rows.getValue("press").sets.single().previous)
        assertNotEquals("첫 기록", rows.getValue("curl").delta)
        assertEquals("첫 기록", rows.getValue("new").delta)
        FinishedWorkoutStore(context).delete("other")
        assertEquals("40kg × 7회", loadResultPresentation(context, "current").exercises.first().sets.single().previous)
    }

    @Test fun ambiguousTimestampsHaveNoComparisonAndDoNotClaimFirstRecord() {
        record("older", 1000, listOf(set("press", 7)))
        record("tied", 1000, listOf(set("press", 8)), "other")
        record("current", 2000, listOf(set("press", 9)))
        val row = loadResultPresentation(context, "current").exercises.single()
        assertEquals("—", row.delta)
        assertEquals("—", row.sets.single().previous)
        assertNull(row.direction)
    }

    @Test fun eachGripInAnExerciseUsesItsOwnMostRecentCondition() {
        val normal = set("press", 7)
        val wide = normal.copy(gripType = "와이드", setIndex = 1, performedReps = 8)
        record("normal", 1000, listOf(normal))
        record("wide", 2000, listOf(wide), "other")
        record("current", 3000, listOf(normal.copy(performedReps = 9), wide.copy(performedReps = 10)))
        val rows = loadResultPresentation(context, "current").exercises.single().sets
        assertEquals(listOf("40kg × 7회", "40kg × 8회"), rows.map { it.previous })
    }
}
