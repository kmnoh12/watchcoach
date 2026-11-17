package dev.kyungmin.watchcoach.core

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

    /**
     * Days until a part is fully recovered after a hard session, i.e. where its [recoveryLeft] curve reaches zero
     * (rule-of-thumb gym convention, not a measured value).
     */
    val RECOVERY_DAYS = mapOf(
        "가슴" to 4.0, "등" to 4.0, "하체" to 5.0, "이두" to 3.0, "삼두" to 3.0,
        "전면어깨" to 3.0, "측면어깨" to 3.0, "후면어깨" to 3.0, "코어" to 3.0, "승모" to 3.0,
    )

    /**
     * How much of a session's fatigue is left, by hours since it started: it stays at full strength for the first day
     * (soreness builds up to about a day later), then eases off slowly and drops faster towards the end. The points are
     * for a session that fills the colour (about [FULL_FATIGUE_SETS] sets); a smaller session is the same shape, lighter.
     */
    private val CURVE_BIG = RecoveryCurve(doubleArrayOf(0.0, 24.0, 48.0, 72.0, 96.0), doubleArrayOf(1.0, 1.0, 0.8, 0.5, 0.0))
    private val CURVE_LEGS = RecoveryCurve(doubleArrayOf(0.0, 24.0, 48.0, 72.0, 96.0, 120.0), doubleArrayOf(1.0, 1.0, 0.9, 0.6, 0.3, 0.0))
    private val CURVE_SMALL = RecoveryCurve(doubleArrayOf(0.0, 24.0, 48.0, 72.0), doubleArrayOf(1.0, 1.0, 0.55, 0.0))

    /** Share of fatigue left on [part] [ageHours] after a session (1 at the start, 0 once recovered). */
    fun recoveryLeft(part: String, ageHours: Double): Double = when (part) {
        "가슴", "등" -> CURVE_BIG
        "하체" -> CURVE_LEGS
        else -> CURVE_SMALL
    }.at(ageHours)

    /** Smooth, monotone curve through the given points (Fritsch-Carlson), 1 before the first and 0 after the last. */
    private class RecoveryCurve(private val x: DoubleArray, private val y: DoubleArray) {
        private val m: DoubleArray = slopes()

        private fun slopes(): DoubleArray {
            val n = x.size
            val h = DoubleArray(n - 1) { x[it + 1] - x[it] }
            val d = DoubleArray(n - 1) { (y[it + 1] - y[it]) / h[it] }
            val s = DoubleArray(n)
            for (i in 1 until n - 1) {
                s[i] = if (d[i - 1] * d[i] <= 0.0) 0.0 else {
                    val w1 = 2 * h[i] + h[i - 1]; val w2 = h[i] + 2 * h[i - 1]
                    (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
                }
            }
            s[0] = edge(h[0], h[1], d[0], d[1])
            s[n - 1] = edge(h[n - 2], h[n - 3], d[n - 2], d[n - 3])
            return s
        }

        private fun edge(h0: Double, h1: Double, d0: Double, d1: Double): Double {
            val v = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
            return when {
                v * d0 <= 0.0 -> 0.0
                d0 * d1 <= 0.0 && kotlin.math.abs(v) > 3 * kotlin.math.abs(d0) -> 3 * d0
                else -> v
            }
        }

        fun at(t: Double): Double {
            if (t <= x.first()) return y.first()
            if (t >= x.last()) return y.last()
            var i = 0
            while (t >= x[i + 1]) i++
            val h = x[i + 1] - x[i]
            val s = (t - x[i]) / h
            val s2 = s * s; val s3 = s2 * s
            val v = (2 * s3 - 3 * s2 + 1) * y[i] + (s3 - 2 * s2 + s) * h * m[i] +
                (-2 * s3 + 3 * s2) * y[i + 1] + (s3 - s2) * h * m[i + 1]
            return v.coerceIn(0.0, 1.0)
        }
    }

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
            val ageHours = (atMs - start) / 3_600_000.0
            for ((part, weight) in weightsOf(log.exerciseId).orEmpty()) {
                if (part !in RECOVERY_DAYS) continue
                val left = recoveryLeft(part, ageHours)
                if (left > 0.0 && weight > 0) units.merge(part, sets * weight * left, Double::plus)
            }
        }
        return units.mapValues { (it.value / FULL_FATIGUE_SETS).coerceIn(0.0, 1.0) }
    }
}
