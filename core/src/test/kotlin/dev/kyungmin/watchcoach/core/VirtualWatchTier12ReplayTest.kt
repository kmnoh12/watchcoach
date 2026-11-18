package dev.kyungmin.watchcoach.core

import java.io.File
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Offline batch replay harness for Tier 1/2 virtual-watch synthetic captures.
 * Only runs when WATCHCOACH_TIER12_INDEX is configured.
 */
class VirtualWatchTier12ReplayTest {
    private data class Observed(
        val channel: String,
        val accepted: Boolean,
        val emittedAtNs: Long,
        val event: ProfiledMotionRepEvent,
    )

    @Test
    fun replayTier12SyntheticIndex() {
        val configured = System.getenv("WATCHCOACH_TIER12_INDEX")
        assumeTrue(!configured.isNullOrBlank(), "Tier 1/2 synthetic index not configured")
        val index = File(configured!!)
        require(index.isFile) { "Configured index is missing: $index" }
        val lines = index.readLines().filter { it.isNotBlank() }
        require(lines.first() == "case_id\texercise_id\tprep_end_ns\tkcs_path\toutput_path")
        lines.drop(1).forEach { line ->
            val fields = line.split('\t')
            require(fields.size == 5) { "Bad index row: $line" }
            val caseId = fields[0]
            val exerciseId = fields[1]
            val prepEndNs = fields[2].toLong()
            val kcsFile = File(fields[3])
            val outputDir = File(fields[4])
            outputDir.mkdirs()

            val profile = ExerciseTrackingProfiles.resolve(exerciseId)
            val document = SensorCaptureFormat.read(kcsFile.inputStream())
            assertTrue(document.validateTimestamps().isEmpty(), "Invalid timestamps for $caseId")

            if (profile.mode == TrackingMode.MANUAL_REQUIRED) {
                File(outputDir, "stats.tsv").writeText(
                    listOf(
                        "case_id" to caseId,
                        "exercise_id" to profile.exerciseId,
                        "algorithm_id" to profile.id,
                        "family" to profile.family,
                        "signal" to profile.signal,
                        "mode" to profile.mode,
                        "skipped" to 0,
                        "first_fed_ns" to -1L,
                    ).joinToString("\n", postfix = "\n") { "${it.first}\t${it.second}" }
                )
                File(outputDir, "events.tsv").writeText(
                    "channel\taccepted\temitted_at_ns\tstart_ns\tturnaround_ns\tend_ns\tduration_ms\tpeak_motion_rate\tmotion_displacement\ttrajectory_spread\tconfidence\n"
                )
                return@forEach
            }

            val prepSamples = mutableListOf<SensorSample>()
            val workSamples = mutableListOf<SensorSample>()
            document.records.forEach { record ->
                val s = SensorRecordQuality.forCounting(record)
                if (s.timestampNs <= prepEndNs) prepSamples += s else workSamples += s
            }
            require(workSamples.isNotEmpty()) { "No working samples for $caseId" }

            val events = mutableListOf<Observed>()
            if (profile.signal == TrackingSignal.FOREARM_ROTATION) {
                val detector = ForearmRotationRepDetector(profile)
                detector.beginCounting()
                workSamples.forEach { sample ->
                    detector.add(sample)?.let { e ->
                        val pe = ProfiledMotionRepEvent(
                            e.startTimestampNs, e.turnaroundTimestampNs, e.endTimestampNs,
                            e.durationMs, e.peakAngularVelocity, e.angularDisplacement, 0.0, e.confidence,
                        )
                        events += Observed("live", true, sample.timestampNs, pe)
                    }
                }
                detector.finish()?.let { e ->
                    val pe = ProfiledMotionRepEvent(
                        e.startTimestampNs, e.turnaroundTimestampNs, e.endTimestampNs,
                        e.durationMs, e.peakAngularVelocity, e.angularDisplacement, 0.0, e.confidence,
                    )
                    events += Observed("offline_flush", true, workSamples.last().timestampNs, pe)
                }
            } else {
                val detector = ProfiledMotionRepDetector(profile)
                detector.beginCounting()
                if (prepSamples.isNotEmpty()) {
                    detector.prime(prepSamples)
                }
                fun accept(event: ProfiledMotionRepEvent) =
                    profile.family != MotionFamily.VERTICAL_PRESS_RETURN || VerticalRepAmplitude.accepts(event)
                workSamples.forEach { sample ->
                    detector.add(sample)?.let { e ->
                        events += Observed("live", accept(e), sample.timestampNs, e)
                    }
                }
                detector.finishAll().forEach { e ->
                    events += Observed("offline_flush", accept(e), workSamples.last().timestampNs, e)
                }
            }

            File(outputDir, "stats.tsv").writeText(
                listOf(
                    "case_id" to caseId,
                    "exercise_id" to profile.exerciseId,
                    "algorithm_id" to profile.id,
                    "family" to profile.family,
                    "signal" to profile.signal,
                    "mode" to profile.mode,
                    "skipped" to prepSamples.size,
                    "first_fed_ns" to workSamples.first().timestampNs,
                ).joinToString("\n", postfix = "\n") { "${it.first}\t${it.second}" }
            )
            File(outputDir, "events.tsv").bufferedWriter().use { writer ->
                writer.appendLine("channel\taccepted\temitted_at_ns\tstart_ns\tturnaround_ns\tend_ns\tduration_ms\tpeak_motion_rate\tmotion_displacement\ttrajectory_spread\tconfidence")
                events.forEach { observed ->
                    val e = observed.event
                    writer.appendLine(
                        listOf(
                            observed.channel, observed.accepted, observed.emittedAtNs,
                            e.startTimestampNs, e.turnaroundTimestampNs, e.endTimestampNs, e.durationMs,
                            e.peakMotionRate, e.motionDisplacement, e.trajectorySpread, e.confidence
                        ).joinToString("\t")
                    )
                }
            }
        }
    }

