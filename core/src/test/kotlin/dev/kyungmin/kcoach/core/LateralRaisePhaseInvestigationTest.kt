package dev.kyungmin.kcoach.core

import java.io.File
import kotlin.math.*
import kotlin.test.Test
import kotlin.test.assertTrue

/** Test-only diagnostics. MM-Fit labels contain set bounds/counts, not arm-height or per-rep phase labels. */
class LateralRaisePhaseInvestigationTest {
    private fun field(o: Any, n: String): Any? = o.javaClass.getDeclaredField(n).apply { isAccessible = true }.get(o)
    private fun call(o: Any, n: String, vararg args: Any?): Any? = o.javaClass.declaredMethods.single {
        it.name == n
    }.apply { isAccessible = true }.invoke(o, *args)
    private data class Label(val start: Long, val end: Long, val reps: Int)
    private data class Row(val t: Long, val a: FloatArray, val g: FloatArray)
    private data class Emission(val peak: Long, val delivered: Long, val source: String, val sign: Int, val fallback: Boolean,
        val firstSame: Long, val firstOther: Long)

    /** Reconstruct the actual pre-lock candidate decision using private production helpers, without changing production. */
    private fun firstDecision(d: CycleAxisRepDetector, now: Long): Triple<Any, Any?, Boolean> {
        val from = call(d, "windowStart", now) as Int
        val times = field(d, "times") as LongArray
        var best: Any? = null
        for (gyro in listOf(true, false)) {
            val projected = call(d, "project", field(d, if (gyro) "gyro" else "dyn"), from) as DoubleArray
            val sorted = projected.map { abs(it) }.sorted()
            val p95 = max(sorted[(.95 * (sorted.size - 1)).toInt()], 1e-9)
            val floor = if (gyro) .4 else 1.5
            if (p95 < floor) continue
            for (sign in listOf(1, -1)) {
                val peaks = call(d, "findSourcePeaks", projected, from, sign, p95, gyro) as IntArray
                if (peaks.isEmpty()) continue
                val c = call(d, "candidate", peaks, p95, floor, gyro, sign) ?: continue
                val opposite = call(d, "findSourcePeaks", projected, from, -sign, p95, gyro) as IntArray
                c.javaClass.getDeclaredField("oppositeNs").apply { isAccessible = true }
                    .set(c, LongArray(opposite.size) { times[opposite[it]] })
                if (best == null || (field(c, "score") as Double) < (field(best, "score") as Double)) best = c
            }
        }
        val chosen = requireNotNull(best)
        val returned = call(d, "returnLobeDelivery", chosen, now)
        return Triple(chosen, returned, returned === chosen)
    }

    private fun replay(rows: List<Row>): List<Emission> {
        val d = CycleAxisRepDetector(countOnReturn = true)
        d.beginCounting()
        val out = mutableListOf<Emission>()
        var fallback = false
        var firstSame = 0L
        var firstOther = 0L
        for (r in rows) {
            val first = field(d, "lastPeakNs") == null
            val e = d.add(SensorSample(r.t, r.a[0], r.a[1], r.a[2], r.g[0], r.g[1], r.g[2], 3)) ?: continue
            if (first) {
                val (chosen, _, usedFallback) = firstDecision(d, r.t)
                fallback = usedFallback
                firstSame = (field(chosen, "peaksNs") as LongArray).firstOrNull() ?: 0L
                firstOther = (field(chosen, "oppositeNs") as LongArray).firstOrNull() ?: 0L
            }
            out += Emission(e.endTimestampNs, r.t, if (field(d, "lockedGyro") == true) "gyro" else "accel",
                field(d, "lockedSign") as Int, fallback, firstSame, firstOther)
        }
        // No finishAll(): real haptics are emitted only by add(), never from a final offline flush.
        return out
    }

