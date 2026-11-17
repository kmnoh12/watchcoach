package dev.kyungmin.watchcoach.phone.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.*
import androidx.compose.foundation.layout.Box
import androidx.compose.ui.Modifier
import androidx.compose.runtime.*
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import dev.kyungmin.watchcoach.phone.SetAnalysisUi
import dev.kyungmin.watchcoach.phone.resultMetricRows
import dev.kyungmin.watchcoach.phone.ANALYSIS_ESTIMATE_NOTE
import dev.kyungmin.watchcoach.phone.WorkoutData
import dev.kyungmin.watchcoach.phone.WorkoutRecord
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Eight window sizes, real screen entry points and scroll reachability without a device. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
abstract class ScreenSizeMatrixBase {
    @get:Rule
    val compose = createComposeRule()

    private fun output(name: String): String {
        val config = org.robolectric.RuntimeEnvironment.getApplication().resources.configuration
        val size = "${config.screenWidthDp}x${config.screenHeightDp}"
        val phase = if (System.getenv("SCREEN_CAPTURE_PHASE") == "before") "before/" else ""
        return "build/outputs/roborazzi/screens/$size/$phase$name.png"
    }

    private fun shot(name: String, content: @androidx.compose.runtime.Composable () -> Unit) {
        var withTabs by mutableStateOf(false)
        val tab = when (name) { "home" -> 0; "records" -> 1; "stats" -> 2; "menu" -> 4; else -> null }
        compose.setContent {
            Box(Modifier.fillMaxSize().background(KColors.Bg)) {
                Box(Modifier.fillMaxSize().padding(bottom = if (withTabs && tab != 2) 86.dp else 0.dp)) { content() }
                if (withTabs && tab != null) Box(Modifier.align(androidx.compose.ui.Alignment.BottomCenter)) {
                    FloatingTabBar(tab, true) {}
                }
            }
        }
        compose.onRoot().captureRoboImage(output(name))
        if (tab != null) {
            compose.runOnIdle { withTabs = true }
            compose.onNodeWithTag("nav-item-$tab", useUnmergedTree = true).assertIsDisplayed()
            compose.onRoot().captureRoboImage(output("${name}_with_tabs"))
        }
    }

    @Test
    fun home() {
        val routines = WorkoutData.defaultRoutines()
        val rows = routines.mapIndexed { i, r -> RoutineRowUi2(r, if (i == 0) null else i * 3) }
        val ui = HomeUi(
            week = listOf(
                WeekDayUi("월", 0.8, false, false), WeekDayUi("화", null, false, false),
                WeekDayUi("수", 0.5, false, false), WeekDayUi("목", null, true, false),
                WeekDayUi("금", null, false, true), WeekDayUi("토", null, false, true), WeekDayUi("일", null, false, true),
            ),
            weekCount = 2, rows = rows, longestRest = rows.lastOrNull(),
        )
        val actions = HomeActions({}, {}, {}, {}, {}, {}, {}, {})
        shot("home") { HomeScreen(ui, null, actions) }
    }

    @Test
    fun stats() = shot("stats") {
        StatsScreen(
            StatsUi(
                monthLabel = "10월",
                workouts = listOf(dev.kyungmin.watchcoach.core.WorkoutLog(java.time.LocalDate.now().toEpochDay(), "등·이두", 60, 20, 4080)),
                history = listOf(dev.kyungmin.watchcoach.core.ExerciseLog("bench", java.time.LocalDate.now().toEpochDay(),
                    List(12) { dev.kyungmin.watchcoach.core.LoggedSet(50.0, 10) }, startedAtMs = java.time.LocalDate.now().atTime(11, 0).atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli())),
                bodies = mapOf("bench" to "가슴"),
                weights = mapOf("bench" to mapOf("가슴" to 1.0, "전면어깨" to 0.5)),
                names = mapOf("bench" to "벤치프레스"),
            ),
        )
    }





    @Test
    fun records() {
        val month = java.time.YearMonth.now()
        val records = listOf(
            WorkoutRecord("${month}-03", "어깨전문", 74, 24, 9120),
            WorkoutRecord("${month}-05", "등·이두", 68, 22, 7840),
            WorkoutRecord("${month}-09", "가슴·삼두", 81, 26, 10450),
        )
        shot("records") { RecordsScreen(records, month, "가슴·삼두", RecordsActions({}, {}, {})) }
    }

