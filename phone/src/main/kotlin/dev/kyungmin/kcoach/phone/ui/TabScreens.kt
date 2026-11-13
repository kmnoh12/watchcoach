package dev.kyungmin.kcoach.phone.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.kyungmin.kcoach.phone.WorkoutRecord
import dev.kyungmin.kcoach.updates.OtaAction
import dev.kyungmin.kcoach.updates.OtaCard
import dev.kyungmin.kcoach.updates.OtaMessages
import dev.kyungmin.kcoach.updates.OtaNotice
import dev.kyungmin.kcoach.updates.OtaRow
import dev.kyungmin.kcoach.updates.OtaRowKind
import java.time.LocalDate
import java.time.YearMonth

@Composable
private fun TabPage(title: String, right: String, rightIcon: KIcon? = null, rightAction: (() -> Unit)? = null, content: @Composable () -> Unit) {
    Column(
        Modifier
            .fillMaxSize()
            .background(KColors.Bg)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 20.dp),
    ) {
        Row(Modifier.fillMaxWidth().heightIn(min = 52.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(title, color = KColors.White, fontSize = 32.sp, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
            if (right.isNotEmpty()) Text(right, color = KColors.Muted, fontSize = 14.sp)
            if (rightIcon != null) {
                if (rightAction == null) KIcon(rightIcon, KColors.Muted, Modifier.padding(start = 4.dp), 22.dp)
                else Box(Modifier.size(48.dp).clip(KShape.Control).semantics { contentDescription = "설정" }
                    .tapClickable(rightAction), contentAlignment = Alignment.Center) { KIcon(rightIcon, KColors.White, size = 24.dp) }
            }
        }
        content()
    }
}

@Composable
fun SectionCard(title: String, values: List<Pair<String, String>>, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth()) {
        Text(title, color = KColors.Muted, fontSize = 13.sp, modifier = Modifier.padding(bottom = 6.dp))
        HairlineRule()
        values.forEach { (name, value) ->
            Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(name, color = KColors.Soft, fontSize = 15.sp, modifier = Modifier.weight(1f))
                Text(value, color = KColors.White, fontSize = 15.sp, fontWeight = FontWeight.Medium)
            }
            HairlineRule()
        }
    }
}

@Composable
private fun HairlineRule() {
    Box(Modifier.fillMaxWidth().height(0.5.dp).background(KColors.Hairline))
}

@Composable
fun MetricGrid(metrics: List<Pair<String, String>>) {
    metrics.chunked(2).forEachIndexed { index, pair ->
        if (index > 0) HairlineRule()
        Row(Modifier.fillMaxWidth().padding(vertical = 16.dp)) {
            pair.forEach { (value, title) ->
                Column(Modifier.weight(1f)) {
                    Text(value, color = KColors.White, fontSize = 30.sp, fontWeight = FontWeight.Medium, letterSpacing = (-0.5).sp)
                    Spacer(Modifier.height(2.dp))
                    Text(title, color = KColors.Muted, fontSize = 12.sp)
                }
            }
        }
    }
}

class RecordsActions(
    val openResult: () -> Unit,
    val openRecord: (WorkoutRecord) -> Unit,
    val monthChanged: (YearMonth) -> Unit,
    /** The three-dot menu of a record row: start from it, edit it, delete it. */
    val recordMenu: (WorkoutRecord) -> Unit = {},
    /** Delete the chosen rows after a confirmation; the flag is true when the user asked for every record of every month. */
    val deleteRecords: (List<WorkoutRecord>, Boolean) -> Unit = { _, _ -> },
)

