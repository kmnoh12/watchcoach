package dev.kyungmin.kcoach.phone.ui

import android.graphics.Paint
import android.graphics.Typeface
import android.os.Build
import android.view.HapticFeedbackConstants
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import dev.kyungmin.kcoach.core.BodyLoad
import dev.kyungmin.kcoach.core.StatsAnalytics
import dev.kyungmin.kcoach.phone.Exercise3DView
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.*

internal fun statsNumber(value: Double): String = String.format(Locale.KOREA, "%,.0f", value)
private fun weightNumber(value: Double): String = if (value == floor(value)) statsNumber(value) else String.format(Locale.KOREA, "%,.1f", value)
private fun kilos(value: Double): String = String.format(Locale.KOREA, "%.1fk", value / 1000)

@Composable
internal fun StatsHeading(title: String, days: Int? = null, onPeriod: (Int) -> Unit = {}, trailing: String? = null) {
    Spacer(Modifier.height(28.dp))
    Row(Modifier.fillMaxWidth().padding(bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, color = KColors.Muted, fontSize = 13.sp, modifier = Modifier.weight(1f))
        val tick = rememberTapHaptic()
        if (days != null) Row(Modifier.selectableGroup(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            listOf(7, 30, 90, 0).forEach { period ->
                val selected = days == period
                Box(Modifier.clip(KShape.Control)
                    .background(if (selected) KColors.AccentWash else KColors.Surface)
                    .border(1.dp, if (selected) KColors.Accent else Color.Transparent, KShape.Control)
                    .selectable(selected, role = Role.RadioButton, onClick = { if (!selected) tick(); onPeriod(period) })
                    .padding(horizontal = 11.dp, vertical = 7.dp)) {
                    Text(if (period == 0) "전체" else "${period}일", fontSize = 13.sp,
                        color = if (selected) KColors.Accent else KColors.Muted,
                        fontWeight = if (selected) FontWeight.Medium else FontWeight.Normal)
                }
            }
        }
        if (trailing != null) Text(trailing, color = KColors.Muted, fontSize = 13.sp)
    }
    Box(Modifier.fillMaxWidth().height(0.5.dp).background(KColors.Hairline))
}

@Composable
internal fun StatsFatigue(ui: StatsUi) {
    var step by remember(ui) { mutableStateOf(0) }
    val view = LocalView.current
    val at = ui.nowMs + step * 3 * 3_600_000L
    val fatigue = remember(ui, at) { BodyLoad.fatigueByPartAt(ui.history, ui.weights::get, at) }
    val top = fatigue.entries.filter { it.value >= 0.08 }.sortedByDescending { it.value }.take(3)
        .joinToString(" · ") { it.key.replace("어깨", " 어깨") }
    val hours = abs(step * 3)
    val span = (if (hours >= 24) "${hours / 24}일 " else "") + (if (hours % 24 > 0) "${hours % 24}시간 " else "")
    val date = Instant.ofEpochMilli(at).atZone(ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("M월 d일 (E) H시", Locale.KOREAN))
    fun move(next: Int) {
        if (next == step) return
        step = next
        view.performHapticFeedback(if (Build.VERSION.SDK_INT >= 34) HapticFeedbackConstants.SEGMENT_FREQUENT_TICK
            else HapticFeedbackConstants.CLOCK_TICK)
    }
    Spacer(Modifier.height(6.dp))
    AndroidView(factory = { Exercise3DView(it, "", "human_stats.html", android.graphics.Color.BLACK) },
        update = { it.setFatigue(fatigue) },
        modifier = Modifier.fillMaxWidth().aspectRatio(1.43f).clip(KShape.Panel)
            .semantics { contentDescription = "근육 피로도 3D 인체, 두 모델을 각각 좌우로 회전" })
    Text(if (top.isEmpty()) "모두 회복" else (if (step > 0) "회복 중 · " else "") + top,
        color = KColors.White, fontSize = 16.sp, fontWeight = FontWeight.Medium, textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp))
    Text("$date · " + if (step == 0) "지금" else span + if (step > 0) "뒤" else "전",
        color = KColors.Muted, fontSize = 13.sp, textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth().padding(top = 3.dp))
    Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.weight(1f)) {
            Slider(value = step.toFloat(), onValueChange = { move(it.roundToInt().coerceIn(-32, 32)) },
                valueRange = -32f..32f, steps = 63,
                colors = SliderDefaults.colors(thumbColor = KColors.Accent, activeTrackColor = KColors.Accent,
                    inactiveTrackColor = KColors.Selected, activeTickColor = Color.Transparent, inactiveTickColor = Color.Transparent),
                modifier = Modifier.fillMaxWidth().height(28.dp).semantics { contentDescription = "시각, 지금 기준 앞뒤 4일을 3시간 간격으로" })
            Row(Modifier.fillMaxWidth().padding(top = 2.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                listOf("4일 전", "지금", "4일 뒤").forEach { Text(it, color = KColors.Faint, fontSize = 11.sp) }
            }
        }
        Text("지금", color = KColors.Accent, fontSize = 13.sp,
            modifier = Modifier.clip(KShape.Control).background(KColors.Surface)
                .clickable(role = Role.Button) { move(0) }.padding(horizontal = 12.dp, vertical = 7.dp))
    }
}

