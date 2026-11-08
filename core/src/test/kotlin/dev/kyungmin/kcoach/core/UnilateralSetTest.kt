package dev.kyungmin.kcoach.core

import kotlin.test.*

class UnilateralSetTest {
    private fun initial(id: String = "one_arm_dumbbell_row") = WorkoutSnapshot(sessionId = "s", routineId = "r",
        exerciseIndex = 0, setIndex = 0, plannedSets = listOf(
            PlannedSetSnapshot(0, id, 0, 10, 20.0, false, restSeconds = 60, setId = "set", attemptId = "a", identityRequired = true),
            PlannedSetSnapshot(0, id, 1, 10, 20.0, false, setId = "next", attemptId = "b", identityRequired = true)),
        performedReps = emptyMap(), phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0,
        paused = false, startedAtMs = 1, pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0,
        lastCompletedSetKey = null, captureStates = emptyMap())
    private fun first(s: WorkoutSnapshot = initial(), source: SetRepSource = SetRepSource.WATCH) =
        assertIs<SetCompletionResult.Applied>(WorkoutSessionReducer.completeSet(s,
            SetCompletionEvent("s", s.plannedSets.first().exerciseId, 0, 12, 61_000, 1, source, "set", "a"))).snapshot
    private fun action(s: WorkoutSnapshot, action: UnilateralAction, count: Int? = null) =
        UnilateralSetReducer.apply(s, "s", "set", "a", action, 5_000, count)

    @Test fun `automatic and manual first completion hold rest without advancing or crediting full set`() {
        for (source in listOf(SetRepSource.WATCH, SetRepSource.MANUAL)) {
            val s = first(source = source)
            assertEquals(UnilateralStage.AWAITING_OTHER_SIDE, s.plannedSets[0].unilateral?.stage)
            assertEquals(source, s.plannedSets[0].unilateral?.watchRepSource)
            assertFalse(s.plannedSets[0].completed)
            assertEquals(0, s.setIndex); assertEquals(0, s.restEndAtMs); assertTrue(s.performedReps.isEmpty())
            assertNull(WorkoutSessionReducer.advanceAfterRest(s, 100_000))
            assertEquals(s, WorkoutSnapshotCodec.decode(WorkoutSnapshotCodec.encode(s)))
        }
    }
    @Test fun `both arms require explicit start and explicit completion then start exactly one rest`() {
        val first = first()
        assertIs<SetCompletionResult.Rejected>(action(first, UnilateralAction.COMPLETE_OTHER_SIDE))
        val other = assertIs<SetCompletionResult.Applied>(action(first, UnilateralAction.START_OTHER_SIDE)).snapshot
        assertEquals(0, other.restEndAtMs)
        assertIs<SetCompletionResult.Duplicate>(WorkoutSessionReducer.completeSet(other,
            SetCompletionEvent("s", "one_arm_dumbbell_row", 0, 12, 90_000, 2, SetRepSource.WATCH, "set", "a")))
        val done = assertIs<SetCompletionResult.Applied>(action(other, UnilateralAction.COMPLETE_OTHER_SIDE, 9)).snapshot
        assertTrue(done.plannedSets[0].completed)
        assertEquals(9, done.plannedSets[0].unilateral?.otherReps)
        assertEquals(12, done.plannedSets[0].performedReps)
        assertEquals(UnilateralStage.BOTH_COMPLETE, done.plannedSets[0].unilateral?.stage)
        assertEquals(65_000, done.restEndAtMs); assertEquals(1, done.setIndex)
        assertIs<SetCompletionResult.Duplicate>(action(done, UnilateralAction.COMPLETE_OTHER_SIDE))
        assertEquals(done, WorkoutSnapshotCodec.decode(WorkoutSnapshotCodec.encode(done)))
    }
    @Test fun `watch arm only finalizes without inventing opposite reps`() {
        val done = assertIs<SetCompletionResult.Applied>(action(first(), UnilateralAction.FINISH_WATCH_SIDE_ONLY)).snapshot
        assertEquals(UnilateralStage.WATCH_SIDE_ONLY, done.plannedSets[0].unilateral?.stage)
        assertNull(done.plannedSets[0].unilateral?.otherReps)
        assertEquals(WorkoutPhase.RESTING, done.phase)
    }
    @Test fun `stale identity paused set wrong order and invalid count cannot mutate progress`() {
        assertIs<SetCompletionResult.Rejected>(action(initial(), UnilateralAction.START_OTHER_SIDE))
        assertIs<SetCompletionResult.Rejected>(action(first().copy(paused = true), UnilateralAction.START_OTHER_SIDE))
        assertIs<SetCompletionResult.Rejected>(UnilateralSetReducer.apply(first(), "s", "set", "old", UnilateralAction.START_OTHER_SIDE, 1))
        assertIs<SetCompletionResult.Rejected>(action(first(), UnilateralAction.START_OTHER_SIDE, -1))
    }
    @Test fun `bilateral completion keeps existing automatic rest behavior`() {
        val s = first(initial("cable_seated_row"))
        assertNull(s.plannedSets[0].unilateral)
        assertTrue(s.plannedSets[0].completed); assertEquals(WorkoutPhase.RESTING, s.phase)
    }
    @Test fun `late analysis updates first arm without creating opposite arm evidence`() {
        val s = WorkoutSessionReducer.confirmReps(first(), "one_arm_dumbbell_row", 0, 11, "set", "a")
        assertEquals(11, s.plannedSets[0].unilateral?.watchReps)
        assertNull(s.plannedSets[0].performedReps); assertTrue(s.performedReps.isEmpty())
        val manual = first(source = SetRepSource.MANUAL)
        assertEquals(manual, WorkoutSessionReducer.confirmReps(manual, "one_arm_dumbbell_row", 0, 8, "set", "a"))
    }

