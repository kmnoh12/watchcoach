package dev.kyungmin.watchcoach.core

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.sqrt

/** Motion families describe the observable wrist cycle, not whole-body form. */
enum class MotionFamily {
    FLEXION_EXTENSION,
    PRESS_RETURN,
    VERTICAL_PRESS_RETURN,
    TRANSLATION_PRESS_RETURN,
    PULL_RETURN,
    MULTI_AXIS_RETURN,
    ARC_RETURN,
    FOREARM_ROTATION,
    CYCLE_AXIS_RETURN,
    UNOBSERVABLE_MANUAL;

    val sharedAlgorithmId: String
        get() = when (this) {
            FLEXION_EXTENSION -> "flexion-extension-pose-v4"
            PRESS_RETURN -> "press-return-family-v4"
            VERTICAL_PRESS_RETURN -> "vertical-press-return-family-v1"
            TRANSLATION_PRESS_RETURN -> "translation-press-return-family-v1"
            PULL_RETURN -> "pull-return-family-v4"
            MULTI_AXIS_RETURN -> "multi-axis-return-family-v4"
            ARC_RETURN -> "arc-return-family-v1"
            FOREARM_ROTATION -> "forearm-rotation-family-v4"
            CYCLE_AXIS_RETURN -> "cycle-axis-return-family-v1"
            UNOBSERVABLE_MANUAL -> "manual-required-v3"
        }

    /** Accepted only to replay an explicitly frozen historical detector. */
    val legacyAlgorithmId: String?
        get() = when (this) {
            PRESS_RETURN, PULL_RETURN, MULTI_AXIS_RETURN, FOREARM_ROTATION -> sharedAlgorithmId.removeSuffix("v4") + "v3"
            else -> null
        }

    val displayLabel: String
        get() = when (this) {
            FLEXION_EXTENSION -> "굴곡-신전 공통 측정"
            PRESS_RETURN -> "프레스-복귀 공통 측정"
            VERTICAL_PRESS_RETURN -> "상하 프레스-복귀 측정"
            TRANSLATION_PRESS_RETURN -> "이동 프레스-복귀 측정"
            PULL_RETURN -> "당김-복귀 공통 측정"
            MULTI_AXIS_RETURN -> "다축 왕복 공통 측정"
            ARC_RETURN -> "원호 왕복 공통 측정"
            FOREARM_ROTATION -> "전완 회전 공통 측정"
            CYCLE_AXIS_RETURN -> "주기 축 왕복 공통 측정"
            UNOBSERVABLE_MANUAL -> "수동 측정"
        }
}

data class ProfiledMotionRepEvent(
    val startTimestampNs: Long,
    val turnaroundTimestampNs: Long,
    val endTimestampNs: Long,
    val durationMs: Long,
    val peakMotionRate: Double,
    val motionDisplacement: Double,
    val trajectorySpread: Double,
    val confidence: Double,
    val cueDelayMs: Long = 0L,
)

/**
 * Deterministic, profile-driven repetition detector for non-rotation exercises.
 *
 * Flexion/extension uses departure from and return to the starting wrist tilt.
 * Other families retain their existing signed-signal cycle detector below.
 * Each exercise supplies a motion family; that family supplies shared thresholds. The detector only
 * claims a rep after two valid, opposite-direction lobes (out and back) and can
 * require multi-axis trajectory spread for arc/fly movements. It does not claim
 * joint position, shoulder fixation, load travel, or strict form.
 */
