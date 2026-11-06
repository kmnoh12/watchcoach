package dev.kyungmin.kcoach.phone

import dev.kyungmin.kcoach.phone.ui.LiveLine
import dev.kyungmin.kcoach.phone.ui.LivePanelText
import org.junit.Assert.assertEquals
import org.junit.Test

class LivePanelTextTest {
    @Test fun workingShowsOnlyTheCountAndHeartRate() {
        val expected = LivePanelText("7", "/10회", "", 112)
        assertEquals(expected, LivePanelText.of("WORKING_START_CONFIRMED", 7, 10, 112))
        assertEquals(expected, LivePanelText.of("WORKING_START_BYPASSED", 7, 10, 112))
        assertEquals(expected, LivePanelText.of("WORKING", 7, 10, 112))
    }

    @Test fun restAndCompletionKeepTheHeartRate() {
        assertEquals(LivePanelText("휴식 중", "", "", 98), LivePanelText.of("RESTING", 0, 10, 98))
        assertEquals(LivePanelText("10", "회 완료", "", 98), LivePanelText.of("SET_COMPLETE", 10, 10, 98))
    }

    @Test fun preparationIsGuidanceWithoutAHeart() {
        assertEquals(LivePanelText("측정 준비 중", "", "흔들림 없이 1.2초 유지", 0), LivePanelText.of("PREPARING", 0, 10, 98))
    }

    @Test fun plainStatusClearsTheLiveCount() {
        val line = LiveLine("", "t")
        line.show(LivePanelText.of("WORKING", 7, 10, 112))
        line.text = "Watch8 연결 확인 중"
        assertEquals("", line.suffix)
        assertEquals(0, line.heartRate)
    }
}