    @Test fun reportAllAvailableMmFitSets() {
        val dir = File("../work/datasets/mmfit-probe")
        require(dir.isDirectory) { "MM-Fit probe CSVs required for this investigation" }
        val report = File("build/latraise-investigation").apply { mkdirs() }
        val summary = mutableListOf("session,set,labelReps,reports,peakLift,peakReturn,deliveryLift,deliveryMiddle,deliveryReturn,source,sign,fallback,firstSameMs,firstOtherMs,gyroAxis,gyroOnlyReports,gyroOnlyLift,accelOnlyReports,accelOnlyLift,lockChanges")
        val details = mutableListOf("session,set,rep,peakMs,deliveryMs,peakPhase,deliveryPhase,source,sign,fallback")
        for (labelFile in dir.listFiles()!!.filter { it.name.endsWith("_labels.csv") }.sorted()) {
            val labels = labelFile.readLines().drop(1).map { it.split(',') }.filter { it[3] == "lateral_shoulder_raises" }
                .map { Label(it[0].toLong(), it[1].toLong(), it[2].toInt()) }
            if (labels.isEmpty()) continue
            val name = labelFile.name.removeSuffix("_labels.csv")
            val sets = labels.map { mutableListOf<Row>() }
            var a = FloatArray(3)
            File(dir, "$name.csv").forEachLine { line ->
                if (!line.startsWith("sensor")) {
                    val p = line.split(','); val t = p[1].toLong()
                    val values = floatArrayOf(p[2].toFloat(), p[3].toFloat(), p[4].toFloat())
                    if (p[0] == "0") a = values
                    else labels.forEachIndexed { i, l -> if (t in l.start..l.end) sets[i] += Row(t - l.start + 1_000_000_000L, a, values) }
                }
            }
            sets.forEachIndexed { index, rows ->
                // Independent raw-gyro dominant-axis lobe proxy. The earliest substantial lobe is called lift,
                // its opposite return. This is explicitly NOT video ground truth or the arm-down instant.
                val axis = (0..2).maxBy { c -> val mean = rows.map { it.g[c].toDouble() }.average(); rows.sumOf { (it.g[c] - mean).pow(2) } }
                val signal = rows.indices.map { i -> (max(0, i - 6)..i).map { rows[it].g[axis].toDouble() }.average() }
                val p95 = signal.map { abs(it) }.sorted().let { it[(.95 * (it.size - 1)).toInt()] }
                val first = signal.firstOrNull { abs(it) > .25 * p95 } ?: 1.0
                val liftSign = if (first > 0) 1 else -1
                fun phase(t: Long, middle: Boolean): String {
                    val i = rows.indices.minBy { abs(rows[it].t - t) }
                    val v = signal[i] * liftSign
                    return if (middle && abs(v) < .25 * p95) "middle" else if (v >= 0) "lift" else "return"
                }
                val events = replay(rows)
                val gyroOnly = replay(rows.map { it.copy(a = floatArrayOf(0f, 0f, 9.80665f)) })
                val accelOnly = replay(rows.map { it.copy(g = floatArrayOf(0f, 0f, 0f)) })
                val peakPhases = events.map { phase(it.peak, false) }
                val deliveryPhases = events.map { phase(it.delivered, true) }
                val firstEvent = events.firstOrNull()
                summary += listOf(name, index + 1, labels[index].reps, events.size,
                    peakPhases.count { it == "lift" }, peakPhases.count { it == "return" },
                    deliveryPhases.count { it == "lift" }, deliveryPhases.count { it == "middle" }, deliveryPhases.count { it == "return" },
                    firstEvent?.source, firstEvent?.sign, firstEvent?.fallback, firstEvent?.firstSame?.div(1_000_000),
                    firstEvent?.firstOther?.div(1_000_000), axis,
                    gyroOnly.size, gyroOnly.count { phase(it.peak, false) == "lift" },
                    accelOnly.size, accelOnly.count { phase(it.peak, false) == "lift" },
                    events.zipWithNext().count { (a, b) -> a.source != b.source || a.sign != b.sign }).joinToString(",")
                events.forEachIndexed { i, e -> details += listOf(name, index + 1, i + 1, e.peak / 1_000_000,
                    e.delivered / 1_000_000, peakPhases[i], deliveryPhases[i], e.source, e.sign, e.fallback).joinToString(",") }
            }
        }
        File(report, "sets.csv").writeText(summary.joinToString("\n") + "\n")
        File(report, "events.csv").writeText(details.joinToString("\n") + "\n")
        println(summary.joinToString("\n"))
    }

    @Test fun stillLeadInMustNotInvertReturnCuesForIdenticalReps() {
        val rows = mutableListOf<Row>()
        var t = 1_000_000_000L
        fun feed(g: Double) { rows += Row(t, floatArrayOf(0f, 0f, 9.80665f), floatArrayOf(g.toFloat(), 0f, 0f)); t += 40_000_000L }
        val lift = mutableListOf<Long>(); val returned = mutableListOf<Long>()
        repeat(6) {
            lift += t + 600_000_000L
            repeat(30) { feed(1.6 * sin(PI * it / 30)) }
            repeat(8) { feed(0.0) }
            returned += t + 600_000_000L
            repeat(30) { feed(-1.0 * sin(PI * it / 30)) }
            repeat(8) { feed(0.0) }
        }
        repeat(50) { feed(0.0) }
        val baseline = replay(rows)
        assertTrue(baseline.size == 6, "Normal first lift must produce all six return reports")
        assertTrue(baseline.all { e -> returned.minOf { abs(it - e.peak) } < lift.minOf { abs(it - e.peak) } }, "Normal first lift baseline: $baseline")
        for (leadNs in listOf(0L, 500_000_000L, 1_200_000_000L, 2_500_000_000L)) {
            val still = generateSequence(1_000_000_000L) { it + 40_000_000L }
                .takeWhile { it < 1_000_000_000L + leadNs }.map { Row(it,
                    floatArrayOf(0f, 0f, 9.80665f), floatArrayOf(0f, 0f, 0f)) }.toList()
            val events = replay(still + rows.map { it.copy(t = it.t + leadNs) })
            val wrong = events.filter { e -> lift.minOf { abs(it + leadNs - e.peak) } < returned.minOf { abs(it + leadNs - e.peak) } }
            println("identical-reps: stillMs=${leadNs / 1_000_000}; events=$events; liftReports=${wrong.size}")
            assertTrue(events.size == 6, "Still ${leadNs / 1_000_000}ms must retain all six reps: $events")
            assertTrue(wrong.isEmpty(), "Still ${leadNs / 1_000_000}ms inverted ${wrong.size}/${events.size} reports onto lift lobes")
            assertTrue(events.all { e ->
                rows.single { it.t == e.delivered - leadNs }.g[0] < 0f
            }, "Actual delivery must also be during the return, not just its historical peak: $events")
        }
    }

}
