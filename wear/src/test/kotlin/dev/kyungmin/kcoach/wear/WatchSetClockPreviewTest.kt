package dev.kyungmin.kcoach.wear
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

import java.io.File
import java.time.Duration

/** Renders the set-clock screens (manual exercises and one-arm opposite side) next to a rest clock for visual review. */
@RunWith(RobolectricTestRunner::class)
@org.robolectric.annotation.LooperMode(org.robolectric.annotation.LooperMode.Mode.PAUSED)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w216dp-h216dp-round-xhdpi")
class WatchSetClockPreviewTest {
    private var manualButtonCenterY = 0f
    private var manualHeaderGeometry: List<Float>? = null
    private val app get() = RuntimeEnvironment.getApplication()
    private fun measure(root: View) {
        root.measure(View.MeasureSpec.makeMeasureSpec(432, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(432, View.MeasureSpec.EXACTLY))
        root.layout(0, 0, 432, 432)
    }
    private fun shot(root: View, name: String) {
        measure(root)
        // Force a full software capture, including unchanged labels cached by the native renderer.
        descendants(root).forEach { it.invalidate() }
        val bitmap = Bitmap.createBitmap(432, 432, Bitmap.Config.ARGB_8888)
        root.draw(Canvas(bitmap))
        val face = descendants(root).filterIsInstance<WatchWorkoutFace>().first()
        if (name.startsWith("setclock-") && face.setTiming) {
            val subtitleBottom = face.subtitle.top + face.subtitle.baseline + face.subtitle.paint.fontMetrics.descent
            assertTrue("Control must sit below the subtitle", face.jog.top > subtitleBottom)
            assertTrue("Control must clear completion buttons", face.jog.bottom < face.restPause.top)
            assertTrue("Goal must sit above countdown", face.goal.bottom < face.jog.top)
            assertEquals("Countdown must use the shared control", face.value.text.toString(), face.jog.centerLabel)
            assertEquals(View.INVISIBLE, face.value.visibility)
            assertEquals("Goal must be fully visible", 0, face.goal.layout.getEllipsisCount(0))
            assertEquals("40kg × 12회", face.goal.text.toString())
            assertEquals("완료", face.restPause.caption)
            assertEquals(View.VISIBLE, face.jog.visibility)
            assertEquals(View.GONE, face.hint.visibility)
            assertEquals(View.GONE, face.bpm.visibility)
            assertEquals(View.GONE, face.heartRate.visibility)
            for (button in listOf(face.restPause, face.restSkip).filter { it.visibility == View.VISIBLE }) {
                for (x in listOf(button.left, button.right)) for (y in listOf(button.top, button.bottom)) {
                    val radius = face.width / 2f
                    assertTrue("Buttons must stay clear of the round ring", (x-radius)*(x-radius)+(y-radius)*(y-radius) < (radius-12f)*(radius-12f))
                }
            }
        }
        val headerGeometry = listOf(face.title, face.goal, face.jog).flatMap {
            listOf(it.left.toFloat(), it.top.toFloat(), it.right.toFloat(), it.bottom.toFloat())
        } + face.goal.textSize
        if (name == "setclock-manual-45s") {
            manualHeaderGeometry = headerGeometry
            manualButtonCenterY = (face.restPause.top + face.restPause.bottom) / 2f + face.restPause.translationY
            assertEquals(1f, face.restPause.completionTextScale)
        }
        if (name.startsWith("setclock-first-set-")) {
            assertTrue("First sets must show the set clock", face.setTiming)
            assertEquals(manualHeaderGeometry, headerGeometry)
        }
        if ((name.startsWith("setclock-manual-") || name.startsWith("setclock-first-set-")) && face.setTiming) {
            assertEquals(108, face.restPause.left)
            assertEquals(324, face.restPause.right)
            assertEquals(290, face.restPause.top)
            assertEquals(78, face.restPause.height)
            assertEquals(78f, face.restPause.completionHeightUnits)
            assertEquals(1f, face.restPause.completionTextScale)
            assertEquals(0f, face.restPause.translationY)
        }
        if (name == "setclock-other-side") {
            assertEquals(94, face.restPause.left)
            assertEquals(207, face.restPause.right)
            assertEquals(295, face.restPause.top)
            assertEquals(69, face.restPause.height)
            assertEquals(225, face.restSkip.left)
            assertEquals(338, face.restSkip.right)
            assertEquals(295, face.restSkip.top)
            assertEquals(69, face.restSkip.height)
            listOf(face.restPause, face.restSkip).forEach {
                assertEquals("Button rows must share the manual action centre", manualButtonCenterY,
                    (it.top + it.bottom) / 2f + it.translationY, 0f)
            }
            assertEquals("Opposite-side header must match manual-set geometry", manualHeaderGeometry, headerGeometry)
            assertEquals("", face.subtitle.text.toString())
            assertEquals(.81f, face.restPause.completionTextScale)
            assertEquals(View.VISIBLE, face.subtitle.visibility)
            assertEquals(1f, face.subtitle.alpha)
            assertEquals("건너뛰기", face.restSkip.caption)
            assertTrue(face.restPause.right < face.restSkip.left)
        }
        if (name == "rest-for-comparison") {
            assertFalse(face.setTiming)
            assertEquals(View.GONE, face.title.visibility)
            assertEquals(227, face.restSkip.left)
            assertEquals(182, face.jog.top)
        }
        val file = File("build/outputs/watch-preview/$name.png").apply { parentFile?.mkdirs() }
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
    }
    private fun descendants(view: View): Sequence<View> = sequence {
        yield(view)
        if (view is ViewGroup) for (i in 0 until view.childCount) yieldAll(descendants(view.getChildAt(i)))
    }
    private fun idle(ms: Long = 0) {
        if (ms > 0) shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(ms)) else shadowOf(Looper.getMainLooper()).idle()
    }
    private fun state(exerciseId: String, name: String, phase: String, running: Boolean, resting: Boolean = false,
        restEndAtMs: Long = 0L, extras: Intent.() -> Unit = {}) {
        app.sendBroadcast(Intent(WearWorkoutService.ACTION_STATE).setPackage(app.packageName)
            .putExtra("session", "preview").putExtra("setId", "set-2").putExtra("attemptId", "a-2")
            .putExtra("exerciseId", exerciseId).putExtra("exerciseName", name).putExtra("paired", true)
            .putExtra("running", running).putExtra("resting", resting).putExtra("paused", false)
            .putExtra("setIndex", 1).putExtra("reps", 0).putExtra("targetReps", 12).putExtra("weightKg", 40.0)
            .putExtra("heartRate", 0).putExtra("restSeconds", 90).putExtra("restEndAtMs", restEndAtMs)
            .putExtra("phase", phase).apply(extras))
        idle()
    }
    private fun start(): Pair<org.robolectric.android.controller.ActivityController<MainActivity>, View> {
        WatchWorkoutOutbox(app).receivePhoneHello(listOf("1", "phone", "0", "WORKOUT_CONTROL_V1"))
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        val root = controller.get().findViewById<ViewGroup>(android.R.id.content).getChildAt(0)
        measure(root)
        return controller to root
    }

