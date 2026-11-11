package dev.kyungmin.kcoach.wear

import android.app.Notification
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Looper
import dev.kyungmin.kcoach.core.WearSync
import org.junit.Assert.*
import org.junit.After
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import org.robolectric.shadows.ShadowService
import org.robolectric.shadows.ShadowBuild
import java.io.File
import java.time.Duration
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

/** Exercises the listener/owner boundary; OS CPU kills themselves require a physical watch. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], shadows = [WatchCrashLifecycleTest.ForegroundService::class])
class WatchCrashLifecycleTest {
    @Implements(Service::class)
    class ForegroundService : ShadowService() {
        companion object { var reject = false }
        @Implementation override fun startForeground(id: Int, notification: Notification) {
            if (reject) throw SecurityException("injected promotion refusal")
            super.startForeground(id, notification)
        }
        @Implementation override fun startForeground(id: Int, notification: Notification, type: Int) {
            if (reject) throw SecurityException("injected promotion refusal")
            super.startForeground(id, notification, type)
        }
    }

    @After fun reset() { ForegroundService.reject = false }

    private fun start() = Intent().putExtra("command", "START").putExtra("session", "crash-session")
        .putExtra("exerciseId", "leg_press").putExtra("setId", "set").putExtra("attemptId", "attempt")
        .putExtra("targetReps", 8).putExtra("commandRevision", 1L)

    private fun field(service: WearWorkoutService, name: String) =
        WearWorkoutService::class.java.getDeclaredField(name).apply { isAccessible = true }.get(service)

    private fun receive(listener: WearCommandService, path: String, payload: String) {
        WearCommandService::class.java.getDeclaredMethod("handlePayload", String::class.java, String::class.java)
            .apply { isAccessible = true }.invoke(listener, path, payload)
    }

    @Test fun foregroundRefusalAfterCreationCannotApplyOrAcknowledgeAWorkout() {
        val controller = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            val service = controller.get()
            ForegroundService.reject = true
            assertEquals(Service.START_NOT_STICKY, service.onStartCommand(start(), 0, 1))
            assertEquals("", field(service, "sessionId"))
            assertFalse(field(service, "running") as Boolean)
            assertTrue(shadowOf(service).isStoppedBySelf)
            assertEquals(0L, field(service, "lastCommandRevision"))
        } finally { controller.destroy() }
    }

    @Test fun idlePairMessagesDoNotRepeatedlyCreateAndRestoreTheWorkoutOwner() {
        val listener = Robolectric.buildService(WearCommandService::class.java).get()
        repeat(7) {
            receive(listener, WearSync.PATH_PAIR, WearSync.hello("phone"))
            assertNull("An idle phone greeting must not start another recovery/destroy cycle",
                shadowOf(RuntimeEnvironment.getApplication()).nextStartedService)
        }
    }

    @Test fun pairMessageStillRecoversADurablyOwnedSession() {
        val controller = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            controller.get().onStartCommand(start(), 0, 1)
            val app = RuntimeEnvironment.getApplication()
            while (shadowOf(app).nextStartedService != null) { /* drain existing starts */ }
            val listener = Robolectric.buildService(WearCommandService::class.java).get()
            receive(listener, WearSync.PATH_PAIR, WearSync.hello("phone"))
            assertEquals("HELLO", shadowOf(app).nextStartedService?.getStringExtra("command"))
        } finally { controller.destroy() }
    }

    @Test fun deniedColdRecoveryPreservesTheOriginalSessionWithoutAStickyRestart() {
        val original = Robolectric.buildService(WearWorkoutService::class.java).create()
        original.get().onStartCommand(start(), 0, 1)
        original.destroy()
        val prefs = RuntimeEnvironment.getApplication().getSharedPreferences("workout-runtime", 0)
        val saved = prefs.getString("state", null)
        ForegroundService.reject = true
        val recovery = Robolectric.buildService(WearWorkoutService::class.java).create()
        assertEquals(Service.START_NOT_STICKY,
            recovery.get().onStartCommand(Intent().putExtra("command", "HEARTBEAT"), 0, 1))
        recovery.destroy()
        assertEquals(saved, prefs.getString("state", null))
    }

    @Test fun pairMessagesRecoverPendingCaptureCompletionAndChunkJournalWithoutAnActiveSession() {
        val app = RuntimeEnvironment.getApplication()
        val listener = Robolectric.buildService(WearCommandService::class.java).get()
        fun helloStartsOwner() {
            receive(listener, WearSync.PATH_PAIR, WearSync.hello("phone"))
            assertEquals("HELLO", shadowOf(app).nextStartedService?.getStringExtra("command"))
        }
        val runtime = app.getSharedPreferences("workout-runtime", 0)
        runtime.edit().putString("state", "{\"session\":\"\",\"pendingCompletion\":\"pending\"}").commit()
        helloStartsOwner()
        runtime.edit().clear().commit()
        val captures = app.getSharedPreferences("capture-outbox", 0)
        captures.edit().putStringSet("pendingCaptureIds", setOf("pending")).commit()
        helloStartsOwner()
        captures.edit().clear().commit()
        File(app.filesDir, "capture-checkpoint.json").writeText("journal retained for recovery")
        helloStartsOwner()
    }

    @Test fun aNewStartAfterIdleStopRearmsThePhoneWatchdog() {
        val controller = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            val service = controller.get()
            service.onStartCommand(Intent().putExtra("command", "HELLO"), 0, 1)
            assertNull(field(service, "phoneWatchdog"))
            service.onStartCommand(start(), 0, 2)
            assertNotNull("Re-promotion alone leaves a reused owner without its disconnect watchdog",
                field(service, "phoneWatchdog"))
        } finally { controller.destroy() }
    }

    @Test fun physicalWatchPromotesOnlyTheHealthTypeRatherThanEveryManifestType() {
        ShadowBuild.setFingerprint("samsung/watch8/physical")
        ShadowBuild.setModel("Galaxy Watch8")
        val controller = Robolectric.buildService(WearWorkoutService::class.java).create()
        try {
            assertEquals(ServiceInfo.FOREGROUND_SERVICE_TYPE_HEALTH, controller.get().foregroundServiceType)
        } finally { controller.destroy() }
    }

    @Test fun captureRetryDefersFileWorkAndDoesNotQueueTheSameCaptureTwice() {
        val service = Robolectric.buildService(WearWorkoutService::class.java).get()
        val queued = mutableListOf<Runnable>()
        val executor = object : ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS, LinkedBlockingQueue<Runnable>()) {
            override fun execute(command: Runnable) { queued.add(command) }
        }
        WearWorkoutService::class.java.getDeclaredField("captureTransferExecutor").apply { isAccessible = true }
            .set(service, executor)
        val app = RuntimeEnvironment.getApplication()
        val prefs = app.getSharedPreferences("capture-outbox", 0)
        prefs.edit().putStringSet("pendingCaptureIds", setOf("offline-capture")).commit()
        // Even missing-file discovery belongs to the transfer worker, away from lifecycle/sensor callbacks.
        val retry = WearWorkoutService::class.java.getDeclaredMethod("retryPendingCaptures").apply { isAccessible = true }
        try {
            retry.invoke(service)
            retry.invoke(service)
            assertEquals("Only one lazy file load per capture may be queued", 1, queued.size)
            assertFalse(File(app.filesDir, "capture-storage.json").exists())
            queued.single().run()
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(15))
            assertEquals(setOf("offline-capture"), prefs.getStringSet("pendingCaptureIds", emptySet()))
            assertEquals("Missing originals must stay retained without a five-second file retry loop", 1, queued.size)
        } finally { executor.shutdownNow() }
    }
}
