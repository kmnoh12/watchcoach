package dev.kyungmin.watchcoach.core

import java.io.File
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test

/**
 * straight_arm_pulldown virtual-watch replay through the real production profile resolver and ProfiledMotionRepDetector.
 *
 * The cases are the independent synthetic inputs written by tools/gen_virtual_watch_straight_arm_pulldown.py. Only
 * this exercise is allowed. Synthetic mounting and noise are not physically calibrated; nothing here is Wear accuracy.
 */
class VirtualWatchStraightArmPulldownTest {
    private val exercise = "straight_arm_pulldown"
    private val cases = setOf("continuous_10_clean", "continuous_10_tempo_variation", "return_boundary_hold",
        "ten_then_handle_down", "handle_down_only")

    private data class Observed(val channel: String, val emittedAtNs: Long, val event: ProfiledMotionRepEvent)

    /** The production KCS reader, so the capture layout is never imitated here. */
    private object CaptureReader {
        fun records(file: File): List<SensorCaptureRecord> =
            SensorCaptureFormat.read(file.inputStream()).let { document ->
                require(document.records.size >= 40) { "Too few capture records" }
                document.records.map { record ->
                    val sample = record.sample
                    require(listOf(sample.accelerationX, sample.accelerationY, sample.accelerationZ,
                        sample.gyroscopeX, sample.gyroscopeY, sample.gyroscopeZ).all { it.isFinite() && kotlin.math.abs(it) < 1e5 }) {
                        "Unusable capture sample at ${sample.timestampNs}"
                    }
                    record
                }
            }
    }

    @Test fun replayConfiguredStraightArmPulldownCasesWithProductionDetector() {
        val root = System.getenv("WATCHCOACH_STRAIGHT_ARM_PULLDOWN_ROOT")?.takeIf { it.isNotBlank() }
        assumeTrue(root != null, "Optional straight_arm_pulldown case root not configured")
        val index = File(root!!)
        require(index.isFile) { "Configured case index is missing" }
        val lines = index.readLines()
        require(lines.first() == "case_path\tmode\toutput_path") { "Unexpected straight_arm_pulldown index header" }
        lines.drop(1).forEach { line ->
            val fields = line.split('\t')
            require(fields.size == 3) { "Unexpected straight_arm_pulldown index row" }
            val caseDir = File(fields[0])
            val mode = fields[1]
            require(caseDir.name in cases) { "Only straight_arm_pulldown cases are allowed" }
            require(caseDir.resolve("case_id.json").readText().contains("\"exercise_id\": \"$exercise\"")) {
                "Case is not straight_arm_pulldown"
            }
            val prepEndNs = Regex("\"prep_end_ns\"\\s*:\\s*(\\d+)")
                .find(caseDir.resolve("prep_end_ns.json").readText())!!.groupValues[1].toLong()
            val production = ExerciseTrackingProfiles.resolve(exercise)
            require(production.exerciseId == exercise && production.family == MotionFamily.CYCLE_AXIS_RETURN)
            val profile = when (mode) {
                "baseline" -> production
                // Test-only local seam: ProfiledMotionRepDetector already keys its return-counting option on the
                // exercise id. Only that routing differs; every threshold and constant stays as production.
                "counterfactual_return_counting" -> production.copy(exerciseId = "seated_row")
                else -> error("Unknown replay mode")
            }
            val output = File(fields[2])
            // Only inside the configured case root (canonical, so a symlinked temporary folder is still inside it).
            require(output.canonicalFile.startsWith(index.canonicalFile.parentFile)) { "Output escapes the case root" }
            output.mkdirs()
            val observed = replay(CaptureReader.records(caseDir.resolve("capture.kcs")), profile, prepEndNs)
            val text = StringBuilder("channel\tstart_ns\tturnaround_ns\tend_ns\tduration_ms\tpeak_motion_rate\tmotion_displacement\ttrajectory_spread\tconfidence\tdetector_emitted_at_ns\n")
            observed.forEach { o ->
                val e = o.event
                text.appendLine(listOf(o.channel, e.startTimestampNs, e.turnaroundTimestampNs, e.endTimestampNs, e.durationMs,
                    e.peakMotionRate, e.motionDisplacement, e.trajectorySpread, e.confidence, o.emittedAtNs).joinToString("\t"))
            }
            output.resolve("events.tsv").writeText(text.toString())
            println("CASE ${caseDir.name} mode=$mode live=${observed.count { it.channel == "live" }} " +
                "flush=${observed.count { it.channel == "offline_flush" }}")
        }
    }

    private data class ReplayState(var started: Boolean = false)

    private fun replay(records: List<SensorCaptureRecord>, profile: ExerciseTrackingProfile, prepEndNs: Long): List<Observed> {
        val detector = ProfiledMotionRepDetector(profile)
        val events = mutableListOf<Observed>()
        val state = ReplayState()
        records.forEach { record ->
            val sample = SensorRecordQuality.forCounting(record)
            // The Wear service observes its start gate and calls beginCounting here, not the repetition detector.
            if (sample.timestampNs <= prepEndNs) return@forEach
            if (!state.started) {
                detector.beginCounting()
                state.started = true
            }
            val event = detector.add(sample) ?: return@forEach
            val accepted = profile.family != MotionFamily.VERTICAL_PRESS_RETURN || VerticalRepAmplitude.accepts(event)
            if (accepted) events += Observed("live", sample.timestampNs, event)
        }
        detector.finishAll().forEach { events += Observed("offline_flush", -1L, it) }
        return events
    }
}
