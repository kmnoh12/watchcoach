package dev.kyungmin.watchcoach.phone.ui

import android.content.Context
import dev.kyungmin.watchcoach.core.*
import dev.kyungmin.watchcoach.phone.*
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

internal fun resultNumber(value: Double): String = java.text.DecimalFormat("#,##0.#").format(value)
internal data class ResultSet(val number: Int, val today: String, val previous: String, val record: Boolean)
/** Average seconds per repetition and how the pace moved through the sets: -1 quickening, 0 steady, 1 slowing, null unknown. */
internal data class ResultTempo(val average: String, val trend: Int?, val change: String?)
internal data class ResultExercise(val name: String, val best: String, val delta: String, val direction: Int?, val sets: List<ResultSet>, val tempo: ResultTempo? = null, val growth: String? = null, val exerciseId: String = "")

/** Wrist-observed repetition times only; the 8% steadiness band matches the in-workout set remarks. */
internal fun resultTempo(metrics: List<ObservedMotionMetrics>): ResultTempo? {
    val reps = metrics.flatMap { it.reps }
    if (reps.isEmpty()) return null
    val average = reps.map { it.durationMs }.average().takeIf { it.isFinite() && it > 0 } ?: return null
    val ratios = metrics.mapNotNull { it.lateCycleChangeRatio?.takeIf(Double::isFinite) }
    val change = ratios.takeIf { it.isNotEmpty() }?.average()
    val trend = change?.let { if (it >= .08) 1 else if (it <= -.08) -1 else 0 }
    return ResultTempo("%.1f초".format(Locale.KOREA, average / 1000.0), trend,
        change?.takeIf { trend != 0 }?.let { "후반 %+d%%".format(Locale.KOREA, Math.round(it * 100).toInt()) })
}
internal fun MuscleProgressRow.summaryLine(): String = buildString {
    append(group)
    if (previousSets != null) append(" 세트 ${resultNumber(previousSets)}→${resultNumber(sets)}")
    else append(" ${resultNumber(sets)}세트 · " + if (first) "첫 기록" else "이전 기록 불명확")
    if (intensityPercent != null) {
        val value = resultNumber(if (kotlin.math.abs(intensityPercent) < 0.05) 0.0 else intensityPercent)
        append(" · 강도 " + (if (intensityPercent > 0 && value != "0") "+" else "") + value + "%")
        if (compared < exercises) append(" ($compared/${exercises}종목)")
    } else if (!first && exercises > newExercises) append(" · 강도 비교 불가")
    if (newExercises > 0) append(" · 새 종목 ${newExercises}개")
}

internal data class ResultPresentation(val title: String, val date: String, val photoDate: String, val minutes: Int,
    val volume: String, val exercises: List<ResultExercise>, val vitals: String, val recordCount: Int,
    val avgHeart: String = "—", val maxHeart: String = "—", val kcal: String = "—", val heartPoints: List<Pair<Long, Int>> = emptyList(),
    val muscleLines: List<String> = emptyList()) {
    val setCount get() = exercises.sumOf { it.sets.size }
    val photoSummary get() = muscleLines.firstOrNull() ?: "부위 비교 자료 없음"
}

