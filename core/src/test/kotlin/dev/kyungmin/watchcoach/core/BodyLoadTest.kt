package dev.kyungmin.watchcoach.core

import kotlin.test.Test
import kotlin.test.assertEquals

class BodyLoadTest {
    private fun log(id: String, day: Long, sets: Int) = ExerciseLog(id, day, List(sets) { LoggedSet(50.0, 10) })
    private val parts = mapOf("bench" to "가슴", "row" to "등", "fly" to "가슴")
    private val weights = { id: String -> parts[id]?.let { mapOf(it to 1.0) } }

    @Test
    fun countsSetsPerPartInsideTheWindowOnly() {
        val logs = listOf(log("bench", 100, 4), log("fly", 98, 3), log("row", 93, 5), log("row", 101, 2))
        val result = BodyLoad.setsByPart(logs, parts::get, today = 100)
        assertEquals(mapOf("가슴" to 7), result)
    }

    @Test
    fun unknownExercisesAreSkipped() {
        assertEquals(emptyMap(), BodyLoad.setsByPart(listOf(log("mystery", 100, 3)), parts::get, today = 100))
    }

    @Test fun savedLayoutDoesNotCountUnfinishedOrUnenteredSetsAsTraining() {
        val rows = listOf(LoggedSet(50.0, 6), LoggedSet(50.0, 0, completed = false, repsEntered = false),
            LoggedSet(50.0, 0, repsEntered = false))
        assertEquals(mapOf("가슴" to 1), BodyLoad.setsByPart(listOf(ExerciseLog("bench", 100, rows)), parts::get, 100))
    }

    @Test
    fun intensityIsCappedAtOne() {
        val result = BodyLoad.intensity(mapOf("가슴" to 6, "등" to 40))
        assertEquals(0.5, result["가슴"])
        assertEquals(1.0, result["등"])
    }

    @Test
    fun fatigueBuildsUpAcrossDaysAndFadesWithTime() {
        val weights = { id: String -> if (id == "curl") mapOf("이두" to 1.0) else null }  // recovers in 3 days
        val once = BodyLoad.fatigueByPart(listOf(log("curl", 100, 5)), weights, 100)["이두"]!!
        assertEquals(5.0 / 15, once, 1e-9)
        val twice = BodyLoad.fatigueByPart(listOf(log("curl", 100, 5), log("curl", 101, 5)), weights, 101)["이두"]!!
        // A day later the first session is still at full strength, so the two add up.
        assertEquals((5 * BodyLoad.recoveryLeft("이두", 24.0) + 5) / 15, twice, 1e-9)
        assertEquals(10.0 / 15, twice, 1e-9)
        assertEquals(true, twice > once)
        assertEquals(true, BodyLoad.fatigueByPart(listOf(log("curl", 100, 5)), weights, 102)["이두"]!! < once)
        assertEquals(emptyMap(), BodyLoad.fatigueByPart(listOf(log("curl", 100, 5)), weights, 103))
    }

    @Test
    fun recoveryCurveHoldsADayThenEasesOffAndDropsFasterTowardsTheEnd() {
        fun left(part: String, hours: Int) = BodyLoad.recoveryLeft(part, hours.toDouble())
        // Chest and back (4 days).
        for (part in listOf("가슴", "등")) {
            assertEquals(1.0, left(part, 0), 1e-9); assertEquals(1.0, left(part, 24), 1e-9)
            assertEquals(0.8, left(part, 48), 1e-9); assertEquals(0.5, left(part, 72), 1e-9)
            assertEquals(0.0, left(part, 96), 1e-9)
        }
        // Legs (5 days).
        listOf(0 to 1.0, 24 to 1.0, 48 to 0.9, 72 to 0.6, 96 to 0.3, 120 to 0.0)
            .forEach { (h, v) -> assertEquals(v, left("하체", h), 1e-9) }
        // Smaller muscles (3 days).
        listOf(0 to 1.0, 24 to 1.0, 48 to 0.55, 72 to 0.0).forEach { (h, v) -> assertEquals(v, left("측면어깨", h), 1e-9) }
        // Never rises again, always within 0..1, and the drop speeds up after the first day.
        for (part in listOf("가슴", "하체", "이두")) {
            var prev = 1.0
            for (tenth in 0..1300) {
                val v = BodyLoad.recoveryLeft(part, tenth / 10.0)
                assertEquals(true, v <= prev + 1e-9 && v in 0.0..1.0)
                prev = v
            }
        }
        assertEquals(true, left("가슴", 48) - left("가슴", 72) < left("가슴", 72) - left("가슴", 96))
    }

    @Test
    fun aSeventeenSetBackDayStaysFullForADayThenFades() {
        val weights = { id: String -> if (id == "row") mapOf("등" to 1.0) else null }
        val start = 1_800_000_000_000L
        val row = log("row", 100, 17).copy(startedAtMs = start)
        fun at(hours: Int) = BodyLoad.fatigueByPartAt(listOf(row), weights, start + hours * 3_600_000L)["등"]
        assertEquals(1.0, at(0)); assertEquals(1.0, at(24))
        assertEquals(17 * 0.8 / 15, at(48)!!, 1e-9)
        assertEquals(17 * 0.5 / 15, at(72)!!, 1e-9)
        assertEquals(null, at(96))
    }

