package dev.kyungmin.watchcoach.core

import java.io.File
import org.junit.jupiter.api.Assumptions.assumeTrue
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Optional private sensor exports, not synthetic replacements or human training labels. */
class ChestPressEvidenceTest {
    private val profile = ExerciseTrackingProfiles.resolve("machine_chest_press_plate")

    private fun capture(date: String, time: String): SensorCaptureDocument {
        val root = System.getenv("WATCHCOACH_CHEST_CAPTURE_DIR")
        assumeTrue(!root.isNullOrBlank(), "Configure the local chest press export directory")
        val dir = File(root, date).listFiles().orEmpty().single { it.name.startsWith("${time}_machine_chest_press_plate_") }
        return dir.resolve("capture.kcs").inputStream().use(SensorCaptureFormat::read)
    }

    @Test fun unprimedRetryCountsTenReturnsNotTheOpeningSettle() {
        val records = capture("2026-11-18", "122744").records
        val detector = ProfiledMotionRepDetector(profile)
        detector.beginCounting()
        // Watch start without saved preparation: the first recorded sample was the start trigger.
        val events = records.drop(1).mapNotNull { detector.add(SensorRecordQuality.forCounting(it)) } + detector.finishAll()
        assertEquals(10, events.size)
        assertTrue((events.first().endTimestampNs - records.first().sample.timestampNs) / 1e9 in 3.0..4.0)
    }

    @Test fun unevenPressesKeepTheObservedReturnBetweenTheTwoNeighbors() {
        val doc = capture("2026-11-05", "123448")
        val ends = PhoneRepAnalyzer.analyze(doc, profile, 12).events.map { (it.endTimestampNs - doc.records.first().sample.timestampNs) / 1e9 }
        assertTrue(ends.windowed(3).any { (a, b, c) -> a in 20.0..21.0 && b in 23.0..23.6 && c in 24.8..25.6 })
    }

    @Test fun isolatedReturnsAreReportedButDoNotReplaceTheWatchCount() {
        val out = PhoneRepAnalyzer.analyze(capture("2026-10-24", "195856"), profile, 11)
        assertEquals(2, out.events.size)
        assertEquals(2, out.result.phoneReanalyzedReps)
        assertNull(out.result.confirmedReps)
        assertEquals(11, out.result.watchDetectedReps)
    }
}
