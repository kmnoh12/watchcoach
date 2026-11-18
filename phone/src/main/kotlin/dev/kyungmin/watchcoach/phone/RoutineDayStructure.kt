package dev.kyungmin.watchcoach.phone

/**
 * Takes the shape of a finished workout (exercises added, removed or reordered that day, sets added or removed)
 * back into the saved routine, so "루틴 저장" keeps what the user actually did. Weights and reps are not copied:
 * they reach the next session through the exercise history, so progression keeps working.
 */
internal object RoutineDayStructure {
    /** The exercise list the saved routine should become, or null when the day changed nothing structural. */
    fun carried(saved: List<RoutineExercise>, day: List<RoutineExercise>): List<RoutineExercise>? {
        val pool = saved.toMutableList()
        val result = day.map { item ->
            val match = pool.firstOrNull { it.exercise.id == item.exercise.id && it.exercise.equipment == item.exercise.equipment }
                ?.also { pool.remove(it) }
            if (match == null) fresh(item) else resized(match, item)
        }
        val unchanged = result.size == saved.size && result.indices.all { result[it] === saved[it] }
        return if (unchanged) null else result
    }

    private fun fresh(item: RoutineExercise) = RoutineExercise(item.exercise, item.sets.map(::cleared).toMutableList(), item.restSeconds)

    /** Keeps the saved sets (and their ids, so progression state still lines up) and only grows or shrinks the tail. */
    private fun resized(saved: RoutineExercise, day: RoutineExercise): RoutineExercise {
        if (saved.sets.map { it.setType } == day.sets.map { it.setType }) return saved
        val sets = day.sets.mapIndexed { i, set ->
            saved.sets.getOrNull(i)?.takeIf { it.setType == set.setType } ?: cleared(set)
        }
        return RoutineExercise(saved.exercise, sets.toMutableList(), saved.restSeconds)
    }

    private fun cleared(set: PlannedSet) = set.copy(completed = false, performedReps = null, repSource = null, durationSeconds = null,
        unilateral = null, setId = java.util.UUID.randomUUID().toString(), attemptId = java.util.UUID.randomUUID().toString(), identityRequired = true)
}
