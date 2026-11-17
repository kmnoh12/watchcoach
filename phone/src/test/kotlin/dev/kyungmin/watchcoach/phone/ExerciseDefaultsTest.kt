package dev.kyungmin.watchcoach.phone

import dev.kyungmin.watchcoach.core.ExerciseLog
import dev.kyungmin.watchcoach.core.LoggedSet
import org.junit.Assert.*
import org.junit.Test

class ExerciseDefaultsTest {
    private fun exercise(pattern: String, equipment: String = "머신") =
        ExerciseDefinition("test", "테스트", "", "", equipment, pattern = pattern)

    @Test fun defaultRestFollowsBodyCategory() {
        val expectedByExercise = mapOf(
            "leg_extension" to 120,
            "flat_bench" to 120,
            "pull_up" to 120,
            "dumbbell_shoulder_press" to 90,
            "dumbbell_triceps_extension" to 90,
            "plank" to 90,
        )
        for ((id, seconds) in expectedByExercise) {
            val definition = WorkoutData.catalog.single { it.id == id }
            assertEquals(id, seconds, RoutineExercise(definition, mutableListOf()).restSeconds)
            assertEquals(id, seconds, ExerciseDefaults.newExercise(definition).restSeconds)
        }
        assertEquals(90, ExerciseDefaults.restSeconds(exercise("unknown")))
    }

    @Test fun customRestAppliesOnlyBeforeFirstCompletedSet() {
        val definition = WorkoutData.catalog.single { it.id == "leg_extension" }
        val incomplete = ExerciseLog(definition.id, 1, listOf(LoggedSet(20.0, 0, completed = false)))
        val completed = ExerciseLog(definition.id, 2, listOf(LoggedSet(20.0, 10)))
        val otherExercise = completed.copy(exerciseId = "pull_up")
        assertEquals(150, ExerciseDefaults.newExercise(definition, history = listOf(incomplete, otherExercise),
            firstWorkoutRestSeconds = 150).restSeconds)
        assertEquals(120, ExerciseDefaults.newExercise(definition, history = listOf(completed),
            firstWorkoutRestSeconds = 150).restSeconds)
    }

    @Test fun estimatesDependOnEquipmentPatternAndAvailableProfileFields() {
        assertEquals(60.0, ExerciseDefaults.startingWeight(exercise("leg_press"))!!, 0.0)
        assertEquals(30.0, ExerciseDefaults.startingWeight(exercise("row", "바벨"))!!, 0.0)
        assertEquals(4.0, ExerciseDefaults.startingWeight(exercise("lateral_raise", "덤벨"))!!, 0.0)
        assertEquals(10.0, ExerciseDefaults.startingWeight(exercise("row"), WorkoutProfile(gender = "FEMALE"))!!, 0.0)
        assertEquals(15.0, ExerciseDefaults.startingWeight(exercise("row"), WorkoutProfile(ageYears = 65))!!, 0.0)
        assertEquals(15.0, ExerciseDefaults.startingWeight(exercise("row"), WorkoutProfile(weightKg = 50.0, weightMeasuredOn = "2026-10-30"))!!, 0.0)
        assertEquals(20.0, ExerciseDefaults.startingWeight(exercise("row"), WorkoutProfile())!!, 0.0)
    }

    @Test fun cableStartsLightForSmallMusclesAndLateralRaiseIsAlwaysFiveKilos() {
        val female = WorkoutProfile(gender = "FEMALE")
        val heavyMan = WorkoutProfile(weightKg = 100.0, weightMeasuredOn = "2026-10-30")
        assertEquals(5.0, ExerciseDefaults.startingWeight(exercise("lateral_raise", "케이블"))!!, 0.0)
        assertEquals(5.0, ExerciseDefaults.startingWeight(exercise("lateral_raise", "케이블"), female)!!, 0.0)
        assertEquals(5.0, ExerciseDefaults.startingWeight(exercise("lateral_raise", "케이블"), heavyMan)!!, 0.0)
        assertEquals(10.0, ExerciseDefaults.startingWeight(exercise("curl", "케이블"))!!, 0.0)
        assertEquals(5.0, ExerciseDefaults.startingWeight(exercise("curl", "케이블"), female)!!, 0.0)
        assertEquals(10.0, ExerciseDefaults.startingWeight(exercise("triceps_pushdown", "케이블"))!!, 0.0)
        assertEquals(60.0, ExerciseDefaults.startingWeight(exercise("leg_press"))!!, 0.0)
    }

    @Test fun onlyBodyweightStartsWithoutExternalWeightAndWeightedDipIsFixed() {
        assertNull(ExerciseDefaults.newExercise(exercise("push_up", "맨몸")).sets.single().weightKg)
        val dip = WorkoutData.catalog.single { it.id == "weighted_dip" }
        assertNotEquals("맨몸", dip.equipment)
        assertEquals(5.0, ExerciseDefaults.newExercise(dip).sets.single().weightKg!!, 0.0)
        for (e in WorkoutData.catalog.filter { it.equipment != "맨몸" }) {
            val kg = ExerciseDefaults.startingWeight(e, WorkoutProfile(gender = "FEMALE", ageYears = 65, weightKg = 50.0, weightMeasuredOn = "2026-10-30"))!!
            val step = if (e.equipment in setOf("머신", "케이블", "핀 머신")) 5.0
                else if (e.equipment in setOf("바벨", "덤벨")) 2.0 else 1.0
            assertTrue(e.id, kg > 0 && kg % step == 0.0)
        }
    }

    @Test fun latestCompletedWorkingWeightWinsWithoutRoundingOrOtherEquipmentLeaking() {
        val logs = listOf(
            ExerciseLog("test", 1, listOf(LoggedSet(27.0, 10)), equipment = "머신"),
            ExerciseLog("test", 2, listOf(LoggedSet(35.0, 10), LoggedSet(54.0, 0, completed = false)), startedAtMs = 1, equipment = "머신"),
            ExerciseLog("test", 2, listOf(LoggedSet(45.0, 10), LoggedSet(10.0, 10, isWarmup = true)), startedAtMs = 2, equipment = "머신"),
            ExerciseLog("test", 3, listOf(LoggedSet(99.0, 10)), equipment = "바벨"))
        val item = ExerciseDefaults.newExercise(exercise("row").copy(bodyCategory = "등"), WorkoutProfile(gender = "FEMALE"), logs)
        assertEquals(45.0, item.sets.single().weightKg!!, 0.0)
        assertEquals(10, item.sets.single().targetReps)
        assertEquals(120, item.restSeconds)
        assertFalse(item.sets.single().completed)
    }

    @Test fun defaultTemplatesUpgradeOnlyNinetySecondRest() {
        val routines = WorkoutData.defaultRoutines()
        assertTrue(routines.flatMap { it.exercises }.none { it.restSeconds == 90 })
        assertEquals(45, routines.first().exercises.first().restSeconds)
        assertEquals(150, routines.first { it.id == "chest_triceps" }.exercises.first { it.exercise.id == "flat_bench" }.restSeconds)
    }
}
