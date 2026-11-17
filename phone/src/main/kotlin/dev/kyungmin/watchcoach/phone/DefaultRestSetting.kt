package dev.kyungmin.watchcoach.phone

import android.content.Context

internal enum class RestMuscleGroup(val label: String, val defaultSeconds: Int, val preferenceKey: String) {
    LARGE("대근육", 120, "largeMuscleRestSeconds"),
    SMALL("소근육", 90, "smallMuscleRestSeconds"),
}

internal object DefaultRestSetting {
    val choices = listOf(30, 45, 60, 90, 120, 150, 180)

    fun seconds(context: Context, group: RestMuscleGroup): Int =
        context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE)
            .getInt(group.preferenceKey, group.defaultSeconds)

    fun save(context: Context, group: RestMuscleGroup, seconds: Int): Boolean =
        seconds in choices && context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE)
            .edit().putInt(group.preferenceKey, seconds).commit()
}