    @Test
    fun library() = shot("library") {
        val context = androidx.compose.ui.platform.LocalContext.current
        val entries = WorkoutData.catalog.map { item ->
            val (order, title) = dev.kyungmin.watchcoach.core.ExerciseTaxonomy.section(item.bodyCategory, item.pattern)
            LibraryEntry(item, order, title, dev.kyungmin.watchcoach.core.ExerciseTaxonomy.bodyRank(item.bodyCategory))
        }
        LibraryScreen(entries, setOf("pull_up", "lat_pull_down"), LibraryActions({}, {}, {}), FavoriteUi(setOf("machine_fly", "dumbbell_pullover")) {}) { android.view.View(context) }
    }



    @Test
    fun result() = shot("result") {
        WorkoutResultScreen(
            ResultUi(
                "등·이두", "68분 · 22세트 · 세션 12345678",
                listOf(ResultSectionUi("랫풀다운 · 세트 1", SetAnalysisUi("lat_pull_down", "랫풀다운", 0, 10, 10, 10, 0.87).resultMetricRows(),
                    listOf(2.9, 3.0, 2.8, 2.6, 2.9, 3.1, 3.3, 3.4, 3.6, 3.5))),
                ANALYSIS_ESTIMATE_NOTE,
                listOf(
                    RecordUi("랫풀다운", RecordTier.MAX_WEIGHT, "62.5kg", "이전 60kg · +2.5kg", value = 62.5, previous = 60.0),
                    RecordUi("시티드 로우", RecordTier.REPS, "50kg 12회", "이 무게 최고 횟수 · 이전 10회", reps = 12, previousReps = 10),
                    RecordUi("덤벨 컬", RecordTier.ESTIMATE, "추정 1RM 24 → 25kg", ""),
                ),
            ),
            {}, {},
        )
    }



    @Test
    fun routineDetail() = shot("routine_detail") {
        val context = androidx.compose.ui.platform.LocalContext.current
        val routine = WorkoutData.defaultRoutines()[1]
        val rows = routine.exercises.mapIndexed { i, item ->
            RoutineRowUi(i, item.exercise.name, "${item.sets.size}세트 · ${item.exercise.muscles}", { android.view.View(context) })
        }
        RoutineDetailScreen(
            routine.name, rows, "시작", KIcon.Play, false,
            RoutineDetailActions({}, {}, {}, {}, { _, _ -> }, {}, {}, {}),
        )
    }

    private fun noActions(): WorkoutActions = java.lang.reflect.Proxy.newProxyInstance(
        WorkoutActions::class.java.classLoader, arrayOf(WorkoutActions::class.java),
    ) { proxy, method, args ->
        when (method.name) {
            "equals" -> proxy === args?.get(0)
            "hashCode" -> System.identityHashCode(proxy)
            "toString" -> "NoActions"
            "onEditFinished" -> true
            else -> null
        }
    } as WorkoutActions

    private fun workoutModel(resting: Boolean): WorkoutUiModel {
        val now = System.currentTimeMillis()
        fun set(uid: Int, label: String, kg: String, reps: Int, done: Boolean, prev: String?) =
            SetUi(uid, label, kg, reps, done, label == "노멀" && false, "", 90, false, null, prev)
        val sets = listOf(
            set(0, "1", "50", 10, true, "45×10"),
            set(1, "2", "55", 10, true, "50×10"),
            set(2, "3", "55", 10, false, "50×9"),
            set(3, "4", "55", 8, false, null),
        )
        val ex = ExerciseUi(
            "lat_pull_down", "랫풀다운", "등, 이두", true, 90, 10, 20, 2, 4, 2, sets,
            volumeDone = 1050, volumeTarget = 2100,
            history = HistoryUi("지난번 45×10 · 50×10 · 50×9", 1840, "55kg로 올리기", "모든 작업 세트를 목표 횟수까지 채웠습니다", true),
        )
        return WorkoutUiModel(
            "등·이두", false, false, now - 21 * 60_000L, 0L, 0L, 0, listOf(ex),
            if (resting) now - 20_000L else 0L, if (resting) now + 70_000L else 0L, 0L, "다음 랫풀다운 3세트",
            restingSet = if (resting) 0 to 1 else null,
        )
    }

