package dev.kyungmin.kcoach.core

import java.time.LocalDate
import java.time.ZoneId

/** Calculations shared by the statistics charts; periods include today and exclude future dates. */
object StatsAnalytics {
    val GROUPS = listOf("가슴", "어깨", "팔", "등", "코어", "하체")

    fun inPeriod(day: Long, today: Long, days: Int, previous: Boolean = false): Boolean {
        require(days >= 0)
        if (days == 0) return !previous && day <= today
        val end = today - if (previous) days else 0
        return day in (end - days + 1)..end
    }

    /** Monday-first running totals; the current line ends today, never projects future days. */
    fun weekVolumes(logs: List<WorkoutLog>, today: Long, previous: Boolean = false): List<Double> {
        val weekday = LocalDate.ofEpochDay(today).dayOfWeek.value - 1
        val monday = today - weekday - if (previous) 7 else 0
        val byDay = logs.groupBy { it.epochDay }
        var total = 0.0
        return List(if (previous) 7 else weekday + 1) { i ->
            total += byDay[monday + i].orEmpty().sumOf { it.volumeKg.toDouble() }
            total
        }
    }

    /** Volume uses the exercise's catalog category. Whole-body lifts split by normalized muscle weights. */
    fun volumeByGroup(logs: List<ExerciseLog>, bodyOf: (String) -> String?, weightsOf: (String) -> Map<String, Double>?,
                      today: Long, days: Int, previous: Boolean = false): List<Double> {
        val totals = GROUPS.associateWith { 0.0 }.toMutableMap()
        fun group(part: String): String = when (part) {
            "전면어깨", "측면어깨", "후면어깨" -> "어깨"
            "이두", "삼두" -> "팔"
            "승모" -> "등"
            else -> part
        }
        for (log in logs.filter { inPeriod(it.epochDay, today, days, previous) }) {
            val body = bodyOf(log.exerciseId) ?: continue
            val shares = if (body == "전신") weightsOf(log.exerciseId).orEmpty()
                .filter { group(it.key) in GROUPS && it.value > 0 }
                else mapOf(body to 1.0)
            val sum = shares.values.sum()
            if (sum <= 0) continue
            for ((part, weight) in shares) {
                val key = group(part)
                if (key in totals) totals[key] = totals.getValue(key) + log.volumeKg * weight / sum
            }
        }
        return GROUPS.map { totals.getValue(it) }
    }

    data class Record(val exerciseId: String, val atMs: Long, val epochDay: Long,
                      val best: LoggedSet, val previous: LoggedSet)

    /** A PR strictly improves the best weight × reps. First attempts and ties are not broken records. */
    fun records(logs: List<ExerciseLog>, nowMs: Long, zone: ZoneId = ZoneId.systemDefault()): List<Record> {
        val bestByExercise = mutableMapOf<String, LoggedSet>()
        val latest = mutableMapOf<String, Record>()
        for (log in logs.sortedBy { BodyLoad.startedAtMs(it, zone) }) {
            val at = BodyLoad.startedAtMs(log, zone)
            if (at > nowMs) continue
            val best = log.sets.filter {
                it.completed && it.repsEntered && it.durationSeconds == null && it.reps > 0 &&
                    it.weightKg?.let { kg -> kg.isFinite() && kg > 0 } == true
            }.maxByOrNull { it.weightKg!! * it.reps } ?: continue
            val previous = bestByExercise[log.exerciseId]
            if (previous == null || best.weightKg!! * best.reps > previous.weightKg!! * previous.reps) {
                bestByExercise[log.exerciseId] = best
                if (previous != null) latest[log.exerciseId] = Record(log.exerciseId, at, log.epochDay, best, previous)
            }
        }
        return latest.values.sortedByDescending { it.atMs }.take(3)
    }
}
