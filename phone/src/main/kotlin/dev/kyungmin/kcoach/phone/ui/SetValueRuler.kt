package dev.kyungmin.kcoach.phone.ui

import android.view.HapticFeedbackConstants
import android.view.View
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.animate
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.util.VelocityTracker
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.abs
import kotlin.math.asin
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.floor
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/** Where the dial may rest: every 1, plus the 2.5 marks between (52, 52.5, 53 ... 57, 57.5, 58) for weight. */
object SetValueDial {
    fun snap(position: Float, weight: Boolean): Float {
        val low = floor(position)
        val stops = buildList {
            add(low)
            add(low + 1)
            if (weight && hasHalfStop(low)) add(low + 0.5f)
        }
        return stops.minBy { abs(it - position) }.coerceAtLeast(0f)
    }

    fun hasHalfStop(whole: Float) = whole.roundToInt().mod(5) == 2

    fun nearestFive(position: Float) = ((position / 5).roundToInt() * 5).coerceAtLeast(0).toFloat()
}

private const val DRUM_RADIUS = 0.62f
private const val DRUM_REACH = 1.45f
private const val NUMBER_ROW_DP = 27f
private const val NEEDLE_DP = 27f
private const val LABEL_BASELINE_DP = 42f
private const val SETTLE_MS = 220
private const val GLIDE_DECAY_MS = 260f
private const val MAX_FLICK_DP_PER_MS = 1.5f
private const val MIN_GLIDE_DP_PER_MS = 0.05f
private const val MOVE_SLOP_DP = 6f
private val EaseOutCubic = CubicBezierEasing(0.33f, 1f, 0.68f, 1f)

/** The key-press haptic the stock keyboard uses, shared by the dial and the number keys. */
fun View.keyTick() {
    performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
}

