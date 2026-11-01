package dev.kyungmin.kcoach.core

/** Active-time clock shared by manual sets and the unobserved arm. Phone alone claims completion. */
object SetClock {
    const val MAX_LIMIT_MS = 300_000L
    fun isManual(set: PlannedSetSnapshot) = set.setType != "WARMUP" && set.unilateral == null &&
        ExerciseTrackingProfiles.resolve(set.exerciseId, set.exerciseName).mode == TrackingMode.MANUAL_REQUIRED

    fun elapsed(snapshot: WorkoutSnapshot, set: PlannedSetSnapshot, nowMs: Long): Long =
        ((if (snapshot.paused) snapshot.pausedSinceMs else nowMs) - set.workingStartedAtMs -
            (snapshot.totalPausedMs - set.workingPausedAtStartMs).coerceAtLeast(0)).coerceAtLeast(0)

    fun defaultLimitMs(targetReps: Int): Long = ((targetReps.takeIf { it > 0 } ?: 10).toLong() * 3_000L + 5_000L)
        .coerceIn(20_000L, 90_000L)

    fun prepare(snapshot: WorkoutSnapshot, old: WorkoutSnapshot?, nowMs: Long, enabled: Boolean,
        history: ExerciseHistory = ExerciseHistory()): WorkoutSnapshot {
        val targetIndex = snapshot.plannedSets.indexOf(WorkoutSessionReducer.nextPendingSet(snapshot))
        // UI plans omit clock metadata. Merge by attempt before deriving the preceding duration.
        val merged = snapshot.plannedSets.map { candidate ->
            val previous = old?.plannedSets?.singleOrNull { it.setId == candidate.setId && it.attemptId == candidate.attemptId &&
                it.exerciseId == candidate.exerciseId && (candidate.setId.isNotBlank() || it.setIndex == candidate.setIndex) }
            if (previous != null && candidate.workingStartedAtMs == 0L) candidate.copy(
                workingStartedAtMs = previous.workingStartedAtMs, workingPausedAtStartMs = previous.workingPausedAtStartMs,
                completedDurationMs = previous.completedDurationMs, setTimerLimitMs = previous.setTimerLimitMs,
                setTimerAdjustmentMs = previous.setTimerAdjustmentMs) else candidate
        }
        val sets = merged.mapIndexed { index, candidate ->
            var set = candidate
            if ((isManual(set) || set.unilateral != null) && index == targetIndex && snapshot.phase == WorkoutPhase.WORKING && !snapshot.paused) {
                if (set.workingStartedAtMs == 0L) set = set.copy(workingStartedAtMs = nowMs,
                    workingPausedAtStartMs = snapshot.totalPausedMs, completedDurationMs = null, setTimerAdjustmentMs = 0)
                if (enabled && isManual(set) && set.setTimerLimitMs == null) {
                    val prior = merged.filter { it.exerciseIndex == set.exerciseIndex && it.exerciseId == set.exerciseId &&
                        it.setIndex < set.setIndex && it.completed && it.setType != "WARMUP" }.maxByOrNull { it.setIndex }
                    val previousSessionDuration = if (prior == null) history.recent(set.exerciseId, Int.MAX_VALUE)
                        .firstOrNull { it.sessionId != snapshot.sessionId }
                        ?.sets?.firstOrNull { !it.isWarmup }?.takeIf { it.completed }?.completedDurationMs else null
                    val duration = prior?.completedDurationMs ?: previousSessionDuration
                    set = set.copy(setTimerLimitMs = duration?.let { (it + 10_000L).coerceAtMost(MAX_LIMIT_MS) }
                        ?: defaultLimitMs(set.targetReps))
                }
            }
            if (!enabled && isManual(set)) set = set.copy(setTimerLimitMs = null)
            set
        }
        return snapshot.copy(plannedSets = sets)
    }

    fun remainingMs(snapshot: WorkoutSnapshot, nowMs: Long, enabled: Boolean = true): Long? {
        if (snapshot.phase != WorkoutPhase.WORKING && !snapshot.paused) return null
        val set = WorkoutSessionReducer.nextPendingSet(snapshot) ?: return null
        val side = set.unilateral
        if (side?.stage == UnilateralStage.OTHER_SIDE_WORKING) {
            val limit = side.firstSideDurationMs?.plus(15_000L) ?: return null
            val start = side.otherStartedAtMs ?: return null
            val active = ((if (snapshot.paused) snapshot.pausedSinceMs else nowMs) - start -
                (snapshot.totalPausedMs - side.pausedAtOtherStartMs).coerceAtLeast(0)).coerceAtLeast(0)
            return (limit + set.setTimerAdjustmentMs - active).coerceAtLeast(0)
        }
        if (!enabled || !isManual(set) || set.workingStartedAtMs == 0L) return null
        return ((set.setTimerLimitMs ?: return null) + set.setTimerAdjustmentMs - elapsed(snapshot, set, nowMs)).coerceAtLeast(0)
    }

    fun adjust(snapshot: WorkoutSnapshot, deltaSeconds: Int, nowMs: Long, enabled: Boolean = true): WorkoutSnapshot? {
        val remaining = remainingMs(snapshot, nowMs, enabled) ?: return null
        if (deltaSeconds !in setOf(-10, 10)) return null
        val target = WorkoutSessionReducer.nextPendingSet(snapshot) ?: return null
        val applied = (remaining + deltaSeconds * 1000L).coerceIn(0, MAX_LIMIT_MS) - remaining
        return snapshot.copy(plannedSets = snapshot.plannedSets.map {
            if (it === target) it.copy(setTimerAdjustmentMs = it.setTimerAdjustmentMs + applied) else it
        })
    }

    fun autoComplete(snapshot: WorkoutSnapshot, nowMs: Long, enabled: Boolean): WorkoutSnapshot? {
        if (snapshot.paused || snapshot.phase != WorkoutPhase.WORKING || remainingMs(snapshot, nowMs, enabled) != 0L) return null
        val set = WorkoutSessionReducer.nextPendingSet(snapshot) ?: return null
        if (set.unilateral != null) return UnilateralSetReducer.autoComplete(snapshot, nowMs)
        val result = WorkoutSessionReducer.completeSet(snapshot, SetCompletionEvent(snapshot.sessionId, set.exerciseId, set.setIndex,
            set.targetReps, nowMs + set.restSeconds * 1000L, 0, SetRepSource.ESTIMATED, set.setId, set.attemptId, completedAtMs = nowMs))
        return (result as? SetCompletionResult.Applied)?.snapshot
    }
}
