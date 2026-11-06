package dev.kyungmin.kcoach.phone.ui

import android.view.View
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w360dp-h800dp-xxhdpi")
class ActiveSetRowTest {
    @get:Rule val compose = createComposeRule()

    private fun show(resting: Boolean, preview: Boolean = false) {
        val now = System.currentTimeMillis()
        val sets = listOf(
            SetUi(1, "1", "50", 10, true, false, "", 60, false),
            SetUi(2, "2", "55", 10, false, false, "", 60, false),
            SetUi(3, "3", "55", 8, false, false, "", 60, false),
        )
        val model = WorkoutUiModel("등 루틴", preview, false, now, 0, 0, 0,
            listOf(ExerciseUi("lat_pulldown", "랫풀다운", "등", true, 60, 28, 10, 1, 3, 1, sets, 500, 1500, null)),
            if (resting) now else 0, if (resting) now + 60_000 else 0, 0, null,
            restingSet = if (resting) 0 to 0 else null)
        val actions = java.lang.reflect.Proxy.newProxyInstance(WorkoutActions::class.java.classLoader,
            arrayOf(WorkoutActions::class.java)) { proxy, method, args ->
            when (method.name) {
                "equals" -> proxy === args?.get(0)
                "hashCode" -> System.identityHashCode(proxy)
                "toString" -> "NoActions"
                else -> null
            }
        } as WorkoutActions
        compose.setContent {
            val context = LocalContext.current
            ActiveWorkoutScreen(model, actions, LiveLine("워치 연결됨", "title"), LiveLine("", "telemetry")) { View(context) }
        }
        compose.mainClock.advanceTimeBy(600)
        compose.waitForIdle()
    }

    @Test
    fun onlyTheSetBeingWorkedOnIsTaller() {
        show(resting = false)
        compose.onNodeWithTag("setRow-2").assertHeightIsEqualTo(69.dp)
        compose.onNodeWithTag("setRow-1").assertHeightIsEqualTo(46.dp)
        compose.onNodeWithTag("setRow-3").assertHeightIsEqualTo(46.dp)
        compose.onRoot().captureRoboImage("build/outputs/roborazzi/active_set.png")
    }

    @Test
    fun everySetIsNormalDuringRest() {
        show(resting = true)
        compose.onNodeWithTag("setRow-1").assertHeightIsEqualTo(46.dp)
        compose.onNodeWithTag("setRow-2").assertHeightIsEqualTo(46.dp)
        compose.onRoot().captureRoboImage("build/outputs/roborazzi/active_set_rest.png")
    }

    @Test
    fun browsingARoutineHasNoActiveSet() {
        show(resting = false, preview = true)
        compose.onNodeWithTag("setRow-2").assertHeightIsEqualTo(46.dp)
    }
}
