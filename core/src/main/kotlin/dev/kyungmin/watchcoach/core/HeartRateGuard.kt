package dev.kyungmin.watchcoach.core

/**
 * Filters the watch's optical heart-rate stream. During exercise the sensor can lock onto half of the real beat
 * (e.g. 55 instead of 110) until it is restarted. A reading that suddenly drops far below the recent level is
 * "suspect": the last stable value is kept and the sample is not accepted. If suspect readings persist for
 * [RESTART_AFTER_NS] the caller should restart the sensor (the same thing pause/resume does).
 *
 * Pure and deterministic: all times come from the caller.
 */
class HeartRateGuard {
    enum class Verdict { ACCEPTED, SUSPECT, RESTART_SENSOR }

    class Result(val verdict: Verdict, val stableBpm: Int)

    private val recent = ArrayDeque<Pair<Long, Int>>()
    private var suspectSinceNs = 0L
    private var lastRestartNs = Long.MIN_VALUE
    private var lastStable = 0
    private var lastStableNs = Long.MIN_VALUE

    fun reset() {
        recent.clear(); suspectSinceNs = 0L; lastRestartNs = Long.MIN_VALUE; lastStable = 0; lastStableNs = Long.MIN_VALUE
    }

    fun offer(timestampNs: Long, bpm: Int): Result {
        if (bpm !in MIN_BPM..MAX_BPM) return Result(Verdict.SUSPECT, lastStable)
        while (recent.isNotEmpty() && timestampNs - recent.first().first > WINDOW_NS) recent.removeFirst()
        // The recent window, or the last stable value for a while after it ran dry (a long suspect run must stay suspect).
        val baseline = median(recent.map { it.second })
            ?: lastStable.takeIf { it > 0 && lastStableNs != Long.MIN_VALUE && timestampNs - lastStableNs <= MEMORY_NS }
        val suspect = baseline != null && baseline >= BASELINE_FLOOR && bpm < baseline * DROP_RATIO
        if (!suspect) {
            suspectSinceNs = 0L
            recent.addLast(timestampNs to bpm)
            lastStable = bpm; lastStableNs = timestampNs
            return Result(Verdict.ACCEPTED, bpm)
        }
        if (suspectSinceNs == 0L) suspectSinceNs = timestampNs
        val persisted = timestampNs - suspectSinceNs >= RESTART_AFTER_NS
        val restartAllowed = lastRestartNs == Long.MIN_VALUE || timestampNs - lastRestartNs >= RESTART_COOLDOWN_NS
        if (persisted && restartAllowed) {
            lastRestartNs = timestampNs
            suspectSinceNs = 0L
            return Result(Verdict.RESTART_SENSOR, lastStable)
        }
        return Result(Verdict.SUSPECT, lastStable)
    }

    companion object {
        const val MIN_BPM = 20
        const val MAX_BPM = 240
        const val WINDOW_NS = 15_000_000_000L
        const val MEMORY_NS = 90_000_000_000L
        const val RESTART_AFTER_NS = 8_000_000_000L
        const val RESTART_COOLDOWN_NS = 30_000_000_000L
        const val DROP_RATIO = 0.65
        const val BASELINE_FLOOR = 90

        internal fun median(values: List<Int>): Int? {
            if (values.isEmpty()) return null
            val s = values.sorted()
            return if (s.size % 2 == 1) s[s.size / 2] else (s[s.size / 2 - 1] + s[s.size / 2]) / 2
        }
    }
}

/**
 * Decides which heart rate the watch face shows. The face does not need a new number every second: during a set it
 * refreshes every [workingIntervalMs], otherwise every [otherIntervalMs], showing the median of what arrived since the
 * last refresh. The first value is shown at once.
 */
class HeartDisplayGate(
    private val workingIntervalMs: Long = 10_000L,
    private val otherIntervalMs: Long = 5_000L,
) {
    private val pending = ArrayList<Int>()
    private var shown = 0
    private var lastRefreshMs = Long.MIN_VALUE

    fun reset() { pending.clear(); shown = 0; lastRefreshMs = Long.MIN_VALUE }

    /** Feeds a live reading (0 = none) and returns the number the face should show now. */
    fun offer(nowMs: Long, bpm: Int, working: Boolean): Int {
        if (bpm <= 0) { pending.clear(); shown = 0; lastRefreshMs = Long.MIN_VALUE; return 0 }
        pending.add(bpm)
        val interval = if (working) workingIntervalMs else otherIntervalMs
        if (shown == 0 || lastRefreshMs == Long.MIN_VALUE || nowMs - lastRefreshMs >= interval) {
            shown = HeartRateGuard.median(pending) ?: bpm
            pending.clear()
            lastRefreshMs = nowMs
        }
        return shown
    }
}
