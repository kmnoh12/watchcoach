package dev.kyungmin.watchcoach.phone

import dev.kyungmin.watchcoach.core.ExerciseHistoryCodec
import dev.kyungmin.watchcoach.core.ExerciseLog
import dev.kyungmin.watchcoach.core.LoggedSet
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ExerciseHistoryUnifyTest {
    private val context get() = RuntimeEnvironment.getApplication()
    private val prefs get() = context.getSharedPreferences("exercise-history", 0)
    @Before fun clear() { prefs.edit().clear().commit() }

    @Test fun oldPoundStackRecordsMoveToFiveKgOnceAndOtherEquipmentStays() {
        val logs = listOf(
            ExerciseLog("machine_shoulder_press", 1, listOf(LoggedSet(27.0, 10), LoggedSet(54.0, 8))),
            ExerciseLog("lat_pull_down", 1, listOf(LoggedSet(47.0, 10)), equipment = "머신"),
            ExerciseLog("incline_hammer_curl", 1, listOf(LoggedSet(12.5, 10))),
            ExerciseLog("flat_bench", 1, listOf(LoggedSet(72.5, 8))),
        )
        prefs.edit().putString("logs", ExerciseHistoryCodec.encode(logs)).commit()
        val weights = ExerciseHistoryStore(context).load().all.associate { log -> log.exerciseId to log.sets.map { it.weightKg } }
        assertEquals(listOf(25.0, 55.0), weights["machine_shoulder_press"])
        assertEquals(listOf(45.0), weights["lat_pull_down"])
        assertEquals(listOf(12.5), weights["incline_hammer_curl"])
        assertEquals(listOf(72.5), weights["flat_bench"])
        // Runs once: a later 27 kg entry (already past the migration) is kept as typed.
        ExerciseHistoryStore(context).add(ExerciseLog("machine_shoulder_press", 2, listOf(LoggedSet(27.0, 10))))
        assertEquals(listOf(27.0), ExerciseHistoryStore(context).load().all.last { it.epochDay == 2L }.sets.map { it.weightKg })
    }
}
