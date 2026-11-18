package dev.kyungmin.watchcoach.core

import java.io.File
import org.junit.jupiter.api.Assumptions.assumeTrue
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Narrow production-path regression around the machine_fly finding: a wrist that never moves must not count in the
 * multi-axis family, and the normal controls must keep counting an ordinary out-and-back wrist cycle.
 */
class ProfiledMotionRepDetectorNoMotionRegressionTest {
    private val fly = ExerciseTrackingProfiles.resolve("machine_fly")
    private val g = 9.80665f

    private fun sample(index: Int, ax: Float = 0f, ay: Float = -g, az: Float = 0f, axG: Float = 0f, ayG: Float = 0f, azG: Float = 0f) =
        SensorSample(1_000_000_000L + index * 20_000_000L, ax, ay, az, axG, ayG, azG)

    private fun feed(profile: ExerciseTrackingProfile, samples: List<SensorSample>): List<ProfiledMotionRepEvent> {
        val detector = ProfiledMotionRepDetector(profile)
        val events = mutableListOf<ProfiledMotionRepEvent>()
        samples.forEachIndexed { index, sample ->
            if (index == 0) detector.beginCounting()
            detector.add(sample)?.let { events.add(it) }
        }
        events.addAll(detector.finishAll())
        return events
    }

    /** A still wrist: all samples carry constant orientation, so gyro and dynamic acceleration stay zero. */
    @Test fun stillWristCountsNothingForFlyFamilyEvenForTwentySeconds() {
        val still = (0 until 1_000).map { sample(it) }
        assertEquals(0, feed(fly, still).size)
    }

    /** The same still signal with tiny sensor offset must also stay at zero, not become a rep. */
    @Test fun stillWristWithSmallOffsetCountsNothingForFlyFamily() {
        val still = (0 until 1_000).map { sample(it, ax = 0.07f, ay = -g + 0.10f, az = -0.05f) }
        assertEquals(0, feed(fly, still).size)
    }

    /** Sumo and trap-bar deadlifts are counted from height change: still and noisy-but-idle wrists must count nothing. */
    @Test fun lowFloorDeadliftsCountNothingOnStillOrNoisyWrist() {
        for (id in listOf("sumo_deadlift", "trap_bar_deadlift")) {
            val profile = ExerciseTrackingProfiles.resolve(id)
            val still = (0 until 1_500).map { sample(it, ax = 0.07f, ay = -g + 0.10f, az = -0.05f) }
            assertEquals(0, feed(profile, still).size, "$id still")
            val random = java.util.Random(7)
            val noisy = (0 until 1_500).map {
                sample(it, ax = (random.nextGaussian() * 0.35).toFloat(), ay = -g + (random.nextGaussian() * 0.35).toFloat(),
                    az = (random.nextGaussian() * 0.35).toFloat(),
                    axG = (random.nextGaussian() * 0.03).toFloat(), ayG = (random.nextGaussian() * 0.03).toFloat(), azG = (random.nextGaussian() * 0.03).toFloat())
            }
            assertEquals(0, feed(profile, noisy).size, "$id noise")
        }
    }

    private inner class Stream {
        val samples = mutableListOf<SensorSample>()
        var index = 0
        val mark: Int get() = index
        fun still(count: Int) = repeat(count) { samples.add(sample(index++)) }
        fun move(count: Int, axG: Float, azG: Float = 0.4f) =
            repeat(count) { samples.add(sample(index++, axG = axG, azG = azG)) }
        fun jiggle(count: Int) = repeat(count) {
            samples.add(sample(index++, axG = if (it % 2 == 0) 0.03f else -0.03f, azG = 0.01f))
        }
        fun twitch(count: Int) = move(count, 1.5f)
    }

    /** Unilateral swings never close a cycle, so they must not count. */
    @Test fun repeatedOneWaySwingsWithoutReturnCountNothing() {
        val stream = Stream()
        stream.still(20)
        repeat(6) {
            stream.move(25, 1.5f)
            stream.move(25, 1.5f)
            stream.still(10)
        }
        assertEquals(0, feed(fly, stream.samples).size)
    }

