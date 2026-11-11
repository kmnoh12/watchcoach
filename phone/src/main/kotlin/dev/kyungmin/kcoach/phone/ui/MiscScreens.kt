package dev.kyungmin.kcoach.phone.ui

import android.view.View
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.graphics.rememberGraphicsLayer
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
private fun DetailHeader(title: String, back: () -> Unit, menu: (@Composable () -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().height(58.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(54.dp, 58.dp).pressable(back), contentAlignment = Alignment.Center) {
            KIcon(KIcon.Back, KColors.White, size = 28.dp)
        }
        Text(title, color = KColors.White, fontSize = 25.sp, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
        Box(Modifier.size(54.dp, 58.dp), contentAlignment = Alignment.Center) {
            if (menu != null) menu() else KIcon(KIcon.Dots, KColors.Muted, size = 24.dp)
        }
    }
}

@Composable
private fun WideButton(text: String, background: Color, content: Color, height: Int, enabled: Boolean = true, onClick: () -> Unit) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(height.dp)
            .alpha(if (enabled) 1f else 0.6f)
            .clip(KShape.Control)
            .background(background)
            .then(if (enabled) Modifier.pressable(onClick) else Modifier),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = content, fontSize = 18.sp, fontWeight = FontWeight.Medium)
    }
}

// ---- Calibration -----------------------------------------------------------

class CalibrationUi(
    val catalog: List<LibraryEntry>,
    val instructions: String,
    val statuses: Map<String, String>,
    val selectableIds: Set<String>,
)

/** Live capture state, driven by watch events. */
class CalibrationButtonUi(val text: String, val enabled: Boolean, val textAmber: Boolean = false)

class CalibrationActions(
    val toggle: () -> Unit,
    val deleteProfile: (String) -> Unit,
    val select: (String) -> Unit,
    val openSensorView: (() -> Unit)? = null,
    val openCaptureReview: (() -> Unit)? = null,
)

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun CalibrationScreen(
    ui: CalibrationUi,
    sessionActive: () -> Boolean,
    button: () -> CalibrationButtonUi,
    actions: CalibrationActions,
    thumbnail: (dev.kyungmin.kcoach.phone.ExerciseDefinition) -> View,
) {
    var researchVisible by remember { mutableStateOf(false) }
    val active = sessionActive()
    ExerciseBrowser(
        catalog = ui.catalog,
        actions = LibraryActions({}, {}, { actions.select(it.id) }),
        thumbnail = thumbnail,
        calibration = true,
        enabled = { !active && it.id in ui.selectableIds },
        status = { ui.statuses[it.id] },
        onLongClick = { if (!active) actions.deleteProfile(it.id) },
        header = {
            Text("측정·보정", color = KColors.White, fontSize = 32.sp, fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(top = 6.dp, bottom = 12.dp)
                    .combinedClickable(onClick = {}, onLongClick = { researchVisible = !researchVisible }))
            Text(ui.instructions, color = KColors.Muted, fontSize = 14.sp)
            Spacer(Modifier.height(12.dp))
            if (active) {
                val state = button()
                WideButton(state.text, KColors.Accent, KColors.OnAccent, 48,
                    enabled = state.enabled, onClick = actions.toggle)
                Spacer(Modifier.height(8.dp))
            }
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                actions.openCaptureReview?.let { open ->
                    Text("저장한 촬영", color = KColors.Soft, fontSize = 14.sp,
                        modifier = Modifier.pressable { if (!active) open() }.padding(vertical = 10.dp))
                }
                if (researchVisible) actions.openSensorView?.let { open ->
                    Spacer(Modifier.width(20.dp))
                    Text("연구 모드 · 센서·3D", color = KColors.Soft, fontSize = 14.sp,
                        modifier = Modifier.pressable { if (!active) open() }.padding(vertical = 10.dp))
                }
            }
            Spacer(Modifier.height(6.dp))
        },
    )
}

// ---- Workout result --------------------------------------------------------

class ResultSectionUi(val title: String, val values: List<Pair<String, String>>, val repSeconds: List<Double> = emptyList())

class ResultUi(
    val title: String,
    val subtitle: String,
    val sections: List<ResultSectionUi>,
    val footnote: String,
    val records: List<RecordUi> = emptyList(),
    val sessionId: String? = null,
)

@Composable
fun WorkoutResultScreen(result: ResultUi, back: () -> Unit, toRecords: () -> Unit, summary: (@Composable () -> Unit)? = null,
    editableSets: List<Pair<String, Int>> = emptyList(), confirmReps: (Int, Int) -> Unit = { _, _ -> }) {
    DesignedWorkoutResult(result, back, toRecords, editableSets, confirmReps)
}

/** How long each repetition took, one bar per rep: the fastest in sage, the slowest in bone, the rest muted. */
@Composable
fun RepTempoBars(seconds: List<Double>, modifier: Modifier = Modifier) {
    val longest = seconds.max(); val shortest = seconds.min()
    // Bars span 35 to 100 percent of the height so small differences stay visible; the numbers below are the exact values.
    fun height(value: Double): Float = if (longest - shortest < 0.05) .7f else (.35 + .65 * (value - shortest) / (longest - shortest)).toFloat()
    val fastest = seconds.indices.minByOrNull { seconds[it] }
    val slowest = seconds.indices.maxByOrNull { seconds[it] }
    fun format(value: Double) = "%.1f초".format(java.util.Locale.US, value)
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().height(64.dp), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.Bottom) {
            seconds.forEachIndexed { index, value ->
                val color = when {
                    seconds.size < 2 -> KColors.Muted
                    index == slowest -> KColors.Accent
                    index == fastest -> KColors.Sage
                    else -> KColors.Muted.copy(alpha = .45f)
                }
                Box(Modifier.weight(1f).fillMaxHeight(height(value)).clip(RoundedCornerShape(2.dp)).background(color))
            }
        }
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth()) {
            Text("한 회 걸린 시간", color = KColors.Muted, fontSize = 12.sp, modifier = Modifier.weight(1f))
            Text("평균 ${format(seconds.average())}", color = KColors.White, fontSize = 12.sp)
        }
        if (seconds.size >= 2) {
            Spacer(Modifier.height(4.dp))
            Row(Modifier.fillMaxWidth()) {
                Text("가장 빠른 ${format(seconds[fastest!!])}", color = KColors.Sage, fontSize = 12.sp, modifier = Modifier.weight(1f))
                Text("가장 느린 ${format(seconds[slowest!!])}", color = KColors.Soft, fontSize = 12.sp)
            }
        }
    }
}
