package dev.kyungmin.watchcoach.core

import java.io.File
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Export the actual resolver, not a second Python implementation of routing. */
class VirtualWatchCampaignInventoryTest {
    @Test fun exportCurrentPhoneCatalogWithResolvedMeasurementProfiles() {
        val cwd = File(System.getProperty("user.dir"))
        val root = if (File(cwd, "phone").isDirectory) cwd else cwd.parentFile
        val catalog = File(root, "phone/src/main/kotlin/dev/kyungmin/watchcoach/phone/WorkoutData.kt")
        val source = catalog.readText()
        val body = source.substringAfter("val catalog = mutableListOf(")
            .substringBefore("val builtInExerciseIds:")
        val declarations = body.lineSequence().filter { it.trimStart().startsWith("exercise(") }.toList()
        val pattern = Regex("""^\s*exercise\("([^"]+)",\s*"([^"]+)".*$""")
        val rows = declarations.map { line ->
            val match = requireNotNull(pattern.matchEntire(line)) { "Catalog grammar changed: " + line }
            match.groupValues[1] to match.groupValues[2]
        }
        assertTrue(rows.isNotEmpty(), "No phone exercises extracted")
        assertEquals(rows.size, rows.map { it.first }.toSet().size, "Duplicate phone exercise IDs")
        val out = File(root, "work/virtual-watch/campaign/resolved-profiles.tsv")
        out.parentFile.mkdirs()
        val core = File(root, "core/src/main")
        val engineIndex = core.walkTopDown().filter { it.isFile && it.extension == "kt" }
            .sortedBy { it.relativeTo(core).invariantSeparatorsPath }
            .joinToString("\n", postfix = "\n") {
                it.relativeTo(core).invariantSeparatorsPath + "\t" + SensorCaptureFormat.sha256(it.readBytes())
            }
        out.bufferedWriter().use { writer ->
            writer.appendLine("#catalog_sha256\t" + SensorCaptureFormat.sha256(catalog.readBytes()))
            writer.appendLine("#engine_sha256\t" + SensorCaptureFormat.sha256(engineIndex.toByteArray(Charsets.UTF_8)))
            writer.appendLine("exercise_id\tname\tnormalized_id\tkind\tmode\ttier\tcount_mode\tfamily\tdeclared_signal\talgorithm_id\tprofile_snapshot\tmeasurement_recipe")
            rows.forEach { (id, name) ->
                val p = ExerciseTrackingProfiles.resolve(id, name)
                val fields = listOf(id, name, p.exerciseId, HoldExercise.kind(id), p.mode,
                    p.capabilityTier, p.countMode, p.family, p.signal, p.id,
                    TrackingProfileSnapshot.encode(p), ExerciseMeasurementContracts.resolve(id).recipe)
                require(fields.none { '\t' in it.toString() || '\n' in it.toString() })
                writer.appendLine(fields.joinToString("\t"))
            }
        }
        println("CAMPAIGN catalog=" + rows.size + "; routing exported from current production resolver")
    }
}
