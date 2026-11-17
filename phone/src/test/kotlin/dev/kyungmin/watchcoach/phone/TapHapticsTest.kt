package dev.kyungmin.watchcoach.phone

import android.content.Context
import android.view.HapticFeedbackConstants
import android.widget.CheckBox
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class TapHapticsTest {
    private class RecordingCheckBox(context: Context) : CheckBox(context) {
        val haptics = mutableListOf<Int>()
        override fun performHapticFeedback(feedbackConstant: Int): Boolean {
            haptics += feedbackConstant
            return true
        }
    }

    @Test fun userClickTicksOnceAndCheckedStateAssignmentsStaySilent() {
        val control = RecordingCheckBox(RuntimeEnvironment.getApplication())
        var clicks = 0
        control.setOnTapClickListener { clicks++ }
        control.isChecked = true
        control.isChecked = false
        assertTrue(control.haptics.isEmpty())
        assertEquals(0, clicks)

        control.performClick()
        assertEquals(listOf(HapticFeedbackConstants.CONTEXT_CLICK), control.haptics)
        assertEquals(1, clicks)
        assertTrue(control.isChecked)
    }

    @Test fun disabledControlDoesNotTickOrInvokeItsListener() {
        val control = RecordingCheckBox(RuntimeEnvironment.getApplication())
        var clicks = 0
        control.setOnTapClickListener { clicks++ }
        control.isEnabled = false
        control.performClick()
        assertTrue(control.haptics.isEmpty())
        assertEquals(0, clicks)
    }
}
