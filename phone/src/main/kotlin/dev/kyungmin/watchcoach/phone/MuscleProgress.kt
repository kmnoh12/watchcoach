package dev.kyungmin.watchcoach.phone

import dev.kyungmin.watchcoach.core.*

internal data class MuscleProgressRow(
    val group: String, val sets: Double, val previousSets: Double?, val first: Boolean,
    val intensityPercent: Double?, val compared: Int, val exercises: Int, val newExercises: Int,
)

private data class ExerciseWork(val credits: Map<String, Double>, val best: Double?)
private data class SessionWork(val time: Long, val routine: String, val gym: String?, val work: Map<String, ExerciseWork>) {
    fun sets(group: String) = work.values.sumOf { it.credits[group] ?: 0.0 }
}

/** Regional set counts prefer the same routine, then the latest workout for that region.
 * Intensity always uses the exercise's own latest workout, independent of the sets baseline.
 * Gym is optional: finished snapshots currently have no location, so their exercise IDs share one unknown-gym bucket. */
internal fun muscleProgress(current: WorkoutSnapshot, records: List<WorkoutSnapshot>,
    catalog: Map<String, ExerciseDefinition>, gymOf: (String) -> String? = { null },
    frozenWeightOf: (String) -> Double? = { null },
): List<MuscleProgressRow> {
    fun summarize(snapshot: WorkoutSnapshot): SessionWork {
        val bodyWeight by lazy { frozenWeightOf(snapshot.sessionId) }
        val exercises = snapshot.plannedSets.filter { it.completed && it.setType != "WARMUP" &&
            (if (it.exerciseKind == ExerciseKind.HOLD) it.durationSeconds != 0 else it.performedReps != 0) }
            .groupBy { it.exerciseId }.mapNotNull { (id, sets) ->
                val first = sets.first()
                val fallback = catalog[id]
                val body = first.bodyCategory.ifBlank { fallback?.bodyCategory.orEmpty() }
                val pattern = first.pattern.ifBlank { fallback?.pattern.orEmpty() }
                val shares = BodyLoad.partWeights(body, pattern, id).ifEmpty {
                    if (body in StatsAnalytics.GROUPS) mapOf(body to 1.0) else emptyMap()
                }.entries.groupBy { StatsAnalytics.muscleGroup(it.key) }
                    // Multiple shoulder heads (or back + traps) still represent at most one set for that region.
                    .mapValues { (_, parts) -> parts.sumOf { it.value }.coerceAtMost(1.0) }
                if (shares.isEmpty()) return@mapNotNull null
                val load = progressionLoad(id, first.exerciseName.ifBlank { fallback?.name.orEmpty() }, pattern,
                    first.equipment.ifBlank { fallback?.equipment.orEmpty() }, sets.map { it.weightKg })
                val halfPeak = (sets.maxOfOrNull { it.weightKg ?: 0.0 } ?: 0.0) / 2
                val working = sets.filterNot { load == ProgressionLoad.EXTERNAL && it.setType == "NORMAL" &&
                    it.weightKg?.let { kg -> kg < halfPeak } == true }
                if (working.isEmpty()) return@mapNotNull null
                val best = working.mapNotNull { set ->
                    val kg = when (load) {
                        ProgressionLoad.EXTERNAL -> set.weightKg
                        ProgressionLoad.WEIGHTED_BODYWEIGHT -> bodyWeight?.plus(set.weightKg ?: 0.0)
                        else -> null // Assistance is not lifted mass; timed holds aren't repetitions.
                    }
                    if (set.exerciseKind == ExerciseKind.HOLD || set.setType == "ASSISTED") null
                    else EstimatedOneRepMax.epley(kg, set.performedReps ?: 0)
                }.maxOrNull()
                id to ExerciseWork(shares.mapValues { it.value * working.size }, best)
            }.toMap()
        return SessionWork(snapshot.startedAtMs, snapshot.routineId, gymOf(snapshot.sessionId)?.trim()?.ifEmpty { null }, exercises)
    }
    val now = summarize(current)
    val history = records.filter { it.sessionId != current.sessionId && it.startedAtMs <= now.time }.map(::summarize)
    // Equal timestamps establish neither a previous workout nor a first-ever record.
    fun latest(matches: List<SessionWork>): SessionWork? {
        val time = matches.maxOfOrNull { it.time } ?: return null
        return if (time == now.time) null else matches.singleOrNull { it.time == time }
    }
    val priorByExercise = now.work.keys.associateWith { id -> history.filter { it.gym == now.gym && id in it.work } }
    return StatsAnalytics.GROUPS.mapNotNull { group ->
        val sets = now.sets(group)
        if (sets == 0.0) return@mapNotNull null
        val regionHistory = history.filter { it.sets(group) > 0 }
        val prior = regionHistory.filter { now.routine != "free" && it.routine == now.routine }.ifEmpty { regionHistory }
        var weighted = 0.0; var weight = 0.0; var compared = 0; var fresh = 0; var count = 0
        for ((id, exercise) in now.work) {
            val credits = exercise.credits[group] ?: continue
            count++
            val matches = priorByExercise.getValue(id)
            if (matches.isEmpty()) fresh++
            val before = latest(matches)?.work?.get(id)?.best ?: continue
            val change = exercise.best?.let { (it / before - 1) * 100 }?.takeIf { it.isFinite() } ?: continue
            weighted += change * credits; weight += credits; compared++
        }
        MuscleProgressRow(group, sets, latest(prior)?.sets(group), prior.isEmpty(),
            if (weight > 0) weighted / weight else null, compared, count, fresh)
    }.sortedByDescending { it.sets }
}
