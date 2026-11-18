package dev.kyungmin.watchcoach.phone

import android.content.Context

/** Three rest tiers. LARGE and SMALL keep their old preference keys, so a rest time the user already chose survives. */
internal enum class RestMuscleGroup(val label: String, val hint: String, val defaultSeconds: Int, val preferenceKey: String) {
    HEAVY("고중량 복합", "벤치·T바 로우·스쿼트·레그 프레스 등", 180, "heavyCompoundRestSeconds"),
    LARGE("대근육", "그 외 가슴·등·하체 (체스트 프레스, 풀다운 등)", 120, "largeMuscleRestSeconds"),
    SMALL("소근육", "팔·어깨·복근 등", 90, "smallMuscleRestSeconds"),
}

internal object DefaultRestSetting {
    val choices = listOf(30, 45, 60, 90, 120, 150, 180)

    fun seconds(context: Context, group: RestMuscleGroup): Int =
        context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE)
            .getInt(group.preferenceKey, group.defaultSeconds)

    fun save(context: Context, group: RestMuscleGroup, seconds: Int): Boolean =
        seconds in choices && context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE)
            .edit().putInt(group.preferenceKey, seconds).commit()

    private const val TIERS_APPLIED_KEY = "restTiersAppliedV2"

    /**
     * One-time lift for routines saved before the three tiers: every exercise rests at least its tier's time.
     * Never lowers a rest. [save] persists the changed routines; the flag is set only once that succeeded.
     */
    fun liftSavedRoutines(context: Context, routines: List<WorkoutRoutine>, save: () -> Boolean) {
        val prefs = context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE)
        if (prefs.getBoolean(TIERS_APPLIED_KEY, false)) return
        val changed = liftRests(routines) { exercise ->
            if (exercise.pattern == "rotation") ExerciseDefaults.restSeconds(exercise) else seconds(context, ExerciseDefaults.restGroup(exercise))
        }
        if (!changed || save()) prefs.edit().putBoolean(TIERS_APPLIED_KEY, true).commit()
    }

    /**
     * Raises each exercise's rest to [floor] when below it; returns whether anything changed.
     */
    internal fun liftRests(routines: List<WorkoutRoutine>, floor: (ExerciseDefinition) -> Int): Boolean {
        var changed = false
        routines.forEach { routine -> routine.exercises.forEach { item ->
            val target = floor(item.exercise)
            if (item.restSeconds < target) { item.restSeconds = target; changed = true }
        } }
        return changed
    }
}