@Composable
fun RecordsScreen(
    records: List<WorkoutRecord>,
    initialMonth: YearMonth,
    lastResultTitle: String?,
    actions: RecordsActions,
) {
    var month by remember { mutableStateOf(initialMonth) }
    var selecting by remember { mutableStateOf(false) }
    // A selection belongs to the visible month and never includes hidden rows.
    var selected by remember(month, records) { mutableStateOf<Set<WorkoutRecord>>(emptySet()) }
    val monthRecords = records.filter { it.date.startsWith(month.toString()) }
    androidx.activity.compose.BackHandler(selecting) { selecting = false; selected = emptySet() }
    Column(Modifier.fillMaxSize().background(KColors.Bg)
        .verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        Row(Modifier.fillMaxWidth().height(76.dp).padding(top = 14.dp).testTag("records-header"),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (selecting) {
                val allChosen = monthRecords.isNotEmpty() && selected.containsAll(monthRecords)
                val tick = rememberTapHaptic()
                Column(Modifier.width(40.dp).testTag("select-all")
                    .semantics { this.selected = allChosen }
                    .clickable { tick(); selected = if (allChosen) emptySet() else monthRecords.toSet() },
                    horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    RecordSelectionCircle(allChosen)
                    Text("전체", color = KColors.Soft, fontSize = 11.5.sp, fontWeight = FontWeight.Medium)
                }
                Text(androidx.compose.ui.text.buildAnnotatedString {
                    withStyle(androidx.compose.ui.text.SpanStyle(color = KColors.Accent, fontWeight = FontWeight.Medium)) { append("${selected.size}") }
                    append("개 선택됨")
                }, color = KColors.White, fontSize = 21.sp, fontWeight = FontWeight.Bold,
                    letterSpacing = (-0.4).sp, maxLines = 1, style = RecordNumerals, modifier = Modifier.weight(1f))
                Box(Modifier.height(40.dp).clickable { tick(); selecting = false; selected = emptySet() }
                    .padding(horizontal = 4.dp), contentAlignment = Alignment.Center) {
                    Text("취소", color = KColors.Soft, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                }
                val canDelete = selected.isNotEmpty()
                Row(Modifier.height(40.dp).clip(RoundedCornerShape(10.dp))
                    .background(KColors.DangerFill.copy(alpha = if (canDelete) 1f else 0.3f))
                    .clickable(enabled = canDelete) { tick(); actions.deleteRecords(selected.toList(), false) }
                    .padding(horizontal = 11.dp), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    val ink = Color(0xFF2A0B08).copy(alpha = if (canDelete) 1f else 0.5f)
                    KIcon(KIcon.Trash, ink, size = 18.dp)
                    Text("삭제", color = ink, fontSize = 15.sp, fontWeight = FontWeight.Bold)
                }
            } else {
                Text("운동 기록", color = KColors.White, fontSize = 28.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.6).sp)
            }
        }
        val swipeStep = with(androidx.compose.ui.platform.LocalDensity.current) { 56.dp.toPx() }
        Column(Modifier.fillMaxWidth().testTag("records-calendar")
            .clip(RoundedCornerShape(14.dp)).background(KColors.Surface)
            .pointerInput(Unit) {
                var drag = 0f
                detectHorizontalDragGestures(
                    onDragStart = { drag = 0f }, onDragCancel = { drag = 0f },
                    onDragEnd = {
                        if (drag <= -swipeStep) { month = month.plusMonths(1); actions.monthChanged(month) }
                        else if (drag >= swipeStep) { month = month.minusMonths(1); actions.monthChanged(month) }
                        drag = 0f
                    },
                ) { _, delta -> drag += delta }
            }.padding(start = 10.dp, end = 10.dp, top = 10.dp, bottom = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                MonthArrow(KIcon.Back) { month = month.minusMonths(1); actions.monthChanged(month) }
                AnimatedContent(targetState = month, modifier = Modifier.weight(1f),
                    transitionSpec = {
                        fadeIn(tween(Motion.UI_MS / 2, delayMillis = Motion.UI_MS / 2, easing = Motion.UiEasing)) togetherWith
                            fadeOut(tween(Motion.UI_MS / 2, easing = Motion.UiEasing))
                    }, label = "month") { m ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp, Alignment.CenterHorizontally),
                        verticalAlignment = Alignment.Bottom) {
                        Text("${m.year}년", color = KColors.Muted, fontSize = 13.sp, fontWeight = FontWeight.Medium,
                            style = RecordNumerals, modifier = Modifier.alignByBaseline())
                        Text("${m.monthValue}월", color = KColors.White, fontSize = 17.sp, fontWeight = FontWeight.Bold,
                            modifier = Modifier.alignByBaseline())
                    }
                }
                MonthArrow(KIcon.Forward) { month = month.plusMonths(1); actions.monthChanged(month) }
            }
            Spacer(Modifier.height(4.dp))
            AnimatedContent(targetState = month, transitionSpec = {
                val dir = if (targetState > initialState) 1 else -1
                (slideInHorizontally(tween(Motion.UI_MS, easing = Motion.UiEasing)) { it / 3 * dir } +
                    fadeIn(tween(Motion.UI_MS, easing = Motion.UiEasing))) togetherWith
                    (slideOutHorizontally(tween(Motion.UI_MS, easing = Motion.UiEasing)) { -it / 3 * dir } +
                        fadeOut(tween(Motion.UI_MS / 2, easing = Motion.UiEasing)))
            }, label = "calendar") { m -> CalendarGrid(m, records) }
        }
        Row(Modifier.padding(start = 2.dp, top = 24.dp, bottom = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("${month.monthValue}월 기록", color = KColors.White, fontSize = 16.sp, fontWeight = FontWeight.Bold)
            Text("·", color = KColors.Faint)
            Text("${monthRecords.size}회", color = KColors.Soft, fontSize = 14.sp, fontWeight = FontWeight.Medium, style = RecordNumerals)
        }
        if (monthRecords.isEmpty()) {
            Text(if (records.isEmpty()) "아직 기록 없음" else "이 달 기록 없음", color = KColors.Muted, fontSize = 14.sp, modifier = Modifier.padding(vertical = 18.dp))
        }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            monthRecords.forEach { record ->
                RecordCard(record, selecting, record in selected, onMenu = { actions.recordMenu(record) },
                    onLongClick = { selecting = true; selected = selected + record }) {
                    if (selecting) selected = if (record in selected) selected - record else selected + record
                    else actions.openRecord(record)
                }
            }
        }
        Spacer(Modifier.height(100.dp))
    }
}