    /** Sub-threshold jiggle around the start pose must not become a rep. */
    @Test fun subThresholdJiggleCountsNothing() {
        val stream = Stream()
        stream.still(20)
        repeat(200) { stream.jiggle(6); stream.still(4) }
        assertEquals(0, feed(fly, stream.samples).size)
    }

    /** A short twitch followed by a reversal is not a repetition. */
    @Test fun shortTwitchAndReversalCountsNothing() {
        val stream = Stream()
        stream.still(20)
        repeat(6) {
            stream.twitch(3)
            stream.still(2)
            stream.move(3, -1.5f)
            stream.still(40)
        }
        assertEquals(0, feed(fly, stream.samples).size)
    }

    /**
     * The measured reproduction: 1.6 s out + 1.6 s back captures of the fly cycle, labelled here by their own
     * authored schedule (ten complete cycles, ten turns), driven through the production detector.
     */
    @Test fun measuredFlyCycleCapturesCountOneEventPerAuthoredTurnaround() {
        val configured = System.getenv("WATCHCOACH_MACHINE_FLY_CYCLES")
        assumeTrue(!configured.isNullOrBlank(), "Optional measured cycle inputs not configured")
        File(configured!!).readLines().filter { it.isNotBlank() }.forEach { line ->
            val fields = line.split('\t')
            require(fields.size == 5 && fields[1] == "machine_fly")
            val truth = File(fields[0], "truth.json").readText()
            val expected = Regex("\"expected_reps\"\\s*:\\s*(\\d+)").find(truth)!!.groupValues[1].toInt()
            val turns = Regex("\"turnaround_ns\"\\s*:\\s*(\\d+)").findAll(truth).map { it.groupValues[1].toLong() }.toList()
            val document = SensorCaptureFormat.read(File(fields[0], "capture.kcs").readBytes().inputStream())
            val profile = ExerciseTrackingProfiles.resolve("machine_fly")
            val detector = ProfiledMotionRepDetector(profile)
            val events = mutableListOf<ProfiledMotionRepEvent>()
            val feedNs = fields[2].toLong()
            var started = false
            SensorCaptureReplay.replay(document) { _, record ->
                val sample = SensorRecordQuality.forCounting(record)
                if (sample.timestampNs <= feedNs) return@replay
                if (!started) { detector.beginCounting(); started = true }
                detector.add(sample)?.let { events.add(it) }
            }
            events.addAll(detector.finishAll())
            println("MEASURED ${File(fields[0]).name}: expected=$expected got=${events.size}")
            assertEquals(expected, turns.size)
            // Names embed the current reproduced count: the unfixed detector drops every other rep in these two cases.
            val knownCounts = mapOf(
                "comfortable80_2.0out_2.0ret-fusion-clean" to 10,
                "comfortable80_2.0out_hold_0.35ret_2.0-fusion-clean" to 5,
            )
            assertEquals(knownCounts.getValue(File(fields[0]).name), events.size,
                "Reproduced production count changed: ${File(fields[0]).name}")
            events.forEachIndexed { i, event ->
                assertTrue(event.durationMs in profile.minimumRepMs..profile.maximumRepMs)
            }
            // Each detection is the authored turnaround plus a bounded emission delay (synthetic accel peak),
            // checked only where every authored cycle was counted.
            if (events.size == turns.size) {
                turns.zip(events.map { it.turnaroundTimestampNs }).forEach { (authored, reported) ->
                    val errorMs = (reported - authored) / 1_000_000.0
                    assertTrue(reported >= authored && errorMs <= 750.0,
                        "Reported turnaround must lag the authored one by at most 750 ms: ${File(fields[0]).name}")
                }
            }
        }
    }

    @Test fun normalControlIdsKeepTheirResolvedFamilies() {
        assertEquals(MotionFamily.TRANSLATION_PRESS_RETURN, ExerciseTrackingProfiles.resolve("flat_machine_bench_press").family)
        assertEquals(
            MotionFamily.VERTICAL_PRESS_RETURN,
            ExerciseTrackingProfiles.resolve("dumbbell_shoulder_press").family,
        )
    }
}
