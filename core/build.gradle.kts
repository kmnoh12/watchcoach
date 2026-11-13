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
    inputs.property("selectedEvidenceZip", System.getenv("WATCHCOACH_EVIDENCE_ZIP").orEmpty())
    inputs.property("ropeEvidenceDirectory", System.getenv("WATCHCOACH_ROPE_EVIDENCE_DIR").orEmpty())
    System.getenv("WATCHCOACH_ROPE_EVIDENCE_DIR")?.takeIf { file(it).isDirectory }?.let {
        inputs.files(fileTree(it) { include("*/watch.kcs", "*/watch.manifest") })
    }
    System.getenv("WATCHCOACH_EVIDENCE_ZIP")?.takeIf { file(it).isFile }?.let { inputs.file(it) }
    System.getenv("WATCHCOACH_PRESS_EVIDENCE_ZIP")?.takeIf { file(it).isFile }?.let { inputs.file(it) }
}
