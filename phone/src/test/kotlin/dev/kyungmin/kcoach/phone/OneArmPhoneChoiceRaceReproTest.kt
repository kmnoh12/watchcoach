package dev.kyungmin.kcoach.phone

import dev.kyungmin.kcoach.core.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.Robolectric
import org.robolectric.shadows.ShadowToast
import dev.kyungmin.kcoach.phone.ui.OverlayState
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class OneArmPhoneChoiceRaceReproTest {
    private fun field(activity: MainActivity, name: String): Any? = MainActivity::class.java
        .getDeclaredField(name).apply { isAccessible = true }.get(activity)
    private fun choose(activity: MainActivity) = MainActivity::class.java.getDeclaredMethod("chooseOtherSide",
        String::class.java, String::class.java, String::class.java, String::class.java)
        .apply { isAccessible = true }.invoke(activity, "s", "set", "a", "start")
    private fun ask(activity: MainActivity, snapshot: WorkoutSnapshot) = MainActivity::class.java
        .getDeclaredMethod("askOtherSide", WorkoutSnapshot::class.java).apply { isAccessible = true }.invoke(activity, snapshot)

    private fun completedFirstArm(legacy: Boolean = false, manual: Boolean = false, oneArmOnly: Boolean = false): Pair<SessionStore, PhoneSessionController> {
        assertTrue(OneArmSetting.setEnabled(RuntimeEnvironment.getApplication(), oneArmOnly))
        val store = SessionStore(RuntimeEnvironment.getApplication())
        val initial = WorkoutSnapshot(sessionId = "s", routineId = "r", exerciseIndex = 0, setIndex = 0,
            plannedSets = listOf(PlannedSetSnapshot(0, "single_arm_cable_reverse_fly", 0, 12, 5.0, false,
                restSeconds = 60, setId = "set", attemptId = "a", identityRequired = true)),
            performedReps = emptyMap(), phase = WorkoutPhase.WORKING, restEndAtMs = 0, pausedRestRemainingMs = 0,
            paused = false, startedAtMs = 1, pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0,
            lastCompletedSetKey = null, captureStates = emptyMap())
        assertTrue(store.saveActive(initial))
        val sent = mutableListOf<Pair<String, String>>()
        val controller = PhoneSessionController(store) { path, payload -> sent += path to payload }
        val completion = WearSync.liveState("s", "single_arm_cable_reverse_fly", "원암 케이블 리버스 플라이",
            0, 12, 12, 5.0, 80, "SET_COMPLETE", false, completionId = "completion", setId = "set", attemptId = "a")
        if (manual) {
            val result = store.applyManualSet(ManualSetCommand("manual", "s", "single_arm_cable_reverse_fly", 0,
                "set", "a", 12, 0, ManualSetOperation.COMPLETE), 1_000).getOrThrow()
            assertEquals(oneArmOnly, result.restStarted)
        } else controller.receiveCompletion(completion, 1_000).getOrThrow()
        val questionSnapshot = store.loadActive().getOrThrow()!!
        assertEquals(if (oneArmOnly) UnilateralStage.WATCH_SIDE_ONLY else UnilateralStage.OTHER_SIDE_WORKING,
            questionSnapshot.plannedSets.single().unilateral!!.stage)
        assertEquals(if (oneArmOnly) 61_000L else 0L, questionSnapshot.restEndAtMs)
        if (legacy) {
            // A snapshot persisted by the old app may still be waiting for its explicit side choice.
            assertTrue(store.saveActive(questionSnapshot.copy(plannedSets = questionSnapshot.plannedSets.map {
                it.copy(unilateral = it.unilateral!!.copy(stage = UnilateralStage.AWAITING_OTHER_SIDE))
            })))
        }
        return store to controller
    }

    @Test fun automaticOtherSideHasNoQuestionAndReplayDoesNotStartRest() {
        val (store, controller) = completedFirstArm()
        controller.receiveCompletion(WearSync.liveState("s", "single_arm_cable_reverse_fly", "원암 케이블 리버스 플라이",
            0, 12, 12, 5.0, 80, "SET_COMPLETE", false, completionId = "completion", setId = "set", attemptId = "a"), 4_100).getOrThrow()
        controller.resync().getOrThrow()
        val activity = Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            ask(activity.get(), store.loadActive().getOrThrow()!!)
            assertNull((field(activity.get(), "overlays") as OverlayState).current)
            val selected = store.loadActive().getOrThrow()!!
            assertEquals(UnilateralStage.OTHER_SIDE_WORKING, selected.plannedSets.single().unilateral!!.stage)
            assertEquals(WorkoutPhase.WORKING, selected.phase)
            assertEquals(0L, selected.restEndAtMs)
            assertFalse(selected.plannedSets.single().completed)
        } finally { activity.pause().stop().destroy() }
    }

    @Test fun phoneOtherSideChoiceMustNotBeSilentlyLostAfterWatchQuestionTimeout() {
        val (store, _) = completedFirstArm(legacy = true)
        val activity = Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
        ask(activity.get(), store.loadActive().getOrThrow()!!)
        val overlays = field(activity.get(), "overlays") as OverlayState
        assertNotNull(overlays.current)
        val timedOut = store.applyWatchControl(WatchWorkoutControl("watch-timeout",
            WatchWorkoutAction.FINISH_WATCH_SIDE_ONLY, "s", "set", "a"), 121_000).getOrThrow()
        assertEquals(WatchWorkoutControlStatus.APPLIED, timedOut.ack.status)
        choose(activity.get()) // The actual sheet callback re-reads the snapshot and explains a stale choice.
        assertEquals("운동 상태가 바뀌었어요. 현재 상태를 확인해 주세요", ShadowToast.getTextOfLatestToast())
        assertNull(overlays.current)
        val latest = store.loadActive().getOrThrow()!!
        assertEquals(UnilateralStage.WATCH_SIDE_ONLY, latest.plannedSets.single().unilateral!!.stage)
        assertEquals(WorkoutPhase.RESTING, latest.phase)
        assertEquals(181_000L, latest.restEndAtMs)
        } finally { activity.pause().stop().destroy() }
    }

    @Test fun watchChoiceClosesPhoneSheetOnSnapshotRefresh() {
        val (store, controller) = completedFirstArm(legacy = true)
        val activity = Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            ask(activity.get(), store.loadActive().getOrThrow()!!)
            assertNotNull((field(activity.get(), "overlays") as OverlayState).current)
            controller.unilateralAction("s", "set", "a", UnilateralAction.START_OTHER_SIDE, 2_000).getOrThrow()
            MainActivity::class.java.getDeclaredMethod("refreshActiveSession").apply { isAccessible = true }.invoke(activity.get())
            assertNull((field(activity.get(), "overlays") as OverlayState).current)
            assertEquals(UnilateralStage.OTHER_SIDE_WORKING, store.loadActive().getOrThrow()!!.plannedSets.single().unilateral!!.stage)
            assertEquals(0L, store.loadActive().getOrThrow()!!.restEndAtMs)
        } finally { activity.pause().stop().destroy() }
    }

    @Test fun settingAndBothCompletionSourcesPersistTheirChosenPolicy() {
        val app = RuntimeEnvironment.getApplication()
        assertFalse(OneArmSetting.isEnabled(app))
        for (manual in listOf(false, true)) for (single in listOf(false, true)) {
            app.getSharedPreferences("workout-session", android.content.Context.MODE_PRIVATE).edit().clear().commit()
            // Clear only the session fixture between independent policy cases, using the store's actual preference name.
            val (store, _) = completedFirstArm(manual = manual, oneArmOnly = single)
            val snapshot = SessionStore(app).loadActive().getOrThrow()!!
            val set = snapshot.plannedSets.single()
            assertEquals(single, OneArmSetting.isEnabled(app))
            assertEquals(single, set.completed)
            assertNull(set.unilateral!!.otherReps)
            assertEquals(if (manual) SetRepSource.MANUAL else SetRepSource.WATCH, set.unilateral!!.watchRepSource)
            if (!single) {
                assertNull(store.advanceAfterRest(999_999).getOrThrow())
                val done = store.applyWatchControl(WatchWorkoutControl("skip", WatchWorkoutAction.FINISH_WATCH_SIDE_ONLY,
                    "s", "set", "a"), 2_000).getOrThrow()
                assertEquals(WatchWorkoutControlStatus.APPLIED, done.ack.status)
                assertEquals(UnilateralStage.WATCH_SIDE_ONLY, done.snapshot!!.plannedSets.single().unilateral!!.stage)
                assertEquals(12, done.snapshot!!.plannedSets.single().performedReps)
                assertNull(done.snapshot!!.plannedSets.single().unilateral!!.otherReps)
                assertEquals(62_000L, done.snapshot!!.restEndAtMs)
            }
            assertTrue(store.clearActive("s"))
            // Closed-session receipts must not leak into the next independent fixture.
            app.getSharedPreferences("workout-session", android.content.Context.MODE_PRIVATE).edit().clear().commit()
        }
    }

    @Test fun phoneSkipButtonFinishesOnlyTheWatchArmAndHalfCheckPersistsUntilThen() {
        val (store, _) = completedFirstArm()
        val activity = Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            MainActivity::class.java.getDeclaredMethod("refreshActiveSession").apply { isAccessible = true }.invoke(activity.get())
            val workout = field(activity.get(), "activeWorkout")!!
            val model = MainActivity::class.java.declaredMethods.single { it.name == "buildWorkoutModel" }
                .apply { isAccessible = true }.invoke(activity.get(), workout) as dev.kyungmin.kcoach.phone.ui.WorkoutUiModel
            assertTrue(model.exercises.single().sets.single().halfDone)
            assertTrue(model.exercises.single().sets.single().otherSideWorking)
            (field(activity.get(), "workoutActions") as dev.kyungmin.kcoach.phone.ui.WorkoutActions).onFinishWatchSideOnly(0, 0)
            val done = store.loadActive().getOrThrow()!!
            assertEquals(UnilateralStage.WATCH_SIDE_ONLY, done.plannedSets.single().unilateral!!.stage)
            assertNull(done.plannedSets.single().unilateral!!.otherReps)
            assertEquals(WorkoutPhase.RESTING, done.phase)
        } finally { activity.pause().stop().destroy() }
    }
}
