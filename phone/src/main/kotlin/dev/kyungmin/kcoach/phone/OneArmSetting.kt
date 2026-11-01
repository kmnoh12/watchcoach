package dev.kyungmin.kcoach.phone

import android.content.Context
import dev.kyungmin.kcoach.core.UnilateralFirstSidePolicy

/** One app-wide preference, read at first-arm completion; never finishes an already pending other arm. */
internal object OneArmSetting {
    fun isEnabled(context: Context): Boolean =
        context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE).getBoolean("oneArmOnly", false)

    fun setEnabled(context: Context, enabled: Boolean): Boolean =
        context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE).edit().putBoolean("oneArmOnly", enabled).commit()

    fun policy(context: Context): UnilateralFirstSidePolicy = if (isEnabled(context))
        UnilateralFirstSidePolicy.WATCH_SIDE_ONLY else UnilateralFirstSidePolicy.BOTH_SIDES
}
