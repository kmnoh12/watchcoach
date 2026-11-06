package dev.kyungmin.kcoach.phone.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.selection.LocalTextSelectionColors
import androidx.compose.foundation.text.selection.TextSelectionColors
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.InterceptPlatformTextInput
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.awaitCancellation

/** Keypad edits applied to the Android text field's value, honouring its selection and caret. */
object SetValueEdit {
    private const val MAX_LENGTH = 6
    private val Whole = Regex("\\d*")
    private val Decimal = Regex("\\d*\\.?\\d*")

    fun selectAll(text: String) = TextFieldValue(text, TextRange(0, text.length))

    fun type(value: TextFieldValue, c: Char): TextFieldValue {
        val start = value.selection.min
        val base = value.text.removeRange(start, value.selection.max)
        if (c == '.' && '.' in base) return value
        if (base == "0" && start == 1 && c != '.') return TextFieldValue(c.toString(), TextRange(1))
        val next = base.substring(0, start) + c + base.substring(start)
        return if (next.length > MAX_LENGTH) value else TextFieldValue(next, TextRange(start + 1))
    }

    fun backspace(value: TextFieldValue): TextFieldValue {
        val start = value.selection.min
        val end = value.selection.max
        if (start != end) return TextFieldValue(value.text.removeRange(start, end), TextRange(start))
        if (start == 0) return value
        return TextFieldValue(value.text.removeRange(start - 1, start), TextRange(start - 1))
    }

    /** Selection changes pass through; system paste only lands if it is still a number. */
    fun accept(current: TextFieldValue, incoming: TextFieldValue, decimals: Boolean): TextFieldValue {
        if (incoming.text == current.text) return incoming
        val valid = incoming.text.length <= MAX_LENGTH && (if (decimals) Decimal else Whole).matches(incoming.text)
        return if (valid) incoming else current
    }
}

private val SetValueSelection = TextSelectionColors(
    handleColor = KColors.White,
    backgroundColor = KColors.OnAccent.copy(alpha = 0.24f),
)

/**
 * The stock Android text field, so selection, caret and handles are the system's own.
 * Only the system keyboard is held back, because the in-screen keypad does the typing.
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun SetValueField(value: TextFieldValue, onValueChange: (TextFieldValue) -> Unit, modifier: Modifier = Modifier) {
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { focus.requestFocus() }
    CompositionLocalProvider(LocalTextSelectionColors provides SetValueSelection) {
        InterceptPlatformTextInput(interceptor = { _, _ -> awaitCancellation() }) {
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = modifier.fillMaxWidth().focusRequester(focus),
                singleLine = true,
                textStyle = TextStyle(color = KColors.OnAccent, fontSize = 18.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center),
                cursorBrush = SolidColor(KColors.OnAccent),
            )
        }
    }
}