@Composable
internal fun StatsWeekSummary(current: List<Double>, previous: List<Double>) {
    val day = current.lastIndex
    val delta = current.last() - previous[day]
    val weekday = listOf("월", "화", "수", "목", "금", "토", "일")[day]
    Text(buildAnnotatedString {
        append("이번 주 ")
        withStyle(SpanStyle(color = KColors.White, fontWeight = FontWeight.Medium)) { append("${statsNumber(current.last())}kg") }
        append(", 지난주 ${weekday}요일까지보다 ")
        withStyle(SpanStyle(color = KColors.Accent, fontWeight = FontWeight.Medium)) {
            append("${statsNumber(abs(delta))}kg ${if (delta >= 0) "더" else "덜"}")
        }
        append(" 들었어요")
    }, color = KColors.Soft, fontSize = 15.sp, lineHeight = 22.5.sp,
        modifier = Modifier.padding(top = 12.dp, bottom = 10.dp))
}

private fun niceMax(value: Double): Double {
    if (value <= 0 || !value.isFinite()) return 1000.0
    val step = 10.0.pow(floor(log10(value)))
    return listOf(1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
        .first { it * step >= value } * step
}

private fun DrawScope.label(text: String, x: Float, y: Float, color: Color = KColors.Muted,
                            textSize: Float = 10.5f, align: Paint.Align = Paint.Align.CENTER, medium: Boolean = false) {
    val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = color.toArgb(); this.textSize = textSize; textAlign = align
        typeface = Typeface.create(if (medium) "sans-serif-medium" else "sans-serif", Typeface.NORMAL)
    }
    drawIntoCanvas { it.nativeCanvas.drawText(text, x, y, paint) }
}

private fun smooth(points: List<Offset>): Path = Path().apply {
    moveTo(points[0].x, points[0].y)
    for (i in 0 until points.lastIndex) {
        val a = points.getOrElse(i - 1) { points[i] }; val b = points[i]
        val c = points[i + 1]; val d = points.getOrElse(i + 2) { c }
        cubicTo(b.x + (c.x - a.x) / 6, b.y + (c.y - a.y) / 6,
            c.x - (d.x - b.x) / 6, c.y - (d.y - b.y) / 6, c.x, c.y)
    }
}

@Composable
internal fun StatsWeekChart(current: List<Double>, previous: List<Double>) {
    Canvas(Modifier.fillMaxWidth().aspectRatio(360f / 190).semantics {
        contentDescription = "요일별 누적 볼륨. 이번 주 ${current.joinToString { statsNumber(it) }}kg. 지난주 ${previous.joinToString { statsNumber(it) }}kg"
    }) {
        scale(size.width / 360, size.height / 190, Offset.Zero) {
            val max = niceMax(maxOf(current.last(), previous.last()) * 1.05)
            fun x(i: Int) = 36f + 310f * i / 6
            fun y(v: Double) = (164 - 152 * v / max).toFloat()
            for (g in 0..3) {
                val v = max * g / 3
                drawLine(KColors.Selected, Offset(36f, y(v)), Offset(346f, y(v)), 0.6f)
                label(if (g == 0) "0" else kilos(v), 30f, y(v) + 3.5f, align = Paint.Align.RIGHT)
            }
            listOf("월", "화", "수", "목", "금", "토", "일").forEachIndexed { i, day ->
                label(day, x(i), 184f, if (i == current.lastIndex) KColors.White else KColors.Muted)
            }
            val last = previous.mapIndexed { i, v -> Offset(x(i), y(v)) }
            val now = current.mapIndexed { i, v -> Offset(x(i), y(v)) }
            drawPath(smooth(last), KColors.Faint.copy(alpha = 0.65f), style = Stroke(2f, cap = StrokeCap.Round))
            val area = smooth(now).apply { lineTo(now.last().x, y(0.0)); lineTo(now.first().x, y(0.0)); close() }
            drawPath(area, Brush.verticalGradient(listOf(KColors.Accent.copy(alpha = 0.34f), Color.Transparent), 12f, 164f))
            drawPath(smooth(now), KColors.Accent, style = Stroke(2.6f, cap = StrokeCap.Round))
            drawCircle(KColors.Bg, 4.5f, now.last())
            drawCircle(KColors.Accent, 4.5f, now.last(), style = Stroke(2.4f))
        }
    }
}

