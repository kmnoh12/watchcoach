package dev.kyungmin.watchcoach.phone.ui

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.TweenSpec
import androidx.compose.animation.core.tween
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/**
 * One motion language for the whole app: large panels move with a 300ms
 * easeInOutCirc, small state changes with a 200ms easeInOut, and numbers roll
 * linearly. Springs and bounces are deliberately not used, except in the bottom tab bar.
 */
object Motion {
    val PanelEasing = CubicBezierEasing(0.785f, 0.135f, 0.15f, 0.86f)
    val UiEasing = CubicBezierEasing(0.42f, 0f, 0.58f, 1f)
    val PageEasing = CubicBezierEasing(0.25f, 0.1f, 0.25f, 1f)

    const val PANEL_MS = 300
    const val UI_MS = 200
    const val DIGIT_MS = 180
    const val PAGE_MS = 300
    const val RING_INTRO_MS = 900

    fun <T> panel(): TweenSpec<T> = tween(PANEL_MS, easing = PanelEasing)
    fun <T> ui(): TweenSpec<T> = tween(UI_MS, easing = UiEasing)

    /**
     * A spring written the way the reference motion kit writes it: stiffness and damping, mass 1
     * (Compose takes the damping as a ratio, c / (2 * sqrt(k))).
     */
    fun <T> spring(stiffness: Float, damping: Float): androidx.compose.animation.core.SpringSpec<T> =
        androidx.compose.animation.core.spring(dampingRatio = damping / (2f * kotlin.math.sqrt(stiffness)), stiffness = stiffness)

    /**
     * Bottom tab bar springs (the only place springs are used). One spring moves the pill whether a finger holds it or
     * has let go, so there is no second bounce when the finger lifts.
     */
    fun <T> pillSettle(): androidx.compose.animation.core.SpringSpec<T> = spring(1000f, 52f)
    /** A tab's name opening or closing. */
    fun <T> labelOpen(): androidx.compose.animation.core.SpringSpec<T> = spring(520f, 36f)
    /** The icon dipping a little and coming back once when its tab is picked. */
    fun <T> iconPop(): androidx.compose.animation.core.SpringSpec<T> = spring(480f, 22f)
    /** The selected button squashing under a finger that presses it again, and springing back. */
    fun <T> pressSquash(): androidx.compose.animation.core.SpringSpec<T> = spring(600f, 22f)
    fun <T> page(): TweenSpec<T> = tween(PAGE_MS, easing = PageEasing)
    fun <T> digit(): TweenSpec<T> = tween(DIGIT_MS, easing = LinearEasing)
}

object KColors {
    val Bg = Color(0xFF000000)
    val Surface = Color(0xFF151617)
    val SurfaceRaised = Color(0xFF212326)
    val Selected = Color(0xFF2D2F33)
    /** Bone: body text, and anything already done or in the past (workout days, past records). */
    val Bone = Color(0xFFF1F4F6)
    val White = Bone
    val Muted = Color(0xFF8B9095)
    val Soft = Color(0xFFB9BEC3)
    val Faint = Color(0xFF54585C)
    val Hairline = Color(0xFF272A2D)
    /** Sage: the lead colour for actions and state (primary buttons, today, current set, progress). */
    val Accent = Color(0xFF63D6DE)
    val Sage = Accent
    val OnAccent = Color(0xFF04140E)
    val AccentWash = Color(0xFF0B2A2D)
    val Red = Color(0xFFE5483B)
    /** Red with a touch of coral: the filled destructive button (end without saving), white text on top. */
    val DangerFill = Color(0xFFF0594B)
}

/** Radii: slightly rounded rectangles, never pills. */
object KShape {
    val Control = androidx.compose.foundation.shape.RoundedCornerShape(6.dp)
    val Panel = androidx.compose.foundation.shape.RoundedCornerShape(10.dp)
    val Sheet = androidx.compose.foundation.shape.RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp)
}
