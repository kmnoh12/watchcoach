package dev.kyungmin.kcoach.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import java.time.LocalDate
import java.time.ZoneId

class StatsAnalyticsTest {
    @Test fun periodsHaveNoOverlapOrFutureRecords() {
        assertTrue(StatsAnalytics.inPeriod(94, 100, 7))
        assertFalse(StatsAnalytics.inPeriod(93, 100, 7))
        assertTrue(StatsAnalytics.inPeriod(93, 100, 7, true))
        assertFalse(StatsAnalytics.inPeriod(94, 100, 7, true))
        assertFalse(StatsAnalytics.inPeriod(101, 100, 0))
        assertFalse(StatsAnalytics.inPeriod(50, 100, 0, true))
        assertTrue(StatsAnalytics.inPeriod(1, 100, 0))
    }

    @Test fun weeklyTotalsStopTodayAndCompareTheSameWeekday() {
        val today = LocalDate.of(2026, 11, 12).toEpochDay() // Thursday
        val logs = listOf(WorkoutLog(today - 3, "A", 1, 1, 100), WorkoutLog(today, "B", 1, 1, 200),
            WorkoutLog(today + 1, "future", 1, 1, 900), WorkoutLog(today - 10, "last", 1, 1, 50))
        assertEquals(listOf(100.0, 100.0, 100.0, 300.0), StatsAnalytics.weekVolumes(logs, today))
        assertEquals(List(7) { 50.0 }, StatsAnalytics.weekVolumes(logs, today, true))
        assertEquals(listOf(0.0), StatsAnalytics.weekVolumes(emptyList(), today - 3))
    }

    @Test fun volumeUsesKilogramsAndDoesNotMultiplyCompoundLiftTotals() {
        val logs = listOf(ExerciseLog("curl", 100, listOf(LoggedSet(10.0, 8), LoggedSet(20.0, 8, completed = false))),
            ExerciseLog("whole", 100, listOf(LoggedSet(50.0, 10))),
            ExerciseLog("forearm", 100, listOf(LoggedSet(50.0, 10))))
        val volume = StatsAnalytics.volumeByGroup(logs, { mapOf("curl" to "이두", "whole" to "전신", "forearm" to "전완")[it] },
            { mapOf("하체" to 1.0, "등" to 1.0) }, 100, 7)
        assertEquals(listOf(0.0, 0.0, 80.0, 250.0, 0.0, 250.0), volume)
        assertEquals(List(6) { 0.0 }, StatsAnalytics.volumeByGroup(emptyList(), { null }, { null }, 100, 0))
    }

    @Test fun recordsRequireStrictImprovementAndUseChronologyNotInputOrder() {
        val zone = ZoneId.of("UTC")
        fun log(day: Long, vararg sets: LoggedSet) = ExerciseLog("bench", day, sets.toList())
        val logs = listOf(log(3, LoggedSet(60.0, 10)), log(1, LoggedSet(50.0, 10)),
            log(2, LoggedSet(50.0, 11)), log(4, LoggedSet(100.0, 6)), // equal product
            log(5, LoggedSet(200.0, 10, completed = false)),
            log(6, LoggedSet(200.0, 10, repsEntered = false)),
            log(7, LoggedSet(300.0, 10, durationSeconds = 30)),
            log(9, LoggedSet(500.0, 10))) // future
        val now = LocalDate.ofEpochDay(8).atTime(12, 0).atZone(zone).toInstant().toEpochMilli()
        val pr = StatsAnalytics.records(logs, now, zone).single()
        assertEquals(3, pr.epochDay)
        assertEquals(60.0, pr.best.weightKg)
        assertEquals(11, pr.previous.reps)
        assertEquals(emptyList(), StatsAnalytics.records(listOf(logs[1]), now, zone))
    }
}