    private fun tapJog(jog: JogBar, fraction: Float) {
        // Exercise the actual shared bar's hit regions, rather than calling its callback.
        val x = jog.width * fraction
        for (action in listOf(android.view.MotionEvent.ACTION_DOWN, android.view.MotionEvent.ACTION_UP)) {
            val event = android.view.MotionEvent.obtain(0, 0, action, x, jog.height / 2f, 0)
            jog.dispatchTouchEvent(event); event.recycle()
        }
    }

    private fun requests() = generateSequence { shadowOf(app).nextStartedService }.filter {
        it.getStringExtra(WearWorkoutService.EXTRA_COMMAND) == "WORKOUT_CONTROL_SUBMIT"
    }.map { dev.kyungmin.kcoach.core.WatchWorkoutControl.decode(it.getStringExtra("payload")!!) }.toList()

    @Test fun controlsReuseCommandsAndDisconnectedButtonsAreDisabled() {
        val (controller, root) = start()
        try {
            val face = descendants(root).filterIsInstance<WatchWorkoutFace>().first()
            state("leg_press", "레그 프레스", "WORKING", running = true) {
                putExtra("manualRequired", true); putExtra("setClockRemaining", 45_000L)
            }
            measure(root)
            assertTrue(face.restPause.isEnabled)
            tapJog(face.jog, .1f); tapJog(face.jog, .9f); face.restPause.performClick()
            val commands = requests()
            assertEquals(org.robolectric.shadows.ShadowLog.getLogsForTag("WatchMainActivity").toString(), listOf(-10, 10), commands.take(2).map { it.deltaSeconds })
            assertEquals(dev.kyungmin.kcoach.core.WatchWorkoutAction.COMPLETE_MANUAL_SET, commands.last().action)
            state("single_arm_cable_reverse_fly", "원암", "OTHER_SIDE_WORKING", running = false) {
                putExtra("setClockRemaining", 38_000L); putExtra("weightKg", Double.NaN)
            }
            assertEquals("12회", face.goal.text.toString())
            face.restPause.performClick(); face.restSkip.performClick()
            assertEquals(listOf(dev.kyungmin.kcoach.core.WatchWorkoutAction.COMPLETE_OTHER_SIDE,
                dev.kyungmin.kcoach.core.WatchWorkoutAction.FINISH_WATCH_SIDE_ONLY), requests().map { it.action })
            state("single_arm_cable_reverse_fly", "원암", "OTHER_SIDE_WORKING", running = false) {
                putExtra("setClockRemaining", 38_000L); putExtra("paused", true)
            }
            measure(root)
            assertTrue("Paused opposite-side buttons must remain separate", face.restPause.right < face.restSkip.left)
            assertFalse(face.restPause.isEnabled); assertFalse(face.restSkip.isEnabled)
            state("leg_press", "레그 프레스", "WORKING", running = true) {
                putExtra("manualRequired", true); putExtra("setClockRemaining", 45_000L); putExtra("paired", false)
            }
            assertFalse(face.restPause.isEnabled); assertFalse(face.jog.isEnabled)
            assertEquals(.4f, face.restPause.alpha)
            face.restPause.onClick(); face.jog.onStep(10)
            assertTrue(requests().isEmpty())
        } finally { controller.pause().stop().destroy() }
    }

