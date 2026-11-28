package dev.kyungmin.watchcoach.core

import kotlin.math.*

/** Learns one unsigned line of travel from recent acceleration excursions. No fixed device or world axis. */
internal class AdaptivePressDetector(
    private val bench: Boolean,
    private val transitionBlend: Double = 0.0,
    private val recoverRapid: Boolean = true,
    private val helper: Boolean = false,
) {
    companion object {
        const val ID = "adaptive-press-return-v1"
        private const val BASE_TAU = 0.52
        private const val DECAY_TAU = 0.70
        private const val CENTER_TAU = 0.65
        private const val SMOOTHING_TAU = 0.12
        private const val CROSSING = 0.036
        private const val STOP = 0.016
        private const val INITIAL_BALANCE = 0.18
        private const val RELATIVE_LOBE = 0.16
        private const val MAX_FIRST_LOBE_LAG_NS = 1_500_000_000L
    }

    private val quick = if (helper || !recoverRapid) null else AdaptivePressDetector(
        bench = bench,
        transitionBlend = 5.0,
        recoverRapid = false,
        helper = true,
    )
    private var latestQuick: ProfiledMotionRepEvent? = null
    private var latestReported: Long = -1L
    private var latestNormalExtent = 0.0
    private val quickVelocity = DoubleArray(3)
    private var readyAt = -1L
    private var highRatio = 0.0
    private val base = DoubleArray(3)
    private val fast = DoubleArray(3)
    private val vel = DoubleArray(3)
    private val mean = DoubleArray(3)
    private val filter = DoubleArray(3)
    private var peakOn = false
    private var firstImpact = -1L
    private var doubleContact = false
    private var shockNs = -1L
    private var quietSince = -1L
    private var typicalJerk = 1.0
    private var repCount = 0
    private val coherent = DoubleArray(3)
    private val smooth = DoubleArray(3)
    private val cov = DoubleArray(9)
    private val axis = DoubleArray(3)
    private var tLast = -1L
    var lastMotionNs = 0L; private set
    var rackSettled = false; private set
    private var lastRep = -1L
    private var typical = 0.0
    private data class Lobe(val sign: Int, val start: Long, val end: Long, val area: Double, val peak: Double)
    private var first: Lobe? = null
    private var sign = 0
    private var start = 0L
    private var area = 0.0
    private var peak = 0.0
    private var direction = 0
    private var burst = -1L
    private var pulseEnd = -1L
    private var recoilBlocked = false
    private val rackAxis = DoubleArray(3)
    private data class Stroke(val dt: Double, val a: Double)
    private val stroke = ArrayList<Stroke>()
    private var pulseTail = -1L

    // Capture the entire post-lockout stroke, bridging the quiet instant between push and braking.
    // Zero endpoint velocity removes constant gravity and bias. Signed net travel distinguishes a descent from an upstroke.
    private fun watchPlacement(t: Long, dt: Double, a: DoubleArray, moving: Boolean) {
        if (!bench || lastRep < 0L) return
        if (moving) {
            if (burst < 0 && t - max(lastRep, lastMotionNs) >= 180_000_000L) {
                burst = t
                stroke.clear()
                axis.copyInto(rackAxis)
            }
            pulseEnd = -1
            recoilBlocked = false
            rackSettled = false
        }
        if (burst >= 0) {
            if (t - burst > 1_650_000_000L) {
                burst = -1
                stroke.clear()
                return
            }
            stroke.add(Stroke(dt, (0..2).sumOf { rackAxis[it] * a[it] }))
            if (moving) pulseTail = t
            if (!moving && t - pulseTail >= 150_000_000L) {
                val total = stroke.sumOf { it.dt }
                val bias = stroke.sumOf { it.dt * it.a } / total
                var v = 0.0
                var net = 0.0
                var path = 0.0
                for (s in stroke) {
                    val next = v + s.dt * (s.a - bias)
                    val dx = 0.5 * (next + v) * s.dt
                    net += dx
                    path += abs(dx)
                    v = next
                }
                val outgoing = net * direction
                if (outgoing > 0.006 && outgoing > 0.72 * path) {
                    recoilBlocked = true
                    if (pulseTail - burst in 60_000_000L..590_000_000L && outgoing < min(0.075, typical * 0.32)) {
                        // This was a short one-way approach, not a complete return. At its
                        // stationary endpoint forget the integrator tail, not the exercise cadence.
                        pulseEnd = pulseTail
                        first = null
                        sign = 0
                        area = 0.0
                        peak = 0.0
                        a.copyInto(base)
                        a.copyInto(fast)
                        for (field in listOf(vel, mean, filter, smooth, quickVelocity)) field.fill(0.0)
                        history.clear()
                    }
                }
                burst = -1
                stroke.clear()
            }
        }
    }

    // The two halves of a completed candidate are compared at the same phase, not the same tempo.
    // Per-channel normalization removes intensity; vectors stay in 3D so a global rotation cancels in the dot product.
    private data class Frame(val t: Long, val v: DoubleArray, val gyro: DoubleArray, val acc: DoubleArray)
    private val history = ArrayDeque<Frame>()
    private var template: DoubleArray? = null
    private val intervals = ArrayDeque<Long>()
    private var locked = false
    private val poses = ArrayDeque<DoubleArray>()
    private val energy = ArrayDeque<Double>()
    private val scatter = ArrayDeque<Double>()

    private fun consistent(out: Lobe, back: Lobe): Boolean {
        val bins = 8
        val shape = DoubleArray(bins * 6)
        val frames = history.toList()
        if (frames.isEmpty()) return false
        val arc = frames.filter { it.t >= out.start }
        if (arc.isEmpty()) return false
        // A filter can oscillate after the hand is already still. Require independent raw
        // acceleration change in the return half; do not count a predicted reversal.
        val tail = arc.filter { it.t >= back.start }
        if (tail.size < 2) return false
        val avg = DoubleArray(3) { c -> tail.sumOf { it.acc[c] } / tail.size }

        val pose = DoubleArray(3) { c -> arc.sumOf { it.acc[c] } / arc.size }
        val rms = sqrt(arc.sumOf { f -> (0..2).sumOf { (f.acc[it] - pose[it]).pow(2) } } / arc.size)
        if (tail.sumOf { f -> (0..2).sumOf { (f.acc[it] - avg[it]).pow(2) } } / tail.size < min(0.10, 0.25 * rms).pow(2)) return false
        fun median(xs: Collection<Double>) = xs.sorted()[xs.size / 2]
        val dist = if (poses.isEmpty()) 0.0 else sqrt((0..2).sumOf { c -> (pose[c] - poses.map { it[c] }.average()).pow(2) })
        val localDist = poses.lastOrNull()?.let { prev -> sqrt((0..2).sumOf { (pose[it] - prev[it]).pow(2) }) } ?: dist
        val unusual = localDist > max(1.8, 2.5 * median(scatter.ifEmpty { listOf(0.0) })) && poses.size >= 3 && dist > max(1.8, 3.5 * median(scatter))
        if (unusual && (rms > 1.25 * median(energy) || back.end - out.start > 1.45 * (intervals.sorted().getOrNull(intervals.size / 2) ?: Long.MAX_VALUE))) return false
        fun remember() {
            poses.addLast(pose)
            energy.addLast(rms)
            scatter.addLast(dist)
            if (poses.size > 4) {
                poses.removeFirst()
                energy.removeFirst()
                scatter.removeFirst()
            }
        }
        var i = 0
        for (b in 0 until bins) {
            val h = if (b < 4) out else back
            val at = h.start + (h.end - h.start) * (2 * (b % 4) + 1) / 8
            while (i + 1 < frames.size && frames[i].t < at) i++
            for (c in 0..2) {
                shape[3 * b + c] = frames[i].v[c]
                shape[3 * b + c + 24] = frames[i].gyro[c]
            }
        }
        for (offset in listOf(0, 24)) {
            for (c in 0..2) {
                val m = (0 until bins).sumOf { shape[offset + 3 * it + c] } / bins
                for (b in 0 until bins) shape[offset + 3 * b + c] -= m
            }
            val norm = sqrt((offset until offset + 24).sumOf { shape[it] * shape[it] })
            for (k in offset until offset + 24) shape[k] = if (norm > 1e-6) shape[k] / norm else 0.0
        }
        val ref = template
        if (ref == null) {
            template = shape
            remember()
            return true
        }
        fun cosine(a: Int): Double {
            val norm = sqrt((a until a + 24).sumOf { ref[it] * ref[it] })
            return if (norm > 1e-6) (a until a + 24).sumOf { ref[it] * shape[it] } / norm else 0.0
        }
        // Translation dominates; the gyro is independent evidence only when both sets have wrist rotation.
        val sim = if ((24..47).sumOf { ref[it] * ref[it] } > 0.01 && (24..47).sumOf { shape[it] * shape[it] } > 0.01) {
            0.72 * cosine(0) + 0.28 * cosine(24)
        } else {
            cosine(0)
        }

        if (!locked && sim < 0.0 && dist > max(3.0, median(energy))) return false
        if (!locked) {
            if (sim < 0.55) {
                template = shape
                remember()
                return true
            }
            locked = true
        }
        val interval = back.end - lastRep
        val usual = if (intervals.size >= 2) intervals.sorted()[intervals.size / 2].toDouble() else 0.0
        // A tired but on-cadence rep may differ in shape. Cadence alone never creates an event.
        // On an atypical return, elapsed time alone cannot vindicate a ringing filter after a stop.
        fun stillAtReturn(): Boolean {
            val end = tail.filter { back.end - it.t <= 450_000_000L }
            if (end.size < 2) return false
            val center = DoubleArray(3) { c -> end.sumOf { it.acc[c] } / end.size }
            val lin = end.sumOf { f -> (0..2).sumOf { (f.acc[it] - center[it]).pow(2) } } / end.size
            val twist = end.sumOf { f -> f.gyro.sumOf { it * it } } / end.size
            return lin < (0.22 * median(energy)).pow(2) && twist < 0.22 * 0.22
        }
        if (sim < 0.52 && !((!unusual || !stillAtReturn()) && usual > 0 && interval / usual in 0.65..1.5 && sim >= 0.28)) return false
        remember()
        for (k in shape.indices) ref[k] += 0.22 * (shape[k] - ref[k])
        return true
    }

    // Only learn from an already accepted compressed return. A following normal rep must
    // independently arm this lookup; a clock, a target count or a repeating template alone cannot arm it.
    private data class RapidShape(val ga: DoubleArray, val gg: DoubleArray, val ampA: Double, val ampG: Double)
    private var learn: ProfiledMotionRepEvent? = null
    private var learned: Pair<ProfiledMotionRepEvent, RapidShape>? = null
    private var armed = false
    private var peakMatch = 0.0
    private var matched: ProfiledMotionRepEvent? = null
    private val filteredA = DoubleArray(3)
    private val filteredG = DoubleArray(3)
    private data class ShapeSample(val at: Long, val a: DoubleArray, val g: DoubleArray)
    private val shapeBuffer = ArrayDeque<ShapeSample>()

    private fun resetShapes() {
        learn = null
        learned = null
        armed = false
        peakMatch = 0.0
        matched = null
        shapeBuffer.clear()
    }

    private fun shape(start: Long, end: Long): RapidShape? {
        val n = 14
        if (shapeBuffer.isEmpty() || start < shapeBuffer.first().at || end > shapeBuffer.last().at) return null
        val a = DoubleArray(3 * n)
        val g = DoubleArray(3 * n)
        var i = 0
        for (b in 0 until n) {
            val at = start + (end - start) * b / (n - 1)
            while (i + 1 < shapeBuffer.size && shapeBuffer[i + 1].at <= at) i++
            val cur = shapeBuffer[i]
            val after = shapeBuffer.getOrNull(i + 1) ?: cur
            val u = (at - cur.at).toDouble() / max(1L, after.at - cur.at)
            for (k in 0..2) {
                a[3 * b + k] = cur.a[k] + u * (after.a[k] - cur.a[k])
                g[3 * b + k] = cur.g[k] + u * (after.g[k] - cur.g[k])
            }
        }
        fun center(x: DoubleArray): Double {
            for (k in 0..2) {
                val m = (0 until n).sumOf { x[3 * it + k] } / n
                for (b in 0 until n) x[3 * b + k] -= m
            }
            return sqrt(x.sumOf { it * it })
        }
        val aa = center(a)
        val ag = center(g)
        if (aa < 0.01 || ag < 0.01) return null
        fun gram(x: DoubleArray, y: DoubleArray): DoubleArray {
            val v = DoubleArray(n * n) { j -> (0..2).sumOf { x[3 * (j / n) + it] * y[3 * (j % n) + it] } }
            val scale = max(1e-9, sqrt(v.sumOf { it * it }))
            for (j in v.indices) v[j] /= scale
            return v
        }
        return RapidShape(gram(a, a), gram(g, g), aa, ag)
    }

    private fun observeShapeFrame(s: SensorSample, t: Long) {
        if (quick == null) return
        val dt = shapeBuffer.lastOrNull()?.let { (t - it.at) / 1e9 } ?: 1.0
        val blend = 1 - exp(-dt / 0.055)
        val a = doubleArrayOf(s.accelerationX.toDouble(), s.accelerationY.toDouble(), s.accelerationZ.toDouble())
        val g = doubleArrayOf(s.gyroscopeX.toDouble(), s.gyroscopeY.toDouble(), s.gyroscopeZ.toDouble())
        for (j in 0..2) {
            filteredA[j] += blend * (a[j] - filteredA[j])
            filteredG[j] += blend * (g[j] - filteredG[j])
        }
        shapeBuffer.addLast(ShapeSample(t, filteredA.copyOf(), filteredG.copyOf()))
        while (t - shapeBuffer.first().at > 3_000_000_000L) shapeBuffer.removeFirst()
        learn?.let { e ->
            val tail = (e.endTimestampNs - e.startTimestampNs) / 4
            if (t >= e.endTimestampNs + tail) {
                learned = shape(e.startTimestampNs, e.endTimestampNs + tail)?.let { e to it }
                learn = null
            }
        }
    }

    private fun recurring(t: Long): ProfiledMotionRepEvent? {
        val (ref, r) = learned ?: return null
        if (!armed || rackSettled) return null
        val span = ref.endTimestampNs - ref.startTimestampNs
        val since = t - latestReported
        if (since !in (span * 2 / 3)..(span * 2)) {
            if (since > span * 2) armed = false
            return null
        }
        fun dot(a: DoubleArray, b: DoubleArray) = a.indices.sumOf { a[it] * b[it] }
        for (scale in listOf(0.80, 0.90, 1.0, 1.10, 1.20, 1.30)) {
            val d = (span * scale).toLong()
            val run = t - d / 4
            val start = run - d
            if (start < latestReported - span / 2 || run - latestReported < 650_000_000L) continue
            val p = shape(start, t) ?: continue
            if (p.ampA / r.ampA !in 0.55..1.85 || p.ampG / r.ampG !in 0.55..1.85) continue
            val accel = dot(r.ga, p.ga)
            val gyro = dot(r.gg, p.gg)
            val score = min(accel, gyro)
            if (score > max(0.88, peakMatch)) {
                peakMatch = score
                val turn = start + ((ref.turnaroundTimestampNs - ref.startTimestampNs) * scale).toLong()
                matched = ref.copy(
                    startTimestampNs = start,
                    turnaroundTimestampNs = turn,
                    endTimestampNs = run,
                    durationMs = d / 1_000_000,
                    confidence = score,
                )
            }
        }
        val candidate = matched ?: return null
        if (t - candidate.endTimestampNs < span * 3 / 8) return null
        // Timestamp the confirmation, not an extrapolated template endpoint. Report measured
        // motion for this window rather than recycling the earlier rep's amplitude.
        val frames = history.filter { it.t in candidate.startTimestampNs..t }
        if (frames.size < 3) return null
        var area = 0.0
        var speed = 0.0
        for (i in 1 until frames.size) {
            val dt = (frames[i].t - frames[i - 1].t) / 1e9
            val v = sqrt(frames[i].v.sumOf { it * it })
            area += dt * v
            speed = max(speed, v)
        }
        armed = false
        matched = null
        peakMatch = 0.0
        latestReported = t
        return candidate.copy(
            endTimestampNs = t,
            durationMs = (t - candidate.startTimestampNs) / 1_000_000L,
            peakMotionRate = speed,
            motionDisplacement = area,
        )
    }

    fun reset() {
        resetShapes()
        latestQuick = null
        latestReported = -1L
        latestNormalExtent = 0.0
        quick?.reset()
        peakOn = false
        firstImpact = -1
        doubleContact = false
        shockNs = -1
        quietSince = -1
        typicalJerk = 1.0
        repCount = 0
        poses.clear()
        scatter.clear()
        energy.clear()
        coherent.fill(0.0)
        filter.fill(0.0)
        history.clear()
        intervals.clear()
        template = null
        locked = false
        listOf(base, fast, vel, mean, smooth, cov, axis).forEach { it.fill(0.0) }
        quickVelocity.fill(0.0)
        readyAt = -1
        highRatio = 0.0
        tLast = -1
        lastMotionNs = 0
        lastRep = -1
        typical = 0.0
        first = null
        sign = 0
        direction = 0
        recoilBlocked = false
        stroke.clear()
        burst = -1
        pulseTail = -1
        pulseEnd = -1
        rackSettled = false
    }

    fun prime(samples: Iterable<SensorSample>) {
        quick?.prime(samples)
        val s = samples.lastOrNull() ?: return
        seed(s)
    }

    private fun seed(s: SensorSample) {
        base[0] = s.accelerationX.toDouble()
        base[1] = s.accelerationY.toDouble()
        base[2] = s.accelerationZ.toDouble()
        base.copyInto(fast)
        tLast = s.timestampNs
        readyAt = tLast
    }

    fun add(s: SensorSample): ProfiledMotionRepEvent? {
        val previousQuick = latestQuick
        val rapid = quick?.add(s)
        if (rapid != null) latestQuick = rapid
        val normal = observe(s)
        if (normal != null) {
            if (latestReported >= 0 && normal.startTimestampNs < latestReported &&
                normal.endTimestampNs - latestReported < 650_000_000L
            ) return null
            latestReported = normal.endTimestampNs
            armed = learned != null
            matched = null
            peakMatch = 0.0
            latestNormalExtent = normal.motionDisplacement
            return normal
        }
        recurring(s.timestampNs)?.let { return it }
        if (rapid == null || previousQuick == null || latestReported < 0 || rackSettled) return null
        val sincePrevious = rapid.endTimestampNs - previousQuick.endTimestampNs
        // Recover a compressed cycle only if the fast filter agrees on the previous
        // rep, then independently closes a separate shorter out-and-back stroke.
        if (abs(latestReported - previousQuick.endTimestampNs) > 350_000_000L ||
            sincePrevious !in 720_000_000L..1_180_000_000L ||
            rapid.startTimestampNs < previousQuick.endTimestampNs ||
            rapid.endTimestampNs - latestReported < 650_000_000L ||
            rapid.motionDisplacement < 0.30 * latestNormalExtent
        ) return null
        latestReported = rapid.endTimestampNs
        armed = false
        learn = rapid
        matched = null
        peakMatch = 0.0
        return rapid
    }

    private fun observe(s: SensorSample): ProfiledMotionRepEvent? {
        val t = s.timestampNs
        val a = doubleArrayOf(s.accelerationX.toDouble(), s.accelerationY.toDouble(), s.accelerationZ.toDouble())
        val g = sqrt(
            s.gyroscopeX.toDouble() * s.gyroscopeX +
                s.gyroscopeY.toDouble() * s.gyroscopeY +
                s.gyroscopeZ.toDouble() * s.gyroscopeZ,
        )
        if (t < 0 || !g.isFinite() || s.sensorAccuracy == 0 || a.any { !it.isFinite() }) {
            reset()
            return null
        }
        if (t <= tLast) return null
        if (tLast < 0 || t - tLast > 450_000_000L) {
            reset()
            seed(s)
            return null
        }
        val dt = (t - tLast) / 1e9
        tLast = t
        fun alpha(tau: Double) = 1 - exp(-dt / tau)
        var hi2 = 0.0
        val b = alpha(BASE_TAU)
        val f = alpha(0.13)
        val decay = exp(-dt / DECAY_TAU)
        val m = alpha(CENTER_TAU)
        val lp = alpha(SMOOTHING_TAU)
        for (i in 0..2) {
            val hi = a[i] - fast[i]
            hi2 += hi * hi
            fast[i] += f * hi
            base[i] += b * (a[i] - base[i])
            vel[i] = decay * vel[i] + (a[i] - base[i]) * dt
            mean[i] += m * (vel[i] - mean[i])
            filter[i] += lp * (vel[i] - mean[i] - filter[i])
            smooth[i] += lp * (filter[i] - smooth[i])
            quickVelocity[i] += alpha(0.055) * (vel[i] - mean[i] - quickVelocity[i])
        }
        observeShapeFrame(s, t)
        history.addLast(
            Frame(
                t,
                smooth.copyOf(),
                doubleArrayOf(s.gyroscopeX.toDouble(), s.gyroscopeY.toDouble(), s.gyroscopeZ.toDouble()),
                a,
            ),
        )
        while (history.size > 1000 || t - history.first().t > 8_100_000_000L) history.removeFirst()
        val strength = sqrt(smooth.sumOf { it * it })
        val mem = alpha(2.5)
        val weight = mem / max(0.22, strength).pow(2)
        for (i in 0..2) for (j in 0..2) cov[i * 3 + j] = cov[i * 3 + j] * (1 - mem) + smooth[i] * smooth[j] * weight
        if (axis.all { it == 0.0 } && strength > 0.035) smooth.copyInto(axis)
        val w = DoubleArray(3) { i -> (0..2).sumOf { j -> cov[i * 3 + j] * axis[j] } }
        val wn = sqrt(w.sumOf { it * it })
        if (wn > 1e-12) for (i in 0..2) axis[i] = w[i] / wn
        val normalVelocity = (0..2).sumOf { smooth[it] * axis[it] }
        val rapidVelocity = (0..2).sumOf { quickVelocity[it] * axis[it] }
        val residualVelocity = abs(rapidVelocity - normalVelocity)
        val ratio = residualVelocity / max(0.10, abs(rapidVelocity) + abs(normalVelocity))
        highRatio += alpha(0.18) * (ratio - highRatio)
        val v = normalVelocity + transitionBlend * (highRatio - 0.16).coerceIn(0.0, 0.5) * (rapidVelocity - normalVelocity)
        val residual = sqrt(hi2)
        val moving = residual > 0.32 || g > 0.24
        // A weight contacting a stop produces a brief large residual. Isolated spikes, pauses,
        // and motion at the bottom cannot end a set on their own.
        if (repCount >= 2 && residual > max(8.0, typicalJerk * 6.0)) {
            if (!peakOn) {
                doubleContact = firstImpact >= 0 && t - firstImpact in 90_000_000L..600_000_000L
                firstImpact = t
                peakOn = true
            }
            shockNs = t
            quietSince = -1
        } else if (residual < 3.0) {
            peakOn = false
        }
        typicalJerk += alpha(1.8) * (min(residual, max(2.0, typicalJerk * 2.5)) - typicalJerk)
        if (residual < 0.9 && g < 0.55) {
            if (quietSince < 0) quietSince = t
        } else {
            quietSince = -1
        }
        watchPlacement(t, dt, a, moving)
        for (i in 0..2) coherent[i] += alpha(0.16) * (a[i] - fast[i] - coherent[i])
        if (g >= 0.25 || sqrt(coherent.sumOf { it * it }) >= 0.25) lastMotionNs = t
        if (bench && doubleContact && shockNs >= 0 && lastRep >= 0 &&
            shockNs - lastRep in -850_000_000L..650_000_000L &&
            t - shockNs in 180_000_000L..1_800_000_000L &&
            quietSince >= shockNs && t - quietSince >= 320_000_000L
        ) {
            rackSettled = true
        }
        val next = when {
            v > CROSSING -> 1
            v < -CROSSING -> -1
            else -> 0
        }
        var ev: ProfiledMotionRepEvent? = null
        if (sign != 0 && (next == -sign || next == 0 && abs(v) < STOP)) {
            val l = Lobe(sign, start, t, area, peak)
            sign = 0
            if (l.end - l.start in 160_000_000L..4_500_000_000L && l.area >= max(0.032, RELATIVE_LOBE * typical)) {
                val p = first
                if (direction == 0 || l.sign == direction) first = l
                if (p != null && p.sign != l.sign && l.start - p.end < MAX_FIRST_LOBE_LAG_NS &&
                    l.end - p.start in 650_000_000L..8_000_000_000L &&
                    min(l.area, p.area) >= (if (repCount == 0) INITIAL_BALANCE else 0.13) * max(l.area, p.area) &&
                    l.area + p.area >= 0.13 && (direction == 0 || direction == p.sign)
                ) {
                    first = null
                    if ((shockNs >= 0 && p.start < shockNs && shockNs < l.start && lastRep < shockNs && shockNs - lastRep < 650_000_000L) ||
                        recoilBlocked || !consistent(p, l)
                    ) return null
                    direction = p.sign
                    val extent = l.area + p.area
                    val half = extent * 0.5
                    typical = if (typical <= 0) half else typical + 0.22 * (half.coerceIn(0.5 * typical, 2 * typical) - typical)
                    if (lastRep >= 0 && t - lastRep in 650_000_000L..8_000_000_000L) {
                        intervals.addLast(t - lastRep)
                        if (intervals.size > 5) intervals.removeFirst()
                    }
                    repCount++
                    lastRep = t
                    burst = -1
                    pulseEnd = -1
                    rackSettled = false
                    ev = ProfiledMotionRepEvent(p.start, l.start, t, (t - p.start) / 1_000_000L, max(p.peak, l.peak), extent, 0.0, 0.88)
                }
            }
        }
        if (sign == 0 && next != 0) {
            sign = next
            start = t
            area = 0.0
            peak = 0.0
        }
        if (sign != 0) {
            area += abs(v) * dt
            peak = max(peak, abs(v))
        }
        return ev
    }
}