/** Presentation only: finished snapshots and the existing comparison/record rules remain authoritative. */
internal fun loadResultPresentation(context: Context, sessionId: String): ResultPresentation {
    val store = FinishedWorkoutStore(context)
    val all = store.allEvidence()
    val evidence = all.single { it.snapshot.sessionId == sessionId }
    val current = evidence.snapshot
    val records = all.map { it.snapshot }
    val comparisons = WorkoutComparison.compare(current, records)
    val hits = store.recordHits(sessionId).map { it.second }
    fun value(s: PlannedSetSnapshot): String = if (s.exerciseKind == ExerciseKind.HOLD)
        "${s.durationSeconds?.toString() ?: "—"}초" else
        "${s.weightKg?.let(::resultNumber) ?: "—"}kg × ${s.performedReps?.toString() ?: "—"}회"
    val analyses = runCatching { SetAnalysisStore(context).loadForSession(sessionId) }.getOrDefault(emptyMap())
    val exercises = current.plannedSets.filter { it.completed }.groupBy { it.exerciseIndex }.values.map { group ->
        val sets = group.sortedBy { it.setIndex }
        val first = sets.first()
        val conditions = sets.map(WorkoutCondition::of).toSet()
        val before = conditions.flatMap { condition ->
            WorkoutComparison.previousFor(current, records, condition)?.plannedSets.orEmpty()
                .filter { it.completed && WorkoutCondition.of(it) == condition }
        }
        val hasEarlierCondition = records.any { it.sessionId != current.sessionId && it.startedAtMs <= current.startedAtMs &&
            WorkoutComparison.normalGroups(it).keys.any { condition -> condition in conditions } }
        val best = sets.maxWith(compareBy<PlannedSetSnapshot> { if (it.exerciseKind == ExerciseKind.HOLD) (it.durationSeconds ?: 0).toDouble() else it.weightKg ?: -1.0 }.thenBy { it.performedReps ?: -1 })
        val changes = comparisons.filter { it.condition in conditions }
        val weights = changes.flatMap { it.sameReps }.map { it.currentWeightsKg.max() - it.previousWeightsKg.max() }.filter { it != 0.0 }
        val reps = changes.flatMap { it.sameWeight }.filter { it.comparableSetCount }.sumOf { it.currentReps - it.previousReps }
        val hold = first.exerciseKind == ExerciseKind.HOLD
        val seconds = if (hold && before.size == sets.size && before.isNotEmpty() && (before + sets).all { it.durationSeconds != null })
            sets.sumOf { it.durationSeconds!! } - before.sumOf { it.durationSeconds!! } else null
        val comparableReps = changes.flatMap { it.sameWeight }.filter { it.comparableSetCount }
        val delta: Double? = if (hold) seconds?.toDouble() else weights.maxOrNull() ?: reps.toDouble().takeIf { comparableReps.isNotEmpty() && changes.all { it.previous != null && !it.setCountChanged && it.current.volumeKgReps != null && it.previous?.volumeKgReps != null } }
        fun oneRm(list: List<PlannedSetSnapshot>) = list.filter { it.setType == "NORMAL" }.mapNotNull { EstimatedOneRepMax.epley(it.weightKg, it.performedReps ?: 0) }.maxOrNull()
        val nowRm = if (hold) null else oneRm(sets)
        val prevRm = if (hold || changes.any { it.previous == null }) null else oneRm(before)
        val growthRatio = if (nowRm != null && prevRm != null && prevRm > 0) nowRm / prevRm - 1 else null
        val direction = growthRatio?.let { if (it > .005) 1 else if (it < -.005) -1 else 0 } ?: delta?.compareTo(0.0)
        val label = growthRatio?.let { if (direction == 0) "유지" else "%+.1f%%".format(Locale.KOREA, it * 100) } ?: when { delta == null -> if (before.isEmpty() && !hasEarlierCondition) "첫 기록" else "—"; delta == 0.0 -> "유지"; else ->
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
        val tempo = resultTempo(sets.mapNotNull { s -> analyses[SetIdentity.key(s.exerciseId, s.setIndex, s.setId, s.attemptId)]?.takeIf { it.trackingMode != "MANUAL_REQUIRED" }?.motionMetrics })
        ResultExercise(first.exerciseName.ifBlank { first.exerciseId }, value(best), label, direction, sets.map { s ->
            val isRecord = s === recordSet
            ResultSet(s.setIndex + 1, value(s), before.singleOrNull { it.setIndex == s.setIndex && it.setType == s.setType &&
                WorkoutCondition.of(it) == WorkoutCondition.of(s) }?.let(::value) ?: "—", isRecord)
        }, tempo, if (nowRm != null && prevRm != null) (if (resultNumber(prevRm) == resultNumber(nowRm)) "추정 1RM ${resultNumber(nowRm)}kg" else "추정 1RM ${resultNumber(prevRm)} → ${resultNumber(nowRm)}kg") else null, first.exerciseId)
    }
    val date = Instant.ofEpochMilli(current.startedAtMs).atZone(ZoneId.systemDefault())
    val heart = WorkoutVitalsStore(context).summary(sessionId, current.startedAtMs, evidence.finishedAtMs)
    val kcal = runCatching {
        val fallback = UserProfileStore(context).profileForSession(sessionId)
        val profile = WorkoutWearingStore(context).frozenBodyProfile(sessionId, fallback).getOrThrow()
        (WorkoutEnergyStore(context).estimate(evidence, profile).opt("active_kcal") as? Number)?.toInt()
    }.getOrNull()
    val wearing = WorkoutWearingStore(context)
    val muscleLines = muscleProgress(current, records, WorkoutData.catalog.associateBy { it.id },
        frozenWeightOf = { wearing.frozenBodyProfile(it, null).getOrNull()?.weightKg }).map { it.summaryLine() }
    return ResultPresentation(evidence.title, date.format(DateTimeFormatter.ofPattern("yyyy년 M월 d일 EEEE · a h:mm", Locale.KOREA)),
        date.format(DateTimeFormatter.ofPattern("MM.dd EEE", Locale.US)).uppercase(Locale.US), evidence.minutes,
        WorkoutComparison.totals(current.plannedSets.filter { it.completed }).volumeKgReps?.let(::resultNumber) ?: "—", exercises,
        "평균 심박 ${heart.average?.toInt() ?: "—"} · 최고 ${heart.maximum ?: "—"} · ${kcal?.let { "약 ${it}kcal" } ?: "—kcal"}", hits.size,
        heart.average?.toInt()?.toString() ?: "—", heart.maximum?.toString() ?: "—", kcal?.toString() ?: "—", heart.points.map { it.receivedAtMs to it.bpm }, muscleLines)
}