    @Test
    fun allPulloverVariantsUseArcReturnFamily() {
        listOf("dumbbell_pullover", "barbell_pullover", "cable_pullover", "machine_pullover").forEach { id ->
            assertEquals(MotionFamily.ARC_RETURN, ExerciseTrackingProfiles.resolve(id).family, id)
        }
    }

    @Test
    fun excursionPrimeKeepsRepStartAndTurnaroundInActiveWindow() {
        val profile = ExerciseTrackingProfiles.resolve("lat_pull_down")
        val detector = ProfiledMotionRepDetector(profile)
        val stepNs = 20_000_000L
        var t = 1_000_000_000L
        val prep = (0 until 150).map {
            val s = SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3)
            t += stepNs
            s
        }
        val activeStartNs = t
        val active = ArrayList<SensorSample>()
        repeat(4) {
            for (i in 0 until 130) {
                val p = i / 130.0
                val az = 9.80665 + 2.5 * sin(2 * PI * p)
                val gx = 0.4 * sin(2 * PI * p)
                active += SensorSample(t, 0f, 0f, az.toFloat(), gx.toFloat(), 0f, 0f, 3)
                t += stepNs
            }
        }
        repeat(100) {
            active += SensorSample(t, 0f, 0f, 9.80665f, 0f, 0f, 0f, 3)
            t += stepNs
        }
        detector.beginCounting()
        detector.prime(prep)
        val events = active.mapNotNull { detector.add(it) } + detector.finishAll()
        assertEquals(4, events.size)
        assertTrue(events.first().startTimestampNs >= activeStartNs, "rep start must not sit in prime window")
        assertTrue(events.first().turnaroundTimestampNs >= activeStartNs, "rep turnaround must not sit in prime window")
    }

    @Test
    fun uprightRowBarbellAndDumbbellUsePullReturn() {
        listOf("upright_row_barbell", "upright_row_dumbbell").forEach { id ->
            assertEquals(MotionFamily.PULL_RETURN, ExerciseTrackingProfiles.resolve(id).family, id)
        }
    }

    @Test
    fun tier12NineFixOverridesCountZeroOnStillOrNoisyWrist() {
        val g = 9.80665f
        val fixedIds = listOf(
            "single_arm_cable_pushdown",
            "reverse_grip_pushdown",
            "upright_row_barbell",
            "upright_row_dumbbell",
            "one_arm_dumbbell_row",
            "zottman_curl",
        )
        for (id in fixedIds) {
            val profile = ExerciseTrackingProfiles.resolve(id)
            val still = (0 until 1_500).map { i ->
                SensorSample(1_000_000_000L + i * 20_000_000L, 0.07f, -g + 0.10f, -0.05f, 0f, 0f, 0f, 3)
            }
            val detStill = ProfiledMotionRepDetector(profile)
            detStill.beginCounting()
            val stillCount = still.count { detStill.add(it) != null } + detStill.finishAll().size
            assertEquals(0, stillCount, "$id still")

            val rng = java.util.Random(17)
            val noisy = (0 until 1_500).map { i ->
                SensorSample(
                    1_000_000_000L + i * 20_000_000L,
                    (rng.nextGaussian() * 0.35).toFloat(),
                    -g + (rng.nextGaussian() * 0.35).toFloat(),
                    (rng.nextGaussian() * 0.35).toFloat(),
                    (rng.nextGaussian() * 0.03).toFloat(),
                    (rng.nextGaussian() * 0.03).toFloat(),
                    (rng.nextGaussian() * 0.03).toFloat(),
                    3,
                )
            }
            val detNoisy = ProfiledMotionRepDetector(profile)
            detNoisy.beginCounting()
            val noisyCount = noisy.count { detNoisy.add(it) != null } + detNoisy.finishAll().size
            assertEquals(0, noisyCount, "$id noise")
        }
    }

    @Test
    fun zottmanCurlPronationInvariantCountsSupinatedAndPronatedReps() {
        val detector = ProfiledMotionRepDetector(ExerciseTrackingProfiles.resolve("zottman_curl"))
        detector.beginCounting()
        val dtNs = 20_000_000L
        var t = 1_000_000_000L
        val samples = ArrayList<SensorSample>()
        // 30-deg forearm angle at bottom; pronation flips X/Z gravity while forearm Y stays invariant.
        fun addSample(elevDeg: Double, rollRad: Double, gyY: Float = 0f) {
            val elev = Math.toRadians(elevDeg)
            val ay = (9.80665 * cos(elev)).toFloat()
            val radial = 9.80665 * sin(elev)
            val ax = (radial * sin(rollRad)).toFloat()
            val az = (-radial * cos(rollRad)).toFloat()
            samples += SensorSample(t, ax, ay, az, 0f, gyY, 0f, 3)
            t += dtNs
        }
        repeat(20) { addSample(30.0, 0.0) }
        repeat(2) {
            // Rep 1: curl up supinated (roll=0), pronate at top (roll->PI), lower pronated (roll=PI)
            for (i in 1..65) addSample(30.0 + 100.0 * (i / 65.0), 0.0)
            for (i in 1..65) addSample(130.0 - 100.0 * (i / 65.0), PI)
            // Rep 2: curl up pronated (roll=PI), supinate at top (roll->0), lower supinated (roll=0)
            for (i in 1..65) addSample(30.0 + 100.0 * (i / 65.0), PI)
            for (i in 1..65) addSample(130.0 - 100.0 * (i / 65.0), 0.0)
        }
        repeat(20) { addSample(30.0, 0.0) }
        val count = samples.count { detector.add(it) != null } + detector.finishAll().size
        assertEquals(4, count)
    }
}
