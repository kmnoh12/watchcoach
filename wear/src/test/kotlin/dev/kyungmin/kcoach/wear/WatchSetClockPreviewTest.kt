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
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w216dp-h216dp-round-xhdpi")
class WatchSetClockPreviewTest {
    private val app get() = RuntimeEnvironment.getApplication()
    private fun measure(root: View) {
        root.measure(View.MeasureSpec.makeMeasureSpec(432, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(432, View.MeasureSpec.EXACTLY))
        root.layout(0, 0, 432, 432)
    }
    private fun shot(root: View, name: String) {
        measure(root)
        val bitmap = Bitmap.createBitmap(432, 432, Bitmap.Config.ARGB_8888)
        root.draw(Canvas(bitmap))
        val face = descendants(root).filterIsInstance<WatchWorkoutFace>().first()
        if (name.startsWith("setclock-") && face.setTiming) {
            val top = face.value.top + face.value.baseline + face.value.paint.fontMetrics.ascent
            val subtitleBottom = face.subtitle.top + face.subtitle.baseline + face.subtitle.paint.fontMetrics.descent
            assertTrue("Timer must sit below the subtitle", top > subtitleBottom)
            val bottom = face.value.top + face.value.baseline + face.value.paint.fontMetrics.descent
            assertTrue("Timer must sit above time controls", bottom < face.jog.top)
            assertEquals("Countdown must be fully visible", 0, face.value.layout.getEllipsisCount(0))
        }
        if (name == "setclock-other-side") {
            assertEquals("폰에서 횟수 기록", face.hint.text.toString())
            assertEquals("반대손 건너뛰기", face.restSkip.caption)
            assertTrue("Skip button must be centred", kotlin.math.abs((face.restSkip.left + face.restSkip.right) / 2 - face.width / 2) <= 1)
            assertTrue("Skip must clear the time controls", face.restSkip.top > face.jog.bottom)
            for (x in listOf(face.restSkip.left, face.restSkip.right)) {
                for (y in listOf(face.restSkip.top, face.restSkip.bottom)) {
                    val radius = face.width / 2f
                    assertTrue("Skip button must stay inside the round screen",
                        (x - radius) * (x - radius) + (y - radius) * (y - radius) < radius * radius)
                }
            }
        }
        if (name == "setclock-manual-first-set-no-clock") {
            assertFalse(face.setTiming)
            assertEquals("—", face.value.text.toString())
            assertEquals("2세트 · 40kg · 직접 기록", face.subtitle.text.toString())
            assertEquals("위로 · 횟수 기록", face.hint.text.toString())
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
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        val root = controller.get().findViewById<ViewGroup>(android.R.id.content).getChildAt(0)
        measure(root)
        return controller to root
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
            putExtra("manualRequired", true)
        }
        idle(300); shot(root, "setclock-manual-first-set-no-clock")
        state("single_arm_cable_reverse_fly", "원암 케이블 리버스 플라이", "OTHER_SIDE_WORKING", running = false) {
            putExtra("setClockRemaining", 38_000L); putExtra("setClockTotal", 55_000L)
        }
        idle(300); shot(root, "setclock-other-side")
        state("leg_press", "레그 프레스", "RESTING", running = false, resting = true, restEndAtMs = System.currentTimeMillis() + 62_000L)
        idle(300); shot(root, "rest-for-comparison")
        controller.pause().stop().destroy()
    }
}