@Composable
internal fun StatsLegend(current: String, previous: String?) {
    Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        listOfNotNull(current to KColors.Accent, previous?.let { it to KColors.Faint }).forEach { (text, color) ->
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Box(Modifier.size(14.dp, 3.dp).background(color, KShape.Control))
                Text(text, color = KColors.Muted, fontSize = 12.sp)
            }
        }
    }
}

private fun polygon(points: List<Offset>) = Path().apply {
    moveTo(points.first().x, points.first().y)
    points.drop(1).forEach { lineTo(it.x, it.y) }; close()
}

@Composable
internal fun StatsRadarChart(current: List<Double>, previous: List<Double>, compare: Boolean) {
    val max = niceMax(maxOf(current.maxOrNull() ?: 0.0, previous.maxOrNull() ?: 0.0) * 1.05)
    val animated = (current + previous).mapIndexed { i, v ->
        val value by animateFloatAsState((v / max).toFloat(), tween(520), label = "radar$i")
        value
    }
    Canvas(Modifier.fillMaxWidth().aspectRatio(360f / 300).semantics {
        contentDescription = "부위별 볼륨. " + StatsAnalytics.GROUPS.mapIndexed { i, name ->
            "$name ${statsNumber(current[i])}kg" + if (compare) ", 직전 기간 ${statsNumber(previous[i])}kg" else ""
        }.joinToString(". ")
    }) {
        scale(size.width / 360, size.height / 300, Offset.Zero) {
            fun point(i: Int, v: Float): Offset {
                val angle = -PI / 2 + 2 * PI * i / 6
                return Offset(180 + cos(angle).toFloat() * 100 * v, 152 + sin(angle).toFloat() * 100 * v)
            }
            listOf(1f / 3, 2f / 3, 1f).forEach { r ->
                drawPath(polygon(List(6) { point(it, r) }), KColors.Selected, style = Stroke(0.8f))
            }
            StatsAnalytics.GROUPS.forEachIndexed { i, name ->
                drawLine(KColors.Selected, Offset(180f, 152f), point(i, 1f), 0.6f)
                val p = point(i, 1.24f)
                label(name, p.x, p.y, KColors.White, 12.5f, medium = true)
                label(kilos(current[i]), p.x, p.y + 14, textSize = 11f)
            }
            if (compare) {
                val old = polygon(List(6) { point(it, animated[it + 6]) })
                drawPath(old, KColors.Faint.copy(alpha = 0.18f))
                drawPath(old, KColors.Muted.copy(alpha = 0.75f), style = Stroke(1.4f))
            }
            val points = List(6) { point(it, animated[it]) }
            drawPath(polygon(points), KColors.Accent.copy(alpha = 0.24f))
            drawPath(polygon(points), KColors.Accent, style = Stroke(2f, join = StrokeJoin.Round))
            points.forEach { drawCircle(KColors.Accent, 3.2f, it) }
        }
    }
}

@Composable
internal fun StatsRecords(records: List<StatsAnalytics.Record>, names: Map<String, String>, today: Long) {
    if (records.isEmpty()) Text("아직 새 기록 없음", color = KColors.Muted, fontSize = 13.sp, modifier = Modifier.padding(vertical = 14.dp))
    records.forEach { record ->
        val best = record.best; val previous = record.previous
        val kg = requireNotNull(best.weightKg); val oldKg = requireNotNull(previous.weightKg)
        val delta = when {
            kg == oldKg -> "+${best.reps - previous.reps}회"
            best.reps == previous.reps -> "+${weightNumber(kg - oldKg)}kg"
            else -> "+${weightNumber(kg * best.reps - oldKg * previous.reps)}kg·회"
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.weight(1f)) {
                Text(names[record.exerciseId] ?: record.exerciseId, color = KColors.Soft, fontSize = 15.sp)
                Text(if (record.epochDay == today) "오늘" else "${today - record.epochDay}일 전",
                    color = KColors.Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 2.dp))
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("${weightNumber(kg)}kg × ${best.reps}", color = KColors.White, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                Text(delta, color = KColors.Accent, fontSize = 12.sp)
            }
        }
        Box(Modifier.fillMaxWidth().height(0.5.dp).background(KColors.Hairline))
    }
}
