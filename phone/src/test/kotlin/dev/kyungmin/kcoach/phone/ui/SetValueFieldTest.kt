package dev.kyungmin.kcoach.phone.ui

import android.view.View
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w360dp-h800dp-xxhdpi")
class SetValueFieldTest {
    @get:Rule val compose = createComposeRule()

    private fun at(text: String, caret: Int) = TextFieldValue(text, TextRange(caret))

    @Test
    fun typingReplacesTheSelection() {
        assertEquals(at("7", 1), SetValueEdit.type(SetValueEdit.selectAll("55"), '7'))
    }

    @Test
    fun typingInsertsAtTheCaret() {
        assertEquals(at("570", 2), SetValueEdit.type(at("50", 1), '7'))
    }

    @Test
    fun leadingZeroIsReplacedAfterTheCaret() {
        assertEquals(at("7", 1), SetValueEdit.type(at("0", 1), '7'))
        assertEquals(at("0.", 2), SetValueEdit.type(at("0", 1), '.'))
    }

    @Test
    fun secondDecimalPointAndLongValuesAreIgnored() {
        assertEquals(at("2.5", 3), SetValueEdit.type(at("2.5", 3), '.'))
        assertEquals(at("123456", 6), SetValueEdit.type(at("123456", 6), '7'))
    }

    @Test
    fun backspaceClearsSelectionOrTheDigitBeforeTheCaret() {
        assertEquals(at("", 0), SetValueEdit.backspace(SetValueEdit.selectAll("55")))
        assertEquals(at("0", 0), SetValueEdit.backspace(at("50", 1)))
        assertEquals(at("50", 0), SetValueEdit.backspace(at("50", 0)))
    }

    @Test
    fun systemEditsOnlyLandWhenTheyAreNumbers() {
        val current = at("55", 2)
        assertEquals(at("55", 1), SetValueEdit.accept(current, at("55", 1), decimals = true))
        assertEquals(at("5.5", 3), SetValueEdit.accept(current, at("5.5", 3), decimals = true))
        assertEquals(current, SetValueEdit.accept(current, at("5.5", 3), decimals = false))
        assertEquals(current, SetValueEdit.accept(current, at("abc", 3), decimals = true))
    }

    @OptIn(ExperimentalTestApi::class)
    @Test
    fun editedCellIsARealFocusedTextFieldDrivenByTheKeypad() {
        val edits = mutableListOf<String>()
        val now = System.currentTimeMillis()
        val sets = listOf(SetUi(1, "1", "55", 8, false, false, "", 60, false))
        val model = WorkoutUiModel("팔 루틴", false, false, now, 0, 0, 0,
            listOf(ExerciseUi("dumbbell_curl", "덤벨 컬", "이두", true, 60, 16, 0, 0, 1, 0, sets, 0, 160, null)), false,
            0, 0, 0, null)
        val actions = java.lang.reflect.Proxy.newProxyInstance(WorkoutActions::class.java.classLoader,
            arrayOf(WorkoutActions::class.java)) { proxy, method, args ->
            when (method.name) {
                "equals" -> proxy === args?.get(0)
                "hashCode" -> System.identityHashCode(proxy)
                "toString" -> "Actions"
                "onEditValue" -> { edits += args!![3] as String; null }
                else -> null
            }
        } as WorkoutActions
        compose.setContent {
            val context = LocalContext.current
            ActiveWorkoutScreen(model, actions, LiveLine("워치 연결됨", "title"), LiveLine("", "telemetry")) { View(context) }
        }

        // Cell numbers are drawn, not text nodes, so aim just below the KG column header.
        val header = compose.onNodeWithText("KG").performScrollTo().fetchSemanticsNode().boundsInRoot
        compose.onRoot().performTouchInput { click(androidx.compose.ui.geometry.Offset(header.center.x, header.bottom + 72f)) }
        compose.mainClock.advanceTimeBy(600)
        compose.waitForIdle()

        val field = compose.onNode(hasSetTextAction())
        field.assertIsFocused()
        assertEquals(TextRange(0, 2), field.fetchSemanticsNode().config[androidx.compose.ui.semantics.SemanticsProperties.TextSelectionRange])
        compose.onRoot().captureRoboImage("build/outputs/roborazzi/set_value_selected.png")

        field.performTextInputSelection(TextRange(1))
        compose.waitForIdle()
        compose.onRoot().captureRoboImage("build/outputs/roborazzi/set_value_caret.png")

        compose.onNodeWithText("7").performClick()
        compose.waitForIdle()
        assertEquals(listOf("575"), edits)
    }
}