    @Test
    fun workout() = shot("workout") {
        val context = androidx.compose.ui.platform.LocalContext.current
        ActiveWorkoutScreen(
            workoutModel(false), noActions(),
            LiveLine("Watch8 연결됨 · 랫풀다운 · 세트 3", "t").also { it.setTextColor(0xFF63D6DE.toInt()) },
            LiveLine("7/10회 · 55kg · 심박 112bpm", "t"),
        ) { android.view.View(context) }
    }

    @Test
    fun workoutResting() = shot("workout_rest") {
        val context = androidx.compose.ui.platform.LocalContext.current
        ActiveWorkoutScreen(
            workoutModel(true), noActions(),
            LiveLine("Watch8 연결됨", "t"), LiveLine("휴식 중 · 10/10회 · 심박 98bpm", "t"),
        ) { android.view.View(context) }
    }

    private fun overlayShot(name: String, sheet: Boolean, content: @androidx.compose.runtime.Composable (() -> Unit) -> Unit) {
        val state = OverlayState()
        compose.setContent {
            androidx.compose.foundation.layout.Box(androidx.compose.ui.Modifier.fillMaxSize().background(KColors.Bg)) {
                OverlayHost(state)
            }
        }
        compose.runOnUiThread { state.show(Overlay(sheet) { dismiss -> content(dismiss) }) }
        compose.waitForIdle()
        compose.onRoot().captureRoboImage(output(name))
    }





    @Test
    fun dialogConfirm() = overlayShot("dialog_confirm", false) { dismiss ->
        ConfirmDialog("운동을 종료할까요?", "지금까지의 기록은 저장되지 않습니다.", "계속 운동", "종료", dismiss) {}
    }

    @Test
    fun sheetSet() = overlayShot("sheet_set", true) {
        fun seg(vararg labels: String, selected: Int) = labels.mapIndexed { i, l -> SegOption(l, i == selected) {} }
        SetSheet(
            "1세트", "케이블 익스터널 로테이션 · 25회",
            listOf(
                SegGroup("세트 종류", seg("일반", "웜업", "슈퍼", "드랍", "실패", "보조", selected = 1), "근육을 준비하기 위한 워밍업"),
                SegGroup("그립", seg("노멀", "오버", "언더", "뉴트럴", "더보기", selected = 0), "표준 그립"),
                SegGroup("운동 강도 (RPE)", seg("-", "6", "7", "8", "9", "10", "상세", selected = 4), "확실히 1개 더 가능"),
            ),
            listOf(SheetAction("다음 세트로 복제", false) {}, SheetAction("세트 삭제", true) {}),
        )
    }






    @Test
    fun settings() = shot("settings") { SettingsScreen(SettingsActions({})) }

    @Test
    fun bottomTabs() = shot("bottom_tabs") {
        androidx.compose.foundation.layout.Box(androidx.compose.ui.Modifier.fillMaxSize().background(KColors.Bg), contentAlignment = androidx.compose.ui.Alignment.BottomCenter) {
            FloatingTabBar(0, true) {}
        }
    }

    @Test
    fun expandedRest() {
        shot("expanded_rest") {
            ExpandedRestPanel(RestClock(true, false, 70000, 90000), 90, false, {}, {}, {}, {}, {})
        }
        if (System.getenv("SCREEN_CAPTURE_PHASE") != "before") {
            compose.onNode(SemanticsMatcher.keyIsDefined(androidx.compose.ui.semantics.SemanticsProperties.VerticalScrollAxisRange))
                .performScrollToNode(hasText("0:30"))
            compose.onNodeWithText("0:30").assertIsDisplayed()
            compose.onRoot().captureRoboImage(output("expanded_rest_scrolled"))
        }
    }

    @Test
    fun menu() = shot("menu") { MenuScreen("0.2.40", MenuActions({}, { null }, {})) }

