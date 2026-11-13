package dev.kyungmin.kcoach.phone.ui

import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalHapticFeedback
import kotlin.math.abs

/** Keep callbacks fresh without restarting a gesture when selection/layout changes. */
@Composable
internal fun Modifier.slidingSelection(
    selected: Int,
    indexAt: (Float) -> Int,
    preview: (Int?) -> Unit,
    onSelect: (Int) -> Unit,
    /** A real vibration click instead of the feather-light text-handle tick (the bottom tab bar asks for it). */
    strong: Boolean = false,
): Modifier {
    val currentSelected by rememberUpdatedState(selected)
    val currentHitTest by rememberUpdatedState(indexAt)
    val currentPreview by rememberUpdatedState(preview)
    val currentSelect by rememberUpdatedState(onSelect)
    val haptic = LocalHapticFeedback.current
    val context = androidx.compose.ui.platform.LocalContext.current
    val buzz: () -> Unit = {
        val vibrator = if (strong) context.getSystemService(android.os.Vibrator::class.java) else null
        if (vibrator != null && vibrator.hasVibrator()) vibrator.vibrate(android.os.VibrationEffect.createPredefined(android.os.VibrationEffect.EFFECT_CLICK))
        else haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
    }
    return pointerInput(haptic, strong) {
        awaitEachGesture {
            val down = awaitFirstDown()
            // Freeze the visible hit regions for this gesture: expanding tabs must not chase the finger.
            val hitTest = currentHitTest
            var target = hitTest(down.position.x)
            var horizontal = false
            var cancelled = false
            currentPreview(target)
            buzz()
            try {
                while (true) {
                    val change = awaitPointerEvent().changes.firstOrNull { it.id == down.id } ?: break
                    if (change.isConsumed) { cancelled = true; break }
                    val delta = change.position - down.position
                    if (!horizontal && abs(delta.y) > viewConfiguration.touchSlop && abs(delta.y) > abs(delta.x)) {
                        cancelled = true
                        break
                    }
                    if (abs(delta.x) > viewConfiguration.touchSlop) horizontal = true
                    if (horizontal) {
                        val next = hitTest(change.position.x)
                        if (next != target) {
                            target = next
                            currentPreview(target)
                            buzz()
                        }
                        change.consume()
                    }
                    if (!change.pressed) {
                        change.consume()
                        if (!cancelled && target != currentSelected) currentSelect(target)
                        break
                    }
                }
            } finally {
                currentPreview(null)
            }
        }
    }
}
