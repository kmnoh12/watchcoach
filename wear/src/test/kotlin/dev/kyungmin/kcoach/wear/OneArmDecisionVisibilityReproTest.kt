package dev.kyungmin.kcoach.wear

import android.content.Intent
import android.os.Looper
import android.view.View
import dev.kyungmin.kcoach.core.WatchWorkoutControl
import dev.kyungmin.kcoach.core.WatchWorkoutAction
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.time.Duration

/** Regression coverage for visible, explicit side decisions and their two minute safety timeout. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "w216dp-h216dp-round-xhdpi")
class OneArmDecisionVisibilityReproTest {
    private val app get() = RuntimeEnvironment.getApplication()
    @Before fun avoidAnimationClockAdvances() {
        // Keep Handler deadlines deterministic; completion-cover and decision durations stay unchanged.
        android.provider.Settings.Global.putFloat(app.contentResolver,
            android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 0f)
    }
    private fun state(running: Boolean, phase: String) {
        app.sendBroadcast(Intent(WearWorkoutService.ACTION_STATE).setPackage(app.packageName)
            .putExtra("session", "s").putExtra("setId", "set").putExtra("attemptId", "a")
            .putExtra("exerciseId", "single_arm_cable_reverse_fly").putExtra("exerciseName", "원암 케이블 리버스 플라이")
            .putExtra("paired", true).putExtra("running", running).putExtra("resting", false).putExtra("paused", false)
            .putExtra("setIndex", 0).putExtra("reps", 12).putExtra("targetReps", 12)
            .putExtra("phase", phase))
        shadowOf(Looper.getMainLooper()).idle()
    }
    private fun field(activity: MainActivity, name: String): Any? = MainActivity::class.java
        .getDeclaredField(name).apply { isAccessible = true }.get(activity)

    @Test fun automaticFinishMustExposeSideQuestionBeforeItsDecisionClockRuns() {
        WatchWorkoutOutbox(app).receivePhoneHello(listOf("1", "phone", "0", "WORKOUT_CONTROL_V1"))
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            state(true, "WORKING")
            state(false, "READY") // Service local state after sensor completion; SET_COMPLETE is the phone payload.
            state(false, "AWAITING_OTHER_SIDE")
            val face = field(controller.get(), "face") as WatchWorkoutFace
            assertEquals("반대손", face.value.text.toString())
            assertNotNull("The decision clock has already started", field(controller.get(), "sideDecisionKey"))
            val cover = field(controller.get(), "setDoneLayer") as View
            assertEquals("The side question must be exposed while its safety clock runs", View.GONE, cover.visibility)
        } finally { controller.pause().stop().destroy() }
    }

    @Test fun sideQuestionDoesNotAutoRestAfterThreeSeconds() {
        WatchWorkoutOutbox(app).receivePhoneHello(listOf("1", "phone", "0", "WORKOUT_CONTROL_V1"))
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            state(true, "WORKING")
            state(false, "READY")
            state(false, "AWAITING_OTHER_SIDE")
            assertEquals(View.GONE, (field(controller.get(), "setDoneLayer") as View).visibility)
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(3_000))
            assertEquals("The question stays exposed", View.GONE,
                (field(controller.get(), "setDoneLayer") as View).visibility)
            val requests = generateSequence { shadowOf(app).nextStartedService }.filter {
                it.getStringExtra(WearWorkoutService.EXTRA_COMMAND) == "WORKOUT_CONTROL_SUBMIT"
            }.map { WatchWorkoutControl.decode(it.getStringExtra("payload")!!) }.toList()
            assertFalse("The watch must wait for the user's choice: $requests",
                requests.any { it.action == WatchWorkoutAction.FINISH_WATCH_SIDE_ONLY })
        } finally { controller.pause().stop().destroy() }
    }

    @Test fun safetyRestFiresOnceAt120SecondsFromVisibleQuestionAndDoesNotRestartOnTelemetry() {
        WatchWorkoutOutbox(app).receivePhoneHello(listOf("1", "phone", "0", "WORKOUT_CONTROL_V1"))
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        fun requests() = generateSequence { shadowOf(app).nextStartedService }.filter {
            it.getStringExtra(WearWorkoutService.EXTRA_COMMAND) == "WORKOUT_CONTROL_SUBMIT"
        }.map { WatchWorkoutControl.decode(it.getStringExtra("payload")!!) }.toList()
        try {
            state(true, "WORKING")
            state(false, "READY")
            // Time spent under the ordinary completion screen must not count toward the safety timeout.
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(2_000))
            state(false, "AWAITING_OTHER_SIDE")
            assertEquals(View.GONE, (field(controller.get(), "setDoneLayer") as View).visibility)
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(60_000))
            state(false, "AWAITING_OTHER_SIDE")
            // The 120 s clock starts when the question is visible; a couple of seconds of scheduler slack is fine.
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(50_000))
            assertTrue(requests().isEmpty())
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(15_000))
            assertEquals(listOf(WatchWorkoutAction.FINISH_WATCH_SIDE_ONLY), requests().map { it.action })
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1_000))
            assertTrue(requests().isEmpty())
        } finally { controller.pause().stop().destroy() }
    }

    @Test fun choosingOtherSideCancelsSafetyRest() {
        WatchWorkoutOutbox(app).receivePhoneHello(listOf("1", "phone", "0", "WORKOUT_CONTROL_V1"))
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            state(true, "WORKING")
            state(false, "AWAITING_OTHER_SIDE")
            (field(controller.get(), "face") as WatchWorkoutFace).restPause.onClick?.invoke()
            state(false, "OTHER_SIDE_WORKING")
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(120_000))
            val requests = generateSequence { shadowOf(app).nextStartedService }.filter {
                it.getStringExtra(WearWorkoutService.EXTRA_COMMAND) == "WORKOUT_CONTROL_SUBMIT"
            }.map { WatchWorkoutControl.decode(it.getStringExtra("payload")!!) }.toList()
            assertEquals(listOf(WatchWorkoutAction.START_OTHER_SIDE), requests.map { it.action })
        } finally { controller.pause().stop().destroy() }
    }
}