    @Test
    fun savedResult() {
        val context = org.robolectric.RuntimeEnvironment.getApplication()
        val sets = (0..2).flatMap { exercise -> (0..3).map { index ->
            dev.kyungmin.watchcoach.core.PlannedSetSnapshot(exercise, "exercise-$exercise", index, 10, 50.0, true,
                exerciseName = listOf("랫풀다운", "시티드 로우", "덤벨 컬")[exercise], performedReps = 10,
                repSource = dev.kyungmin.watchcoach.core.SetRepSource.MANUAL)
        } }
        val snapshot = dev.kyungmin.watchcoach.core.WorkoutSnapshot(
            sessionId = "size-matrix", routineId = "back", exerciseIndex = 2, setIndex = 3,
            plannedSets = sets, performedReps = emptyMap(), phase = dev.kyungmin.watchcoach.core.WorkoutPhase.WORKING,
            restEndAtMs = 0, pausedRestRemainingMs = 0, paused = false,
            startedAtMs = 1794394800000L, pausedSinceMs = 0, totalPausedMs = 0, lastSequence = 0,
            lastCompletedSetKey = null, captureStates = emptyMap())
        dev.kyungmin.watchcoach.phone.FinishedWorkoutStore(context).finish(snapshot, "등·이두", 62)
        shot("result_saved") {
            WorkoutResultScreen(ResultUi("등·이두", "62분 · 12세트", emptyList(), "", sessionId = "size-matrix"), {}, {})
        }
        compose.waitUntil(10000) { compose.onAllNodesWithText("운동 기록 불러오기 실패").fetchSemanticsNodes().isEmpty() &&
            compose.onAllNodesWithText("6,000", substring = true).fetchSemanticsNodes().isNotEmpty() }
        compose.onRoot().captureRoboImage(output("result_saved"))
    }

    @Test
    fun keypad() {
        shot("workout_keypad_initial") {
            val context = androidx.compose.ui.platform.LocalContext.current
            ActiveWorkoutScreen(workoutModel(false), noActions(), LiveLine("Watch8 연결됨", "t"), LiveLine("7/10회", "t")) { android.view.View(context) }
        }
        if (System.getenv("SCREEN_CAPTURE_PHASE") == "before") return
        compose.onNodeWithTag("setRow-3").performScrollTo().performTouchInput {
            click(androidx.compose.ui.geometry.Offset(width * 0.32f, height / 2f))
        }
        compose.onNodeWithTag("setValueHero").assertExists()
        compose.onRoot().captureRoboImage(output("workout_keypad"))
        if (System.getenv("SCREEN_CAPTURE_PHASE") != "before") {
            // The landscape side panel fits without scrolling; portrait sheets may need a scroll on small windows.
            val close = compose.onNodeWithText("닫기")
            try { close.performScrollTo() } catch (_: AssertionError) { }
            close.assertIsDisplayed().performClick()
            compose.onNodeWithTag("setValueHero").assertDoesNotExist()
        }
    }
}

@Config(sdk = [34], qualifiers = "w320dp-h640dp-xxhdpi")
class ScreenSize320x640Test : ScreenSizeMatrixBase()

@Config(sdk = [34], qualifiers = "w360dp-h800dp-xxhdpi")
class ScreenSize360x800Test : ScreenSizeMatrixBase()

@Config(sdk = [34], qualifiers = "w412dp-h915dp-xxhdpi")
class ScreenSize412x915Test : ScreenSizeMatrixBase()

@Config(sdk = [34], qualifiers = "w800dp-h360dp-land-xxhdpi")
class ScreenSize800x360Test : ScreenSizeMatrixBase()

@Config(sdk = [34], qualifiers = "w280dp-h653dp-xxhdpi")
class ScreenSize280x653Test : ScreenSizeMatrixBase()

@Config(sdk = [34], qualifiers = "w673dp-h841dp-xxhdpi")
class ScreenSize673x841Test : ScreenSizeMatrixBase()

@Config(sdk = [34], qualifiers = "w800dp-h1280dp-xxhdpi")
class ScreenSize800x1280Test : ScreenSizeMatrixBase()

@Config(sdk = [34], qualifiers = "w1280dp-h800dp-land-xxhdpi")
class ScreenSize1280x800Test : ScreenSizeMatrixBase()
