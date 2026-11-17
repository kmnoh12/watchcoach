package dev.kyungmin.watchcoach.core

import kotlin.math.max
import kotlin.math.roundToLong

/**
 * Haptic cue delay for vertical presses and return-counted rows. The counting event closes while the descent is still ~35%
 * from the bottom (or, on acceleration-locked return-counted rows, at pull deceleration), so the cue is held back using
 * the observed phase timing. Counting is not affected.
 */
object RepCueDelay {
    const val FRACTION = 0.40
    const val MIN_MS = 150L
    const val MAX_MS = 600L
    private const val MAX_TURN_TO_EVENT_MS = 5_000.0

    const val ROW_RETURN_FRACTION = 0.85
    const val ROW_SMOOTHING_LAG_NS = 160_000_000L
    const val MIN_ROW_RETURN_NS = 400_000_000L
    const val MAX_ROW_RETURN_NS = 4_000_000_000L

    fun delayMs(turnaroundNs: Long, eventEndNs: Long): Long {
        val sinceTopMs = (eventEndNs - turnaroundNs) / 1e6
        if (!sinceTopMs.isFinite() || sinceTopMs <= 0.0 || sinceTopMs > MAX_TURN_TO_EVENT_MS) return 0L
        return (FRACTION * sinceTopMs).toLong().coerceIn(MIN_MS, MAX_MS)
    }

    fun rowReturnDelayMs(peakNs: Long, emittedAtNs: Long, learnedReturnNs: Long): Long {
        if (learnedReturnNs <= MIN_ROW_RETURN_NS || learnedReturnNs >= MAX_ROW_RETURN_NS || emittedAtNs < peakNs) return 0L
        val targetCueNs = peakNs - ROW_SMOOTHING_LAG_NS + (ROW_RETURN_FRACTION * learnedReturnNs).roundToLong()
        return max(0L, ((targetCueNs - emittedAtNs) / 1e6).roundToLong())
    }
}
