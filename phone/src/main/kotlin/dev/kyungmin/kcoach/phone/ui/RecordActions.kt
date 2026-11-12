package dev.kyungmin.kcoach.phone.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** One tappable action of the record menu; [destructive] draws it in red. */
class RecordMenuItem(val label: String, val destructive: Boolean = false)

/** Bottom sheet opened by the three dots of a record row. */
@Composable
fun RecordMenuSheet(title: String, items: List<RecordMenuItem>, onSelect: (Int) -> Unit) {
    Column(Modifier.padding(bottom = 16.dp)) {
        Text(title, color = KColors.White, fontSize = 20.sp, fontWeight = FontWeight.Medium, maxLines = 1,
            modifier = Modifier.padding(start = 22.dp, end = 22.dp, bottom = 12.dp))
        items.forEachIndexed { index, item ->
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 22.dp, vertical = 3.dp).clip(KShape.Control)
                    .background(KColors.SurfaceRaised).pressable { onSelect(index) }.padding(horizontal = 14.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(item.label, color = if (item.destructive) KColors.Red else KColors.White, fontSize = 16.sp, fontWeight = FontWeight.Medium)
            }
        }
    }
}

/** A completed set of a finished record, as typed text so a half-typed number is never rejected. */
class RecordEditRow(
    val exerciseIndex: Int,
    val setIndex: Int,
    val exerciseName: String,
    val label: String,
    val showsWeight: Boolean,
    weight: String,
    reps: String,
) {
    var weight by mutableStateOfText(weight)
    var reps by mutableStateOfText(reps)
}

private fun mutableStateOfText(initial: String) = androidx.compose.runtime.mutableStateOf(initial)

@Composable
fun RecordEditSheet(title: String, rows: List<RecordEditRow>, note: String?, onSave: () -> Unit, onCancel: () -> Unit) {
    Column(Modifier.imePadding().heightIn(max = 560.dp)) {
        Text(title, color = KColors.White, fontSize = 20.sp, fontWeight = FontWeight.Medium, maxLines = 1,
            modifier = Modifier.padding(start = 22.dp, end = 22.dp, bottom = 8.dp))
        Column(Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()).padding(horizontal = 22.dp)) {
            var last = -1
            rows.forEach { row ->
                if (row.exerciseIndex != last) {
                    last = row.exerciseIndex
                    Text(row.exerciseName, color = KColors.Soft, fontSize = 14.sp, fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(top = 12.dp, bottom = 4.dp))
                }
                Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(row.label, color = KColors.Muted, fontSize = 14.sp, modifier = Modifier.width(52.dp))
                    if (row.showsWeight) {
                        RecordNumberField(row.weight, KeyboardType.Decimal, Modifier.weight(1f)) { row.weight = it }
                        Text("kg", color = KColors.Muted, fontSize = 13.sp, modifier = Modifier.padding(start = 6.dp, end = 12.dp))
                    } else Spacer(Modifier.weight(1f))
                    RecordNumberField(row.reps, KeyboardType.Number, Modifier.weight(1f)) { row.reps = it }
                    Text("회", color = KColors.Muted, fontSize = 13.sp, modifier = Modifier.padding(start = 6.dp))
                }
            }
            if (note != null) Text(note, color = KColors.Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 14.dp))
        }
        Row(Modifier.fillMaxWidth().padding(22.dp, 14.dp, 22.dp, 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1f).height(48.dp).clip(KShape.Control).background(KColors.SurfaceRaised).pressable(onCancel), contentAlignment = Alignment.Center) {
                Text("취소", color = KColors.White, fontSize = 16.sp, fontWeight = FontWeight.Medium)
            }
            Box(Modifier.weight(1f).height(48.dp).clip(KShape.Control).background(KColors.Accent).pressable(onSave), contentAlignment = Alignment.Center) {
                Text("저장", color = KColors.OnAccent, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}

@Composable
private fun RecordNumberField(value: String, type: KeyboardType, modifier: Modifier, onChange: (String) -> Unit) {
    BasicTextField(
        value = value,
        onValueChange = { incoming ->
            val clean = incoming.filter { it.isDigit() || (type == KeyboardType.Decimal && it == '.') }.take(7)
            if (clean.count { it == '.' } <= 1) onChange(clean)
        },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = type),
        textStyle = TextStyle(color = KColors.White, fontSize = 16.sp, fontWeight = FontWeight.Medium, textAlign = TextAlign.Center),
        cursorBrush = SolidColor(KColors.Accent),
        modifier = modifier,
        decorationBox = { inner ->
            Box(Modifier.fillMaxWidth().clip(KShape.Control).background(KColors.SurfaceRaised).padding(vertical = 10.dp), contentAlignment = Alignment.Center) { inner() }
        },
    )
}