// Local to records: these shades and tabular numerals are not new global theme tokens.
private val RecordDay = Color(0xFF979BA0)
private val RecordWash = Color(0xFF0E3A40)
private val RecordWash2 = Color(0xFF0B2A2D)
private val RecordAccent2 = Color(0xFF7FB9BE)
private val RecordNumerals = androidx.compose.ui.text.TextStyle(fontFeatureSettings = "tnum")

@Composable
private fun RecordSelectionCircle(checked: Boolean) {
    Box(Modifier.size(26.dp).clip(CircleShape)
        .background(if (checked) KColors.Accent else Color.Transparent)
        .border(2.dp, if (checked) KColors.Accent else KColors.Muted, CircleShape), contentAlignment = Alignment.Center) {
        if (checked) KIcon(KIcon.Check, KColors.OnAccent, size = 15.dp)
    }
}

@Composable
private fun MonthArrow(icon: KIcon, onClick: () -> Unit) {
    Box(Modifier.size(32.dp).clip(RoundedCornerShape(8.dp)).background(KColors.SurfaceRaised)
        .semantics { contentDescription = if (icon == KIcon.Back) "이전 달" else "다음 달" }
        .pressable(onClick), contentAlignment = Alignment.Center) {
        KIcon(icon, KColors.Soft, size = 17.dp)
    }
}