    @Test fun `global both sides policy enters manual other arm and explicit skip preserves unknown reps`() {
        for (source in listOf(SetRepSource.WATCH, SetRepSource.MANUAL)) {
            val other = assertIs<SetCompletionResult.Applied>(WorkoutSessionReducer.completeSet(initial(),
                SetCompletionEvent("s", "one_arm_dumbbell_row", 0, 12, 61_000, 1, source, "set", "a"),
                UnilateralFirstSidePolicy.BOTH_SIDES)).snapshot
            assertEquals(UnilateralStage.OTHER_SIDE_WORKING, other.plannedSets.first().unilateral?.stage)
            assertEquals(0L, other.restEndAtMs)
            assertFalse(other.plannedSets.first().completed)
            assertIs<SetCompletionResult.Duplicate>(WorkoutSessionReducer.completeSet(other,
                SetCompletionEvent("s", "one_arm_dumbbell_row", 0, 12, 99_000, 2, source, "set", "a"),
                UnilateralFirstSidePolicy.WATCH_SIDE_ONLY))
            val done = assertIs<SetCompletionResult.Applied>(action(other, UnilateralAction.FINISH_WATCH_SIDE_ONLY)).snapshot
            assertEquals(UnilateralStage.WATCH_SIDE_ONLY, done.plannedSets.first().unilateral?.stage)
            assertEquals(12, done.plannedSets.first().performedReps)
            assertNull(done.plannedSets.first().unilateral?.otherReps)
            assertEquals(65_000L, done.restEndAtMs)
        }
    }

    @Test fun `global watch side only policy starts rest at first completion for either source`() {
        for (source in listOf(SetRepSource.WATCH, SetRepSource.MANUAL)) {
            val done = assertIs<SetCompletionResult.Applied>(WorkoutSessionReducer.completeSet(initial(),
                SetCompletionEvent("s", "one_arm_dumbbell_row", 0, 12, 61_000, 1, source, "set", "a"),
                UnilateralFirstSidePolicy.WATCH_SIDE_ONLY)).snapshot
            assertEquals(UnilateralStage.WATCH_SIDE_ONLY, done.plannedSets.first().unilateral?.stage)
            assertTrue(done.plannedSets.first().completed)
            assertNull(done.plannedSets.first().unilateral?.otherReps)
            assertEquals(12, done.plannedSets.first().performedReps)
            assertEquals(61_000L, done.restEndAtMs)
            assertEquals(source, done.plannedSets.first().repSource)
        }
    }

    private fun timed(duration: Long? = 30_000, policy: UnilateralFirstSidePolicy = UnilateralFirstSidePolicy.BOTH_SIDES) =
        assertIs<SetCompletionResult.Applied>(WorkoutSessionReducer.completeSet(initial(),
            SetCompletionEvent("s", "one_arm_dumbbell_row", 0, 12, 61_000, 1, SetRepSource.WATCH, "set", "a",
                firstSideDurationMs = duration, completedAtMs = 1_000), policy)).snapshot