class ProfiledMotionRepDetector(
    private val profile: ExerciseTrackingProfile,
    /** Watch X axis sign toward the hand ([ForearmAxis]); fixes when a press counts. */
    private val handwardX: Int = ForearmAxis.DEFAULT_HANDWARD_X,
) {
    companion object {
        private const val GRAVITY_FILTER_ALPHA = 0.10
        private const val MAX_SAMPLE_GAP_MS = 450L
        private const val MOTION_GYRO_FLOOR = 0.25
        private const val MOTION_ACCELERATION_FLOOR = 0.25
        private const val MOTION_BASELINE_TAU_S = 1.5
        private const val MOTION_SMOOTHING_TAU_S = 0.15

        /** Provisional (no plate-press capture yet): a lobe this large that failed validation still shows which way the press goes. */
        private const val PHASE_LOBE_MIN_MS = 30L
        private const val PHASE_LOBE_FRACTION = 0.15

        /** A truncated opening press and the return that follows it are one rep when they are this close. */
        private const val OPENING_RESCUE_GAP_MS = 500L

        /** The pull alone is half a rep: it must not reach the counter before the handle comes back. */
        private val SEATED_ROWS = setOf("seated_row", "cable_seated_row", "seated_cable_row_close",
            "single_arm_machine_seated_row", "single_arm_cable_seated_row")

        /** Straight-arm pulldown and pullovers: the first lobe is the pull, so count at the return or 10 reps read 11 (virtual-watch replay). */
        private val RETURN_COUNTED = setOf("straight_arm_pulldown", "cable_pullover", "machine_pullover") + setOf(
            // Squats and hinges (virtual-watch tier 3): the wrist travels with the body, a rep is done when the lifter stands again.
            "squat", "goblet_squat", "dumbbell_goblet_squat", "smith_squat", "box_squat", "zercher_squat", "overhead_squat",
            "dumbbell_deadlift", "conventional_deadlift", "sumo_deadlift", "good_morning", "kettlebell_swing",
        )

        /** Deadlifts and hinges counted from the wrist's height change in metres instead of acceleration size (tempo independent). */
        private val HINGE_DISPLACEMENT = setOf(
            "sumo_deadlift", "trap_bar_deadlift", "conventional_deadlift", "dumbbell_deadlift",
            "romanian_deadlift_barbell", "romanian_deadlift_dumbbell", "stiff_leg_deadlift", "good_morning",
        )

        /** Translation-routed pushdowns whose forearm rotates ~66 deg around the elbow, lagging the slow gravity LPF on rep 1. */
        private val GYRO_GRAVITY_PUSHDOWNS = setOf("single_arm_cable_pushdown", "reverse_grip_pushdown")

        /** Flexion-extension curls that pronate at the top and lower pronated, inverting X/Z gravity while forearm Y matches bottom. */
        private val PRONATION_INVARIANT_POSES = setOf("zottman_curl")

        /** Rowing strokes with strong linear travel whose minor forearm pitch wiggle double-peaks in gyro. */
        private val DYN_ONLY_ROWS = setOf("one_arm_dumbbell_row")

        /**
         * Rowing exercises routed to direct causal return-stop detection ([RowReturnStopDetector]).
         * Scoped strictly to rows so lateral/front raises, straight-arm pulldowns, face pulls,
         * squats, and pull-ups keep their existing [CycleAxisRepDetector] behavior unchanged.
         */
        private val ROW_RETURN_STOP_EXERCISES = setOf(
            "seated_row", "cable_seated_row", "seated_cable_row_close",
            "single_arm_machine_seated_row", "single_arm_cable_seated_row",
            "one_arm_cable_row", "barbell_row", "bent_over_dumbbell_row", "one_arm_dumbbell_row",
            "lying_tbar_row", "machine_row_plate", "single_arm_plate_loaded_row",
            "high_row_machine", "single_arm_high_row_machine", "machine_tbar_row", "tbar_row_landmine",
            "chest_supported_dumbbell_row", "single_arm_chest_supported_dumbbell_row",
            "seal_row", "meadows_row", "inverted_row",
        )
    }

    private val poseCounter = if (profile.family == MotionFamily.FLEXION_EXTENSION)
        ReturnToPoseRepDetector(profile.minimumRepMs, pronationInvariant = profile.exerciseId in PRONATION_INVARIANT_POSES) else null
    private val verticalCounter = if (profile.family == MotionFamily.VERTICAL_PRESS_RETURN) VerticalPressRepDetector(profile) else null
    private val translationCounter = if (profile.family == MotionFamily.TRANSLATION_PRESS_RETURN)
        TranslationPressRepDetector(profile, rotateGravityByGyro = profile.exerciseId in GYRO_GRAVITY_PUSHDOWNS) else null
    private val hingeCounter = if (profile.family == MotionFamily.CYCLE_AXIS_RETURN && profile.exerciseId in HINGE_DISPLACEMENT)
        HingeDisplacementRepDetector() else null
    private val rowReturnStopCounter = if (profile.family == MotionFamily.CYCLE_AXIS_RETURN &&
        hingeCounter == null &&
        profile.exerciseId in ROW_RETURN_STOP_EXERCISES
    ) RowReturnStopDetector(dynOnly = profile.exerciseId in DYN_ONLY_ROWS) else null
    private val cycleCountOnReturn = profile.family == MotionFamily.CYCLE_AXIS_RETURN &&
        hingeCounter == null && rowReturnStopCounter == null && (
        ExerciseMeasurementContracts.resolve(profile.exerciseId).recipe in
            setOf(MeasurementRecipe.LATERAL_RAISE, MeasurementRecipe.ROW) ||
            profile.exerciseId in SEATED_ROWS || profile.exerciseId in RETURN_COUNTED
    )
    private val cycleCounter = if (profile.family == MotionFamily.CYCLE_AXIS_RETURN &&
        hingeCounter == null && rowReturnStopCounter == null
    ) CycleAxisRepDetector(
        countOnReturn = cycleCountOnReturn,
        phaseKernel = false,
        dynOnly = profile.exerciseId in DYN_ONLY_ROWS,
    ) else null
    private val arcCounter = if (profile.family == MotionFamily.ARC_RETURN) ForearmRotationRepDetector(profile) else null
    private val legacyLobes = profile.id.substringBefore('+') == profile.family.legacyAlgorithmId
    private val excursionCounter = if (!legacyLobes &&
        profile.id.substringBefore('+') == profile.family.sharedAlgorithmId &&
        profile.family in setOf(MotionFamily.PULL_RETURN, MotionFamily.MULTI_AXIS_RETURN, MotionFamily.PRESS_RETURN)
    ) ExcursionRepDetector(profile, handwardX) else null
    private val cueScheduler = UnifiedCueScheduler(
        family = profile.family,
        returnScale = RepCueDelay.returnScale(profile.exerciseId),
        suppressReturnDelay = rowReturnStopCounter != null,
    )

    private var lastTimestampNs = 0L
    private var motionSampleNs = 0L
    private var accelerationBaseline = Double.NaN
    private var accelerationDeviation = 0.0
    private var gravityInitialized = false
    private val gravity = DoubleArray(3)
    private var lockedAxis = -1
    private var direction = 0
    private var lobeStartNs = 0L
    private var lobeDisplacement = 0.0
    private var lobePeakRate = 0.0
    private var lobeMainEnergy = 0.0
    private var lobeSecondaryEnergy = 0.0
    private var pendingStartNs = 0L
    private var pendingTurnaroundNs = 0L
    private var pendingPeakRate = 0.0
    private var pendingDisplacement = 0.0
    private var pendingSpread = 0.0
    private var pendingDirection = 0
    private var lastCommittedEndNs = Long.MIN_VALUE
    private var refractoryUntilNs = 0L

    // Which signed lobe is the "out" half (the press) on the locked axis, learned from the first meaningful lobe of the set
    // and kept across lobe resets. Used only to recognise a cut-off opening press.
    private var outSign = 0
    private var outAxis = -1
    private var rejectedOutStartNs = 0L
    private var rejectedOutEndNs = 0L
    private var rejectedOutPeak = 0.0
    private var rejectedOutDisplacement = 0.0
    private var rejectedOutSpread = 0.0

    // Pose counting previously allowed long top holds without a maximum duration.
    // Bound set-end grace at 12s, preserving slow returns; this policy still needs Watch8 validation.
    val maximumCycleNs: Long get() = translationCounter?.maximumCycleNs ?: verticalCounter?.maximumCycleNs ?: hingeCounter?.maximumCycleNs ?: rowReturnStopCounter?.maximumCycleNs ?: cycleCounter?.maximumCycleNs ?: if (poseCounter != null) 12_000_000_000L else profile.maximumRepMs * 1_000_000L

    /** Latest sample that looked like working motion, even when no complete rep was accepted. */
    var lastMotionNs: Long = 0L
        private set

    val candidateStartNs: Long? get() = arcCounter?.candidateStartNs ?: if (rowReturnStopCounter != null || cycleCounter != null || hingeCounter != null || excursionCounter != null) null else translationCounter?.candidateStartNs ?: verticalCounter?.candidateStartNs ?: poseCounter?.candidateStartNs ?: pendingStartNs.takeIf { it > 0L }
        ?: lobeStartNs.takeIf { it > 0L && lobeDisplacement >= profile.minimumLobeDisplacement }

    fun add(sample: SensorSample): ProfiledMotionRepEvent? {
        trackMotion(sample)
        cueScheduler.observe(sample)
        val event = detectSample(sample) ?: return null
        return event.copy(cueDelayMs = cueScheduler.schedule(event, sample.timestampNs))
    }

    private fun detectSample(sample: SensorSample): ProfiledMotionRepEvent? {
        arcCounter?.let { return it.add(sample)?.asProfiledEvent() }
        translationCounter?.let { return it.add(sample) }
        verticalCounter?.let { return it.add(sample) }
        hingeCounter?.let { return it.add(sample) }
        rowReturnStopCounter?.let { return it.add(sample) }
        cycleCounter?.let { return it.add(sample) }
        poseCounter?.let { return it.add(sample) }
        excursionCounter?.let { return it.add(sample) }
        if (sample.sensorAccuracy == 0) { resetAll(); lastTimestampNs = 0L; return null }
        val timestampNs = sample.timestampNs
        if (lastTimestampNs > 0L && timestampNs <= lastTimestampNs) return null
        val dtMs = if (lastTimestampNs > 0L) {
            ((timestampNs - lastTimestampNs) / 1_000_000L).coerceAtLeast(0L)
        } else {
            0L
        }
        lastTimestampNs = timestampNs
        if (dtMs > MAX_SAMPLE_GAP_MS) resetAll()

        val vector = featureVector(sample)
        val candidateAxis = vector.indices.maxByOrNull { abs(vector[it]) } ?: return null
        if (lockedAxis < 0 && abs(vector[candidateAxis]) >= profile.minimumFeatureRate) {
            lockedAxis = candidateAxis
        }
        if (lockedAxis < 0) return null

        val projected = vector[lockedAxis]
        val magnitude = abs(projected)
        if (timestampNs < refractoryUntilNs) return null

        if (magnitude < profile.minimumFeatureRate) {
            return if (direction != 0) closeLobe(timestampNs) else null
        }

        val nextDirection = if (projected >= 0.0) 1 else -1
        if (direction == 0) {
            startLobe(timestampNs, nextDirection, magnitude)
            return null
        }

        if (nextDirection != direction) {
            val completed = closeLobe(timestampNs)
            if (lockedAxis < 0) lockedAxis = candidateAxis
            startLobe(timestampNs, nextDirection, magnitude)
            return completed
        }

        if (dtMs in 1..MAX_SAMPLE_GAP_MS) {
            lobeDisplacement += magnitude * dtMs / 1_000.0
            lobeMainEnergy += magnitude * dtMs / 1_000.0
            lobeSecondaryEnergy += secondaryMagnitude(vector) * dtMs / 1_000.0
        }
        lobePeakRate = max(lobePeakRate, magnitude)
        return null
    }

    fun finish(): ProfiledMotionRepEvent? {
        arcCounter?.let { return it.finish()?.asProfiledEvent() }
        if (translationCounter != null || verticalCounter != null || rowReturnStopCounter != null || cycleCounter != null || hingeCounter != null || excursionCounter != null) return null
        if (poseCounter != null) return null // A partial return never becomes a rep when the set ends.
        if (!legacyLobes) { resetAll(); return null } // Only observed quiet/reversal closes a new-engine lobe.
        if (direction == 0 || lastTimestampNs == 0L) return null
        val result = closeLobe(lastTimestampNs)
        resetActiveLobe()
        return result
    }

    /**
     * Ends the stationary preparation window without throwing away the gravity
     * estimate learned from the user's real starting pose.
     */
    /** Offline end of stream: every rep still undelivered (the cycle engine confirms reps with a delay). */
    fun finishAll(): List<ProfiledMotionRepEvent> = translationCounter?.finishAll() ?: hingeCounter?.finishAll() ?: rowReturnStopCounter?.finishAll() ?: cycleCounter?.finishAll() ?: listOfNotNull(finish())

    fun beginCounting() {
        arcCounter?.beginCounting()
        translationCounter?.beginCounting()
        verticalCounter?.beginCounting()
        hingeCounter?.beginCounting()
        rowReturnStopCounter?.beginCounting()
        cycleCounter?.beginCounting()
        poseCounter?.reset()
        excursionCounter?.beginCounting()
        resetActiveLobe()
        pendingStartNs = 0L
        pendingTurnaroundNs = 0L
        pendingPeakRate = 0.0
        pendingDisplacement = 0.0
        pendingSpread = 0.0
        pendingDirection = 0
        lastCommittedEndNs = Long.MIN_VALUE
        refractoryUntilNs = 0L
        lockedAxis = -1
        lastTimestampNs = 0L
        lastMotionNs = 0L
        forgetPhase()
    }

    /**
     * Primes the underlying rep detector with stable preparation samples without updating
     * motion-idle tracking or emitting repetitions.
     */
    fun prime(samples: Iterable<SensorSample>) {
        val iterator = samples.iterator()
        if (!iterator.hasNext()) return
        when {
            arcCounter != null -> return
            translationCounter != null -> {
                while (iterator.hasNext()) translationCounter.add(iterator.next())
                translationCounter.beginCounting()
            }
            verticalCounter != null -> {
                while (iterator.hasNext()) verticalCounter.add(iterator.next())
                verticalCounter.beginCounting()
            }
            hingeCounter != null -> hingeCounter.prime(samples)
            rowReturnStopCounter != null -> rowReturnStopCounter.prime(samples)
            cycleCounter != null -> cycleCounter.prime(samples)
            poseCounter != null -> while (iterator.hasNext()) poseCounter.add(iterator.next())
            excursionCounter != null -> excursionCounter.prime(samples)
            else -> while (iterator.hasNext()) {
                val sample = iterator.next()
                if (sample.sensorAccuracy == 0) {
                    resetAll()
                    lastTimestampNs = 0L
                } else {
                    featureVector(sample)
                }
            }
        }
    }

    private fun ForearmRotationRepEvent.asProfiledEvent() = ProfiledMotionRepEvent(
        startTimestampNs = startTimestampNs,
        turnaroundTimestampNs = turnaroundTimestampNs,
        endTimestampNs = endTimestampNs,
        durationMs = durationMs,
        peakMotionRate = peakAngularVelocity,
        motionDisplacement = angularDisplacement,
        trajectorySpread = 0.0,
        confidence = confidence,
    )

    private fun trackMotion(sample: SensorSample) {
        if (sample.sensorAccuracy == 0) return
        val gyro = sqrt(
            sample.gyroscopeX.toDouble() * sample.gyroscopeX +
                sample.gyroscopeY.toDouble() * sample.gyroscopeY +
                sample.gyroscopeZ.toDouble() * sample.gyroscopeZ,
        )
        val acceleration = sqrt(
            sample.accelerationX.toDouble() * sample.accelerationX +
                sample.accelerationY.toDouble() * sample.accelerationY +
                sample.accelerationZ.toDouble() * sample.accelerationZ,
        )
        // The accelerometer magnitude of a motionless Watch8 sits 0.07-0.21 m/s^2 off 9.80665 and varies between sessions
        // (recorded captures). Measured against that fixed value a still wrist read as moving a third of the time and the
        // set never ended, so movement is a deviation from a slow baseline, smoothed against single noisy samples.
        val t = sample.timestampNs
        var accelerationMoving = false
        if (acceleration.isFinite()) {
            val dtS = if (motionSampleNs > 0L && t > motionSampleNs) ((t - motionSampleNs) / 1e9).coerceAtMost(0.5) else 0.0
            if (accelerationBaseline.isNaN()) accelerationBaseline = acceleration
            else accelerationBaseline += (acceleration - accelerationBaseline) * (1.0 - exp(-dtS / MOTION_BASELINE_TAU_S))
            accelerationDeviation += (abs(acceleration - accelerationBaseline) - accelerationDeviation) *
                (1.0 - exp(-dtS / MOTION_SMOOTHING_TAU_S))
            accelerationMoving = accelerationDeviation >= MOTION_ACCELERATION_FLOOR
        }
        motionSampleNs = t
        if (gyro.isFinite() && gyro >= MOTION_GYRO_FLOOR || accelerationMoving) lastMotionNs = t
    }

    private fun featureVector(sample: SensorSample): DoubleArray {
        val acceleration = doubleArrayOf(
            sample.accelerationX.toDouble(),
            sample.accelerationY.toDouble(),
            sample.accelerationZ.toDouble(),
        )
        if (!gravityInitialized) {
            acceleration.copyInto(gravity)
            gravityInitialized = true
            return doubleArrayOf(0.0, 0.0, 0.0)
        }
        for (index in acceleration.indices) {
            gravity[index] = gravity[index] * (1.0 - GRAVITY_FILTER_ALPHA) +
                acceleration[index] * GRAVITY_FILTER_ALPHA
        }
        val dynamic = DoubleArray(3) { index -> acceleration[index] - gravity[index] }
        val gyro = doubleArrayOf(
            sample.gyroscopeX.toDouble(),
            sample.gyroscopeY.toDouble(),
            sample.gyroscopeZ.toDouble(),
        )
        return when (profile.signal) {
            TrackingSignal.ROTATION_ENERGY -> gyro
            TrackingSignal.DYNAMIC_ACCELERATION -> dynamic
            TrackingSignal.COMBINED_MOTION -> DoubleArray(3) { index ->
                gyro[index] + dynamic[index] * 0.12
            }
            TrackingSignal.FOREARM_ROTATION -> gyro
            TrackingSignal.UNOBSERVABLE_FROM_WRIST -> doubleArrayOf(0.0, 0.0, 0.0)
        }
    }

    private fun secondaryMagnitude(vector: DoubleArray): Double = sqrt(
        vector.indices
            .filter { it != lockedAxis }
            .sumOf { vector[it] * vector[it] },
    )

    private fun startLobe(timestampNs: Long, nextDirection: Int, magnitude: Double) {
        direction = nextDirection
        lobeStartNs = timestampNs
        lobeDisplacement = 0.0
        lobePeakRate = magnitude
        lobeMainEnergy = 0.0
        lobeSecondaryEnergy = 0.0
    }

    private fun closeLobe(endTimestampNs: Long): ProfiledMotionRepEvent? {
        if (direction == 0 || lobeStartNs == 0L) return null
        val durationMs = ((endTimestampNs - lobeStartNs) / 1_000_000L).coerceAtLeast(0L)
        val spread = lobeSecondaryEnergy / lobeMainEnergy.coerceAtLeast(1e-6)
        val valid = durationMs in profile.minimumLobeMs..profile.maximumLobeMs &&
            lobeDisplacement >= profile.minimumLobeDisplacement &&
            spread >= profile.minimumTrajectorySpread
        if (!valid) {
            if (!legacyLobes) {
                noteRejectedLobe(endTimestampNs, durationMs, spread)
                // A brief twitch between the press and its return (or from the haptic motor) is not a movement:
                // it must not throw away the half rep already seen. Over-long or single-axis lobes still reset.
                if (durationMs <= profile.maximumLobeMs &&
                    (durationMs < profile.minimumLobeMs || lobeDisplacement < profile.minimumLobeDisplacement)) {
                    resetActiveLobe()
                    return null
                }
            }
            resetAll()
            return null
        }
        if (!legacyLobes) rescueTruncatedOpeningPress()

        val result = if (pendingStartNs == 0L || !legacyLobes && pendingDirection == direction) {
            pendingStartNs = lobeStartNs
            pendingTurnaroundNs = endTimestampNs
            pendingPeakRate = lobePeakRate
            pendingDisplacement = lobeDisplacement
            pendingSpread = spread
            pendingDirection = direction
            null
        } else {
            val repDurationMs = ((endTimestampNs - pendingStartNs) / 1_000_000L).coerceAtLeast(0L)
            val separated = lastCommittedEndNs == Long.MIN_VALUE ||
                (pendingStartNs - lastCommittedEndNs) / 1_000_000L >= profile.minimumSeparationMs
            val repValid = repDurationMs in profile.minimumRepMs..profile.maximumRepMs && separated
            val event = if (repValid) {
                ProfiledMotionRepEvent(
                    startTimestampNs = pendingStartNs,
                    turnaroundTimestampNs = pendingTurnaroundNs,
                    endTimestampNs = endTimestampNs,
                    durationMs = repDurationMs,
                    peakMotionRate = max(pendingPeakRate, lobePeakRate),
                    motionDisplacement = pendingDisplacement + lobeDisplacement,
                    trajectorySpread = (pendingSpread + spread) / 2.0,
                    confidence = confidence(repDurationMs, pendingDisplacement + lobeDisplacement, spread),
                )
            } else {
                null
            }
            if (event != null) {
                lastCommittedEndNs = endTimestampNs
                refractoryUntilNs = endTimestampNs + profile.minimumSeparationMs * 1_000_000L
            }
            pendingStartNs = 0L
            pendingTurnaroundNs = 0L
            pendingPeakRate = 0.0
            pendingDisplacement = 0.0
            pendingSpread = 0.0
            pendingDirection = 0
            event
        }
        resetActiveLobe()
        return result
    }

    private fun meaningfulLobe(durationMs: Long): Boolean =
        durationMs >= PHASE_LOBE_MIN_MS && lobeDisplacement >= profile.minimumLobeDisplacement * PHASE_LOBE_FRACTION

    private fun forgetPhase() {
        outSign = 0
        outAxis = -1
        rejectedOutStartNs = 0L
        rejectedOutEndNs = 0L
    }

    /** A lobe too short or small to count still tells which way the press goes, and may be the cut-off start of the first rep. */
    private fun noteRejectedLobe(endTimestampNs: Long, durationMs: Long, spread: Double) {
        if (!meaningfulLobe(durationMs)) return
        if (outSign != 0 && lockedAxis != outAxis) forgetPhase()
        if (outSign == 0) { outSign = direction; outAxis = lockedAxis }
        if (direction == outSign) {
            rejectedOutStartNs = lobeStartNs
            rejectedOutEndNs = endTimestampNs
            rejectedOutPeak = lobePeakRate
            rejectedOutDisplacement = lobeDisplacement
            rejectedOutSpread = spread
        }
    }

    /**
     * The first press can be cut off by the start of counting, leaving only its return lobe valid. Pairing that return with the
     * next press shifted the whole set by half a cycle: the count and cue fired at every lift and the last return was left over.
     * When a rejected press lobe sits right before a valid return and nothing has been counted yet, the two are the first rep.
     * Later lone returns are left alone: dropping them cost real reps on recorded sets.
     */
    private fun rescueTruncatedOpeningPress() {
        if (outSign != 0 && lockedAxis != outAxis) forgetPhase()
        if (outSign == 0) { outSign = direction; outAxis = lockedAxis }
        if (pendingStartNs != 0L || direction == outSign) return
        val rescuable = rejectedOutEndNs > 0L && lastCommittedEndNs == Long.MIN_VALUE &&
            lobeStartNs - rejectedOutEndNs in 0L..OPENING_RESCUE_GAP_MS * 1_000_000L
        if (rescuable) {
            pendingStartNs = rejectedOutStartNs
            pendingTurnaroundNs = rejectedOutEndNs
            pendingPeakRate = rejectedOutPeak
            pendingDisplacement = rejectedOutDisplacement
            pendingSpread = rejectedOutSpread
            pendingDirection = outSign
            rejectedOutEndNs = 0L
        } else if (lastCommittedEndNs == Long.MIN_VALUE) {
            // Nothing counted yet, so the earlier guess may have been a stray movement: take this lobe as the press.
            outSign = direction
            outAxis = lockedAxis
        }
    }

    private fun confidence(durationMs: Long, displacement: Double, spread: Double): Double {
        val targetDuration = (profile.minimumRepMs + profile.maximumRepMs) / 2.0
        val durationScore = (1.0 - abs(durationMs - targetDuration) / targetDuration).coerceIn(0.0, 1.0)
        val displacementScore = ((displacement / (profile.minimumLobeDisplacement * 2.0)) - 1.0)
            .coerceIn(0.0, 1.0)
        val spreadScore = if (profile.minimumTrajectorySpread <= 0.0) 1.0 else
            (spread / profile.minimumTrajectorySpread).coerceIn(0.0, 1.0)
        return (0.50 + durationScore * 0.20 + displacementScore * 0.20 + spreadScore * 0.10)
            .coerceIn(0.0, 1.0)
    }

    private fun resetActiveLobe() {
        direction = 0
        lobeStartNs = 0L
        lobeDisplacement = 0.0
        lobePeakRate = 0.0
        lobeMainEnergy = 0.0
        lobeSecondaryEnergy = 0.0
    }

    private fun resetAll() {
        resetActiveLobe()
        pendingStartNs = 0L
        pendingTurnaroundNs = 0L
        pendingPeakRate = 0.0
        pendingDisplacement = 0.0
        pendingSpread = 0.0
        pendingDirection = 0
        lockedAxis = -1
        refractoryUntilNs = 0L
    }
}
