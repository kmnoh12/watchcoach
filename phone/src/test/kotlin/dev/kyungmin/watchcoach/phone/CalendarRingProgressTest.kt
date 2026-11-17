package dev.kyungmin.watchcoach.phone

import dev.kyungmin.watchcoach.phone.ui.calendarMonthRingProgress
import dev.kyungmin.watchcoach.phone.ui.recordRingProgress
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.YearMonth

class CalendarRingProgressTest {

    @Test
    fun routinesAreScoredIndependentlyByTitle() {
        val legsBest = WorkoutRecord("2026-10-10", "하체", minutes = 70, sets = 20, volumeKg = 20000)
        val shoulderBest = WorkoutRecord("2026-10-12", "어깨", minutes = 50, sets = 18, volumeKg = 5000)
        val shoulderLight = WorkoutRecord("2026-10-15", "어깨", minutes = 25, sets = 10, volumeKg = 2500)
        val records = listOf(legsBest, shoulderBest, shoulderLight)

        val progress = calendarMonthRingProgress(YearMonth.of(2026, 10), records)

        assertEquals(1.0f, progress[10]!!, 0.0001f)
        assertEquals(1.0f, progress[12]!!, 0.0001f)
        assertEquals(0.7f, progress[15]!!, 0.0001f)
    }

    @Test
    fun appliesSeventyVolumeThirtyMinutesWeightingAndBestDayNormalization() {
        // Max volume = 10,000kg (on day 1), max minutes = 100m (on day 5) -> neither hits raw 1.0,
        // so day 1 (score = 0.7 * 1.0 + 0.3 * 0.5 = 0.85) becomes the cohort's 100% best day.
        val peakVolume = WorkoutRecord("2026-10-01", "가슴", minutes = 50, sets = 20, volumeKg = 10000)
        val peakMinutes = WorkoutRecord("2026-10-05", "가슴", minutes = 100, sets = 18, volumeKg = 6000)
        val halfDay = WorkoutRecord("2026-10-08", "가슴", minutes = 50, sets = 12, volumeKg = 5000)
        val records = listOf(peakVolume, peakMinutes, halfDay)

        val progress = calendarMonthRingProgress(YearMonth.of(2026, 10), records)

        assertEquals(1.0f, progress[1]!!, 0.0001f)
        // day 5 score = 0.7 * 0.6 + 0.3 * 1.0 = 0.72; rawRatio = 0.72 / 0.85
        val expectedDay5 = 0.4f + 0.6f * (0.72f / 0.85f)
        assertEquals(expectedDay5, progress[5]!!, 0.0001f)
        // day 8 score = 0.7 * 0.5 + 0.3 * 0.5 = 0.50; rawRatio = 0.50 / 0.85
        val expectedDay8 = 0.4f + 0.6f * (0.50f / 0.85f)
        assertEquals(expectedDay8, progress[8]!!, 0.0001f)
    }

    @Test
    fun clampsMinutesAt120ToProtectAgainstForgotToStopTimer() {
        val forgotToStop = WorkoutRecord("2026-10-02", "등", minutes = 360, sets = 16, volumeKg = 8000)
        val normalPeak = WorkoutRecord("2026-10-10", "등", minutes = 120, sets = 20, volumeKg = 8000)
        val halfTimeSameVol = WorkoutRecord("2026-10-15", "등", minutes = 60, sets = 20, volumeKg = 8000)
        val records = listOf(forgotToStop, normalPeak, halfTimeSameVol)

        val progress = calendarMonthRingProgress(YearMonth.of(2026, 10), records)

        assertEquals(1.0f, progress[2]!!, 0.0001f)
        assertEquals(1.0f, progress[10]!!, 0.0001f)
        // On day 15: volRatio = 1.0, minRatio = 60 / 120 = 0.5 -> score = 0.7 + 0.15 = 0.85
        assertEquals(0.4f + 0.6f * 0.85f, progress[15]!!, 0.0001f)
    }

    @Test
    fun zeroVolumeRoutineUsesDurationOnly() {
        val longSession = WorkoutRecord("2026-10-03", "유산소", minutes = 60, sets = 1, volumeKg = 0)
        val shortSession = WorkoutRecord("2026-10-06", "유산소", minutes = 30, sets = 1, volumeKg = 0)
        val records = listOf(longSession, shortSession)

        val progress = calendarMonthRingProgress(YearMonth.of(2026, 10), records)

        assertEquals(1.0f, progress[3]!!, 0.0001f)
        assertEquals(0.7f, progress[6]!!, 0.0001f)
    }

    @Test
    fun minimumFloorIs40PercentEvenForVeryLightSession() {
        val heavy = WorkoutRecord("2026-10-01", "하체", minutes = 120, sets = 24, volumeKg = 20000)
        val tiny = WorkoutRecord("2026-10-04", "하체", minutes = 1, sets = 1, volumeKg = 0)

        val progress = recordRingProgress(tiny, listOf(heavy, tiny))

        assertTrue(progress >= 0.4f)
        assertTrue(progress < 0.41f)
    }

    @Test
    fun trailing30DayWindowIgnoresOlderRecordsAndFutureRecords() {
        val oldMonster = WorkoutRecord("2026-09-01", "가슴", minutes = 90, sets = 25, volumeKg = 20000)
        val recentPeak = WorkoutRecord("2026-10-10", "가슴", minutes = 60, sets = 18, volumeKg = 10000)
        val futureMonster = WorkoutRecord("2026-10-20", "가슴", minutes = 120, sets = 30, volumeKg = 30000)
        val records = listOf(oldMonster, recentPeak, futureMonster)

        // Evaluating 2026-10-10 uses window 2026-09-10..2026-10-10 -> oldMonster (09-01) and futureMonster (10-20) excluded.
        assertEquals(1.0f, recordRingProgress(recentPeak, records), 0.0001f)
    }

    @Test
    fun multipleWorkoutsOnSameDayPickHighestProgress() {
        val chestBest = WorkoutRecord("2026-10-14", "가슴", minutes = 60, sets = 18, volumeKg = 10000)
        val shoulderLight = WorkoutRecord("2026-10-14", "어깨", minutes = 20, sets = 8, volumeKg = 1000)
        val shoulderBest = WorkoutRecord("2026-10-02", "어깨", minutes = 60, sets = 20, volumeKg = 6000)
        val records = listOf(chestBest, shoulderLight, shoulderBest)

        val progress = calendarMonthRingProgress(YearMonth.of(2026, 10), records)

        assertEquals(1.0f, progress[14]!!, 0.0001f)
    }
}
