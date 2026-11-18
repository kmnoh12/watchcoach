package dev.kyungmin.watchcoach.phone

import android.content.Context
import dev.kyungmin.watchcoach.core.ExerciseHistory
import dev.kyungmin.watchcoach.core.ExerciseHistoryCodec
import dev.kyungmin.watchcoach.core.ExerciseLog

/** Keeps what was actually done per exercise, on this phone only. */
class ExerciseHistoryStore(context: Context) {
    private val prefs = context.getSharedPreferences("exercise-history", Context.MODE_PRIVATE)

    fun load(): ExerciseHistory = synchronized(lock) {
        runCatching { ExerciseHistory(ExerciseHistoryCodec.decode(prefs.getString(KEY, "").orEmpty())) }
            .getOrDefault(ExerciseHistory())
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
    }
}
