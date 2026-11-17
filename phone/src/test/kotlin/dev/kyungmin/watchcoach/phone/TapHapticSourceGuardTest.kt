package dev.kyungmin.watchcoach.phone

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TapHapticSourceGuardTest {
    private data class AllowedCall(val file: String, val line: String, val count: Int, val reason: String)

    // Exact call lines and counts are allowed, never a whole screen or file.
    private val allowed = listOf(
        AllowedCall("ui/RootScreens.kt",
            "this.clickable(enabled = enabled, onClickLabel = onClickLabel, role = role, onClick = tapAction(onClick))", 1,
            "The default clickable helper wraps its callback with the common tick."),
        AllowedCall("ui/RootScreens.kt",
            "this.clickable(interactionSource = interactionSource, indication = indication, enabled = enabled,", 1,
            "The explicit indication/source overload preserves caller parameters and wraps the callback."),
        AllowedCall("ui/RootScreens.kt",
            "this.toggleable(value, interactionSource, indication, enabled, role, tapToggleChange(onValueChange))", 1,
            "Only user toggle callbacks tick, never recomposition or a state assignment."),
        AllowedCall("ui/RootScreens.kt",
            "this.selectable(selected, enabled = enabled, role = role, onClick = tapAction(onClick))", 1,
            "Selection retains its accessibility role and wraps its click callback."),
        AllowedCall("ui/RootScreens.kt",
            "return this.combinedClickable(enabled = enabled, onClickLabel = onClickLabel, role = role,", 1,
            "The long-click helper gives short taps one tick and long presses one firmer haptic."),
        AllowedCall("ui/RootScreens.kt",
            "return this.combinedClickable(interactionSource = interactionSource, indication = indication,", 1,
            "The press-shrink variant keeps its interaction source and existing long-press haptic."),
        AllowedCall("ui/Overlays.kt",
            ".clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) {}", 2,
            "SheetSurface and DialogSurface only consume panel-background taps. Both are commented as intentionally silent."),
        AllowedCall("ui/StatsCharts.kt",
            ".clickable(role = Role.Button) { move(0) }.padding(horizontal = 12.dp, vertical = 7.dp))", 1,
            "The commented Now action already ticks in move(). A second tap tick would duplicate it."),
        AllowedCall("TapHaptics.kt", "setOnClickListener { view ->", 1,
            "The classic View helper supplies exactly one common tick and checks enabled state."),
        AllowedCall("TapHaptics.kt",
            "setPositiveButton(text) { dialog, which -> dialog.tapHaptic(); listener?.onClick(dialog, which) }", 1,
            "The dialog helper supplies the tick and preserves automatic dismissal."),
        AllowedCall("TapHaptics.kt",
            "setNegativeButton(text) { dialog, which -> dialog.tapHaptic(); listener?.onClick(dialog, which) }", 1,
            "Cancel also ticks when its original listener is null."),
        AllowedCall("TapHaptics.kt",
            "setItems(items) { dialog, which -> dialog.tapHaptic(); listener.onClick(dialog, which) }", 1,
            "Native dialog list-item callbacks supply their own common tick."),
        AllowedCall("TapHaptics.kt",
            "setMultiChoiceItems(items, checked) { dialog, which, value -> dialog.tapHaptic(); listener.onClick(dialog, which, value) }", 1,
            "Native dialog checkbox callbacks supply their own common tick."),
    )

    private val rawControl = Regex(
        """\.\s*clickable\s*(?:\(|\{)|\b(?:combinedClickable|toggleable|triStateToggleable|selectable)\s*\(|\bsetOnClickListener\s*(?:\(|\{)|\bset(?:PositiveButton|NegativeButton|NeutralButton|Items|SingleChoiceItems|MultiChoiceItems)\s*\(""",
    )
    private val nonCode = Regex(
        "\"\"\"[\\s\\S]*?\"\"\"|\"(?:\\\\.|[^\"\\\\])*\"|'(?:\\\\.|[^'\\\\])*'|/\\*[\\s\\S]*?\\*/|//[^\\n]*",
    )

    private fun codeOnly(source: String) = nonCode.replace(source) { match ->
        match.value.map { if (it == '\n') '\n' else ' ' }.joinToString("")
    }

    private fun sourceRoot(): File {
        val path = "src/main/kotlin/dev/kyungmin/watchcoach/phone"
        return listOf(File(path), File("phone/$path")).first { it.isDirectory }
    }

    @Test fun everyRawInteractionUsesAnExplainedExactAllowlistEntry() {
        val root = sourceRoot()
        val seen = mutableMapOf<AllowedCall, Int>()
        val violations = mutableListOf<String>()
        val sources = root.walkTopDown().filter { it.extension == "kt" }.toList()
        assertTrue("No phone sources scanned", sources.isNotEmpty())
        for (file in sources) {
            val path = file.relativeTo(root).invariantSeparatorsPath
            val text = file.readText()
            val lines = text.lines()
            for (match in rawControl.findAll(codeOnly(text))) {
                val index = text.take(match.range.first).count { it == '\n' }
                val entry = allowed.singleOrNull { it.file == path && it.line == lines[index].trim() }
                if (entry == null) violations += "$path:${index + 1} ${lines[index].trim()}"
                else seen[entry] = seen.getOrDefault(entry, 0) + 1
            }
        }
        assertTrue("Use the haptic helpers or justify a precise exception:\n${violations.joinToString("\n")}", violations.isEmpty())
        for (entry in allowed) assertEquals(entry.reason, entry.count, seen.getOrDefault(entry, 0))
    }

    @Test fun guardRecognizesMultilineAndEveryRequestedModifier() {
        val controls = listOf(".clickable {}", ".clickable\n(enabled = false) {}", ".combinedClickable(onClick = {})",
            ".toggleable(true) {}", ".selectable(true) {}", ".triStateToggleable(state) {}", "setOnClickListener {}")
        for (control in controls) assertTrue(control, rawControl.containsMatchIn(codeOnly(control)))
        assertTrue(rawControl.findAll(codeOnly("// .clickable {}\nval label = \"combinedClickable()\" ")).none())
    }

    @Test fun materialButtonsAndCheckboxesKeepTheirHapticCallbacks() {
        val violations = mutableListOf<String>()
        for (file in sourceRoot().walkTopDown().filter { it.extension == "kt" }) {
            val text = codeOnly(file.readText())
            val buttons = Regex("""\b(?:Button|TextButton|OutlinedButton|IconButton|FilledTonalButton)\s*\(\s*onClick\s*=\s*(\w+|\{)""")
            for (match in buttons.findAll(text)) {
                if (match.groupValues[1] != "tapAction") violations += "${file.name}: ${match.value}"
            }
            val checks = Regex("""\b(?:Checkbox|Switch|RadioButton)\s*\([^,]+,\s*(?:onCheckedChange\s*=\s*|onClick\s*=\s*)?(\w+|\{)""")
            for (match in checks.findAll(text)) {
                if (match.groupValues[1] !in setOf("tapValueChange", "tapAction", "null")) violations += "${file.name}: ${match.value}"
            }
        }
        assertTrue(violations.joinToString("\n"), violations.isEmpty())
    }
}
