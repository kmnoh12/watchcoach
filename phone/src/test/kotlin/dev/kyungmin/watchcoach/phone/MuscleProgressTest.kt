package dev.kyungmin.watchcoach.phone

import dev.kyungmin.watchcoach.core.*
import dev.kyungmin.watchcoach.phone.ui.summaryLine
import org.junit.Assert.*
import org.junit.Test

class MuscleProgressTest {
    private val catalog = WorkoutData.catalog.associateBy { it.id }
    private val press = "machine_chest_press_plate"
    private val fly = "machine_fly"
    private fun set(id: String, kg: Double?, reps: Int? = 8, type: String = "NORMAL") =
        PlannedSetSnapshot(0, id, 0, 8, kg, true, type, performedReps = reps)
    private fun session(time: Long, vararg sets: PlannedSetSnapshot) = WorkoutSnapshot(
        sessionId = "s$time", startedAtMs = time, routineId = "routine$time", exerciseIndex = 0, setIndex = 0,
        plannedSets = sets.toList(), performedReps = emptyMap(), phase = WorkoutPhase.WORKING,
        restEndAtMs = 0, pausedRestRemainingMs = 0, paused = false, pausedSinceMs = 0,
        totalPausedMs = 0, lastSequence = 0, lastCompletedSetKey = null, captureStates = emptyMap())
    private fun compare(now: WorkoutSnapshot, vararg history: WorkoutSnapshot) =
        muscleProgress(now, history.toList(), catalog).associateBy { it.group }

    @Test fun replacementUsesChestVolumeButOnlyTheFlysOwnPreviousBestForIntensity() {
        val older = session(1, set(fly, 20.0))
        val before = session(2, set(press, 100.0), set(press, 100.0), set(press, 100.0))
        val now = session(4, set(fly, 19.0), set(fly, 22.0))
        val rows = compare(now, older, before, session(3, set("lat_pull_down", 90.0)), now, session(5, set(fly, 80.0)))
        assertEquals(setOf("가슴"), rows.keys)
        assertEquals("가슴 세트 3→2 · 강도 +10%", rows.getValue("가슴").summaryLine())
        val fresh = compare(now, before).getValue("가슴")
        assertNull(fresh.intensityPercent)
        assertEquals("가슴 세트 3→2 · 새 종목 1개", fresh.summaryLine())
        assertEquals("가슴 2세트 · 첫 기록 · 새 종목 1개", compare(now).getValue("가슴").summaryLine())
    }

    @Test fun volumePrefersSameRoutineOverIncidentalChestWorkButIntensityUsesLatestSameExercise() {
        val chestDay = session(1, set(press, 50.0), set(fly, 20.0)).copy(routineId = "chest")
        val mixed = session(2, set(fly, 40.0))
        val now = session(3, set(fly, 44.0)).copy(routineId = "chest")
        assertEquals("가슴 세트 2→1 · 강도 +10%", compare(now, chestDay, mixed).getValue("가슴").summaryLine())
        // Free workouts are not one named routine; use the latest matching region instead.
        val free = now.copy(routineId = "free")
        assertEquals("가슴 세트 1→1 · 강도 +10%", compare(free, chestDay.copy(routineId = "free"), mixed).getValue("가슴").summaryLine())
    }

    @Test fun explicitAndLikelyWarmupsExcludedButHalfPeakAndMarkedDropSetsCount() {
        val now = session(2, set(press, 200.0, type = "WARMUP"), set(press, 19.0), set(press, 20.0),
            set(press, 40.0), set(press, 10.0, type = "DROP"), set(press, 100.0).copy(completed = false),
            set(press, 200.0, 0))
        val rows = compare(now, session(1, set(press, 100.0, type = "WARMUP"), set(press, 40.0)))
        assertEquals("가슴 세트 1→3 · 강도 0%", rows.getValue("가슴").summaryLine())
        assertEquals("어깨 세트 0.5→1.5 · 강도 0%", rows.getValue("어깨").summaryLine())
        assertTrue(compare(session(3, set(press, 100.0, type = "WARMUP"))).isEmpty())
    }

    @Test fun percentagesUseRegionalSetCreditsAndIgnoreNewExerciseInDenominator() {
        val dip = "chest_dip"
        val prior = session(1, set(press, 50.0), set(fly, 100.0))
        val now = session(2, set(press, 50.0), set(press, 55.0), set(fly, 80.0), set(dip, null))
        val rows = compare(now, prior)
        assertEquals("가슴 세트 2→4 · 강도 0% (2/3종목) · 새 종목 1개", rows.getValue("가슴").summaryLine())
        assertEquals("어깨 세트 0.5→1.5 · 강도 +10% (1/2종목) · 새 종목 1개", rows.getValue("어깨").summaryLine())
        assertEquals(0.8, rows.getValue("팔").sets, 0.001)
    }

    @Test fun gymSeparatesIntensityNotRegionalVolumeAndMissingLocationUsesId() {
        val a = session(1, set(fly, 20.0)); val b = session(2, set(fly, 90.0), set(fly, 100.0))
        val now = session(3, set(fly, 22.0))
        fun withGyms(gyms: Map<String, String>) = muscleProgress(now, listOf(a, b), catalog, gyms::get).single()
        assertEquals("가슴 세트 2→1 · 강도 +10%", withGyms(mapOf("s1" to "A", "s2" to "B", "s3" to "A")).summaryLine())
        assertEquals(1, withGyms(mapOf("s1" to "A", "s3" to "B")).newExercises)
        assertEquals("가슴 세트 2→1 · 강도 -78%", withGyms(emptyMap()).summaryLine())
    }

    @Test fun unmeasurableLatestAndAmbiguousTimesNeverFallBackOrBecomeFirsts() {
        val a = session(1, set(fly, 20.0)); val b = session(2, set(fly, 30.0, 12)); val now = session(3, set(fly, 22.0))
        val past = compare(now, a, b).getValue("가슴")
        assertNull(past.intensityPercent); assertEquals(0, past.newExercises)
        val tie = compare(now, a, b, b.copy(sessionId = "duplicate-time")).getValue("가슴")
        assertNull(tie.previousSets); assertFalse(tie.first); assertEquals(0, tie.newExercises); assertNull(tie.intensityPercent)
    }

    @Test fun assistedAndTimedWorkCountWithoutTreatingCounterweightOrSecondsAsStrength() {
        val pull = "assisted_pull_up"
        val plank = set("plank", null, null).copy(durationSeconds = 30)
        val old = session(1, set(pull, 40.0), plank); val now = session(2, set(pull, 40.0), set(pull, 10.0), plank)
        val rows = compare(now, old)
        assertEquals("등 세트 1→2 · 강도 비교 불가", rows.getValue("등").summaryLine())
        assertEquals("코어 세트 1→1 · 강도 비교 불가", rows.getValue("코어").summaryLine())
    }

    @Test fun weightedPullUpNeedsTheBodyWeightRecordedAtEachWorkout() {
        val id = "weighted_pull_up"; val old = session(1, set(id, 10.0)); val now = session(2, set(id, 20.0))
        assertNull(compare(now, old).getValue("등").intensityPercent)
        val rows = muscleProgress(now, listOf(old), catalog, frozenWeightOf = { 90.0 })
        assertEquals(10.0, rows.first { it.group == "등" }.intensityPercent!!, 0.001)
    }
}