@Composable
private fun CalendarGrid(month: YearMonth, records: List<WorkoutRecord>) {
    val recorded = records.filter { it.date.startsWith(month.toString()) }.map { LocalDate.parse(it.date).dayOfMonth }.toSet()
    val today = LocalDate.now()
    val cells: List<Int?> = List(month.atDay(1).dayOfWeek.value % 7) { null } + (1..month.lengthOfMonth()).toList()
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(Modifier.fillMaxWidth()) {
            listOf("일", "월", "화", "수", "목", "금", "토").forEach {
                Text(it, color = KColors.Muted, fontSize = 11.sp, fontWeight = FontWeight.Medium,
                    textAlign = TextAlign.Center, modifier = Modifier.weight(1f).padding(top = 6.dp, bottom = 5.dp))
            }
        }
        cells.chunked(7).forEach { week ->
            Row(Modifier.fillMaxWidth()) {
                for (i in 0 until 7) {
                    val day = week.getOrNull(i)
                    Box(Modifier.weight(1f).height(34.dp), contentAlignment = Alignment.Center) {
                        if (day != null) {
                            val has = day in recorded
                            val shape = RoundedCornerShape(8.dp)
                            Box(Modifier.size(32.dp, 30.dp).clip(shape).background(if (has) RecordWash else Color.Transparent)
                                .then(if (month.atDay(day) == today) Modifier.border(1.5.dp, KColors.Bone, shape) else Modifier),
                                contentAlignment = Alignment.Center) {
                                Text(day.toString(), color = if (has) KColors.Accent else RecordDay, fontSize = 14.sp,
                                    fontWeight = if (has) FontWeight.Bold else FontWeight.Normal, style = RecordNumerals)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun RecordCard(record: WorkoutRecord, selecting: Boolean, checked: Boolean, onMenu: () -> Unit, onLongClick: () -> Unit, onClick: () -> Unit) {
    val date = LocalDate.parse(record.date)
    val shape = RoundedCornerShape(14.dp)
    Row(Modifier.fillMaxWidth().testTag("record-${record.sessionId ?: record.date}")
        .semantics { if (selecting) this.selected = checked }
        .clip(shape).background(if (checked) KColors.Selected else KColors.Surface)
        // Border draws inside the existing bounds; selection never changes row size.
        .border(1.5.dp, if (checked) KColors.Accent else Color.Transparent, shape)
        .pressableLong(onLongClick, onClick)
        .padding(start = 12.dp, end = if (selecting) 14.dp else 6.dp, top = 12.dp, bottom = 12.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        if (selecting) RecordSelectionCircle(checked)
        Column(Modifier.size(48.dp, 52.dp).clip(RoundedCornerShape(10.dp)).background(RecordWash2),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Text("${date.dayOfMonth}", color = KColors.Accent, fontSize = 20.sp, fontWeight = FontWeight.Medium, style = RecordNumerals)
            Text(listOf("월", "화", "수", "목", "금", "토", "일")[date.dayOfWeek.value - 1],
                color = RecordAccent2, fontSize = 11.sp, fontWeight = FontWeight.Medium)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(record.title, color = KColors.White, fontSize = 16.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.3).sp,
                maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
            Text("${record.minutes}분 · ${record.sets}세트", color = KColors.Soft, fontSize = 13.sp, maxLines = 1, style = RecordNumerals)
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(androidx.compose.ui.text.buildAnnotatedString {
                append("%,d".format(java.util.Locale.US, record.volumeKg))
                withStyle(androidx.compose.ui.text.SpanStyle(color = KColors.Muted, fontSize = 12.sp, fontWeight = FontWeight.Normal)) { append(" kg") }
            }, color = KColors.White, fontSize = 17.sp, fontWeight = FontWeight.Medium, letterSpacing = (-0.2).sp, style = RecordNumerals)
            Text("볼륨", color = KColors.Muted, fontSize = 12.sp)
        }
        if (!selecting) Box(Modifier.size(30.dp, 40.dp).semantics { contentDescription = "${record.title} 메뉴" }.pressable(onMenu),
            contentAlignment = Alignment.Center) { KIcon(KIcon.Dots, KColors.Muted, size = 20.dp) }
    }
}

class StatsUi(
    val monthLabel: String,
    val workouts: List<dev.kyungmin.kcoach.core.WorkoutLog> = emptyList(),
    val history: List<dev.kyungmin.kcoach.core.ExerciseLog> = emptyList(),
    val bodies: Map<String, String> = emptyMap(),
    val weights: Map<String, Map<String, Double>> = emptyMap(),
    val names: Map<String, String> = emptyMap(),
    val nowMs: Long = System.currentTimeMillis(),
    /** The body figure view. The app hands in one kept view so switching tabs quickly never builds and destroys a WebView each time. */
    val figure: (android.content.Context) -> dev.kyungmin.kcoach.phone.Exercise3DView = { dev.kyungmin.kcoach.phone.Exercise3DView(it, "", "human_stats.html", android.graphics.Color.BLACK) },
)

@Composable
fun StatsScreen(ui: StatsUi) {
    val today = remember(ui) { java.time.Instant.ofEpochMilli(ui.nowMs).atZone(java.time.ZoneId.systemDefault()).toLocalDate().toEpochDay() }
    var radarDays by remember { mutableStateOf(7) }
    var cumulativeDays by remember { mutableStateOf(0) }
    val week = remember(ui, today) { dev.kyungmin.kcoach.core.StatsAnalytics.weekVolumes(ui.workouts, today) }
    val lastWeek = remember(ui, today) { dev.kyungmin.kcoach.core.StatsAnalytics.weekVolumes(ui.workouts, today, true) }
    val current = remember(ui, today, radarDays) {
        dev.kyungmin.kcoach.core.StatsAnalytics.volumeByGroup(ui.history, ui.bodies::get, ui.weights::get, today, radarDays)
    }
    val previous = remember(ui, today, radarDays) {
        dev.kyungmin.kcoach.core.StatsAnalytics.volumeByGroup(ui.history, ui.bodies::get, ui.weights::get, today, radarDays, true)
    }
    val records = remember(ui) { dev.kyungmin.kcoach.core.StatsAnalytics.records(ui.history, ui.nowMs) }
    val selected = remember(ui, today, cumulativeDays) {
        ui.workouts.filter { dev.kyungmin.kcoach.core.StatsAnalytics.inPeriod(it.epochDay, today, cumulativeDays) }
    }
    TabPage("통계", ui.monthLabel) {
        StatsHeading("근육 피로도")
        StatsFatigue(ui)
        StatsHeading("이번 주 볼륨")
        StatsWeekSummary(week, lastWeek)
        StatsWeekChart(week, lastWeek)
        StatsLegend("이번 주", "지난주")
        StatsHeading("부위별 볼륨", radarDays, { radarDays = it })
        StatsRadarChart(current, previous, radarDays != 0)
        StatsLegend(if (radarDays == 0) "전체 기간" else "이번 기간", if (radarDays == 0) null else "직전 기간")
        StatsHeading("새 기록")
        StatsRecords(records, ui.names, today)
        StatsHeading("누적 기록", cumulativeDays, { cumulativeDays = it })
        MetricGrid(listOf(
            "${statsNumber(selected.size.toDouble())}회" to "운동",
            "${statsNumber(selected.sumOf { it.minutes.toLong() }.toDouble())}분" to "총 시간",
            "${statsNumber(selected.sumOf { it.sets.toLong() }.toDouble())}세트" to "총 세트",
            "${statsNumber(selected.sumOf { it.volumeKg.toLong() }.toDouble())}kg" to "총 볼륨",
        ))
        HairlineRule()
        StatsHeading("루틴별 세트", trailing = if (cumulativeDays == 0) "전체" else "최근 ${cumulativeDays}일")
        dev.kyungmin.kcoach.core.WorkoutStats.byTitle(selected).forEach { (title, sets) ->
            Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(title, color = KColors.Soft, fontSize = 15.sp, modifier = Modifier.weight(1f))
                Text("${statsNumber(sets.toDouble())}세트", color = KColors.White, fontSize = 15.sp, fontWeight = FontWeight.Medium)
            }
            HairlineRule()
        }
        Spacer(Modifier.height(94.dp))
    }
}

class UpdateUi(val message: String, val readyToInstall: Boolean, val busy: Boolean = false, val card: OtaCard? = null) {
    /** The card to draw; a plain message (before the first check, or from older callers) becomes a card of the same shape. */
    fun asCard(): OtaCard = card ?: OtaCard(
        headline = message,
        phone = OtaRow("폰", if (busy) "확인 중" else "확인 전", if (busy) OtaRowKind.WORKING else OtaRowKind.IDLE),
        watch = OtaRow("워치", if (busy) "확인 중" else "확인 전", if (busy) OtaRowKind.WORKING else OtaRowKind.IDLE),
        action = if (busy) OtaAction.WORKING else if (readyToInstall) OtaAction.INSTALL else OtaAction.CHECK,
        actionLabel = if (busy) "확인 중" else if (readyToInstall) "설치" else "업데이트 확인")
}

class MenuActions(
    val checkUpdate: ((UpdateUi) -> Unit) -> Unit,
    val install: () -> String?,
    val openSettings: () -> Unit = {},
    val observeUpdate: (((UpdateUi) -> Unit) -> (() -> Unit))? = null,
)

@Composable
fun MenuScreen(version: String, actions: MenuActions, wearing: dev.kyungmin.kcoach.phone.WorkoutWearingSelection? = null, notice: OtaNotice? = null,
    onNoticeShown: () -> Unit = {}) {
    var state by remember { mutableStateOf(UpdateUi("최신 버전 확인", false)) }
    DisposableEffect(actions.observeUpdate) {
        val unsubscribe = actions.observeUpdate?.invoke { state = it }
        onDispose { unsubscribe?.invoke() }
    }
    TabPage("메뉴", "", KIcon.Settings, actions.openSettings) {
        Spacer(Modifier.height(20.dp))
        UpdatedBanner(notice, onNoticeShown)
        MenuTipBox()
        Spacer(Modifier.height(28.dp))
        SectionCard("기기", listOf(
            "확인한 착용 손" to when (wearing?.side) { "LEFT" -> "왼손"; "RIGHT" -> "오른손"; else -> "미확인" },
            "확인한 화면 방향" to when (wearing?.placement) { "OUTSIDE" -> "손등 쪽"; "INSIDE" -> "손바닥 쪽"; else -> "미확인" }))
        Spacer(Modifier.height(28.dp))
        SectionCard("앱", listOf("현재 버전" to version))
        Spacer(Modifier.height(28.dp))
        val card = state.asCard()
        UpdateCard(card) {
            when (card.action) {
                OtaAction.WORKING -> Unit
                OtaAction.INSTALL -> {
                    // The button answers at once; the coordinator's own states replace this a moment later.
                    state = UpdateUi(card.headline, true, true, card.copy(headline = "업데이트하는 중", action = OtaAction.WORKING, actionLabel = "설치 중"))
                    val refusal = actions.install()
                    if (refusal == OtaMessages.NOTHING_TO_INSTALL || refusal == OtaMessages.CHECK_FIRST)
                        state = UpdateUi(refusal, false, false, card.copy(headline = refusal, action = OtaAction.CHECK, actionLabel = "업데이트 확인"))
                }
                else -> {
                    state = UpdateUi("업데이트 확인 중", false, busy = true)
                    actions.checkUpdate { result -> state = result }
                }
            }
        }
    }
}

/** Shown once, at the top of the menu, the first time the app opens after it was replaced by an update. */
@Composable
private fun UpdatedBanner(notice: OtaNotice?, onShown: () -> Unit) {
    var visible by remember { mutableStateOf(notice != null) }
    LaunchedEffect(notice) {
        if (notice == null) return@LaunchedEffect
        visible = true
        kotlinx.coroutines.delay(3_800)
        visible = false
        kotlinx.coroutines.delay(400)
        onShown()
    }
    AnimatedVisibility(visible && notice != null, enter = fadeIn(tween(260)) + expandVertically(tween(260)), exit = fadeOut(tween(260)) + shrinkVertically(tween(260))) {
        Column {
            Row(
                Modifier.fillMaxWidth().clip(KShape.Control).background(KColors.AccentWash).padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                KIcon(KIcon.Check, KColors.Accent, Modifier.padding(end = 12.dp), 22.dp)
                Column {
                    Text("${notice?.to.orEmpty()}로 업데이트 완료", color = KColors.White, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                    Text("이전 ${notice?.from.orEmpty()}", color = KColors.Muted, fontSize = 13.sp)
                }
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

/** Two fixed rows (phone, watch) and one button whose label and colour change in place, so nothing moves while updating. */
@Composable
private fun UpdateCard(card: OtaCard, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth()) {
        Text("업데이트", color = KColors.Muted, fontSize = 13.sp, modifier = Modifier.padding(bottom = 6.dp))
        HairlineRule()
        UpdateRow(card.phone)
        HairlineRule()
        UpdateRow(card.watch ?: OtaRow("워치", "연결 안 됨", OtaRowKind.IDLE))
        HairlineRule()
        Spacer(Modifier.height(14.dp))
        Box(Modifier.fillMaxWidth().height(22.dp)) {
            Crossfade(card.headline, animationSpec = tween(200), label = "updateHeadline") {
                Text(it, color = KColors.Muted, fontSize = 14.sp, maxLines = 1)
            }
        }
        Spacer(Modifier.height(10.dp))
        UpdateButton(card.action, card.actionLabel, onClick)
    }
}

@Composable
private fun UpdateRow(row: OtaRow) {
    val bar by animateFloatAsState(row.progress ?: 0f, tween(300), label = "updateProgress")
    val color by animateColorAsState(
        when (row.kind) {
            OtaRowKind.READY -> KColors.Accent
            OtaRowKind.FAIL -> KColors.Red
            OtaRowKind.IDLE -> KColors.Muted
            else -> KColors.White
        }, tween(240), label = "updateRowColor")
    Column(Modifier.fillMaxWidth().height(60.dp), verticalArrangement = Arrangement.Center) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(row.device, color = KColors.Soft, fontSize = 15.sp, modifier = Modifier.weight(1f))
            Crossfade(row.text, animationSpec = tween(200), label = "updateRowText") {
                Text(it, color = color, fontSize = 15.sp, fontWeight = FontWeight.Medium, maxLines = 1)
            }
        }
        // The bar's slot is always there, so a row never gets taller when a progress bar appears.
        Spacer(Modifier.height(8.dp))
        Box(Modifier.fillMaxWidth().height(3.dp).clip(RoundedCornerShape(2.dp)).background(if (row.progress != null) KColors.Hairline else Color.Transparent)) {
            if (row.progress != null) Box(Modifier.fillMaxWidth(bar).height(3.dp).background(KColors.Accent))
        }
    }
}

@Composable
private fun UpdateButton(action: OtaAction, label: String, onClick: () -> Unit) {
    val working = action == OtaAction.WORKING
    val fill by animateColorAsState(when (action) {
        OtaAction.INSTALL -> KColors.Accent
        OtaAction.WORKING -> KColors.SurfaceRaised
        else -> Color.Transparent
    }, tween(240), label = "updateButtonFill")
    val outlined = action == OtaAction.CHECK || action == OtaAction.RETRY
    Box(
        Modifier
            .testTag("updateAction")
            .fillMaxWidth()
            .height(58.dp)
            .clip(KShape.Control)
            .background(fill)
            .then(if (outlined) Modifier.border(0.5.dp, Color(0xFF3A3D41), KShape.Control) else Modifier)
            .then(if (working) Modifier else Modifier.pressable(onClick)),
        contentAlignment = Alignment.Center,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            AnimatedVisibility(working) {
                Row {
                    CircularProgressIndicator(Modifier.size(18.dp), color = KColors.Accent, strokeWidth = 2.dp)
                    Spacer(Modifier.width(10.dp))
                }
            }
            Crossfade(label, animationSpec = tween(200), label = "updateButtonLabel") {
                Text(it, color = if (action == OtaAction.INSTALL) KColors.OnAccent else KColors.White, fontSize = 16.sp, fontWeight = FontWeight.Medium)
            }
        }
    }
}

private val MENU_TIPS = listOf(
    "워치를 손목에 단단히 고정하면\n센서가 움직임을 더 정확하게 읽습니다.",
    "운동 전 측정·보정을 해 두면\n내 동작에 맞춰 횟수를 세어 줍니다.",
    "기록은 로그인 없이 이 폰에만 저장됩니다.\n센서 기록은 운동과 보정 중에만 켜집니다.",
)

@Composable
private fun MenuTipBox() {
    var index by remember { mutableStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            kotlinx.coroutines.delay(5_000)
            index = (index + 1) % MENU_TIPS.size
        }
    }
    Box(
        Modifier.fillMaxWidth().heightIn(min = 72.dp).clip(KShape.Control)
            .border(0.5.dp, Color(0xFF3A3D41), KShape.Control).padding(horizontal = 16.dp, vertical = 14.dp),
        contentAlignment = Alignment.CenterStart,
    ) {
        Text(MENU_TIPS[index], color = KColors.Soft, fontSize = 14.sp, maxLines = 2)
    }
}
