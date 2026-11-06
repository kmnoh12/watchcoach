package dev.kyungmin.kcoach.phone.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.layout
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

data class EditTarget(val exerciseIndex: Int, val setIndex: Int, val field: SetField)

private const val PRESS_MIN_MS = 90L
private const val PRESSED_SCALE = 0.86f

/** Edits apply live. The dial and the number keys drive the same value; the footer walks weight, then reps, then finishes. */
@Composable
fun WorkoutKeypad(
    setName: String,
    field: SetField,
    seconds: Boolean,
    usePounds: Boolean,
    alreadyDone: Boolean,
    value: TextFieldValue,
    onValueChange: (TextFieldValue) -> Unit,
    onRulerPick: (String) -> Unit,
    onDigit: (Char) -> Unit,
    onBackspace: () -> Unit,
    onUnit: (Boolean) -> Unit,
    onClose: () -> Unit,
    onGo: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val weight = field == SetField.WEIGHT
    Column(
        modifier.fillMaxWidth().background(KColors.Bg).padding(bottom = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(KColors.Hairline))
        Box(Modifier.fillMaxWidth().padding(horizontal = 12.dp), contentAlignment = Alignment.Center) {
            Column(Modifier.align(Alignment.CenterStart)) {
                Text(setName, color = KColors.Bone, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                Text(if (weight) "무게" else if (seconds) "시간" else "횟수", color = KColors.Soft, fontSize = 14.sp)
            }
            Hero(value, if (weight) (if (usePounds) "lb" else "kg") else if (seconds) "초" else "회", onValueChange)
            if (weight) UnitSwitch(usePounds, onUnit, Modifier.align(Alignment.CenterEnd))
        }
        SetValueRuler(value.text, weight, onRulerPick)
        NumberKeys(weight, onDigit, onBackspace)
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FootButton("닫기", KColors.SurfaceRaised, KColors.Bone, Modifier.weight(1f), onClose)
            val go = when {
                weight -> "다음 · ${if (seconds) "시간" else "횟수"}"
                alreadyDone -> "완료"
                else -> "$setName 완료"
            }
            FootButton(go, KColors.Accent, KColors.OnAccent, Modifier.weight(2.4f), onGo)
        }
    }
}

/** The big number stays centred under the needle; its unit hangs off the right edge of the digits. */
@Composable
private fun Hero(value: TextFieldValue, unit: String, onValueChange: (TextFieldValue) -> Unit) {
    val measurer = rememberTextMeasurer()
    val digitsWidth = measurer.measure(value.text, TextStyle(fontSize = HeroFontSize, fontWeight = FontWeight.Bold)).size.width
    val gap = with(LocalDensity.current) { 5.dp.roundToPx() }
    Box(contentAlignment = Alignment.Center) {
        SetValueField(value, onValueChange, SetValueLook.Hero, autoFocus = true, modifier = Modifier.width(170.dp).testTag("setValueHero"))
        Text(
            unit,
            color = KColors.Muted,
            fontSize = 15.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.align(Alignment.BottomCenter).layout { measurable, constraints ->
                val text = measurable.measure(constraints)
                layout(text.width, text.height) {
                    text.place(digitsWidth / 2 + gap + text.width / 2, -gap)
                }
            },
        )
    }
}

@Composable
private fun UnitSwitch(usePounds: Boolean, onUnit: (Boolean) -> Unit, modifier: Modifier) {
    Row(modifier.clip(KShape.Control).background(KColors.SurfaceRaised)) {
        listOf("kg" to false, "lb" to true).forEach { (text, pounds) ->
            val selected = pounds == usePounds
            Text(
                text,
                color = if (selected) KColors.Accent else KColors.Muted,
                fontSize = 13.sp,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                modifier = Modifier
                    .clip(KShape.Control)
                    .background(if (selected) KColors.AccentWash else Color.Transparent)
                    .clickable { if (!selected) onUnit(pounds) }
                    .padding(horizontal = 10.dp, vertical = 7.dp),
            )
        }
    }
}

@Composable
private fun NumberKeys(decimals: Boolean, onDigit: (Char) -> Unit, onBackspace: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp)) {
        KeyRow { Key("1") { onDigit('1') }; Key("2") { onDigit('2') }; Key("3") { onDigit('3') } }
        KeyRow { Key("4") { onDigit('4') }; Key("5") { onDigit('5') }; Key("6") { onDigit('6') } }
        KeyRow { Key("7") { onDigit('7') }; Key("8") { onDigit('8') }; Key("9") { onDigit('9') } }
        KeyRow {
            if (decimals) Key(".") { onDigit('.') } else Box(Modifier.weight(1f))
            Key("0") { onDigit('0') }
            Key("⌫", repeat = true) { onBackspace() }
        }
    }
}

@Composable
private fun KeyRow(content: @Composable RowScope.() -> Unit) {
    Row(Modifier.fillMaxWidth().height(58.dp), content = content)
}

/** Sinks fast and turns sage, then springs back past its size and settles while the sage fades. */
@Composable
private fun RowScope.Key(label: String, repeat: Boolean = false, onPress: () -> Unit) {
    val scope = rememberCoroutineScope()
    val view = LocalView.current
    val action = rememberUpdatedState(onPress)
    var pressed by remember { mutableStateOf(false) }
    val scale = remember { Animatable(1f) }
    val fill by animateColorAsState(
        if (pressed) KColors.Accent else KColors.Accent.copy(alpha = 0f),
        tween(if (pressed) 40 else 260),
        label = "key-fill",
    )
    val ink by animateColorAsState(if (pressed) KColors.OnAccent else KColors.Bone, tween(if (pressed) 40 else 260), label = "key-ink")
    Box(
        Modifier
            .weight(1f)
            .fillMaxHeight()
            .graphicsLayer { scaleX = scale.value; scaleY = scale.value }
            .clip(KShape.Control)
            .background(fill)
            .pointerInput(repeat) {
                detectTapGestures(onPress = {
                    pressed = true
                    val pressedAt = System.currentTimeMillis()
                    scope.launch { scale.animateTo(PRESSED_SCALE, tween(70)) }
                    view.keyTick()
                    action.value()
                    // Holding a repeat key keeps stepping, like a hardware key.
                    val job = if (repeat) scope.launch {
                        delay(420)
                        while (true) {
                            action.value()
                            delay(70)
                        }
                    } else null
                    tryAwaitRelease()
                    job?.cancel()
                    scope.launch {
                        delay((PRESS_MIN_MS - (System.currentTimeMillis() - pressedAt)).coerceAtLeast(0))
                        pressed = false
                        scale.animateTo(1f, spring(dampingRatio = 0.42f, stiffness = Spring.StiffnessMedium))
                    }
                })
            },
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = ink, fontSize = if (label == "⌫") 27.sp else 31.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun FootButton(text: String, fill: Color, ink: Color, modifier: Modifier, onClick: () -> Unit) {
    Box(
        modifier.height(56.dp).clip(KShape.Control).background(fill).clickable { onClick() },
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = ink, fontSize = 16.sp, fontWeight = FontWeight.Bold)
    }
}