    @Test fun `other side times out at first active duration plus fifteen seconds exactly once`() {
        val s = timed()
        assertNull(UnilateralSetReducer.autoComplete(s, 45_999))
        val done = assertNotNull(UnilateralSetReducer.autoComplete(s, 46_000))
        assertEquals(106_000, done.restEndAtMs)
        val side = done.plannedSets.first().unilateral!!
        assertEquals(12, side.otherReps)
        assertEquals(SetRepSource.MANUAL, side.otherRepSource)
        assertEquals(SetRepSource.WATCH, side.watchRepSource)
        assertNull(UnilateralSetReducer.autoComplete(done, 100_000))
        assertEquals(done, WorkoutSnapshotCodec.decode(WorkoutSnapshotCodec.encode(done)))
        assertEquals(9, side.confirmOther(9).otherReps)
        assertEquals(SetRepSource.MANUAL, side.confirmOther(9).otherRepSource)
        assertEquals(SetRepSource.MANUAL, side.confirmOther(9).otherRepSource)
        assertEquals(12, side.confirmOther(9).watchReps)
    }
    @Test fun `manual opposite completion and skip both cancel timeout`() {
        for (action in listOf(UnilateralAction.COMPLETE_OTHER_SIDE, UnilateralAction.FINISH_WATCH_SIDE_ONLY)) {
            val done = assertIs<SetCompletionResult.Applied>(action(timed(), action,
                if (action == UnilateralAction.COMPLETE_OTHER_SIDE) 8 else null)).snapshot
            assertNull(UnilateralSetReducer.autoComplete(done, 90_000))
            assertNull(done.plannedSets.first().unilateral!!.otherStartedAtMs)
            if (action == UnilateralAction.COMPLETE_OTHER_SIDE) {
                assertEquals(8, done.plannedSets.first().unilateral!!.otherReps)
                assertEquals(SetRepSource.MANUAL, done.plannedSets.first().unilateral!!.otherRepSource)
            }
        }
    }
    @Test fun `persisted active clock excludes pauses and legacy unknown duration waits`() {
        val s = timed()
        assertNull(UnilateralSetReducer.autoComplete(s.copy(paused = true, phase = WorkoutPhase.PAUSED), 100_000))
        val resumed = s.copy(totalPausedMs = 20_000)
        val restored = WorkoutSnapshotCodec.decode(WorkoutSnapshotCodec.encode(resumed))
        assertNull(UnilateralSetReducer.autoComplete(restored, 65_999))
        assertNotNull(UnilateralSetReducer.autoComplete(restored, 66_000))
        assertNull(UnilateralSetReducer.autoComplete(timed(null), 999_999))
        val legacy = UnilateralProgress.decode("OTHER_SIDE_WORKING,12,WATCH,")!!
        assertNull(legacy.firstSideDurationMs)
        assertNull(legacy.otherRepSource)
        assertNull(UnilateralSetReducer.autoComplete(timed(policy = UnilateralFirstSidePolicy.WATCH_SIDE_ONLY), 999_999))
    }

    @Test fun `legacy opposite estimates lose label without rewriting corrected counts`() {
        for (encoded in listOf("BOTH_COMPLETE,12,WATCH,9,ESTIMATED,30000,,0", "BOTH_COMPLETE,12,WATCH,9")) {
            val old = UnilateralProgress.decode(encoded)!!
            assertEquals(12, old.watchReps)
            assertEquals(9, old.otherReps)
            assertEquals(SetRepSource.MANUAL, old.otherRepSource)
            assertEquals(old, UnilateralProgress.decode(old.encode()))
        }
    }
    @Test fun `late watch analysis keeps matched opposite reps together but preserves manual differences`() {
        val done = UnilateralSetReducer.autoComplete(timed(), 46_000)!!
        val corrected = WorkoutSessionReducer.confirmReps(done, "one_arm_dumbbell_row", 0, 11, "set", "a")
        assertEquals(11, corrected.plannedSets.first().performedReps)
        assertEquals(11, corrected.plannedSets.first().unilateral!!.otherReps)
        val edited = done.copy(plannedSets = done.plannedSets.mapIndexed { i, set ->
            if (i == 0) set.copy(unilateral = set.unilateral!!.confirmOther(9)) else set
        })
        val preserved = WorkoutSessionReducer.confirmReps(edited, "one_arm_dumbbell_row", 0, 11, "set", "a")
        assertEquals(11, preserved.plannedSets.first().unilateral!!.watchReps)
        assertEquals(9, preserved.plannedSets.first().unilateral!!.otherReps)
    }

}
