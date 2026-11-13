package dev.kyungmin.kcoach.phone.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.assertIsNotSelected
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.swipeLeft
import androidx.compose.ui.test.swipeRight
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.dp
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.performTouchInput
import com.github.takahirom.roborazzi.captureRoboImage
import dev.kyungmin.kcoach.phone.WorkoutRecord
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.time.YearMonth

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w360dp-h800dp-xxhdpi")
class RecordsAndResultMenuTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun aRecordRowOpensItsSession() {
        var opened: String? = null
        val record = WorkoutRecord("2026-10-20", "가슴·삼두", 81, 26, 10450, "session-1")
        compose.setContent {
            RecordsScreen(listOf(record), YearMonth.of(2026, 10), null,
                RecordsActions(openResult = {}, openRecord = { opened = it.sessionId }, monthChanged = {}))
        }
        compose.onNodeWithText("가슴·삼두").performClick()
        assertEquals("session-1", opened)
    }

    private val records = listOf(
        WorkoutRecord("2026-10-09", "가슴·삼두", 81, 26, 10450, "s3"),
        WorkoutRecord("2026-10-05", "등·이두", 68, 22, 7840, "s2"),
        WorkoutRecord("2026-10-03", "어깨전문", 74, 24, 9120, "s1"),
    )

    private fun renderModes(width: Int, selecting: Boolean) {
        compose.setContent {
            Box(Modifier.fillMaxSize()) {
                RecordsScreen(records, YearMonth.of(2026, 10), "가슴·삼두",
                    RecordsActions(openResult = {}, openRecord = {}, monthChanged = {}))
                Box(Modifier.align(Alignment.BottomCenter).padding(horizontal = 14.dp, vertical = 14.dp)) {
                    FloatingTabBar(1, true) {}
                }
            }
        }
        compose.onNodeWithText("운동 기록").assertExists()
        compose.onNodeWithText("10월 기록").assertExists()
        compose.onNodeWithText("3회").assertExists()
        compose.onNodeWithText("최근 완료 결과 · 가슴·삼두").assertDoesNotExist()
        val calendarTop = compose.onNodeWithTag("records-calendar").fetchSemanticsNode().boundsInRoot.top
        val cardBounds = compose.onNodeWithTag("record-s1").fetchSemanticsNode().boundsInRoot
        if (!selecting) {
            compose.onRoot().captureRoboImage("build/outputs/roborazzi/records_normal_${width}.png")
            return
        }
        compose.onNodeWithText("어깨전문").performTouchInput { longClick() }
        compose.onNodeWithText("등·이두").performClick()
        compose.onNodeWithText("2개 선택됨").assertExists()
        compose.onNodeWithTag("select-all").assertIsNotSelected()
        compose.onNodeWithContentDescription("어깨전문 메뉴").assertDoesNotExist()
        assertEquals(calendarTop, compose.onNodeWithTag("records-calendar").fetchSemanticsNode().boundsInRoot.top)
        assertEquals(cardBounds, compose.onNodeWithTag("record-s1").fetchSemanticsNode().boundsInRoot)
        compose.onRoot().captureRoboImage("build/outputs/roborazzi/records_selecting_${width}.png")
        compose.onNodeWithText("취소").performClick()
        compose.onNodeWithText("운동 기록").assertExists()
        compose.onNodeWithContentDescription("어깨전문 메뉴").assertExists()
    }

    @Test fun normalAt360() = renderModes(360, false)

    @Test fun selectingAt360() = renderModes(360, true)

    @Test
    @Config(qualifiers = "w412dp-h800dp-xxhdpi")
    fun normalAt412() = renderModes(412, false)

    @Test
    @Config(qualifiers = "w412dp-h800dp-xxhdpi")
    fun selectingAt412() = renderModes(412, true)

    @Test
    fun backCancelsSelectionAndMenuStillOpens() {
        var dispatcher: androidx.activity.OnBackPressedDispatcher? = null
        var menuRecord: WorkoutRecord? = null
        compose.setContent {
            dispatcher = androidx.activity.compose.LocalOnBackPressedDispatcherOwner.current?.onBackPressedDispatcher
            RecordsScreen(records, YearMonth.of(2026, 10), null,
                RecordsActions(openResult = {}, openRecord = {}, monthChanged = {}, recordMenu = { menuRecord = it }))
        }
        compose.onNodeWithText("어깨전문").performTouchInput { longClick() }
        compose.runOnIdle { requireNotNull(dispatcher).onBackPressed() }
        compose.onNodeWithText("운동 기록").assertExists()
        compose.onNodeWithContentDescription("어깨전문 메뉴").performClick()
        assertEquals("s1", menuRecord?.sessionId)
    }

    @Test
    fun longPressSelectsRowsAndDeletesThem() {
        val outsideMonth = WorkoutRecord("2026-09-30", "하체", 60, 20, 8000, "outside")
        var deleted: List<String?> = emptyList(); var all = true; var opened = 0
        compose.setContent {
            RecordsScreen(records + outsideMonth, YearMonth.of(2026, 10), null,
                RecordsActions(openResult = {}, openRecord = { opened++ }, monthChanged = {},
                    deleteRecords = { list, everything -> deleted = list.map { it.sessionId }; all = everything }))
        }
        compose.onNodeWithText("어깨전문").performTouchInput { longClick() }
        compose.onNodeWithText("1개 선택됨").assertExists()
        compose.onNodeWithTag("select-all").assertIsNotSelected()
        compose.onNodeWithText("등·이두").performClick()
        compose.onNodeWithText("2개 선택됨").assertExists()
        assertEquals(0, opened)
        compose.onNodeWithText("삭제").performClick()
        assertEquals(listOf("s1", "s2"), deleted.filterNotNull().sorted())
        assertEquals(false, all)
        compose.onNodeWithTag("select-all").performClick()
        compose.onNodeWithTag("select-all").assertIsSelected()
        compose.onNodeWithText("3개 선택됨").assertExists()
        compose.onNodeWithText("삭제").performClick()
        assertEquals(listOf("s1", "s2", "s3"), deleted.filterNotNull().sorted())
        assertEquals(false, all) // Visible month only, never the global-delete action.
        compose.onNodeWithTag("select-all").performClick()
        compose.onNodeWithTag("select-all").assertIsNotSelected()
        compose.onNodeWithText("0개 선택됨").assertExists()
        compose.onNodeWithText("삭제").assertIsNotEnabled()
        compose.onNodeWithText("가슴·삼두").performClick()
        compose.onNodeWithText("삭제").assertIsEnabled()
    }

    @Test
    fun changingMonthClearsSelectionAndSwipeStillNavigates() {
        val outsideMonth = WorkoutRecord("2026-09-30", "하체", 60, 20, 8000, "outside")
        var changed: YearMonth? = null
        compose.setContent {
            RecordsScreen(records + outsideMonth, YearMonth.of(2026, 10), null,
                RecordsActions(openResult = {}, openRecord = {}, monthChanged = { changed = it }))
        }
        compose.onNodeWithText("어깨전문").performTouchInput { longClick() }
        compose.onNodeWithContentDescription("이전 달").performClick()
        compose.onNodeWithText("9월 기록").assertExists()
        compose.onNodeWithText("0개 선택됨").assertExists()
        compose.onNodeWithText("삭제").assertIsNotEnabled()
        compose.onNodeWithTag("select-all").performClick()
        compose.onNodeWithTag("record-outside").assertIsSelected()
        compose.onNodeWithTag("records-calendar").performTouchInput { swipeLeft() }
        compose.onNodeWithText("10월 기록").assertExists()
        assertEquals(YearMonth.of(2026, 10), changed)
        compose.onNodeWithTag("records-calendar").performTouchInput { swipeRight() }
        compose.onNodeWithText("9월 기록").assertExists()
        assertEquals(YearMonth.of(2026, 9), changed)
    }

    @Test
    fun resultExportOpensFormatsAndPhotoEntry() {
        compose.setContent {
            WorkoutResultScreen(
                ResultUi("가슴·삼두", "81분 · 26세트 · 세션 00000000", emptyList(), "센서 추정"),
                back = {}, toRecords = {},
            )
        }
        compose.onNodeWithText("내보내기").performClick()
        compose.onNodeWithText("요약형").assertExists()
        compose.onNodeWithText("상세형").assertExists()
        compose.onNodeWithText("공유").assertExists()
        compose.onNodeWithText("사진에 저장").assertExists()
        compose.onNodeWithText("사진 찍어 공유").assertExists()
    }
}