    @Test
    fun aTenSetSideDeltDayPaintsTwoThirdsAndEndsInThreeDays() {
        val weights = { id: String -> if (id == "lat") mapOf("측면어깨" to 1.0) else null }
        val start = 1_800_000_000_000L
        val row = log("lat", 100, 10).copy(startedAtMs = start)
        fun at(hours: Int) = BodyLoad.fatigueByPartAt(listOf(row), weights, start + hours * 3_600_000L)["측면어깨"]
        assertEquals(10.0 / 15, at(0)!!, 1e-9); assertEquals(10.0 / 15, at(24)!!, 1e-9)
        assertEquals(10.0 / 15 * 0.55, at(48)!!, 1e-9)
        assertEquals(null, at(72))
    }

    @Test
    fun fatigueIsCappedAtOne() {
        assertEquals(1.0, BodyLoad.fatigueByPart(listOf(log("bench", 100, 30)), weights, 100)["가슴"])
    }

    @Test
    fun shoulderIsSplitByHeadAndPressesAlsoHitTheSide() {
        assertEquals(mapOf("측면어깨" to 1.0), BodyLoad.partWeights("어깨", "lateral_raise"))
        assertEquals(mapOf("후면어깨" to 1.0), BodyLoad.partWeights("어깨", "rear_delt"))
        assertEquals(mapOf("전면어깨" to 1.0, "측면어깨" to 0.2), BodyLoad.partWeights("어깨", "shoulder_press"))
        assertEquals(mapOf("승모" to 1.0), BodyLoad.partWeights("어깨", "shrug"))
        assertEquals(mapOf("후면어깨" to 1.0, "승모" to 0.4), BodyLoad.partWeights("어깨", "rear_delt", "face_pull"))
        assertEquals(mapOf("측면어깨" to 1.0, "승모" to 0.5), BodyLoad.partWeights("어깨", "row"))
        assertEquals(mapOf("가슴" to 1.0, "전면어깨" to 0.5), BodyLoad.partWeights("가슴", "chest_press", "flat_bench"))
        assertEquals(mapOf("가슴" to 1.0, "전면어깨" to 0.8), BodyLoad.partWeights("가슴", "chest_press", "incline_dumbbell_bench_press"))
        assertEquals(mapOf("가슴" to 1.0, "전면어깨" to 0.2), BodyLoad.partWeights("가슴", "chest_press", "decline_machine_chest_press"))
        assertEquals(mapOf("가슴" to 1.0, "삼두" to 0.5, "전면어깨" to 0.5), BodyLoad.partWeights("가슴", "push_up", "push_up"))
        assertEquals(mapOf("삼두" to 1.0, "가슴" to 0.5, "전면어깨" to 0.3), BodyLoad.partWeights("삼두", "chest_press", "close_grip_bench_press"))
        assertEquals(mapOf("가슴" to 0.7, "등" to 0.5), BodyLoad.partWeights("등", "pullover"))
        assertEquals(mapOf("가슴" to 1.0, "삼두" to 0.8, "전면어깨" to 0.5), BodyLoad.partWeights("삼두", "dip"))
        assertEquals(mapOf("가슴" to 1.0), BodyLoad.partWeights("가슴", "chest_fly", "incline_dumbbell_fly"))
        assertEquals(mapOf("코어" to 1.0), BodyLoad.partWeights("코어", "sit_up"))
        assertEquals(emptyMap(), BodyLoad.partWeights("전완", "forearm"))
        assertEquals(mapOf("등" to 1.0, "이두" to 0.6, "후면어깨" to 0.4, "승모" to 0.5), BodyLoad.partWeights("등", "row"))
        assertEquals(mapOf("등" to 1.0, "하체" to 0.8, "승모" to 0.3), BodyLoad.partWeights("등", "hinge"))
        assertEquals(mapOf("하체" to 0.8, "등" to 0.6, "전면어깨" to 0.5, "코어" to 0.4), BodyLoad.partWeights("전신", "full_body"))
    }

    @Test fun arbitraryTimeExcludesFutureSessionsAndDecaysWithinADay() {
        val start = 1_800_000_000_000L
        val row = log("bench", 100, 15).copy(startedAtMs = start)
        assertEquals(emptyMap(), BodyLoad.fatigueByPartAt(listOf(row), weights, start - 1))
        assertEquals(1.0, BodyLoad.fatigueByPartAt(listOf(row), weights, start)["가슴"])
        // Still full strength three hours in; recovered after 96 hours.
        assertEquals(1.0, BodyLoad.fatigueByPartAt(listOf(row), weights, start + 3 * 3_600_000)["가슴"]!!, 1e-9)
        assertEquals(emptyMap(), BodyLoad.fatigueByPartAt(listOf(row), weights, start + 96 * 3_600_000))
    }

    @Test fun legacyTimesUseLocalNoonAndIgnoreUnfinishedSets() {
        val zone = java.time.ZoneId.of("Asia/Seoul")
        val noon = java.time.LocalDate.ofEpochDay(100).atTime(12, 0).atZone(zone).toInstant().toEpochMilli()
        val rows = listOf(log("bench", 100, 3), log("bench", 100, 30).copy(
            sets = listOf(LoggedSet(50.0, 10, completed = false), LoggedSet(50.0, 10, repsEntered = false))))
        assertEquals(emptyMap(), BodyLoad.fatigueByPartAt(rows, weights, noon - 1, zone))
        assertEquals(0.2, BodyLoad.fatigueByPartAt(rows, weights, noon, zone)["가슴"])
        assertEquals(emptyMap(), BodyLoad.fatigueByPartAt(rows, weights, noon + 4 * 86_400_000L, zone))
    }
}
