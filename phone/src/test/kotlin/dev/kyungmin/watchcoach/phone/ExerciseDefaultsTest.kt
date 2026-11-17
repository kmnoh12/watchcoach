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
        val bodyweight = ExerciseDefaults.newExercise(exercise("push_up", "맨몸")).sets
        assertEquals(4, bodyweight.size)
        assertTrue(bodyweight.all { it.weightKg == null && it.setType == SetType.NORMAL })
        assertEquals(listOf(15, 12, 10, 8), bodyweight.map { it.targetReps })
        val dip = WorkoutData.catalog.single { it.id == "weighted_dip" }
        assertNotEquals("맨몸", dip.equipment)
        assertEquals(5.0, ExerciseDefaults.newExercise(dip).sets.last().weightKg!!, 0.0)
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

    @Test fun latestSessionCopiesEveryCompletedWorkingSetWithActualReps() {
        val latest = ExerciseLog("test", 2, listOf(
            LoggedSet(10.0, 15, isWarmup = true), LoggedSet(35.0, 9, targetReps = 10),
            LoggedSet(27.0, 11), LoggedSet(45.0, 8, completed = false),
            LoggedSet(40.0, 10, repsEntered = false)), equipment = "머신")
        val older = latest.copy(epochDay = 1, sets = listOf(LoggedSet(99.0, 20)))
        val item = ExerciseDefaults.newExercise(exercise("row"), history = listOf(latest, older))
        assertEquals(listOf(35.0, 27.0), item.sets.map { it.weightKg })
        assertEquals(listOf(9, 11), item.sets.map { it.targetReps })
        assertTrue(item.sets.all { it.setType == SetType.NORMAL && !it.completed })
    }

    @Test fun bodyweightAndLegacyEquipmentHistoryKeepTheirLayouts() {
        val bodyweight = ExerciseDefaults.newExercise(exercise("push_up", "맨몸"), history = listOf(
            ExerciseLog("test", 1, listOf(LoggedSet(null, 14), LoggedSet(null, 9)))))
        assertEquals(listOf(14, 9), bodyweight.sets.map { it.targetReps })
        assertTrue(bodyweight.sets.all { it.weightKg == null })
        val legacy = ExerciseDefaults.newExercise(exercise("row"), history = listOf(
            ExerciseLog("test", 1, listOf(LoggedSet(27.0, 8), LoggedSet(35.0, 6)))))
        assertEquals(listOf(27.0, 35.0), legacy.sets.map { it.weightKg })
    }

    @Test fun similarExerciseCopiesLayoutAndConvertsDumbbellWeightPerHand() {
        val barbell = WorkoutData.catalog.single { it.id == "barbell_biceps_curl" }
        val ez = WorkoutData.catalog.single { it.id == "ez_biceps_curl" }
        val dumbbell = WorkoutData.catalog.single { it.id == "dumbbell_curl" }
        val history = listOf(ExerciseLog(barbell.id, 1, listOf(
            LoggedSet(10.0, 20, isWarmup = true), LoggedSet(30.0, 12), LoggedSet(25.0, 9)), equipment = barbell.equipment))
        val same = ExerciseDefaults.newExercise(ez, history = history)
        assertEquals(listOf(30.0, 25.0), same.sets.map { it.weightKg })
        assertEquals(listOf(12, 9), same.sets.map { it.targetReps })
        val different = ExerciseDefaults.newExercise(dumbbell, history = history)
        assertEquals(listOf(12, 9), different.sets.map { it.targetReps })
        assertEquals(listOf(10.0, 8.0), different.sets.map { it.weightKg })
    }

    @Test fun similarHistoryUsesLatestPatternRegardlessOfBodyLabelAndDeterministicTies() {
        val target = WorkoutData.catalog.single { it.id == "dumbbell_curl" }
        val a = ExerciseLog("barbell_biceps_curl", 1, listOf(LoggedSet(30.0, 9)), sessionId = "a", startedAtMs = 1, equipment = "바벨")
        val b = a.copy(sessionId = "b", exerciseId = "ez_biceps_curl", sets = listOf(LoggedSet(25.0, 11), LoggedSet(20.0, 8)))
        val irrelevant = b.copy(epochDay = 3, exerciseId = "flat_bench")
        val first = ExerciseDefaults.newExercise(target, history = listOf(a, b, irrelevant))
        val reversed = ExerciseDefaults.newExercise(target, history = listOf(irrelevant, b, a))
        assertEquals(first.sets.map { it.targetReps }, reversed.sets.map { it.targetReps })
        assertEquals(listOf(11, 8), first.sets.map { it.targetReps })
        val differentBodyLabel = target.copy(bodyCategory = "팔, 이두")
        assertEquals(9, ExerciseDefaults.newExercise(differentBodyLabel, history = listOf(a)).sets.single().targetReps)
    }

    @Test fun exactHistoryWinsAndUnknownOrUnusableHistoryUsesRampFallback() {
        val target = WorkoutData.catalog.single { it.id == "dumbbell_curl" }
        val exact = ExerciseLog(target.id, 1, listOf(LoggedSet(7.5, 7)), equipment = target.equipment)
        val similar = exact.copy(exerciseId = "barbell_biceps_curl", epochDay = 2, equipment = "바벨", sets = listOf(LoggedSet(30.0, 15)))
        val own = ExerciseDefaults.newExercise(target, history = listOf(exact, similar)).sets.single()
        assertEquals(7, own.targetReps)
        assertEquals(7.5, own.weightKg!!, 0.0)
        for (pattern in listOf("", "unknown")) {
            val definition = target.copy(pattern = pattern)
            val fallback = ExerciseDefaults.newExercise(definition, history = listOf(similar))
            assertEquals(listOf(15, 12, 10, 8), fallback.sets.map { it.targetReps })
            assertEquals(listOf(4.0, 6.0, 7.0, 8.0), fallback.sets.map { it.weightKg })
            assertEquals(SetType.WARMUP, fallback.sets.first().setType)
        }
        val unusable = exact.copy(sets = listOf(LoggedSet(10.0, 0, repsEntered = false)))
        assertEquals(listOf(15, 12, 10, 8), ExerciseDefaults.newExercise(target, history = listOf(unusable)).sets.map { it.targetReps })
    }

    @Test fun relatedCableLateralRaiseWeightIsClampedToTheStartingEstimate() {
        val target = WorkoutData.catalog.single { it.id == "one_arm_cable_lateral" }
        val history = listOf(ExerciseLog("dumbbell_lateral_raise", 1,
            listOf(LoggedSet(20.0, 12), LoggedSet(18.0, 10)), equipment = "덤벨"))
        val item = ExerciseDefaults.newExercise(target, history = history)
        assertEquals(listOf(12, 10), item.sets.map { it.targetReps })
        assertEquals(listOf(5.0, 5.0), item.sets.map { it.weightKg })
    }

    @Test fun barbellBenchCarriesAllWorkingSetsToEveryRelatedMachineAndDumbbellBench() {
        val history = listOf(ExerciseLog("flat_bench", 1, listOf(
            LoggedSet(20.0, 15, isWarmup = true), LoggedSet(60.0, 12), LoggedSet(60.0, 10), LoggedSet(60.0, 8)), equipment = "바벨"))
        for (id in listOf("flat_machine_bench_press", "chest_press", "incline_machine_chest_press_plate", "dumbbell_bench")) {
            val target = WorkoutData.catalog.single { it.id == id }.copy(bodyCategory = "가슴, 삼두")
            val item = ExerciseDefaults.newExercise(target, history = history)
            val expectedWeight = if (target.equipment == "덤벨") 20.0 else 60.0
            assertEquals(id, List(3) { expectedWeight }, item.sets.map { it.weightKg })
            assertEquals(id, listOf(12, 10, 8), item.sets.map { it.targetReps })
            assertTrue(item.sets.all { it.setType == SetType.NORMAL && !it.completed })
        }
    }

    @Test fun dumbbellConversionWorksInBothDirectionsWithEquipmentRoundingAndMinimums() {
        val dumbbell = WorkoutData.catalog.single { it.id == "dumbbell_bench" }
        val barbell = WorkoutData.catalog.single { it.id == "flat_bench" }
        val machine = WorkoutData.catalog.single { it.id == "chest_press" }
        val barbellHistory = listOf(ExerciseLog(barbell.id, 1,
            listOf(LoggedSet(30.0, 10), LoggedSet(31.5, 9), LoggedSet(0.3, 8), LoggedSet(0.0, 7), LoggedSet(null, 6)), equipment = "바벨"))
        assertEquals(listOf(10.0, 11.0, 1.0, 0.0, null),
            ExerciseDefaults.newExercise(dumbbell, history = barbellHistory).sets.map { it.weightKg })
        val dumbbellHistory = listOf(ExerciseLog(dumbbell.id, 1,
            listOf(LoggedSet(10.0, 10), LoggedSet(10.5, 9), LoggedSet(0.0, 8), LoggedSet(null, 7)), equipment = "덤벨"))
        assertEquals(listOf(30.0, 32.0, 0.0, null),
            ExerciseDefaults.newExercise(barbell, history = dumbbellHistory).sets.map { it.weightKg })
        assertEquals(listOf(30.0, 30.0, 0.0, null),
            ExerciseDefaults.newExercise(machine, history = dumbbellHistory).sets.map { it.weightKg })
    }

    @Test fun latestMachineHistoryCarriesUnroundedWeightsToInclineAndOtherNonDumbbellEquipment() {
        val older = ExerciseLog("flat_bench", 1, listOf(LoggedSet(60.0, 10)), equipment = "바벨")
        val latest = older.copy(exerciseId = "chest_press", epochDay = 2, equipment = "머신",
            sets = listOf(LoggedSet(63.2, 12), LoggedSet(54.0, 10)))
        val incline = WorkoutData.catalog.single { it.id == "incline_machine_chest_press_plate" }
        for (target in listOf(incline, incline.copy(equipment = "스미스"), incline.copy(equipment = "케이블"))) {
            val item = ExerciseDefaults.newExercise(target, history = listOf(latest, older))
            assertEquals(listOf(63.2, 54.0), item.sets.map { it.weightKg })
            assertEquals(listOf(12, 10), item.sets.map { it.targetReps })
        }
    }

    @Test fun noRelatedHistoryCreatesFourRoundedRampSetsWithWarmupFirst() {
        val cases = listOf(
            exercise("chest_press", "바벨") to listOf(10.0, 14.0, 18.0, 20.0),
            exercise("leg_press", "머신") to listOf(30.0, 40.0, 50.0, 60.0),
            exercise("chest_press", "덤벨") to listOf(4.0, 6.0, 7.0, 8.0))
        for ((target, weights) in cases) {
            val item = ExerciseDefaults.newExercise(target)
            assertEquals(weights, item.sets.map { it.weightKg })
            assertEquals(listOf(15, 12, 10, 8), item.sets.map { it.targetReps })
            assertEquals(listOf(SetType.WARMUP, SetType.NORMAL, SetType.NORMAL, SetType.NORMAL), item.sets.map { it.setType })
        }
        val female = ExerciseDefaults.newExercise(exercise("chest_press", "덤벨"), WorkoutProfile(gender = "FEMALE"))
        assertEquals(listOf(3.0, 4.0, 5.0, 6.0), female.sets.map { it.weightKg })
    }

    @Test fun cableLateralClampKeepsLowerOrBlankWeightsAndOwnHistoryStillWins() {
        val target = WorkoutData.catalog.single { it.id == "one_arm_cable_lateral" }
        val related = ExerciseLog("dumbbell_lateral_raise", 1,
            listOf(LoggedSet(1.0, 12), LoggedSet(0.0, 10), LoggedSet(null, 8)), equipment = "덤벨")
        assertEquals(listOf(5.0, 0.0, null), ExerciseDefaults.newExercise(target, history = listOf(related)).sets.map { it.weightKg })
        val own = related.copy(exerciseId = target.id, equipment = target.equipment, sets = listOf(LoggedSet(7.5, 9)))
        assertEquals(7.5, ExerciseDefaults.newExercise(target, history = listOf(own, related.copy(epochDay = 2))).sets.single().weightKg!!, 0.0)
    }
}
