package dev.kyungmin.kcoach.phone.ui

import android.content.Context
import dev.kyungmin.kcoach.core.*
import dev.kyungmin.kcoach.phone.*
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

internal fun resultNumber(value: Double): String = java.text.DecimalFormat("#,##0.#").format(value)
internal data class ResultSet(val number: Int, val today: String, val previous: String, val record: Boolean)
internal data class ResultExercise(val name: String, val best: String, val delta: String, val direction: Int?, val sets: List<ResultSet>)
internal data class ResultPresentation(val title: String, val date: String, val photoDate: String, val minutes: Int,
    val volume: String, val exercises: List<ResultExercise>, val vitals: String, val recordCount: Int) {
    val setCount get() = exercises.sumOf { it.sets.size }
    val rising get() = exercises.count { it.direction == 1 }
    val verdict get() = "지난번보다 ${rising}종목 상승"
    val comparison get() = "유지 ${exercises.count { it.direction == 0 }} · 하락 ${exercises.count { it.direction == -1 }} · 최고 기록 $recordCount"
}

/** Presentation only: finished snapshots and the existing comparison/record rules remain authoritative. */
internal fun loadResultPresentation(context: Context, sessionId: String): ResultPresentation {
    val store = FinishedWorkoutStore(context)
    val all = store.allEvidence()
    val evidence = all.single { it.snapshot.sessionId == sessionId }
    val current = evidence.snapshot
    val prior = WorkoutComparison.previous(current, all.map { it.snapshot })
    val comparisons = WorkoutComparison.compare(current, prior)
    val hits = store.recordHits(sessionId).map { it.second }
    fun value(s: PlannedSetSnapshot): String = if (s.exerciseKind == ExerciseKind.HOLD)
        "${s.durationSeconds?.toString() ?: "—"}초" else
        "${s.weightKg?.let(::resultNumber) ?: "—"}kg × ${s.performedReps?.toString() ?: "—"}회"
    val exercises = current.plannedSets.filter { it.completed }.groupBy { it.exerciseIndex }.values.map { group ->
        val sets = group.sortedBy { it.setIndex }
        val first = sets.first()
        val before = prior?.plannedSets.orEmpty().filter { it.completed && WorkoutCondition.of(it) == WorkoutCondition.of(first) }
        val best = sets.maxWith(compareBy<PlannedSetSnapshot> { if (it.exerciseKind == ExerciseKind.HOLD) (it.durationSeconds ?: 0).toDouble() else it.weightKg ?: -1.0 }.thenBy { it.performedReps ?: -1 })
        val changes = comparisons.filter { it.condition == WorkoutCondition.of(first) }
        val weights = changes.flatMap { it.sameReps }.map { it.currentWeightsKg.max() - it.previousWeightsKg.max() }.filter { it != 0.0 }
        val reps = changes.flatMap { it.sameWeight }.filter { it.comparableSetCount }.sumOf { it.currentReps - it.previousReps }
        val hold = first.exerciseKind == ExerciseKind.HOLD
        val seconds = if (hold && before.size == sets.size && before.isNotEmpty() && (before + sets).all { it.durationSeconds != null })
            sets.sumOf { it.durationSeconds!! } - before.sumOf { it.durationSeconds!! } else null
        val comparableReps = changes.flatMap { it.sameWeight }.filter { it.comparableSetCount }
        val delta: Double? = if (hold) seconds?.toDouble() else weights.maxOrNull() ?: reps.toDouble().takeIf { comparableReps.isNotEmpty() && changes.all { it.previous != null && !it.setCountChanged && it.current.volumeKgReps != null && it.previous?.volumeKgReps != null } }
        val direction = delta?.compareTo(0.0)
        val label = when { delta == null -> if (before.isEmpty()) "첫 기록" else "—"; delta == 0.0 -> "유지"; else ->
            (if (delta > 0) "+" else "−") + resultNumber(kotlin.math.abs(delta)) + if (hold) "초" else if (weights.isNotEmpty()) "kg" else "회" }
        val hit = hits.firstOrNull { it.exerciseId == first.exerciseId }
        val normal = sets.filter { it.setType == "NORMAL" }
        val recordSet = hit?.let { h -> normal.firstOrNull { set ->
            when (h.kind) {
                RecordKind.HEAVIEST_WEIGHT -> set.weightKg == h.value
                RecordKind.SAME_WEIGHT_REPS -> set.performedReps == h.value.toInt() && (h.weightKg == null || set.weightKg == h.weightKg)
                RecordKind.ESTIMATED_ONE_REP_MAX -> EstimatedOneRepMax.epley(set.weightKg, set.performedReps ?: 0)?.let { kotlin.math.abs(it - h.value) < .001 } == true
                RecordKind.BEST_VOLUME -> false
            }
        } ?: normal.maxWithOrNull(compareBy<PlannedSetSnapshot> { it.weightKg ?: -1.0 }.thenBy { it.performedReps ?: -1 }) }
        ResultExercise(first.exerciseName.ifBlank { first.exerciseId }, value(best), label, direction, sets.map { s ->
            val isRecord = s === recordSet
            ResultSet(s.setIndex + 1, value(s), before.singleOrNull { it.setIndex == s.setIndex && it.setType == s.setType }?.let(::value) ?: "—", isRecord)
        })
    }
    val date = Instant.ofEpochMilli(current.startedAtMs).atZone(ZoneId.systemDefault())
    val heart = WorkoutVitalsStore(context).summary(sessionId, current.startedAtMs, evidence.finishedAtMs)
    val kcal = runCatching {
        val fallback = UserProfileStore(context).profileForSession(sessionId)
        val profile = WorkoutWearingStore(context).frozenBodyProfile(sessionId, fallback).getOrThrow()
        (WorkoutEnergyStore(context).estimate(evidence, profile).opt("active_kcal") as? Number)?.toInt()
    }.getOrNull()
    return ResultPresentation(evidence.title, date.format(DateTimeFormatter.ofPattern("yyyy년 M월 d일 EEEE · a h:mm", Locale.KOREA)),
        date.format(DateTimeFormatter.ofPattern("MM.dd EEE", Locale.US)).uppercase(Locale.US), evidence.minutes,
        WorkoutComparison.totals(current.plannedSets.filter { it.completed }).volumeKgReps?.let(::resultNumber) ?: "—", exercises,
        "평균 심박 ${heart.average?.toInt() ?: "—"} · 최고 ${heart.maximum ?: "—"} · ${kcal?.let { "약 ${it}kcal" } ?: "—kcal"}", hits.size)
}
