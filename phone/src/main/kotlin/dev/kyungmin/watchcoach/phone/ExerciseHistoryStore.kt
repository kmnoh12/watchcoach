package dev.kyungmin.watchcoach.phone

import android.content.Context
import dev.kyungmin.watchcoach.core.ExerciseHistory
import dev.kyungmin.watchcoach.core.ExerciseHistoryCodec
import dev.kyungmin.watchcoach.core.ExerciseLog
import dev.kyungmin.watchcoach.core.ProgressionDefaults

/** Keeps what was actually done per exercise, on this phone only. */
class ExerciseHistoryStore(context: Context) {
    private val prefs = context.getSharedPreferences("exercise-history", Context.MODE_PRIVATE)

    fun load(): ExerciseHistory = synchronized(lock) {
        runCatching { ExerciseHistory(ExerciseHistoryCodec.decode(prefs.getString(KEY, "").orEmpty())) }
            .map { if (prefs.getBoolean(UNIFIED_5KG, false)) it else unifyOnce(it) }
            .getOrDefault(ExerciseHistory())
    }

    /** One-time: machine/cable weights typed from pound stacks move to the nearest 5 kg number. */
    private fun unifyOnce(history: ExerciseHistory): ExerciseHistory {
        val equipmentById = WorkoutData.catalog.associate { it.id to it.equipment }
        val updated = ExerciseHistory(history.all.map { log ->
            val equipment = log.equipment.ifEmpty { equipmentById[log.exerciseId].orEmpty() }
            log.copy(sets = log.sets.map { set ->
                set.copy(weightKg = set.weightKg?.let { ProgressionDefaults.unifiedRecordWeight(it, equipment) })
            })
        })
        check(prefs.edit().putString(KEY, ExerciseHistoryCodec.encode(updated.all)).putBoolean(UNIFIED_5KG, true).commit()) {
            "Failed to save exercise history"
        }
        return updated
    }

    private val carryOver = CarryOverStore(context)

    /** What next-time targets and "last time" read: everything except sessions the user chose not to carry over. */
    fun loadForCarry(): ExerciseHistory {
        val all = load()
        val skipped = carryOver.excluded()
        return if (skipped.isEmpty()) all else ExerciseHistory(all.all.filterNot { it.sessionId in skipped })
    }

    fun add(log: ExerciseLog): ExerciseHistory = synchronized(lock) {
        val updated = load().with(log)
        check(prefs.edit().putString(KEY, ExerciseHistoryCodec.encode(updated.all)).commit()) { "Failed to save exercise history" }
        updated
    }

    /** Removes the logs one finished session contributed, so comparisons and records forget it. */
    fun removeSession(sessionId: String): ExerciseHistory = synchronized(lock) {
        val updated = ExerciseHistory(load().all.filterNot { it.sessionId == sessionId })
        check(prefs.edit().putString(KEY, ExerciseHistoryCodec.encode(updated.all)).commit()) { "Failed to save exercise history" }
        updated
    }

    private companion object {
        val lock = Any()
        const val KEY = "logs"
        const val UNIFIED_5KG = "unified-5kg-v1"
    }
}
