package dev.kyungmin.kcoach.phone

import dev.kyungmin.kcoach.core.*
import java.time.LocalDate

/** Routine targets are not completed workout history. */
internal data class ExerciseRecordOverview(val records: List<Pair<String, String>>, val stats: List<Pair<String, String>>) {
    companion object {
        fun from(history: ExerciseHistory, exerciseId: String, hold: Boolean): ExerciseRecordOverview {
            val rows = history.all.filter { it.exerciseId == exerciseId }
                .map { it to it.sets.filter { s -> s.completed && (if (hold) s.durationSeconds != null else s.repsEntered && s.durationSeconds == null) } }
                .filter { it.second.isNotEmpty() }
                .sortedWith(compareByDescending<Pair<ExerciseLog, List<LoggedSet>>> { it.first.epochDay }.thenByDescending { it.first.startedAtMs })
            val sets = rows.flatMap { it.second }
            fun result(set: LoggedSet) = set.weightKg?.let { it.toString().removeSuffix(".0") + "kg × " }.orEmpty() +
                (if (hold) HoldExercise.time(requireNotNull(set.durationSeconds)) else "${set.reps}회") + (if (set.isWarmup) " · 웜업" else "")
            return ExerciseRecordOverview(
                rows.take(3).map { (log, done) -> LocalDate.ofEpochDay(log.epochDay).toString() to
                    (done.take(5).joinToString("\n", transform = ::result) + if (done.size > 5) "\n외 ${done.size - 5}세트" else "") }
                    .ifEmpty { listOf("아직 완료한 기록 없음" to "운동을 마치면 수행 기록이 여기에 쌓입니다.") },
                listOf("${rows.map { it.first.epochDay }.distinct().size}일" to "운동한 날", "${sets.size}세트" to "완료 세트",
                    (if (hold) HoldExercise.time(sets.sumOf { it.durationSeconds ?: 0 }) else "${sets.sumOf { it.reps }}회") to (if (hold) "누적 시간" else "수행 횟수"),
                    (rows.firstOrNull()?.first?.epochDay?.let { LocalDate.ofEpochDay(it).toString() } ?: "—") to "최근 운동"))
        }
    }
}
