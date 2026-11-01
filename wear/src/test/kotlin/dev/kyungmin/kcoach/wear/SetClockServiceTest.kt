package dev.kyungmin.kcoach.wear

import android.content.Intent
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RuntimeEnvironment
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SetClockServiceTest {
    private fun command(type: String, rev: Long) = Intent().putExtra("command", type).putExtra("session", "clock-session")
        .putExtra("exerciseId", "leg_press").putExtra("exerciseName", "레그프레스").putExtra("setId", "set").putExtra("attemptId", "attempt")
        .putExtra("targetReps", 8).putExtra("commandRevision", rev)
    private fun state() = shadowOf(RuntimeEnvironment.getApplication()).broadcastIntents.last { it.action == WearWorkoutService.ACTION_STATE }
    private fun field(service: WearWorkoutService, name: String) = WearWorkoutService::class.java.getDeclaredField(name).apply { isAccessible = true }.get(service)
    @Test fun manualClockBroadcastsRemainingAndPersistsAcrossServiceRecreation() {
        var owner = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            owner.get().onStartCommand(command("START", 1).putExtra("setClockValue", System.currentTimeMillis() + 70_000)
                .putExtra("setClockTotal", 70_000L), 0, 1)
            assertTrue(state().getBooleanExtra("manualRequired", false))
            assertTrue(state().getLongExtra("setClockRemaining", -1) in 69_000L..70_000L)
            owner.destroy()
            owner = Robolectric.buildService(WearWorkoutService::class.java).create()
            owner.get().onStartCommand(Intent().putExtra("command", "REQUEST_STATE"), 0, 2)
            assertTrue(state().getLongExtra("setClockRemaining", -1) in 68_000L..70_000L)
            assertEquals(70_000L, state().getLongExtra("setClockTotal", -1))
        } finally { owner.destroy() }
    }
    @Test fun pausedClockDoesNotCueAndResumesSameRemainingTime() {
        val owner = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            val service = owner.get()
            service.onStartCommand(command("START", 1).putExtra("setClockValue", System.currentTimeMillis() + 4000)
                .putExtra("setClockTotal", 70_000L), 0, 1)
            service.onStartCommand(command("PAUSE", 2), 0, 2)
            val remaining = state().getLongExtra("setClockRemaining", -1)
            (field(service, "setClockTicker") as Runnable).run()
            assertEquals(remaining, state().getLongExtra("setClockRemaining", -2))
            assertFalse(field(service, "setClockWarned") as Boolean)
            service.onStartCommand(command("RESUME", 3), 0, 3)
            (field(service, "setClockTicker") as Runnable).run()
            assertTrue(field(service, "setClockWarned") as Boolean)
            (field(service, "setClockTicker") as Runnable).run()
            assertTrue(field(service, "setClockWarned") as Boolean)
        } finally { owner.destroy() }
    }
    @Test fun restAndStopCancelClockAndSensorSetWithoutClockStaysUnchanged() {
        val owner = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            val service = owner.get()
            service.onStartCommand(command("START", 1).putExtra("setClockValue", System.currentTimeMillis() + 70_000), 0, 1)
            service.onStartCommand(command("REST", 2).putExtra("restEndAtMs", System.currentTimeMillis() + 60_000), 0, 2)
            assertEquals(-1L, state().getLongExtra("setClockRemaining", -2))
            service.onStartCommand(command("SET", 3).putExtra("exerciseId", "barbell_biceps_curl"), 0, 3)
            assertFalse(state().getBooleanExtra("manualRequired", true))
            assertEquals(-1L, state().getLongExtra("setClockRemaining", -2))
            service.onStartCommand(command("STOP", 4), 0, 4)
            assertEquals(-1L, field(service, "setClockValue"))
        } finally { owner.destroy() }
    }
}
