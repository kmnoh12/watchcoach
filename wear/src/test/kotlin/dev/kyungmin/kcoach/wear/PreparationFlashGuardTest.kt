package dev.kyungmin.kcoach.wear

import org.junit.Assert.assertEquals
import org.junit.Test

class PreparationFlashGuardTest {
    @Test fun `a preparation step that passes quickly never reaches the screen`() {
        val guard = PreparationFlashGuard()
        assertEquals(0L, guard.holdMs(false, true, 1_000))
        assertEquals(400L, guard.holdMs(true, false, 2_000))
        assertEquals(150L, guard.holdMs(true, false, 2_250))
        assertEquals(0L, guard.holdMs(false, true, 2_300))
    }

    @Test fun `a preparation step that lasts is shown and stays shown`() {
        val guard = PreparationFlashGuard()
        guard.holdMs(false, true, 1_000)
        guard.holdMs(true, false, 2_000)
        assertEquals(0L, guard.holdMs(true, false, 2_400))
        assertEquals(0L, guard.holdMs(true, false, 3_000))
    }

    @Test fun `the first preparation of a session is drawn at once`() {
        val guard = PreparationFlashGuard()
        assertEquals(0L, guard.holdMs(false, false, 1_000))
        assertEquals(0L, guard.holdMs(true, false, 1_100))
    }
}
