package dev.kyungmin.kcoach.wear

import android.content.Intent
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/** Field crash 2026-10-29/30/11-06: ForegroundServiceDidNotStartInTimeException right after a workout start. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class WearForegroundStartTest {
    private fun idle(type: String) = Intent().putExtra("command", type)
    private fun start() = Intent().putExtra("command", "START").putExtra("session", "foreground-session")
        .putExtra("exerciseId", "leg_press").putExtra("setId", "set").putExtra("attemptId", "attempt")
        .putExtra("targetReps", 8).putExtra("commandRevision", 1L)

    @Test fun workoutStartQueuedBehindAnIdleStopPutsTheSameInstanceBackInTheForeground() {
        val controller = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            val service = controller.get()
            // A phone HELLO on an idle watch tears foreground down while START is already queued for this instance.
            service.onStartCommand(idle("HELLO"), 0, 1)
            assertTrue(shadowOf(service).isForegroundStopped)
            service.onStartCommand(start(), 0, 2)
            assertFalse("Android kills the app unless every foreground start is answered with startForeground",
                shadowOf(service).isForegroundStopped)
        } finally { controller.destroy() }
    }

    @Test fun anOlderStartCannotStopTheServiceOnceANewerStartArrived() {
        val controller = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            val service = controller.get()
            service.onStartCommand(start(), 0, 5)
            val stop = WearWorkoutService::class.java.getDeclaredMethod("stopRuntimeService", Int::class.javaPrimitiveType)
                .apply { isAccessible = true }
            service.onStartCommand(idle("HELLO"), 0, 6)
            stop.invoke(service, 5)
            assertFalse(shadowOf(service).isForegroundStopped)
            assertFalse(shadowOf(service).isStoppedBySelf)
        } finally { controller.destroy() }
    }

    @Test fun aTimerDrivenStopTargetsTheNewestStartInsteadOfDroppingQueuedOnes() {
        val controller = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            val service = controller.get()
            service.onStartCommand(idle("HELLO"), 0, 7)
            // The default argument is what timer and acknowledgement callbacks use, away from any onStartCommand.
            val stop = WearWorkoutService::class.java.getDeclaredMethod("stopRuntimeService\$default",
                WearWorkoutService::class.java, Int::class.javaPrimitiveType, Int::class.javaPrimitiveType, Any::class.java)
                .apply { isAccessible = true }
            service.onStartCommand(start(), 0, 8)
            stop.invoke(null, service, 0, 1, null)
            assertEquals("A bare stopSelf() also drops a start Android has already queued", 8, shadowOf(service).stopSelfResultId)
        } finally { controller.destroy() }
    }
}