    @Test fun disabledAnimationsSwitchImmediately() {
        android.provider.Settings.Global.putFloat(app.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 0f)
        val (controller, root) = start()
        try {
            state("leg_press", "레그 프레스", "WORKING", running = true) {
                putExtra("manualRequired", true); putExtra("setClockRemaining", 45_000L)
            }
            state("leg_press", "레그 프레스", "RESTING", false, true, System.currentTimeMillis() + 60_000L)
            val face = descendants(root).filterIsInstance<WatchWorkoutFace>().first()
            assertEquals(1f, face.setRestProgress)
            assertEquals(1f, face.value.scaleX)
            assertEquals(0f, face.value.translationY)
            assertEquals(View.GONE, face.goal.visibility)
            assertNull(face.restPause.caption)
            assertEquals(0f, face.restPause.translationY)
            assertEquals(0f, face.restSkip.translationY)
            assertEquals("10초", face.jog.centerLabel)
            assertEquals(1f, face.jog.labelOpacity)
            assertEquals(0f, face.jog.translationY)
        } finally {
            controller.pause().stop().destroy()
            android.provider.Settings.Global.putFloat(app.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
        }
    }

    @Test fun renderSetClockScreens() {
        val (controller, root) = start()
        state("leg_press", "레그 프레스", "WORKING", running = true) {
            putExtra("manualRequired", true); putExtra("setClockRemaining", 45_000L); putExtra("setClockTotal", 70_000L)
        }
        idle(300); shot(root, "setclock-manual-45s")
        state("leg_press", "레그 프레스", "WORKING", running = true) {
            putExtra("manualRequired", true); putExtra("setClockRemaining", 8_000L); putExtra("setClockTotal", 70_000L)
        }
        idle(300); shot(root, "setclock-manual-8s")
        state("leg_press", "레그 프레스", "WORKING", running = true) {
            putExtra("manualRequired", true); putExtra("setIndex", 0)
            putExtra("setClockRemaining", 45_000L); putExtra("setClockTotal", 70_000L)
        }
        idle(300); shot(root, "setclock-first-set-history-45s")
        state("leg_press", "레그 프레스", "WORKING", running = true) {
            putExtra("manualRequired", true); putExtra("setIndex", 0)
            putExtra("setClockRemaining", 41_000L); putExtra("setClockTotal", 41_000L)
        }
        idle(300); shot(root, "setclock-first-set-default-41s")
        state("single_arm_cable_reverse_fly", "원암 케이블 리버스 플라이", "OTHER_SIDE_WORKING", running = false) {
            putExtra("setClockRemaining", 38_000L); putExtra("setClockTotal", 55_000L)
        }
        idle(300); shot(root, "setclock-other-side")
        assertTrue(descendants(root).filterIsInstance<WatchWorkoutFace>().first().setTiming)
        android.provider.Settings.Global.putFloat(app.contentResolver, android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
        android.animation.ValueAnimator::class.java.getDeclaredMethod("setDurationScale", Float::class.javaPrimitiveType).invoke(null, 1f)
        state("leg_press", "레그 프레스", "RESTING", running = false, resting = true, restEndAtMs = System.currentTimeMillis() + 62_000L)
        val face = descendants(root).filterIsInstance<WatchWorkoutFace>().first()
        val morph = WatchWorkoutFace::class.java.getDeclaredField("setRestAnimator").apply { isAccessible = true }.get(face)
        assertNotNull(org.robolectric.shadows.ShadowLog.getLogsForTag("WatchMainActivity").joinToString { "${it.msg}: ${it.throwable?.stackTraceToString()}" }, morph)
        morph as android.animation.ValueAnimator
        // Seek the real animator so exported intermediate frames have repeatable timestamps.
        morph.currentPlayTime = 100
        assertTrue("Must capture a genuine intermediate frame: ${face.setRestProgress}", face.setRestProgress > 0f && face.setRestProgress < 1f)
        shot(root, "set-to-rest-100ms")
        morph.currentPlayTime = 200; shot(root, "set-to-rest-200ms")
        val timerInk = android.graphics.RectF(0f, face.value.baseline + face.value.paint.fontMetrics.ascent,
            face.value.width.toFloat(), face.value.baseline + face.value.paint.fontMetrics.descent)
        face.value.matrix.mapRect(timerInk)
        timerInk.offset(face.value.left.toFloat(), face.value.top.toFloat())
        assertTrue("Growing time must clear the ten-second label", timerInk.bottom < face.jog.top + face.jog.translationY)
        morph.currentPlayTime = 400; shot(root, "rest-for-comparison")
        controller.pause().stop().destroy()
    }
}
