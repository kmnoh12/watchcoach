package dev.kyungmin.watchcoach.core

import java.io.File
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test

/**
 * machine_fly ablation replay through the real production detector and profile resolver.
 * The optional index is configured only for offline diagnostics; nothing here asserts a count.
 */
class VirtualWatchMachineFlyTest {
    @Test fun replayConfiguredMachineFlyAblationCasesWithProductionDetector() {
        val configured = System.getenv("WATCHCOACH_MACHINE_FLY_INDEX")
        assumeTrue(!configured.isNullOrBlank(), "Optional machine_fly ablation index not configured")
        val index = File(configured!!)
        require(index.isFile) { "Configured ablation index is missing" }
        val header = "case_path\tsignal\tfeed_ns\ttime_s\tacceleration\tgyro\toutput_path"
        val lines = index.readLines()
        require(lines.first() == header) { "Unexpected ablation index header" }
        lines.drop(1).forEach { line ->
            val fields = line.split('\t')
            require(fields.size == 7)
            val truth = File(fields[0], "truth.json").readText()
            val exercise = Regex("\"exercise_id\"\\s*:\\s*\"([^\"]+)\"").find(truth)?.groupValues?.get(1)
            require(exercise == "machine_fly") { "Only machine_fly cases are allowed" }
            val profile = ExerciseTrackingProfiles.resolve(exercise).let { resolved ->
                val signal = when (fields[1]) {
                    "fusion" -> resolved.signal
                    "accel_only" -> TrackingSignal.DYNAMIC_ACCELERATION
                    "gyro_only" -> TrackingSignal.ROTATION_ENERGY
                    else -> error("Unknown ablation signal")
                }
                resolved.copy(signal = signal)
            }
            val detector = ProfiledMotionRepDetector(profile)
            val times = fields[3].split(',').map(String::toDouble)
            val accel = fields[4].split(';').map { it.split(',') }
            val gyro = fields[5].split(';').map { it.split(',') }
            require(times.size == accel.size && times.size == gyro.size)
            val feedNs = fields[2].toLong()
            val records = times.indices.map { i ->
                SensorCaptureRecord(SensorSample(
                    Math.round(times[i] * 1e9),
                    accel[i][0].toFloat(), accel[i][1].toFloat(), accel[i][2].toFloat(),
                    gyro[i][0].toFloat(), gyro[i][1].toFloat(), gyro[i][2].toFloat(),
                ))
            }
            val events = mutableListOf<Pair<String, ProfiledMotionRepEvent>>()
            // Read-only copy of the production blending (same constants) for offline axis diagnosis.
            val gravity = doubleArrayOf(0.0, 0.0, 0.0)
            var gravityInitialized = false
            val traces = StringBuilder("time_s\tacc_x\tacc_y\tacc_z\tgyro_x\tgyro_y\tgyro_z\tfeature_x\tfeature_y\tfeature_z\tgyro_dominant\tdynamic_dominant\n")
            var started = false
            SensorCaptureReplay.replay(SensorCaptureDocument(2, 50.0, records)) { _, record ->
                val sample = SensorRecordQuality.forCounting(record)
                if (sample.timestampNs <= feedNs) return@replay
                if (!started) {
                    detector.beginCounting()
                    started = true
                }
                if (profile.signal == TrackingSignal.COMBINED_MOTION && started) {
                    val a = doubleArrayOf(sample.accelerationX.toDouble(), sample.accelerationY.toDouble(), sample.accelerationZ.toDouble())
                    val g = doubleArrayOf(sample.gyroscopeX.toDouble(), sample.gyroscopeY.toDouble(), sample.gyroscopeZ.toDouble())
                    if (!gravityInitialized) {
                        a.copyInto(gravity); gravityInitialized = true
                    } else {
                        for (k in 0..2) gravity[k] = gravity[k] * 0.9 + a[k] * 0.1
                        val dynamic = DoubleArray(3) { i -> a[i] - gravity[i] }
                        val blended = DoubleArray(3) { i -> g[i] + dynamic[i] * 0.12 }
                        val gyroDominant = (0..2).maxByOrNull { kotlin.math.abs(g[it]) }!!
                        val dynamicDominant = (0..2).maxByOrNull { kotlin.math.abs(dynamic[it]) }!!
                        traces.append((sample.timestampNs / 1e9).toString()).append("\t")
                        (a + g).forEach { traces.append(String.format("%.4f", it)).append("\t") }
                        blended.forEach { traces.append(String.format("%.4f", it)).append("\t") }
                        traces.append(gyroDominant).append("\t").append(dynamicDominant).append("\n")
                    }
                }
                detector.add(sample)?.let { events.add(Pair("live", it)) }
            }
            detector.finishAll().forEach { events.add(Pair("offline_flush", it)) }
            val output = File(fields[6])
            require(output.canonicalFile.parentFile == index.canonicalFile.parentFile)
            output.mkdirs()
            File(output, "events.tsv").writeText(
                buildString {
                    appendLine("channel\tstart_ns\tturnaround_ns\tend_ns\tduration_ms\tpeak_motion_rate\tmotion_displacement\ttrajectory_spread\tconfidence")
                    events.forEach { (channel, e) ->
                        appendLine(listOf(channel, e.startTimestampNs, e.turnaroundTimestampNs, e.endTimestampNs, e.durationMs,
                            e.peakMotionRate, e.motionDisplacement, e.trajectorySpread, e.confidence).joinToString("\t"))
                    }
                },
            )
            File(output, "trace.tsv").writeText(traces.toString())
            File(output, "stats.tsv").writeText(listOf(
                "algorithm_id" to profile.id, "signal" to profile.signal,
                "minimum_lobe_ms" to profile.minimumLobeMs, "maximum_lobe_ms" to profile.maximumLobeMs,
                "minimum_lobe_displacement" to profile.minimumLobeDisplacement,
                "minimum_trajectory_spread" to profile.minimumTrajectorySpread,
                "minimum_rep_ms" to profile.minimumRepMs, "maximum_rep_ms" to profile.maximumRepMs,
                "minimum_separation_ms" to profile.minimumSeparationMs,
                "sample_count" to records.size, "last_motion_ns" to detector.lastMotionNs,
                "candidate_start_ns" to detector.candidateStartNs,
            ).joinToString("\n", postfix = "\n") { "${it.first}\t${it.second}" })
            println("ABLATION ${File(fields[0]).name}: events=${events.size}")
        }
    }
}
