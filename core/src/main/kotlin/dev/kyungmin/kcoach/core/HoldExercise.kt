package dev.kyungmin.kcoach.core

/** Explicit static holds only; moving exercises such as dead bug remain repetition based. */
object HoldExercise {
    val catalogIds = setOf("plank", "side_plank", "hollow_hold", "plate_pinch")
    fun kind(id: String) = if (id in catalogIds) ExerciseKind.HOLD else ExerciseKind.RESISTANCE
    fun time(seconds: Int): String = "%d:%02d".format(java.util.Locale.US, seconds.coerceAtLeast(0) / 60, seconds.coerceAtLeast(0) % 60)
    fun record(set: PlannedSetSnapshot): String {
        val weight = set.weightKg?.let { (if (it % 1.0 == 0.0) it.toInt().toString() else it.toString()) + "kg × " }.orEmpty()
        return weight + if (set.exerciseKind == ExerciseKind.HOLD) set.durationSeconds?.let(::time) ?: "시간 미입력"
            else set.performedReps?.let { "${it}회" } ?: "횟수 미입력"
    }
    fun nextTarget(sets: List<LoggedSet>, current: Int): Int =
        if (sets.isNotEmpty() && sets.all { it.completed && it.durationSeconds != null && it.durationSeconds >= (it.targetDurationSeconds ?: current) }) current + 5 else current
}