/** A dial on a drum: drag it, flick it, or tap a mark. Ticks a haptic at every stop it passes. */
@Composable
fun SetValueRuler(value: String, weight: Boolean, onPick: (String) -> Unit, modifier: Modifier = Modifier) {
    val view = LocalView.current
    val scope = rememberCoroutineScope()
    val measurer = rememberTextMeasurer(cacheSize = 32)
    val shown by rememberUpdatedState(value)
    val pick by rememberUpdatedState(onPick)
    val unitDp = if (weight) 12f else 22f
    val target = value.toFloatOrNull()?.coerceAtLeast(0f) ?: 0f
    var position by remember(weight) { mutableFloatStateOf(target) }
    var turning by remember { mutableStateOf(false) }
    var glide by remember { mutableStateOf<Job?>(null) }

    LaunchedEffect(target, turning, weight) {
        if (!turning && position != target) {
            animate(position, target, animationSpec = tween(SETTLE_MS, easing = EaseOutCubic)) { now, _ -> position = now }
        }
    }

    fun publish(stop: Float) {
        val text = cleanNumber(stop.toDouble())
        if (text == shown) return
        view.keyTick()
        pick(text)
    }

    Canvas(
        modifier.fillMaxWidth().height(54.dp).testTag("setValueRuler").pointerInput(weight) {
            val unit = unitDp.dp.toPx()
            val slop = MOVE_SLOP_DP.dp.toPx()
            awaitEachGesture {
                val down = awaitFirstDown(requireUnconsumed = false)
                val wasTurning = glide?.isActive == true
                glide?.cancel()
                turning = true
                val velocity = VelocityTracker()
                velocity.addPosition(down.uptimeMillis, down.position)
                val startPosition = position
                var moved = false
                var lastAt = down.uptimeMillis
                var up = down
                while (true) {
                    val change = awaitPointerEvent().changes.firstOrNull { it.id == down.id } ?: break
                    up = change
                    if (!change.pressed) break
                    val travelled = change.position.x - down.position.x
                    if (abs(travelled) > slop) moved = true
                    velocity.addPosition(change.uptimeMillis, change.position)
                    lastAt = change.uptimeMillis
                    change.consume()
                    position = (startPosition - travelled / unit).coerceAtLeast(0f)
                    if (moved) publish(SetValueDial.snap(position, weight))
                }
                if (!moved && !wasTurning) {
                    val radius = size.width * DRUM_RADIUS
                    val offset = ((up.position.x - size.width / 2f) / radius).coerceIn(-1f, 1f)
                    val under = startPosition + asin(offset) * radius / unit
                    val onLabels = up.position.y >= NUMBER_ROW_DP.dp.toPx()
                    publish(if (onLabels) SetValueDial.nearestFive(under) else SetValueDial.snap(under, weight))
                    turning = false
                } else {
                    val fastest = MAX_FLICK_DP_PER_MS.dp.toPx()
                    val flick = if (up.uptimeMillis - lastAt > 80) 0f else (velocity.calculateVelocity().x / 1000f).coerceIn(-fastest, fastest)
                    glide = scope.launch {
                        var speed = -flick / unit
                        val slowest = MIN_GLIDE_DP_PER_MS.dp.toPx() / unit
                        var before = withFrameMillis { it }
                        while (abs(speed) >= slowest) {
                            val now = withFrameMillis { it }
                            val elapsed = (now - before).toFloat()
                            before = now
                            position = (position + speed * elapsed).coerceAtLeast(0f)
                            speed = if (position == 0f) 0f else speed * exp(-elapsed / GLIDE_DECAY_MS)
                            publish(SetValueDial.snap(position, weight))
                        }
                        publish(SetValueDial.snap(position, weight))
                        turning = false
                    }
                }
            }
        },
    ) {
        val unit = unitDp.dp.toPx()
        val radius = size.width * DRUM_RADIUS
        val middle = size.width / 2f
        val baseline = LABEL_BASELINE_DP.dp.toPx()
        val currentStyle = TextStyle(color = KColors.Sage, fontSize = 15.sp, fontWeight = FontWeight.Bold)
        val tenStyle = TextStyle(color = KColors.Bone, fontSize = 15.sp, fontWeight = FontWeight.Bold)
        val fiveStyle = TextStyle(color = KColors.Muted, fontSize = 12.sp, fontWeight = FontWeight.Normal)
        val current = value.takeIf { it.isNotEmpty() }?.let { measurer.measure(it, currentStyle) }

        fun tick(mark: Float) {
            val angle = (mark - position) * unit / radius
            if (mark < 0f || abs(angle) > DRUM_REACH) return
            val x = middle + radius * sin(angle)
            val depth = cos(angle).coerceAtLeast(0f)
            val whole = mark.roundToInt()
            val half = mark % 1f != 0f
            val ten = !half && whole % 10 == 0
            val five = !half && whole % 5 == 0
            val heightDp = when {
                !weight -> if (five) 20f else 12f
                ten -> 22f
                five -> 18f
                half -> 8f
                else -> 13f
            }
            val width = (if (ten) 2.2f else 1.6f).dp.toPx() * (0.5f + 0.5f * depth)
            drawRect(
                color = if (five) KColors.Bone else KColors.Soft,
                topLeft = Offset(x - width / 2f, 0f),
                size = Size(width, heightDp.dp.toPx() * (0.65f + 0.35f * depth)),
                alpha = depth,
            )
            if (five) {
                val label = measurer.measure(whole.toString(), if (ten) tenStyle else fiveStyle)
                // Only a label that would actually touch the sage value gives way.
                val clear = (label.size.width + (current?.size?.width ?: 0)) / 2f + 3.dp.toPx()
                if (abs(x - middle) > clear) {
                    drawText(label, topLeft = Offset(x - label.size.width / 2f, baseline - label.firstBaseline), alpha = depth)
                }
            }
        }

        val span = ceil(radius * DRUM_REACH / unit).toInt() + 1
        val base = position.roundToInt()
        for (step in -span..span) {
            val mark = (base + step).toFloat()
            tick(mark)
            if (weight && SetValueDial.hasHalfStop(mark)) tick(mark + 0.5f)
        }
        val needle = 3.dp.toPx()
        drawRect(KColors.Sage, topLeft = Offset(middle - needle / 2f, 0f), size = Size(needle, NEEDLE_DP.dp.toPx()))
        // The current value always sits under the needle, even between the printed 5s.
        if (current != null) {
            drawText(current, topLeft = Offset(middle - current.size.width / 2f, baseline - current.firstBaseline))
        }
    }
}
