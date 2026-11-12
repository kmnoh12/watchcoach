package dev.kyungmin.kcoach.core

/** How hard each body part was worked recently, for the muscle map. */
object BodyLoad {
    /** About this many sets a week on one part counts as fully worked. */
    const val FULL_SETS = 12

    /** Sets per body part over the last [days] days ending at [today], from the logs of every exercise. */
    fun setsByPart(logs: List<ExerciseLog>, partOf: (String) -> String?, today: Long, days: Int = 7): Map<String, Int> =
        logs.filter { it.epochDay in (today - days + 1)..today }
            .mapNotNull { log -> partOf(log.exerciseId)?.let { part -> part to log.sets.count { it.completed && it.repsEntered } } }
            .groupBy({ it.first }, { it.second })
            .mapValues { (_, counts) -> counts.sum() }

    /** 0..1 per part, 1 meaning [FULL_SETS] or more. */
    fun intensity(sets: Map<String, Int>): Map<String, Double> =
        sets.mapValues { (_, count) -> (count.toDouble() / FULL_SETS).coerceIn(0.0, 1.0) }

    /** Days a part usually needs to recover after a hard session (rule-of-thumb gym convention, not a measured value). */
    val RECOVERY_DAYS = mapOf(
        "가슴" to 3.0, "등" to 3.0, "하체" to 3.5, "이두" to 2.0, "삼두" to 2.0,
        "전면어깨" to 2.0, "측면어깨" to 2.0, "후면어깨" to 2.0, "코어" to 2.0, "승모" to 2.0,
    )

    /**
     * The parts a set of this exercise tires, each with the share of the set it counts for. The shoulder is split into
     * front, side and rear: presses mainly hit the front and a fifth on the side, raises and rows their own head.
     * Chest presses add front-shoulder load too (0.5 a set, incline 0.8, decline 0.2). Shrugs load the trapezius.
     */
    fun partWeights(body: String, pattern: String, exerciseId: String = ""): Map<String, Double> = when {
        // Whole-body lifts and swings are spread over the big movers.
        body == "전신" -> if (pattern == "hinge") mapOf("하체" to 0.8, "등" to 0.5, "후면어깨" to 0.3, "코어" to 0.4)
            else mapOf("하체" to 0.8, "등" to 0.6, "전면어깨" to 0.5, "코어" to 0.4)
        // Movements listed under two body parts load both, whichever list they sit in.
        pattern == "pullover" -> mapOf("가슴" to 0.7, "등" to 0.5)
        pattern == "dip" -> mapOf("가슴" to 1.0, "삼두" to 0.8, "전면어깨" to 0.5)
        else -> partWeightsOf(body, pattern, exerciseId)
    }

    private fun partWeightsOf(body: String, pattern: String, exerciseId: String): Map<String, Double> = when (body) {
        "어깨" -> when (pattern) {
            "shoulder_press" -> mapOf("전면어깨" to 1.0, "측면어깨" to 0.2)
            "front_raise" -> mapOf("전면어깨" to 1.0)
            "lateral_raise" -> mapOf("측면어깨" to 1.0)
            "row" -> mapOf("측면어깨" to 1.0, "승모" to 0.5)
            "rear_delt", "rotation" -> if (exerciseId == "face_pull") mapOf("후면어깨" to 1.0, "승모" to 0.4) else mapOf("후면어깨" to 1.0)
            "shrug" -> mapOf("승모" to 1.0)
            else -> emptyMap()
        }
        // Chest presses also load the front shoulder, incline ones the most, decline ones the least.
        // Back work also pulls with the biceps, the rear shoulder and the trapezius (most in rows); hinges (deadlifts) also drive the legs.
        "등" -> when (pattern) {
            "hinge" -> mapOf("등" to 1.0, "하체" to 0.8, "승모" to 0.3)
            "row" -> mapOf("등" to 1.0, "이두" to 0.6, "후면어깨" to 0.4, "승모" to 0.5)
            else -> mapOf("등" to 1.0, "이두" to 0.6, "후면어깨" to 0.4, "승모" to 0.2)
        }
        "가슴" -> if (pattern == "push_up") mapOf("가슴" to 1.0, "삼두" to 0.5, "전면어깨" to 0.5)
        else if (pattern == "chest_press") mapOf("가슴" to 1.0, "전면어깨" to when { "incline" in exerciseId -> 0.8; "decline" in exerciseId -> 0.2; else -> 0.5 }) else mapOf("가슴" to 1.0)
        // Push-ups and close-grip presses work chest, triceps and front shoulder together, in a different mix.
        "삼두" -> when (pattern) {
            "chest_press" -> mapOf("삼두" to 1.0, "가슴" to 0.5, "전면어깨" to 0.3)
            "push_up" -> mapOf("삼두" to 1.0, "가슴" to 0.5, "전면어깨" to 0.5)
            else -> mapOf("삼두" to 1.0)
        }
        "코어" -> mapOf(body to 1.0)
        else -> if (body in RECOVERY_DAYS) mapOf(body to 1.0) else emptyMap()
    }

    /** This many un-recovered sets on one part paint it at full strength. */
    const val FULL_FATIGUE_SETS = 15

    /** Session time, with local noon for legacy records that only have a date. */
    fun startedAtMs(log: ExerciseLog, zone: java.time.ZoneId = java.time.ZoneId.systemDefault()): Long =
        log.startedAtMs.takeIf { it > 0 } ?: java.time.LocalDate.ofEpochDay(log.epochDay)
            .atTime(12, 0).atZone(zone).toInstant().toEpochMilli()

    /** Share of fatigue left after a fraction of the recovery time. */
    internal fun stillTired(x: Double): Double = 1.0 - (3 * x * x - 2 * x * x * x)

    /** Date-only callers keep their noon-to-noon interpretation. */
    fun fatigueByPart(logs: List<ExerciseLog>, weightsOf: (String) -> Map<String, Double>?, today: Long): Map<String, Double> =
        fatigueByPartAt(logs, weightsOf, java.time.LocalDate.ofEpochDay(today)
            .atTime(12, 0).atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli())

    /** Accumulated fatigue at an instant; future sessions contribute nothing. */
    fun fatigueByPartAt(
        logs: List<ExerciseLog>, weightsOf: (String) -> Map<String, Double>?, atMs: Long,
        zone: java.time.ZoneId = java.time.ZoneId.systemDefault(),
    ): Map<String, Double> {
        val units = HashMap<String, Double>()
        for (log in logs) {
            val start = startedAtMs(log, zone)
            if (start > atMs) continue
            val sets = log.sets.count { it.completed && it.repsEntered }
            if (sets == 0) continue
            val ageDays = (atMs - start) / 86_400_000.0
            for ((part, weight) in weightsOf(log.exerciseId).orEmpty()) {
                val recovery = RECOVERY_DAYS[part] ?: continue
                val x = ageDays / recovery
                if (x < 1 && weight > 0) units.merge(part, sets * weight * stillTired(x), Double::plus)
            }
        }
        return units.mapValues { (it.value / FULL_FATIGUE_SETS).coerceIn(0.0, 1.0) }
    }
}
