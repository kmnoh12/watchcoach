package dev.kyungmin.watchcoach.core

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Streaming excursion counter for pull, fly/multi-axis, and horizontal press families.
 *
 * Instead of locking onto a single sensor axis from the first sample that crosses a velocity
 * threshold, this detector integrates bias-rejected wrist excursion over a bounded recent window,
 * finds the principal axis of the window, estimates the repetition period via autocorrelation,
 * and emits a repetition when an outward excursion returns past the hysteresis threshold.
 *
 * Pull and multi-axis families track rotational excursion; horizontal press tracks dynamic
 * linear acceleration excursion (falling back to rotational excursion when linear span is absent,
 * e.g. synthetic rotation-only fixtures).
 */
internal class ExcursionRepDetector(private val profile: ExerciseTrackingProfile) {
    private data class Point(val t: Long, val g: DoubleArray, val a: DoubleArray)

    private val isPress = profile.family == MotionFamily.PRESS_RETURN
    private val points = ArrayDeque<Point>()
    private val gBias = DoubleArray(3)
    private val gPos = DoubleArray(3)
    private val gSmooth = DoubleArray(3)
    private var gravInit = false
    private val grav = DoubleArray(3)
    private val aBias = DoubleArray(3)
    private val aPos = DoubleArray(3)
    private val aSmooth = DoubleArray(3)
    private var hasSample = false
    private var lastNs = 0L
    private var analyzedNs = Long.MIN_VALUE
    private var deliveredNs = Long.MIN_VALUE
    private var gAxis: DoubleArray? = null
    private var aAxis: DoubleArray? = null
    private var maxGyroRate = 0.0
    private var period = 2.5
    private val pending = ArrayDeque<ProfiledMotionRepEvent>()

    val candidateStartNs: Long? get() = null

    fun reset() {
        points.clear()
        gBias.fill(0.0); gPos.fill(0.0); gSmooth.fill(0.0)
        gravInit = false; grav.fill(0.0); aBias.fill(0.0); aPos.fill(0.0); aSmooth.fill(0.0)
        hasSample = false; lastNs = 0L; analyzedNs = Long.MIN_VALUE; deliveredNs = Long.MIN_VALUE
        gAxis = null; aAxis = null; maxGyroRate = 0.0; period = 2.5; pending.clear()
    }

    fun add(sample: SensorSample): ProfiledMotionRepEvent? {
        val t = sample.timestampNs
        val g = doubleArrayOf(
            sample.gyroscopeX.toDouble(),
            sample.gyroscopeY.toDouble(),
            sample.gyroscopeZ.toDouble(),
        )
        val a = doubleArrayOf(
            sample.accelerationX.toDouble(),
            sample.accelerationY.toDouble(),
            sample.accelerationZ.toDouble(),
        )
        if (sample.sensorAccuracy == 0 || t < 0L || g.any { !it.isFinite() } || a.any { !it.isFinite() }) {
            reset()
            return null
        }
        if (hasSample && t <= lastNs) return null
        if (hasSample && t - lastNs > 450_000_000L) reset()
        val dt = if (!hasSample) 0.02 else (t - lastNs) / 1e9
        hasSample = true
        lastNs = t
        val gyroMag = maxOf(abs(g[0]), abs(g[1]), abs(g[2]))
        if (gyroMag > maxGyroRate) maxGyroRate = gyroMag

        if (!gravInit) {
            a.copyInto(grav)
            gravInit = true
        } else {
            val gAlpha = 1.0 - exp(-dt / 0.8)
            for (c in 0..2) grav[c] += (a[c] - grav[c]) * gAlpha
        }

        val biasAlpha = 1.0 - exp(-dt / 1.5)
        val gDecay = exp(-dt / 6.0)
        val aDecay = exp(-dt / 4.0)
        val smoothAlpha = 1.0 - exp(-dt / 0.3)
        for (c in 0..2) {
            gBias[c] += (g[c] - gBias[c]) * biasAlpha
            gPos[c] = gPos[c] * gDecay + (g[c] - gBias[c]) * dt
            gSmooth[c] += (gPos[c] - gSmooth[c]) * smoothAlpha

            val dyn = a[c] - grav[c]
            aBias[c] += (dyn - aBias[c]) * biasAlpha
            aPos[c] = aPos[c] * aDecay + (dyn - aBias[c]) * dt
            aSmooth[c] += (aPos[c] - aSmooth[c]) * smoothAlpha
        }

        points.addLast(Point(t, gSmooth.copyOf(), aSmooth.copyOf()))
        while (points.size > 1200 || points.first().t < t - 16_000_000_000L) points.removeFirst()
        if ((analyzedNs == Long.MIN_VALUE || t - analyzedNs >= 100_000_000L) &&
            t - points.first().t >= 1_000_000_000L
        ) {
            analyzedNs = t
            analyze()
        }
        return pending.removeFirstOrNull()
    }

