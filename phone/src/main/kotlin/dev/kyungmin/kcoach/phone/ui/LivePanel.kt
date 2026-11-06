package dev.kyungmin.kcoach.phone.ui

import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.keyframes
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.kyungmin.kcoach.core.HeartZone
import kotlin.math.abs

/** One status line of the watch panel. Observable text and color; [tag] tells connection text from live telemetry. */
class LiveLine(text: String, var tag: String?) {
    private var line by mutableStateOf(text)
    var color by mutableStateOf(KColors.Accent)
    /** Smaller text after the live count, e.g. "/10회". */
    var suffix by mutableStateOf("")
        private set
    var heartRate by mutableIntStateOf(0)
        private set

    /** Plain status text replaces whatever live count the line was showing. */
    var text: String
        get() = line
        set(value) {
            line = value
            suffix = ""
            heartRate = 0
        }

    fun show(live: LivePanelText) {
        line = live.title
        suffix = live.suffix
        heartRate = live.heartRate
    }

    fun setTextColor(argb: Int) {
        color = Color(argb)
    }
}

/** The panel carries only what the set rows don't: the live count and the heart rate. */
data class LivePanelText(val title: String, val suffix: String, val detail: String, val heartRate: Int) {
    companion object {
        fun of(phase: String, reps: Int, targetReps: Int, heartRate: Int): LivePanelText = when (phase) {
            "POSITIONING" -> LivePanelText("측정 준비 중", "", "손목 안정 확인", 0)
            "PREPARING" -> LivePanelText("측정 준비 중", "", "흔들림 없이 1.2초 유지", 0)
            "START_DIRECTION_WAITING" -> LivePanelText("손목 방향 확인", "", "2초 유지 또는 워치에서 직접 시작", 0)
            "RESTING" -> LivePanelText("휴식 중", "", "", heartRate)
            "SET_COMPLETE" -> LivePanelText("$reps", "회 완료", "", heartRate)
            else -> LivePanelText("$reps", "/${targetReps}회", "", heartRate)
        }
    }
}

/** Sits over the exercise viewer: readable from a distance while the phone lies beside you. */
@Composable
fun LivePanel(title: LiveLine, telemetry: LiveLine, modifier: Modifier = Modifier) {
    Column(modifier, horizontalAlignment = Alignment.End) {
        val counting = title.suffix.isNotEmpty()
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                title.text,
                color = title.color,
                fontSize = if (counting) 35.sp else 12.sp,
                lineHeight = if (counting) 37.sp else 16.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (counting) {
                Text(title.suffix, color = KColors.Bone, fontSize = 14.sp, lineHeight = 26.sp, fontWeight = FontWeight.Medium, maxLines = 1)
            }
        }
        if (telemetry.text.isNotEmpty()) {
            Text(telemetry.text, color = telemetry.color, fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        if (title.heartRate in VALID_HEART_RATE) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                BeatingHeart(title.heartRate)
                Spacer(Modifier.width(5.dp))
                Text(title.heartRate.toString(), color = KColors.Bone, fontSize = 14.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium)
            }
        }
    }
}

private val VALID_HEART_RATE = 20..240

/** The watch's heart: filled in its zone colour, with a double beat at the measured rate. */
@Composable
private fun BeatingHeart(bpm: Int) {
    var periodMs by remember { mutableIntStateOf(beatPeriodMs(bpm)) }
    // A beat or two of drift in the reading must not restart the animation.
    LaunchedEffect(bpm) { if (abs(beatPeriodMs(bpm) - periodMs) >= 40) periodMs = beatPeriodMs(bpm) }
    val color = Color(HeartZone.color(bpm))
    key(periodMs) {
        val scale by rememberInfiniteTransition(label = "heart").animateFloat(
            initialValue = 1f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(
                keyframes {
                    durationMillis = periodMs
                    1.22f at (periodMs * 14 / 100)
                    1f at (periodMs * 28 / 100)
                    1.12f at (periodMs * 42 / 100)
                    1f at (periodMs * 56 / 100)
                },
            ),
            label = "beat",
        )
        Canvas(Modifier.size(16.dp).graphicsLayer { scaleX = scale; scaleY = scale }) {
            drawPath(heartPath(size.minDimension / 24f), color)
        }
    }
}

private fun beatPeriodMs(bpm: Int) = (60_000 / bpm).coerceIn(300, 1_500)

/** Material "favorite" on a 24 unit grid, the same outline the watch draws. */
private fun heartPath(unit: Float) = Path().apply {
    moveTo(12f * unit, 21.35f * unit)
    lineTo(10.55f * unit, 20.03f * unit)
    cubicTo(5.4f * unit, 15.36f * unit, 2f * unit, 12.28f * unit, 2f * unit, 8.5f * unit)
    cubicTo(2f * unit, 5.42f * unit, 4.42f * unit, 3f * unit, 7.5f * unit, 3f * unit)
    cubicTo(9.24f * unit, 3f * unit, 10.91f * unit, 3.81f * unit, 12f * unit, 5.09f * unit)
    cubicTo(13.09f * unit, 3.81f * unit, 14.76f * unit, 3f * unit, 16.5f * unit, 3f * unit)
    cubicTo(19.58f * unit, 3f * unit, 22f * unit, 5.42f * unit, 22f * unit, 8.5f * unit)
    cubicTo(22f * unit, 12.28f * unit, 18.6f * unit, 15.36f * unit, 13.45f * unit, 20.04f * unit)
    close()
}
