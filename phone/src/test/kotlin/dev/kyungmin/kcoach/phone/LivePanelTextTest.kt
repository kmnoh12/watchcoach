package dev.kyungmin.kcoach.phone

import dev.kyungmin.kcoach.phone.ui.LivePanelText
import org.junit.Assert.assertEquals
import org.junit.Test

class LivePanelTextTest {
    @Test fun workingShowsOnlyTheCountAndHeartRate() {
        assertEquals(LivePanelText("7/10회", "심박 112bpm", true), LivePanelText.of("WORKING_START_CONFIRMED", 7, 10, 112))
        assertEquals(LivePanelText("7/10회", "심박 112bpm", true), LivePanelText.of("WORKING_START_BYPASSED", 7, 10, 112))
        assertEquals(LivePanelText("7/10회", "심박 측정 대기", true), LivePanelText.of("WORKING", 7, 10, 0))
    }

    @Test fun restAndCompletionKeepTheHeartRate() {
        assertEquals(LivePanelText("휴식 중", "심박 98bpm", true), LivePanelText.of("RESTING", 0, 10, 98))
        assertEquals(LivePanelText("10회 완료", "심박 98bpm", true), LivePanelText.of("SET_COMPLETE", 10, 10, 98))
    }

    @Test fun preparationStaysAsGuidance() {
        assertEquals(false, LivePanelText.of("PREPARING", 0, 10, 98).headline)
    }
}
