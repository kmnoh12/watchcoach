package dev.kyungmin.watchcoach.phone

import android.content.res.Configuration
import dev.kyungmin.watchcoach.core.PlannedSetSnapshot
import dev.kyungmin.watchcoach.core.WorkoutPhase
import dev.kyungmin.watchcoach.core.WorkoutSnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertSame
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "w360dp-h800dp-xxhdpi")
class ScreenConfigurationTest {
    private fun snapshot(resting: Boolean): WorkoutSnapshot {
        val now = System.currentTimeMillis()
        return WorkoutSnapshot(
            sessionId = "screen-change", routineId = "screen-routine", exerciseIndex = 0, setIndex = 0,
            plannedSets = listOf(PlannedSetSnapshot(0, "dumbbell_curl", 0, 10, 12.5, false,
                exerciseName = "덤벨 컬")),
            performedReps = emptyMap(), phase = if (resting) WorkoutPhase.RESTING else WorkoutPhase.WORKING,
            restEndAtMs = if (resting) now + 90000 else 0, pausedRestRemainingMs = 0,
            paused = false, startedAtMs = now, pausedSinceMs = 0, totalPausedMs = 0,
            lastSequence = 0, lastCompletedSetKey = null, captureStates = emptyMap(),
        )
    }

    @Test
    fun rotationAndFoldKeepTheActiveSessionAndDeadline() {
        for (resting in listOf(false, true)) {
            val store = SessionStore(RuntimeEnvironment.getApplication())
            store.saveActive(snapshot(resting))
            val controller = Robolectric.buildActivity(MainActivity::class.java).setup().visible()
            try {
                val activity = controller.get()
                val active = MainActivity::class.java.getDeclaredField("activeWorkout").apply { isAccessible = true }
                val workout = active.get(activity)
                assertNotNull(workout)
                val before = store.loadActive().getOrThrow()
                for ((width, height) in listOf(800 to 360, 673 to 841, 280 to 653, 360 to 800)) {
                    controller.configurationChange(Configuration(activity.resources.configuration).apply {
                        screenWidthDp = width
                        screenHeightDp = height
                        smallestScreenWidthDp = minOf(width, height)
                        orientation = if (width > height) Configuration.ORIENTATION_LANDSCAPE else Configuration.ORIENTATION_PORTRAIT
                    })
                    assertSame(activity, controller.get())
                    assertSame(workout, active.get(controller.get()))
                    assertEquals(before, store.loadActive().getOrThrow())
                }
                // The persisted workout also survives an explicit Activity recreation.
                controller.recreate()
                assertNotNull(active.get(controller.get()))
                assertEquals(before, store.loadActive().getOrThrow())
            } finally {
                controller.pause().stop().destroy()
            }
        }
    }
    @Test
    fun landscapeSideBarsAndCutoutsStayOutsideContent() {
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup().visible()
        try {
            val root = MainActivity::class.java.getDeclaredField("root").apply { isAccessible = true }
                .get(controller.get()) as android.view.View
            val insets = androidx.core.view.WindowInsetsCompat.Builder()
                .setInsets(androidx.core.view.WindowInsetsCompat.Type.systemBars(), androidx.core.graphics.Insets.of(0, 24, 48, 0))
                .setInsets(androidx.core.view.WindowInsetsCompat.Type.displayCutout(), androidx.core.graphics.Insets.of(40, 0, 0, 0))
                .build()
            androidx.core.view.ViewCompat.dispatchApplyWindowInsets(root, insets)
            assertEquals(40, root.paddingLeft)
            assertEquals(24, root.paddingTop)
            assertEquals(48, root.paddingRight)
        } finally {
            controller.pause().stop().destroy()
        }
    }
}
