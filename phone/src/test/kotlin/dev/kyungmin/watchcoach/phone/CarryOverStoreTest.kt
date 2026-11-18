package dev.kyungmin.watchcoach.phone

import dev.kyungmin.watchcoach.core.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class CarryOverStoreTest {
    private fun log(session: String, day: Long, kg: Double) =
        ExerciseLog("barbell_biceps_curl", day, listOf(LoggedSet(kg, 10)), sessionId = session, startedAtMs = day)

    @Test fun skippedSessionLeavesNextTimeHistoryButStaysInStoredRecords() {
        val app = RuntimeEnvironment.getApplication()
        val history = ExerciseHistoryStore(app)
        history.add(log("old", 1, 20.0))
        history.add(log("today", 2, 30.0))
        val carry = CarryOverStore(app)

        assertTrue(carry.carries("today"))
        assertEquals(setOf("old", "today"), history.loadForCarry().all.mapNotNull { it.sessionId }.toSet())

        assertTrue(carry.setCarry("today", false))
        assertFalse(carry.carries("today"))
        assertEquals(listOf("old"), history.loadForCarry().all.mapNotNull { it.sessionId })
        // Records and stats read the full history, so the session is still there.
        assertEquals(2, history.load().all.size)
        // The next routine day seeds from the older session, not the skipped one.
        val seeded = ExerciseDefaults.newExercise(WorkoutData.catalog.first { it.id == "barbell_biceps_curl" }, null, history.loadForCarry().all)
        assertEquals(20.0, seeded.sets.first().weightKg ?: 0.0, 0.0)

        assertTrue(carry.setCarry("today", true))
        assertEquals(2, history.loadForCarry().all.size)
    }
}
