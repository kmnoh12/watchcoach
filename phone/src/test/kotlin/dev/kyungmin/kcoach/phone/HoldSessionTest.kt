package dev.kyungmin.kcoach.phone

import dev.kyungmin.kcoach.core.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class HoldSessionTest {
    private val app get() = RuntimeEnvironment.getApplication()
    private fun snapshot() = WorkoutSnapshot(sessionId = "hold", routineId = "r", exerciseIndex = 0, setIndex = 0,
        plannedSets = listOf(PlannedSetSnapshot(0, "plate_pinch", 0, 0, 40.0, false,
            setId = "s", attemptId = "a", targetDurationSeconds = 30, workingStartedAtMs = 1000)),
        performedReps = emptyMap(), phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0,
        paused = false, startedAtMs = 1000, pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0, lastCompletedSetKey = null, captureStates = emptyMap())
    @Test fun phoneAndWatchCompletionStoreSameMeasuredSeconds() {
        for (watch in listOf(false, true)) {
            app.getSharedPreferences("workout-session", 0).edit().clear().commit()
            val store = SessionStore(app)
            assertTrue(store.saveActive(snapshot()))
            assertNull(store.advanceOtherSide(99_000).getOrThrow())
            if (watch) assertEquals(WatchWorkoutControlStatus.APPLIED, store.applyWatchControl(
                WatchWorkoutControl("complete", WatchWorkoutAction.COMPLETE_MANUAL_SET, "hold", "s", "a"), 46_000).getOrThrow().ack.status)
            else assertEquals(ManualSetStatus.APPLIED, store.applyManualSet(
                ManualSetCommand("complete", "hold", "plate_pinch", 0, "s", "a", 0, 0, ManualSetOperation.COMPLETE), 46_000).getOrThrow().ack.status)
            val saved = SessionStore(app).loadActive().getOrThrow()!!
            assertEquals(45, saved.plannedSets.single().durationSeconds)
            assertEquals(SetRepSource.MANUAL, saved.plannedSets.single().repSource)
            val restored = restoreWorkoutRoutine(saved, null)
            assertEquals(ExerciseKind.HOLD, restored.exercises.single().exercise.kind)
            assertEquals(45, restored.exercises.single().sets.single().durationSeconds)
            assertEquals(45, ProgressionPlanStore(app).logs(saved, 1).single().sets.single().durationSeconds)
        }
    }
    @Test fun defaultsAndCustomTypePersist() {
        val custom = ExerciseDefinition("custom_hold", "버티기", "코어", "코어", "맨몸", kind = ExerciseKind.HOLD)
        val item = ExerciseDefaults.newExercise(custom)
        assertEquals(3, item.sets.size); assertTrue(item.sets.all { it.targetDurationSeconds == 30 })
        val file = java.io.File(app.cacheDir, "hold-library.json")
        val store = RoutineLibraryStore(file)
        store.load().getOrThrow()
        store.save(RoutineLibrary(listOf(WorkoutRoutine("hold-r", "버티기", "코어", "", mutableListOf(item))), listOf(custom))).getOrThrow()
        val saved = RoutineLibraryStore(file).load().getOrThrow()!!
        assertEquals(custom, saved.customExercises.single())
        assertEquals(30, saved.routines.single().exercises.single().sets.first().targetDurationSeconds)
    }
    @Test fun successfulHoldTargetsGrowFiveSecondsOnceWithoutAddingWeight() {
        app.getSharedPreferences("progression-plans", 0).edit().clear().commit()
        app.getSharedPreferences("exercise-history", 0).edit().clear().commit()
        val definition = WorkoutData.catalog.single { it.id == "plate_pinch" }
        val item = ExerciseDefaults.newExercise(definition)
        val routine = WorkoutRoutine("progress-hold", "핀치", "전완", "", mutableListOf(item))
        ExerciseHistoryStore(app).add(ExerciseLog(definition.id, 1,
            List(3) { LoggedSet(40.0, 0, durationSeconds = 35, targetDurationSeconds = 30) },
            "source", 1000, routine.id, 0, definition.equipment))
        val weights = item.sets.map { it.weightKg }
        ProgressionPlanStore(app).prefill(routine).getOrThrow()
        assertEquals(listOf(35, 35, 35), item.sets.map { it.targetDurationSeconds })
        assertEquals(weights, item.sets.map { it.weightKg })
        ProgressionPlanStore(app).prefill(routine).getOrThrow()
        assertEquals(listOf(35, 35, 35), item.sets.map { it.targetDurationSeconds })
        ExerciseHistoryStore(app).add(ExerciseLog(definition.id, 2,
            List(3) { LoggedSet(40.0, 0, durationSeconds = 20, targetDurationSeconds = 35) },
            "failed", 2000, routine.id, 0, definition.equipment))
        ProgressionPlanStore(app).prefill(routine).getOrThrow()
        assertEquals(listOf(35, 35, 35), item.sets.map { it.targetDurationSeconds })
    }

}
