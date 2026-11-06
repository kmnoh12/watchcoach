package dev.kyungmin.kcoach.core

/** Heart-rate zones shared by the watch and phone. The bands are a placeholder until a max heart rate is known. */
object HeartZone {
    const val ASSUMED_MAX_HEART_RATE = 185

    /** Zone 1..5 colours as ARGB. */
    val COLORS = longArrayOf(0xFF7C8E9C, 0xFF4DA3FF, 0xFF4FD18B, 0xFFFFA033, 0xFFE5483B).map { it.toInt() }

    fun of(heartRate: Int): Int = when {
        heartRate <= 0 -> 0
        heartRate * 100 < ASSUMED_MAX_HEART_RATE * 60 -> 1
        heartRate * 100 < ASSUMED_MAX_HEART_RATE * 70 -> 2
        heartRate * 100 < ASSUMED_MAX_HEART_RATE * 80 -> 3
        heartRate * 100 < ASSUMED_MAX_HEART_RATE * 90 -> 4
        else -> 5
    }

    fun color(heartRate: Int): Int = COLORS[of(heartRate).coerceAtLeast(1) - 1]
}
