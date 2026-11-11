package dev.kyungmin.kcoach.phone.ui

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.widget.Toast
import androidx.activity.compose.BackHandler
import dev.kyungmin.kcoach.phone.ExercisePreviewView
import dev.kyungmin.kcoach.phone.ExercisePreviews
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.rememberGraphicsLayer
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.unit.Velocity
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.zIndex
import androidx.core.content.ContextCompat
import dev.kyungmin.kcoach.phone.ResultImageExport
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal val ResultMint = Color(0xFF76DBB9)
internal val ResultBone = Color(0xFFEDE8DC)
internal val ResultRaised = Color(0xFF242424)
internal val ResultHair = Color(0xFF353535)
internal val ResultMuted = Color(0xFF909090)
/** Same corner radius as the result screen's bottom buttons, for the card and the camera frame. */
internal const val ResultCameraRadius = 10f
/** Camera photo frame top, below the status bar, and the room the ratio tabs and shutter need under it (dp). */
/** The camera stage starts exactly where the resting card does: 33dp header + 4dp gap. */
internal const val ResultCameraTop = 37
internal const val ResultCameraControls = 120

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun DesignedWorkoutResult(result: ResultUi, back: () -> Unit, done: () -> Unit,
    estimated: List<Pair<String, Int>>, confirm: (Int, Int) -> Unit) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    val density = LocalDensity.current.density
    val scroll = rememberScrollState()
    var read by remember(result.sessionId) { mutableStateOf<ResultPresentation?>(null) }
    var readFailed by remember(result.sessionId) { mutableStateOf(false) }
    var retry by remember { mutableIntStateOf(0) }
    LaunchedEffect(result.sessionId, retry) {
        readFailed = false
        val loaded = withContext(Dispatchers.IO) { runCatching { loadResultPresentation(context.applicationContext, requireNotNull(result.sessionId)) } }
        read = loaded.getOrNull(); readFailed = loaded.isFailure
    }
    var sheet by remember { mutableStateOf(false) }
    var detailed by remember { mutableStateOf(false) }
    var cameraOpen by remember { mutableStateOf(false) }
    var camera by remember { mutableStateOf<ResultCameraView?>(null) }
    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) scope.launch {
            val bitmap = withContext(Dispatchers.IO) { runCatching {
                android.graphics.ImageDecoder.decodeBitmap(android.graphics.ImageDecoder.createSource(context.contentResolver, uri)) { decoder, info, _ ->
                    decoder.allocator = android.graphics.ImageDecoder.ALLOCATOR_SOFTWARE
                    val longest = maxOf(info.size.width,info.size.height)
                    if (longest > 2048) decoder.setTargetSize(info.size.width*2048/longest,info.size.height*2048/longest)
                }
            }.getOrNull() }
            if (bitmap != null) camera?.importPhoto(bitmap)
        }
    }
    var permission by remember { mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) }
    var openAfterPermission by remember { mutableStateOf(false) }
    val request = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        permission = granted
        if (granted) { camera?.bind(); if (openAfterPermission) { cameraOpen = true; camera?.open() } }
        else Toast.makeText(context, "카메라 권한이 필요해요. 앱 설정에서 권한을 허용해 주세요.", Toast.LENGTH_LONG).show()
        openAfterPermission = false
    }
    fun openCamera() {
        sheet = false
        if (!permission) { openAfterPermission = true; request.launch(Manifest.permission.CAMERA) }
        else { scope.launch { scroll.scrollTo(0); androidx.compose.runtime.withFrameNanos { }; cameraOpen = true; camera?.open() } }
    }
    DisposableEffect(owner) { onDispose { camera?.release() } }
    BackHandler(cameraOpen) { camera?.close() }
    var estimateIndex by remember { mutableStateOf<Int?>(null) }
    var estimateText by remember { mutableStateOf("") }
    estimateIndex?.let { index ->
        AlertDialog(onDismissRequest = { estimateIndex = null }, title = { Text("반대손 횟수") }, text = {
            BasicTextField(estimateText, { estimateText = it.filter(Char::isDigit).take(4) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
        }, confirmButton = { TextButton(onClick = { estimateText.toIntOrNull()?.takeIf { it in 0..9999 }?.let { confirm(index, it); estimateIndex = null } }) { Text("확정") } },
            dismissButton = { TextButton(onClick = { estimateIndex = null }) { Text("취소") } })
    }
    // Pull down at the very top to open the camera: a haptic tick marks the release point, letting go opens it.
    val haptics = LocalHapticFeedback.current
    val pullLimit = 72f * density
    var pull by remember { mutableFloatStateOf(0f) }
    var armed by remember { mutableStateOf(false) }
    var released by remember { mutableStateOf(false) }
    val pullShown by animateFloatAsState(pull, if (released) tween(260, easing = FastOutSlowInEasing) else snap(), label = "pull")
    val pullConnection = remember(pullLimit) {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
                if (pull <= 0f || available.y >= 0f) return Offset.Zero
                val used = minOf(pull, -available.y); pull -= used
                if (armed && pull < pullLimit) armed = false
                return Offset(0f, -used)
            }
            override fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset {
                if (source != NestedScrollSource.UserInput || available.y <= 0f || cameraOpen) return Offset.Zero
                released = false
                pull = minOf(pull + available.y * .6f, pullLimit * 1.4f)
                if (!armed && pull >= pullLimit) { armed = true; haptics.performHapticFeedback(HapticFeedbackType.LongPress) }
                return Offset(0f, available.y)
            }
            override suspend fun onPreFling(available: Velocity): Velocity {
                val go = armed; released = true; pull = 0f; armed = false
                if (go) openCamera()
                return Velocity.Zero
            }
        }
    }
    BoxWithConstraints(Modifier.fillMaxSize().background(Color.Black)) {
        val cameraFrameWidth = minOf(maxWidth - 22.dp, (maxHeight - (ResultCameraTop + ResultCameraControls).dp) * (9f / 16f)).coerceAtLeast(1.dp)
        AndroidView(factory = { ResultCameraView(it, owner).also { v -> camera = v; v.onClosed = { cameraOpen = false }; v.onGallery = { gallery.launch(androidx.activity.result.PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }; if (permission) v.bind() } },
            update = { it.presentation = read }, modifier = Modifier.fillMaxSize().zIndex(if (cameraOpen) 2f else 0f))
        Column(Modifier.fillMaxSize().zIndex(1f).nestedScroll(pullConnection)) {
            Column(Modifier.weight(1f).verticalScroll(scroll)) {
                Row(Modifier.fillMaxWidth().background(Color.Black).padding(horizontal = 16.dp).height(33.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("✕", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Medium, modifier = Modifier.clickable(onClick = back).padding(end = 16.dp))
                    Text("저장됨 · ${read?.date?.substringAfter("년 ") ?: ""}", color = Color.White, fontSize = 14.sp)
                }
                val fade = (scroll.value / (120f * density)).coerceIn(0f, 1f)
                Box(Modifier.align(Alignment.CenterHorizontally).padding(top = (ResultCameraTop - 33).dp).width(cameraFrameWidth).height(132.dp + (pullShown / density).dp)
                    .onGloballyPositioned { camera?.cardBounds = it.boundsInRoot(); camera?.cardFade = fade }
                    .graphicsLayer { alpha = 1 - fade; translationY = fade * 10 * density; scaleX = 1 - fade * .04f; scaleY = scaleX }
                    .clip(RoundedCornerShape(ResultCameraRadius.dp))) {
                    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.SpaceBetween) {
                        Column {
                            Text("오운완 사진 남기기", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                            Text("거울 앞에서 찍으면 오늘 기록이 같이 들어가요", color = Color.White.copy(alpha = .82f), fontSize = 12.sp)
                        }
                        ResultButton("카메라 열기", true, Modifier, 13) { openCamera() }
                    }
                    PullHint(Modifier.align(Alignment.BottomCenter).padding(bottom = 15.dp), 1f - (pullShown / (30f * density)).coerceIn(0f, 1f))
                }
                Column(Modifier.fillMaxWidth().background(Color.Black).padding(horizontal = 16.dp)) {
                    Spacer(Modifier.height(18.dp))
                    Text("${result.title} 완료", color = ResultBone, fontSize = 26.sp, fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(12.dp))
                    read?.let { data ->
                        ResultNumbers(data)
                        Column(Modifier.padding(top = 8.dp, bottom = 4.dp).fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(Color(0xFF0F2A22)).padding(13.dp, 11.dp)) {
                            Text(data.verdict, color = ResultMint, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                            Text(data.comparison, color = ResultMuted, fontSize = 12.sp)
                        }
                        data.exercises.forEach { ExerciseResultCard(it) }
                        Spacer(Modifier.height(12.dp))
                    } ?: Text(if (readFailed) "운동 기록을 불러오지 못했어요" else "운동 기록 불러오는 중", color = ResultMuted)
                    if (readFailed) TextButton(onClick = { retry++ }) { Text("다시 시도", color = ResultMint) }
                    estimated.forEachIndexed { i, (label, reps) ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text("$label · ${reps}회", color = ResultMuted, fontSize = 12.sp, modifier = Modifier.weight(1f))
                            TextButton(onClick = { estimateText = reps.toString(); estimateIndex = i }) { Text("수정", color = ResultMint) }
                        }
                    }
                }
            }
            Row(Modifier.fillMaxWidth().background(Color.Black).padding(16.dp, 12.dp, 16.dp, 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ResultButton("내보내기", false, Modifier.width(110.dp)) { sheet = true }
                ResultButton("확인", true, Modifier.weight(1f), action = done)
            }
        }
    }
    if (sheet) ModalBottomSheet(onDismissRequest = { sheet = false }, containerColor = ResultRaised, shape = RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp)) {
        val capture = rememberGraphicsLayer()
        var exporting by remember { mutableStateOf(false) }
        fun export(share: Boolean) {
            if (exporting || read == null) return
            exporting = true
            scope.launch {
                try {
                    val bitmap = capture.toImageBitmap().asAndroidBitmap().copy(Bitmap.Config.ARGB_8888, false)
                    val ok = withContext(Dispatchers.IO) { if (share) ResultImageExport.share(context, bitmap, result.title) else ResultImageExport.save(context, bitmap, result.title) }
                    bitmap.recycle()
                    Toast.makeText(context, if (ok) { if (share) "공유 화면 열림" else "갤러리에 저장됨" } else "이미지 내보내기 실패", Toast.LENGTH_SHORT).show()
                } catch (_: Exception) { Toast.makeText(context, "이미지 내보내기 실패", Toast.LENGTH_SHORT).show() }
                finally { exporting = false }
            }
        }
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 18.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("내보내기", color = ResultBone, fontSize = 16.sp)
                Text("닫기", color = ResultMuted, modifier = Modifier.clickable { sheet = false })
            }
            Row(Modifier.padding(vertical = 10.dp).fillMaxWidth().clip(RoundedCornerShape(8.dp)).background(Color.Black).padding(3.dp)) {
                listOf("요약형", "상세형").forEachIndexed { i, label ->
                    Box(Modifier.weight(1f).clip(RoundedCornerShape(6.dp)).background(if (detailed == (i == 1)) Color(0xFF262522) else Color.Black).clickable { detailed = i == 1 }.padding(7.dp), contentAlignment = Alignment.Center) { Text(label, color = ResultBone, fontSize = 13.sp) }
                }
            }
            read?.let { data ->
                Column(Modifier.fillMaxWidth().drawWithContent { capture.record { this@drawWithContent.drawContent() }; drawContent() }.clip(RoundedCornerShape(14.dp)).background(Color(0xFF0A0A09)).padding(16.dp, 18.dp)) {
                    Text(data.date, color = ResultMuted, fontSize = 12.sp)
                    Text(data.title, color = ResultBone, fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(12.dp)); ResultNumbers(data, true)
                    if (!detailed) {
                        val record = data.exercises.firstOrNull { e -> e.sets.any { it.record } }
                        if (record != null) Column(Modifier.padding(vertical = 8.dp).fillMaxWidth().clip(RoundedCornerShape(8.dp)).background(Color(0xFF0F2A22)).padding(11.dp, 9.dp)) {
                            Text("최고 기록", color = ResultMint, fontSize = 12.sp); Text("${record.name} ${record.sets.first { it.record }.today}", color = ResultBone, fontSize = 14.sp)
                        }
                        Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.SpaceBetween) { Text("종목", color = ResultMuted, fontSize = 11.sp); Text("최고 세트", color = ResultMuted, fontSize = 11.sp) }
                        data.exercises.forEach { e ->
                            HorizontalDivider(color = ResultRaised)
                            Row(Modifier.fillMaxWidth().padding(vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) { Text(e.name, color = ResultBone, fontSize = 14.sp); Text("${e.sets.size}세트", color = ResultMuted, fontSize = 11.sp) }
                                Text(e.best, color = ResultBone, fontSize = 13.sp)
                            }
                        }
                    } else data.exercises.forEach { ExerciseResultCard(it, export = true) }
                    Row(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(if (detailed) data.vitals else data.verdict, color = ResultMuted, fontSize = 10.sp, modifier = Modifier.weight(1f))
                        Text("WatchGym", color = ResultBone, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                ResultButton(if (exporting) "처리 중" else "공유", true, Modifier.weight(1f), 13) { export(true) }
                ResultButton("사진에 저장", false, Modifier.weight(1f), 13) { export(false) }
                ResultButton("텍스트 복사", false, Modifier.weight(1f), 13) {
                    read?.let { data -> (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText(data.title,
                        "${data.date}\n${data.title}\n${data.minutes}분 · ${data.volume}kg · ${data.setCount}세트\n" + data.exercises.joinToString("\n") { e -> e.name + " · " + if (detailed) e.sets.joinToString(" / ") { it.today } else e.best })) }
                }
            }
            ResultButton("사진 찍어 공유", true, Modifier.fillMaxWidth()) { openCamera() }
            Spacer(Modifier.height(24.dp))
        }
    }
}

/** Two wide, translucent chevrons that drop together and spring back on a loop, hinting that the card can be pulled down. */
@Composable
private fun PullHint(modifier: Modifier, visible: Float) {
    val t by rememberInfiniteTransition(label = "hint").animateFloat(0f, 1f, infiniteRepeatable(tween(1800, easing = LinearEasing)), label = "hintT")
    Canvas(modifier.size(36.dp, 18.dp)) {
        // 0..0.2 drop with ease-out, hold until 0.3, then a quick spring back (one small overshoot, done in about 0.36s), rest.
        val drop = when {
            t < .2f -> 1f - (1f - t / .2f).let { it * it * it }
            t < .3f -> 1f
            t < .53f -> { val q = (t - .3f) / .23f; kotlin.math.exp(-4f * q) * kotlin.math.cos(7.5f * q) }
            else -> 0f
        }
        val dy = drop * 7f * density
        val stroke = Stroke(2.9f * density, cap = StrokeCap.Round, join = StrokeJoin.Round)
        for (row in 0..1) {
            val y = (2.7f + row * 6.3f) * density + dy
            val path = Path().apply { moveTo(2.7f * density, y); lineTo(18f * density, y + 6.3f * density); lineTo(33.3f * density, y) }
            drawPath(path, Color.White.copy(alpha = .5f * visible), style = stroke)
        }
    }
}

@Composable
internal fun ResultButton(label: String, mint: Boolean, modifier: Modifier = Modifier, font: Int = 15, action: () -> Unit) {
    Box(modifier.clip(RoundedCornerShape(ResultCameraRadius.dp)).background(if (mint) ResultMint else ResultRaised).clickable(onClick = action).padding(horizontal = 12.dp, vertical = 13.dp), contentAlignment = Alignment.Center) {
        Text(label, color = if (mint) Color(0xFF04140E) else ResultBone, fontSize = font.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun ResultHeadlineStats(data: ResultPresentation) {
    Row(Modifier.fillMaxWidth().padding(bottom = 14.dp)) {
        listOf(Triple("${data.minutes}", "분", "운동 시간"), Triple(data.volume, "kg", "총 볼륨"), Triple("${data.setCount}", "", "세트")).forEachIndexed { i, (value, unit, label) ->
            Column(Modifier.weight(if (i == 1) 1.4f else 1f)) {
                Text(androidx.compose.ui.text.buildAnnotatedString {
                    append(value)
                    if (unit.isNotEmpty()) { pushStyle(androidx.compose.ui.text.SpanStyle(fontSize = 14.sp, color = ResultMuted, fontWeight = FontWeight.Normal)); append(" $unit"); pop() }
                }, color = ResultMint, fontSize = 30.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
                Text(label, color = ResultMuted, fontSize = 12.sp)
            }
        }
    }
}

/** The watch's heart (same shape and zone colour), beating once per heartbeat at the given bpm. */
@Composable
private fun BeatingHeart(bpm: Int?, size: androidx.compose.ui.unit.Dp) {
    if (bpm == null || bpm <= 0) { Spacer(Modifier.size(size)); return }
    val period = (60_000 / bpm).coerceIn(300, 1_500)
    key(period) {
        val scale by rememberInfiniteTransition(label = "beat").animateFloat(1f, 1f, infiniteRepeatable(keyframes {
            durationMillis = period
            1f at 0; 1.22f at (period * .14f).toInt(); 1f at (period * .28f).toInt(); 1.12f at (period * .42f).toInt(); 1f at (period * .56f).toInt(); 1f at period
        }), label = "beatScale")
        val tint = Color(dev.kyungmin.kcoach.core.HeartZone.color(bpm))
        Canvas(Modifier.size(size).graphicsLayer { scaleX = scale; scaleY = scale; transformOrigin = androidx.compose.ui.graphics.TransformOrigin(.5f, .55f) }) {
            val u = minOf(this.size.width, this.size.height) / 24f
            val ox = (this.size.width - 24f * u) / 2f; val oy = (this.size.height - 24f * u) / 2f
            fun x(v: Float) = ox + v * u
            fun y(v: Float) = oy + v * u
            val path = Path().apply {
                moveTo(x(12f), y(21.35f)); lineTo(x(10.55f), y(20.03f))
                cubicTo(x(5.4f), y(15.36f), x(2f), y(12.28f), x(2f), y(8.5f))
                cubicTo(x(2f), y(5.42f), x(4.42f), y(3f), x(7.5f), y(3f))
                cubicTo(x(9.24f), y(3f), x(10.91f), y(3.81f), x(12f), y(5.09f))
                cubicTo(x(13.09f), y(3.81f), x(14.76f), y(3f), x(16.5f), y(3f))
                cubicTo(x(19.58f), y(3f), x(22f), y(5.42f), x(22f), y(8.5f))
                cubicTo(x(22f), y(12.28f), x(18.6f), y(15.36f), x(13.45f), y(20.04f))
                close()
            }
            drawPath(path, tint)
            drawPath(path, tint, style = Stroke(width = this.size.width * .05f, join = StrokeJoin.Round))
        }
    }
}

@Composable
private fun ResultHeartCard(data: ResultPresentation) {
    Row(Modifier.fillMaxWidth().height(128.dp).clip(RoundedCornerShape(10.dp)).background(ResultRaised).padding(14.dp)) {
        Column(Modifier.weight(1.15f).fillMaxHeight(), verticalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text("평균 심박수", color = ResultMuted, fontSize = 11.sp)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    BeatingHeart(data.avgHeart.toIntOrNull(), 22.dp)
                    Spacer(Modifier.width(6.dp))
                    Text(androidx.compose.ui.text.buildAnnotatedString {
                        append(data.avgHeart)
                        pushStyle(androidx.compose.ui.text.SpanStyle(fontSize = 12.sp, color = ResultMuted, fontWeight = FontWeight.Normal)); append(" bpm"); pop()
                    }, color = ResultBone, fontSize = 28.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
                }
            }
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                listOf(Triple("최고 심박수", data.maxHeart, "bpm"), Triple("소모 칼로리", data.kcal, "kcal")).forEach { (label, value, unit) ->
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(label, color = ResultMuted, fontSize = 10.5.sp, modifier = Modifier.width(54.dp), maxLines = 1, softWrap = false)
                        if (unit == "bpm") BeatingHeart(value.toIntOrNull(), 12.dp) else Spacer(Modifier.width(12.dp))   // same slot, so the numbers line up
                        Spacer(Modifier.width(4.dp))
                        Text(androidx.compose.ui.text.buildAnnotatedString {
                            append(value)
                            pushStyle(androidx.compose.ui.text.SpanStyle(fontSize = 10.sp, color = ResultMuted, fontWeight = FontWeight.Normal)); append(" $unit"); pop()
                        }, color = ResultBone, fontSize = 14.sp, fontWeight = FontWeight.Medium, maxLines = 1)
                    }
                }
            }
        }
        Spacer(Modifier.width(14.dp))
        Box(Modifier.weight(1.35f).fillMaxHeight(), contentAlignment = Alignment.Center) {
            if (data.heartPoints.size < 2) Text("그래프를 그릴 심박이 부족해요", color = ResultMuted, fontSize = 11.sp)
            else Canvas(Modifier.fillMaxSize()) {
                val pts = data.heartPoints
                val t0 = pts.first().first; val span = (pts.last().first - t0).coerceAtLeast(1L)
                val barW = 3.dp.toPx(); val step = barW * 2f
                val n = (size.width / step).toInt().coerceAtLeast(2)
                val lo = IntArray(n) { Int.MAX_VALUE }; val hi = IntArray(n) { Int.MIN_VALUE }
                pts.forEach { (at, bpm) ->
                    val i = ((at - t0).toFloat() / span * (n - 1)).toInt().coerceIn(0, n - 1)
                    lo[i] = minOf(lo[i], bpm); hi[i] = maxOf(hi[i], bpm)
                }
                val floor = (pts.minOf { it.second } - 8).toFloat(); val ceil = (pts.maxOf { it.second } + 4).toFloat()
                fun y(bpm: Int) = size.height - (bpm - floor) / (ceil - floor) * size.height
                val peak = hi.indices.maxByOrNull { hi[it] } ?: -1
                val left = (size.width - (n - 1) * step - barW) / 2f
                for (i in 0 until n) {
                    if (hi[i] == Int.MIN_VALUE) continue
                    val x = left + barW / 2f + i * step
                    val top = y(hi[i]); val bottom = maxOf(y(lo[i]), top + 0.1f)
                    drawLine(if (i == peak) ResultBone else ResultMint.copy(alpha = .75f), Offset(x, top), Offset(x, bottom), strokeWidth = barW, cap = StrokeCap.Round)
                }
            }
        }
    }
}

@Composable
internal fun ResultNumbers(data: ResultPresentation, compact: Boolean = false) {
    if (!compact) {
        Column { ResultHeadlineStats(data); if (data.heartPoints.isNotEmpty() || data.avgHeart != "—") ResultHeartCard(data) }   // no watch heart data, no heart card
        return
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        listOf("${data.minutes}분" to "운동 시간", "${data.volume}kg" to "총 볼륨", "${data.setCount}" to "세트").forEach { (value, label) ->
            Column(Modifier.weight(1f).clip(RoundedCornerShape(if (compact) 8.dp else 10.dp)).background(ResultRaised).padding(if (compact) 10.dp else 11.dp)) {
                Text(androidx.compose.ui.text.buildAnnotatedString {
                    val suffix = when (label) { "운동 시간" -> "분"; "총 볼륨" -> "kg"; else -> "" }
                    append(if (suffix.isEmpty()) value else value.removeSuffix(suffix))
                    if (suffix.isNotEmpty()) {
                        pushStyle(androidx.compose.ui.text.SpanStyle(fontSize = 11.sp, color = ResultMuted, fontWeight = FontWeight.Normal))
                        append(suffix); pop()
                    }
                }, color = ResultBone, fontSize = (if (compact) 19 else 22).sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
                Text(label, color = ResultMuted, fontSize = (if (compact) 10 else 11).sp, modifier = Modifier.padding(top = 4.dp))
            }
        }
    }
}

@Composable
internal fun ExerciseResultCard(exercise: ResultExercise, export: Boolean = false, initiallyExpanded: Boolean = false) {
    var expanded by remember(exercise) { mutableStateOf(initiallyExpanded) }
    Column(Modifier.padding(top = 6.dp).fillMaxWidth().clip(RoundedCornerShape(if (export) 8.dp else 12.dp)).background(ResultRaised)) {
        Row(Modifier.fillMaxWidth().then(if (export) Modifier else Modifier.clickable { expanded = !expanded }).padding(start = if (export) 11.dp else 14.dp, end = if (export) 11.dp else 14.dp, top = if (export) 9.dp else 13.dp, bottom = if (export) 3.dp else 13.dp), verticalAlignment = Alignment.CenterVertically) {
            val previewContext = LocalContext.current
            if (!export && exercise.exerciseId.isNotEmpty() && ExercisePreviews.has(previewContext, exercise.exerciseId)) {
                androidx.compose.ui.viewinterop.AndroidView(
                    factory = { ExercisePreviewView(it, exercise.exerciseId) },
                    modifier = Modifier.padding(end = 12.dp).size(44.dp).clip(RoundedCornerShape(ResultCameraRadius.dp)),
                )
            }
            Column(Modifier.weight(1f)) {
                Text(exercise.name, color = ResultBone, fontSize = (if (export) 14 else 15).sp, fontWeight = FontWeight.Medium)
                if (!export) Text("${exercise.sets.size}세트 · 최고 ${exercise.best}", color = ResultMuted, fontSize = 12.sp, modifier = Modifier.padding(top = 2.dp))
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(exercise.delta, color = if (exercise.direction == 1) ResultMint else if (exercise.direction == -1) ResultBone else ResultMuted, fontSize = (if (export) 12 else 15).sp, fontWeight = FontWeight.SemiBold)
            }
            if (!export) {
                val turn by animateFloatAsState(if (expanded) 180f else 0f, tween(240, easing = FastOutSlowInEasing), label = "chev")
                Canvas(Modifier.padding(start = 10.dp).size(14.dp, 8.dp).graphicsLayer { rotationZ = turn }) {
                    val path = Path().apply { moveTo(1f * density, 1.5f * density); lineTo(7f * density, 6.5f * density); lineTo(13f * density, 1.5f * density) }
                    drawPath(path, ResultMuted, style = Stroke(1.8f * density, cap = StrokeCap.Round, join = StrokeJoin.Round))
                }
            }
        }
        androidx.compose.animation.AnimatedVisibility(visible = expanded || export,
            enter = androidx.compose.animation.expandVertically(tween(240, easing = FastOutSlowInEasing)) + androidx.compose.animation.fadeIn(tween(200)),
            exit = androidx.compose.animation.shrinkVertically(tween(220, easing = FastOutSlowInEasing)) + androidx.compose.animation.fadeOut(tween(120))) {
        Column(Modifier.padding(horizontal = if (export) 11.dp else 14.dp).padding(bottom = if (export) 9.dp else 10.dp)) {
            if (!export) exercise.growth?.let { Text(it, color = ResultMuted, fontSize = 12.sp, modifier = Modifier.padding(top = 9.dp)) }
            if (!export) exercise.sets.chunked(6).forEach { line ->
                Row(Modifier.fillMaxWidth().padding(top = 9.dp).height(IntrinsicSize.Min)) {
                    for (i in 0 until 6) {
                        val set = line.getOrNull(i)
                        Column(Modifier.weight(1f).fillMaxHeight()) {
                            if (set != null) {
                                val parts = set.today.split(" × ")
                                val tone = ResultMint
                                Text(resultSetText(parts[0], 10), color = tone, fontSize = 15.sp, fontWeight = if (set.record) FontWeight.Bold else FontWeight.Medium, maxLines = 1, softWrap = false)
                                if (parts.size > 1) Text(resultSetText(parts[1], 10), color = ResultMint, fontSize = 14.sp, fontWeight = if (set.record) FontWeight.Bold else FontWeight.Normal, maxLines = 1, softWrap = false)
                            }
                        }
                    }
                }
            }
            if (export) exercise.sets.forEach { set ->
                Row(Modifier.fillMaxWidth().padding(vertical = if (export) 2.dp else 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("${set.number}", color = ResultMuted, fontSize = 12.sp, modifier = Modifier.width((if (export) 20 else 24).dp))
                    Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
                        Text(resultSetText(set.today, if (export) 10 else 11), color = ResultBone, fontSize = (if (export) 13 else 15).sp, fontWeight = FontWeight.Medium)
                        if (set.record) Text(" 최고", color = ResultMint, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    }
                    if (!export) Text(resultSetText(set.previous,11), color = ResultMuted, fontSize = 12.sp, modifier = Modifier.weight(1f))
                }
            }
            if (!export) exercise.tempo?.let { tempo ->
                HorizontalDivider(color = ResultHair, modifier = Modifier.padding(top = 6.dp))
                Row(Modifier.fillMaxWidth().padding(top = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("평균 반복 시간", color = ResultMuted, fontSize = 12.sp)
                    Text(" ${tempo.average}/회", color = ResultBone, fontSize = if (export) 13.sp else 15.sp, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
                    tempo.trend?.let { trend ->
                        val label = when (trend) { 1 -> "점점 느려짐"; -1 -> "점점 빨라짐"; else -> "일정함" }
                        Text(label, color = if (trend == 0) ResultMint else ResultBone, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                        tempo.change?.let { Text(" $it", color = ResultMuted, fontSize = 11.sp) }
                    }
                }
            }
        }
        }
    }
}

private fun resultSetText(value: String, unitSize: Int) = androidx.compose.ui.text.buildAnnotatedString {
    val units = Regex("kg|회|초|×")
    var at = 0
    units.findAll(value).forEach { match ->
        append(value.substring(at,match.range.first))
        pushStyle(androidx.compose.ui.text.SpanStyle(fontSize = unitSize.sp,color = ResultMuted,fontWeight = FontWeight.Normal))
        append(match.value);pop();at=match.range.last+1
    }
    append(value.substring(at))
}
