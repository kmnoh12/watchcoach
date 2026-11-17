package dev.kyungmin.watchcoach.core

import java.io.File
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Optional synthetic evidence; no app data, detector tuning or Android service. */
class VirtualWatchReplayTest {
    private val exercises = setOf(
        "dumbbell_curl",
        "dumbbell_lateral_raise",
        "barbell_overhead_press",
        "dumbbell_pullover",
    )
    private data class Observed(val channel: String, val accepted: Boolean, val emittedAtNs: Long, val event: ProfiledMotionRepEvent)
    private data class Replayed(val profile: ExerciseTrackingProfile, val summary: CaptureReplaySummary,
                                val skipped: Int, val firstFedNs: Long, val events: List<Observed>)

    private fun replay(document: SensorCaptureDocument, exercise: String, prepEndNs: Long): Replayed {
        require(exercise in exercises)
        val profile = ExerciseTrackingProfiles.resolve(exercise)
        require(profile.exerciseId == exercise && profile.mode != TrackingMode.MANUAL_REQUIRED &&
            profile.signal != TrackingSignal.FOREARM_ROTATION)
        val detector = ProfiledMotionRepDetector(profile)
        val events = mutableListOf<Observed>()
        var skipped = 0
        var firstFedNs = -1L
        fun accept(event: ProfiledMotionRepEvent) = profile.family != MotionFamily.VERTICAL_PRESS_RETURN || VerticalRepAmplitude.accepts(event)
        val summary = SensorCaptureReplay.replay(document) { _, record ->
            val sample = SensorRecordQuality.forCounting(record)
            if (sample.timestampNs <= prepEndNs) {
                // The service observes its start gate here, not the repetition detector.
                skipped++
            } else {
                if (firstFedNs < 0) {
                    detector.beginCounting()
                    firstFedNs = sample.timestampNs
                }
                detector.add(sample)?.let { events += Observed("live", accept(it), sample.timestampNs, it) }
            }
        }
        require(firstFedNs >= 0) { "No samples after preparation" }
        detector.finishAll().forEach {
            events += Observed("offline_flush", accept(it), document.records.last().sample.timestampNs, it)
        }
        return Replayed(profile, summary, skipped, firstFedNs, events)
    }

    @Test fun stationarySyntheticRecordsDoNotCountInAnyPilotFamily() {
        val records = (0..600).map { index ->
            SensorCaptureRecord(SensorSample(1_000_000_000L + index * 20_000_000L, 0f, 9.80665f, 0f, 0f, 0f, 0f))
        }
        exercises.forEach { exercise ->
            val result = replay(SensorCaptureDocument(2, 50.0, records), exercise, 4_000_000_000L)
            assertTrue(result.events.isEmpty(), "Stationary input counted for $exercise")
            assertEquals(151, result.skipped)
            assertEquals(4_020_000_000L, result.firstFedNs)
        }
    }

    @Test fun namedSyntheticIdsResolveToCurrentProductionFamilies() {
        assertEquals(MotionFamily.FLEXION_EXTENSION, ExerciseTrackingProfiles.resolve("dumbbell_curl").family)
        assertEquals(MotionFamily.CYCLE_AXIS_RETURN, ExerciseTrackingProfiles.resolve("dumbbell_lateral_raise").family)
        assertEquals(MotionFamily.VERTICAL_PRESS_RETURN, ExerciseTrackingProfiles.resolve("barbell_overhead_press").family)
        assertEquals(MotionFamily.ARC_RETURN, ExerciseTrackingProfiles.resolve("dumbbell_pullover").family)
    }

    @Test fun replayExplicitSyntheticIndexWithoutRequiringBaselineCountSuccess() {
        val configured = System.getenv("WATCHCOACH_VIRTUAL_WATCH_INDEX")
        assumeTrue(!configured.isNullOrBlank(), "Optional local synthetic capture index not configured")
        val index = File(configured!!)
        require(index.isFile) { "Configured synthetic index is missing" }
        val lines = index.readLines()
        require(lines.first() == "case_path\texercise_id\tprep_end_ns\tcapture_sha256\ttruth_sha256\toutput_path")
        require(lines.size > 1)
        lines.drop(1).forEach { line ->
            val fields = line.split('\t')
            require(fields.size == 6)
            val case = File(fields[0])
            val captureBytes = File(case, "capture.kcs").readBytes()
            assertEquals(fields[3], SensorCaptureFormat.sha256(captureBytes))
            assertEquals(fields[4], SensorCaptureFormat.sha256(File(case, "truth.json").readBytes()))
            val document = SensorCaptureFormat.read(captureBytes.inputStream())
            assertEquals(2, document.formatVersion)
            assertEquals(50.0, document.sampleRateRequestedHz)
            assertTrue(document.records.all { r -> r.sample.sensorAccuracy == null && r.heartRateBpm == null &&
                r.accelerationAccuracy == null && r.receivedElapsedNs == null && r.heartRateTimestampNs == null &&
                r.accelerationTimestampNs == r.sample.timestampNs && r.gyroscopeTimestampNs == r.sample.timestampNs })
            val result = replay(document, fields[1], fields[2].toLong())
            assertTrue(result.summary.timestampErrors.isEmpty())
            val output = File(fields[5])
            require(output.canonicalFile.parentFile == index.canonicalFile.parentFile) { "Output must stay in the private staging directory" }
            output.mkdirs()
            File(output, "stats.tsv").writeText(listOf(
                "exercise_id" to result.profile.exerciseId, "algorithm_id" to result.profile.id,
                "family" to result.profile.family, "signal" to result.profile.signal,
                "tracking_profile_snapshot" to TrackingProfileSnapshot.encode(result.profile),
                "sample_count" to result.summary.sampleCount, "duration_ms" to result.summary.durationMs,
                "preparation_samples_skipped" to result.skipped, "first_fed_ns" to result.firstFedNs,
            ).joinToString("\n", postfix = "\n") { "${it.first}\t${it.second}" })
            File(output, "events.tsv").bufferedWriter().use { writer ->
                writer.appendLine("channel\taccepted\temitted_at_ns\tstart_ns\tturnaround_ns\tend_ns\tduration_ms\tpeak_motion_rate\tmotion_displacement\ttrajectory_spread\tconfidence")
                result.events.forEach { observed ->
                    val e = observed.event
                    assertTrue(e.startTimestampNs <= e.turnaroundTimestampNs && e.turnaroundTimestampNs <= e.endTimestampNs && e.endTimestampNs <= observed.emittedAtNs)
                    assertTrue(listOf(e.peakMotionRate, e.motionDisplacement, e.trajectorySpread, e.confidence).all { it.isFinite() })
                    writer.appendLine(listOf(observed.channel, observed.accepted, observed.emittedAtNs,
                        e.startTimestampNs, e.turnaroundTimestampNs, e.endTimestampNs, e.durationMs,
                        e.peakMotionRate, e.motionDisplacement, e.trajectorySpread, e.confidence).joinToString("\t"))
                }
            }
            println("SYNTHETIC ${case.name}: rawLive=${result.events.count { it.channel == "live" }} acceptedLive=${result.events.count { it.channel == "live" && it.accepted }} offlineFlush=${result.events.count { it.channel == "offline_flush" }}")
        }
    }
}