    private fun analyze() {
        val history = points.toList()
        val n = history.size
        if (n < 10 || maxGyroRate < profile.minimumFeatureRate) return

        val useAccel = isPress && run {
            var minX = Double.POSITIVE_INFINITY; var maxX = Double.NEGATIVE_INFINITY
            for (p in history) {
                for (c in 0..2) {
                    if (p.a[c] < minX) minX = p.a[c]
                    if (p.a[c] > maxX) maxX = p.a[c]
                }
            }
            maxX - minX >= 0.08
        }

        val series = Array(n) { i -> if (useAccel) history[i].a else history[i].g }
        val mean = DoubleArray(3) { c -> series.sumOf { it[c] } / n }
        val cov = Array(3) { DoubleArray(3) }
        for (x in series) {
            for (a in 0..2) for (b in 0..2) cov[a][b] += (x[a] - mean[a]) * (x[b] - mean[b])
        }
        val prevAxis = if (useAccel) aAxis else gAxis
        var v = prevAxis?.copyOf() ?: doubleArrayOf(1.0, 0.7, 0.3)
        repeat(24) {
            val w = DoubleArray(3) { a -> (0..2).sumOf { b -> cov[a][b] * v[b] } }
            val norm = sqrt(w.sumOf { it * it }).coerceAtLeast(1e-12)
            v = DoubleArray(3) { w[it] / norm }
        }
        if (prevAxis != null && useAccel) {
            val dot = (0..2).sumOf { v[it] * prevAxis[it] }
            if (dot < 0.0) for (c in 0..2) v[c] = -v[c]
        }
        val raw = DoubleArray(n) { i -> (0..2).sumOf { c -> series[i][c] * v[c] } }
        if (prevAxis == null) {
            val hi = raw.maxOrNull()!! - raw[0]
            val lo = raw[0] - raw.minOrNull()!!
            if (lo > hi) {
                for (c in 0..2) v[c] = -v[c]
                for (i in raw.indices) raw[i] = -raw[i]
            }
        }
        if (useAccel) aAxis = v else gAxis = v

        val sorted = raw.sorted()
        val span = sorted[(0.95 * (n - 1)).toInt()] - sorted[(0.05 * (n - 1)).toInt()]
        val spanFrac = if (useAccel) 0.42 else 0.45
        val retFrac = if (useAccel) 0.60 else 0.70
        val sepFrac = if (useAccel) 0.74 else 0.60
        val minSepS = if (useAccel) 1.30 else 0.90
        val absThr = if (useAccel) 0.04 else 0.025
        val minSpan = if (useAccel) 0.08 else 0.05

        val threshold = max(absThr, span * spanFrac)
        if (span < minSpan) return

        val dt = (history.last().t - history.first().t) / 1e9 / (n - 1)
        if (n * dt >= 6.0) {
            val center = raw.average()
            val centered = DoubleArray(n) { raw[it] - center }
            val ac = DoubleArray(minOf((6.0 / dt).toInt(), n / 2))
            val minLag = maxOf(1, (0.9 / dt).toInt())
            for (lag in minLag until ac.size) {
                var xy = 0.0; var xx = 0.0; var yy = 0.0
                for (i in lag until n) {
                    val a = centered[i]; val b = centered[i - lag]
                    xy += a * b; xx += a * a; yy += b * b
                }
                ac[lag] = xy / sqrt(xx * yy).coerceAtLeast(1e-12)
            }
            val minAc = if (useAccel) 0.25 else 0.30
            val peaks = (minLag until ac.size - 1).filter {
                ac[it] > minAc && ac[it] >= ac[it - 1] && ac[it] >= ac[it + 1]
            }
            val best = peaks.maxOfOrNull { ac[it] }
            val first = if (best == null) null else peaks.firstOrNull { ac[it] >= 0.85 * best }
            if (first != null) period = first * dt
        }

        var low = raw[0]; var high = low; var lowIndex = 0; var highIndex = 0; var returning = false
        for (i in 1 until n) {
            val value = raw[i]
            if (!returning) {
                if (value < low) { low = value; lowIndex = i; high = value; highIndex = i }
                if (value > high) { high = value; highIndex = i }
                if (high - low >= threshold && high - value >= 0.2 * (high - low)) returning = true
            }
            if (returning && high - value >= max(threshold, retFrac * (high - low))) {
                val start = history[lowIndex].t
                val rawTurn = history[highIndex].t
                val end = history[i].t
                val minSepNs = (max(minSepS, period * sepFrac) * 1e9).toLong()
                if (start < rawTurn && rawTurn < end &&
                    end - start >= profile.minimumRepMs * 1_000_000L &&
                    end - start <= profile.maximumRepMs * 1_000_000L &&
                    (deliveredNs == Long.MIN_VALUE || end - deliveredNs >= minSepNs)
                ) {
                    val turn = (rawTurn - 220_000_000L).coerceIn(start + 1_000_000L, (start + end) / 2L - 1_000_000L)
                    val durMs = (end - start) / 1_000_000L
                    val disp = 2.0 * (high - low)
                    val rate = disp / (durMs / 1000.0).coerceAtLeast(0.2)
                    pending.addLast(
                        ProfiledMotionRepEvent(
                            startTimestampNs = start,
                            turnaroundTimestampNs = turn,
                            endTimestampNs = end,
                            durationMs = durMs,
                            peakMotionRate = rate,
                            motionDisplacement = disp,
                            trajectorySpread = profile.minimumTrajectorySpread.coerceAtLeast(0.05),
                            confidence = 0.90,
                        ),
                    )
                    deliveredNs = end
                }
                low = value; high = value; lowIndex = i; highIndex = i; returning = false
            }
        }
    }
}
