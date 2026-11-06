package dev.kyungmin.kcoach.phone.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.kyungmin.kcoach.phone.heartRateText

/** One status line of the watch panel. Observable text and color; [tag] tells connection text from live telemetry. */
class LiveLine(text: String, var tag: String?) {
    var text by mutableStateOf(text)
    var color by mutableStateOf(KColors.Accent)
    /** A number worth reading from a distance, not a sentence of status text. */
    var headline by mutableStateOf(false)

    fun setTextColor(argb: Int) {
        color = Color(argb)
    }
}

/** The panel carries only what the set rows don't: the live count and the heart rate. */
data class LivePanelText(val title: String, val detail: String, val headline: Boolean) {
    companion object {
        fun of(phase: String, reps: Int, targetReps: Int, heartRate: Int): LivePanelText {
            val heart = heartRateText(heartRate)
            return when (phase) {
                "POSITIONING" -> LivePanelText("측정 준비 중", "손목 안정 확인", false)
                "PREPARING" -> LivePanelText("측정 준비 중", "흔들림 없이 2.5초 유지", false)
                "START_DIRECTION_WAITING" -> LivePanelText("손목 방향 확인", "2초 유지 또는 워치에서 직접 시작", false)
                "RESTING" -> LivePanelText("휴식 중", heart, true)
                "SET_COMPLETE" -> LivePanelText("${reps}회 완료", heart, true)
                else -> LivePanelText("$reps/${targetReps}회", heart, true)
            }
        }
    }
}

/** Sits over the exercise viewer: readable from a distance while the phone lies beside you. */
@Composable
fun LivePanel(title: LiveLine, telemetry: LiveLine, modifier: Modifier = Modifier) {
    Column(
        modifier
            .clip(KShape.Control)
            .background(KColors.Bg.copy(alpha = 0.6f))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.End,
    ) {
        Text(
            title.text,
            color = title.color,
            fontSize = if (title.headline) 30.sp else 12.sp,
            lineHeight = if (title.headline) 32.sp else 16.sp,
            fontWeight = FontWeight.Bold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            telemetry.text,
            color = if (title.headline) KColors.Bone else telemetry.color,
            fontSize = 12.sp,
            lineHeight = 16.sp,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
