package dev.kyungmin.kcoach.wear

/**
 * The service passes through its preparation phases on the way from a set to rest and from rest to the next set.
 * Drawing them as they arrive flashes the 준비 screen for an instant, so the workout screen stays up until the
 * step has lasted [HOLD_MS]; one that is still there by then is a real wait and is shown.
 */
internal class PreparationFlashGuard {
    private var workoutShown = false
    private var preparingSinceMs = -1L

    /** How much longer the screen already shown should stay; 0 means draw the current state now. */
    fun holdMs(preparing: Boolean, workoutScreen: Boolean, nowMs: Long): Long {
        if (!preparing) {
            workoutShown = workoutScreen
            preparingSinceMs = -1L
            return 0L
        }
        if (!workoutShown) return 0L
        if (preparingSinceMs < 0L) preparingSinceMs = nowMs
        val left = preparingSinceMs + HOLD_MS - nowMs
        if (left <= 0L) workoutShown = false
        return left.coerceAtLeast(0L)
    }

    companion object {
        const val HOLD_MS = 400L
        val PHASES = setOf("READY", "POSITIONING", "PREPARING")
    }
}
