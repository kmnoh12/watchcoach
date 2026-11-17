package dev.kyungmin.watchcoach.phone

import dev.kyungmin.watchcoach.core.ExerciseLog
import dev.kyungmin.watchcoach.core.ProgressionDefaults

/** Product starting estimates, not measured strength norms. Dumbbells use one dumbbell's mass. */
internal object ExerciseDefaults {
    private val largeMuscleGroups = setOf("가슴", "등", "하체")

    private val cableSmallMuscle = setOf("curl", "triceps_pushdown", "triceps_extension", "rear_delt", "front_raise", "rotation", "chest_fly")

    fun restGroup(exercise: ExerciseDefinition): RestMuscleGroup =
        if (exercise.bodyCategory in largeMuscleGroups) RestMuscleGroup.LARGE else RestMuscleGroup.SMALL

    fun restSeconds(exercise: ExerciseDefinition): Int = restGroup(exercise).defaultSeconds

    fun startingWeight(exercise: ExerciseDefinition, profile: WorkoutProfile? = null): Double? {
        if (exercise.equipment == "맨몸" && exercise.id !in setOf("weighted_dip", "weighted_pull_up")) return null
        val base = when {
            exercise.id in setOf("weighted_dip", "weighted_pull_up") -> 5.0
            exercise.equipment == "덤벨" -> when (exercise.pattern) {
                "lateral_raise", "front_raise", "rear_delt", "rotation" -> 4.0
                "curl", "triceps_extension", "chest_fly" -> 6.0
                "squat", "hinge", "row", "shrug", "pullover" -> 12.0
                else -> 8.0
            }
            exercise.equipment == "바벨" -> when (exercise.pattern) {
                "squat", "hinge", "row", "shrug" -> 30.0
                "curl", "triceps_extension", "rotation" -> 10.0
                else -> 20.0
            }
            // A cable lateral raise always starts at 5 kg for everyone; body-based scaling would only make it heavier.
            exercise.equipment == "케이블" && exercise.pattern == "lateral_raise" -> return 5.0
            exercise.equipment == "케이블" && exercise.pattern in cableSmallMuscle -> 10.0
            exercise.equipment in setOf("머신", "핀 머신", "케이블") -> when (exercise.pattern) {
                "leg_press" -> 60.0
                "squat", "hinge", "hip" -> 30.0
                "rotation", "lateral_raise", "front_raise", "rear_delt" -> 10.0
                else -> 20.0
            }
            else -> 10.0
        }
        // Upper-body machine and cable work starts at about half the men's weight for women (20 kg -> 10, 10 kg -> 5).
        val upperMachine = exercise.equipment in setOf("머신", "핀 머신", "케이블") && exercise.pattern !in setOf("leg_press", "squat", "hinge", "hip")
        val gender = if (profile?.gender == "FEMALE") (if (upperMachine) 0.5 else 0.65) else 1.0
        val age = when (profile?.ageYears) { in 1..17 -> 0.75; in 60..120 -> 0.8; else -> 1.0 }
        val body = ((profile?.weightKg ?: 75.0) / 75.0).coerceIn(0.6, 1.4)
        return ProgressionDefaults.roundWeight(base * gender * age * body, exercise.equipment)
    }

    fun newExercise(exercise: ExerciseDefinition, profile: WorkoutProfile? = null,
        history: List<ExerciseLog> = emptyList(),
        firstWorkoutRestSeconds: Int = restSeconds(exercise),
    ): RoutineExercise {
        val exerciseHistory = history.filter { it.exerciseId == exercise.id }
        val hasCompletedSet = exerciseHistory.any { log -> log.sets.any { it.completed } }
        val rest = if (hasCompletedSet) restSeconds(exercise) else firstWorkoutRestSeconds
        if (exercise.kind == dev.kyungmin.watchcoach.core.ExerciseKind.HOLD) return RoutineExercise(exercise,
            MutableList(3) { PlannedSet(startingWeight(exercise, profile), 0, targetDurationSeconds = 30) }, rest)
        val last = exerciseHistory.filter { it.equipment == exercise.equipment || it.equipment.isEmpty() ||
            (exercise.id in setOf("weighted_dip", "weighted_pull_up") && it.equipment == "맨몸") }
            .sortedWith(compareByDescending<ExerciseLog> { it.epochDay }.thenByDescending { it.startedAtMs })
            .firstNotNullOfOrNull { log -> log.sets.lastOrNull { it.completed && it.repsEntered &&
                !it.isWarmup && it.reps > 0 && it.weightKg?.let { kg -> kg.isFinite() && kg >= 0 } == true } }
        return RoutineExercise(exercise, mutableListOf(PlannedSet(
            last?.weightKg ?: startingWeight(exercise, profile), 10)), rest)
    }
}
