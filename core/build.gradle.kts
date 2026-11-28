plugins {
    kotlin("jvm")
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
    inputs.property("calibrationMmfitDirectory", System.getenv("WATCHCOACH_CALIBRATION_MMFIT_DIR").orEmpty())
    inputs.property("mmfitDirectory", System.getenv("WATCHCOACH_MMFIT_DIR").orEmpty())
    inputs.property("peakComparisonSessions", System.getenv("WATCHCOACH_PEAK_SESSIONS").orEmpty())
    inputs.property("pressEvidenceZip", System.getenv("WATCHCOACH_PRESS_EVIDENCE_ZIP").orEmpty())
    val chestCaptures = System.getenv("WATCHCOACH_CHEST_CAPTURE_DIR").orEmpty()
    inputs.property("chestCaptureDirectory", chestCaptures)
    if (chestCaptures.isNotEmpty()) inputs.files(fileTree(chestCaptures) {
        include("2026-10-24/195856_machine_chest_press_plate_*/capture.kcs",
            "2026-11-05/123448_machine_chest_press_plate_*/capture.kcs",
            "2026-11-18/122744_machine_chest_press_plate_*/capture.kcs")
    })
    inputs.property("selectedEvidenceZip", System.getenv("WATCHCOACH_EVIDENCE_ZIP").orEmpty())
    inputs.property("ropeEvidenceDirectory", System.getenv("WATCHCOACH_ROPE_EVIDENCE_DIR").orEmpty())
    inputs.property("virtualWatchIndex", System.getenv("WATCHCOACH_VIRTUAL_WATCH_INDEX").orEmpty())
    System.getenv("WATCHCOACH_VIRTUAL_WATCH_INDEX")?.takeIf { file(it).isFile }?.let { inputs.file(it) }
    inputs.file("../phone/src/main/kotlin/dev/kyungmin/watchcoach/phone/WorkoutData.kt")
    System.getenv("WATCHCOACH_ROPE_EVIDENCE_DIR")?.takeIf { file(it).isDirectory }?.let {
        inputs.files(fileTree(it) { include("*/watch.kcs", "*/watch.manifest") })
    }
    System.getenv("WATCHCOACH_EVIDENCE_ZIP")?.takeIf { file(it).isFile }?.let { inputs.file(it) }
    System.getenv("WATCHCOACH_PRESS_EVIDENCE_ZIP")?.takeIf { file(it).isFile }?.let { inputs.file(it) }
}
