package dev.kyungmin.watchcoach.phone

import android.content.Context

/**
 * Sessions the user chose NOT to carry into the next routine day (the "루틴 저장" switch on the fresh result screen).
 * Their logs stay in records and stats; only next-time targets and "last time" ignore them.
 */
class CarryOverStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("carry-over", Context.MODE_PRIVATE)

    fun excluded(): Set<String> = synchronized(lock) { prefs.getStringSet(KEY, emptySet()).orEmpty().toSet() }

    fun carries(sessionId: String): Boolean = sessionId !in excluded()

    /** Returns false when the choice could not be saved, so the caller can undo the switch. */
    fun setCarry(sessionId: String, carry: Boolean): Boolean = synchronized(lock) {
        val updated = excluded().toMutableSet().apply { if (carry) remove(sessionId) else add(sessionId) }
        prefs.edit().putStringSet(KEY, updated).commit()
    }

    private companion object {
        val lock = Any()
        const val KEY = "excluded-sessions"
    }
}
