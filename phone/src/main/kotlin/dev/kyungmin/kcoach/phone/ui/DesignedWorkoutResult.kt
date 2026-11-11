package dev.kyungmin.kcoach.phone.ui

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.rememberGraphicsLayer
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
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
internal val ResultRaised = Color(0xFF1C1B19)
internal val ResultMuted = Color(0xFF8F8B82)
internal const val ResultCameraRadius = 22f

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
    BoxWithConstraints(Modifier.fillMaxSize().background(Color.Black)) {
        val cameraFrameWidth = minOf(maxWidth - 22.dp, (maxHeight - 194.dp) * (9f / 16f)).coerceAtLeast(1.dp)
        AndroidView(factory = { ResultCameraView(it, owner).also { v -> camera = v; v.onClosed = { cameraOpen = false }; v.onGallery = { gallery.launch(androidx.activity.result.PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }; if (permission) v.bind() } },
            update = { it.presentation = read }, modifier = Modifier.fillMaxSize().zIndex(if (cameraOpen) 2f else 0f))
        Column(Modifier.fillMaxSize().zIndex(1f)) {
            Column(Modifier.weight(1f).verticalScroll(scroll)) {
                Row(Modifier.fillMaxWidth().background(Color.Black).padding(horizontal = 16.dp).height(33.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("✕", color = ResultMuted, modifier = Modifier.clickable(onClick = back).padding(end = 16.dp))
                    Text("저장됨 · ${read?.date?.substringAfter("년 ") ?: ""}", color = ResultMuted, fontSize = 12.sp)
                }
                val fade = (scroll.value / (120f * density)).coerceIn(0f, 1f)
                Box(Modifier.align(Alignment.CenterHorizontally).padding(top = 23.dp).width(cameraFrameWidth).height(132.dp)
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
                        Text(data.vitals, color = ResultMuted, fontSize = 12.sp, modifier = Modifier.padding(top = 12.dp, bottom = 12.dp))
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

@Composable
internal fun ResultButton(label: String, mint: Boolean, modifier: Modifier = Modifier, font: Int = 15, action: () -> Unit) {
    Box(modifier.clip(RoundedCornerShape((ResultCameraRadius - 12).dp)).background(if (mint) ResultMint else ResultRaised).clickable(onClick = action).padding(horizontal = 12.dp, vertical = 13.dp), contentAlignment = Alignment.Center) {
        Text(label, color = if (mint) Color(0xFF04140E) else ResultBone, fontSize = font.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun ResultNumbers(data: ResultPresentation, compact: Boolean = false) {
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
private fun ExerciseResultCard(exercise: ResultExercise, export: Boolean = false) {
    var expanded by remember(exercise) { mutableStateOf(false) }
    Column(Modifier.padding(top = 6.dp).fillMaxWidth().clip(RoundedCornerShape(if (export) 8.dp else 12.dp)).background(ResultRaised)) {
        Row(Modifier.fillMaxWidth().then(if (export) Modifier else Modifier.clickable { expanded = !expanded }).padding(start = if (export) 11.dp else 14.dp, end = if (export) 11.dp else 14.dp, top = if (export) 9.dp else 13.dp, bottom = if (export) 3.dp else 13.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(exercise.name, color = ResultBone, fontSize = (if (export) 14 else 15).sp, fontWeight = FontWeight.Medium)
                if (!export) Text("${exercise.sets.size}세트 · 최고 ${exercise.best}", color = ResultMuted, fontSize = 12.sp, modifier = Modifier.padding(top = 2.dp))
            }
            Text(exercise.delta, color = if (exercise.direction == 1) ResultMint else if (exercise.direction == -1) ResultBone else ResultMuted, fontSize = (if (export) 12 else 14).sp, fontWeight = FontWeight.SemiBold)
            if (!export) Text(if (expanded) " ▴" else " ▾", color = ResultMuted)
        }
        if (expanded || export) Column(Modifier.padding(horizontal = if (export) 11.dp else 14.dp).padding(bottom = if (export) 9.dp else 10.dp)) {
            if (!export) {
                Row(Modifier.fillMaxWidth().padding(top = 9.dp, bottom = 3.dp)) {
                    Text("세트", color = ResultMuted, fontSize = 11.sp, modifier = Modifier.width((if (export) 20 else 24).dp))
                    Text("오늘", color = ResultMuted, fontSize = 11.sp, modifier = Modifier.weight(1f)); Text("지난번", color = ResultMuted, fontSize = 11.sp, modifier = Modifier.weight(1f))
                }
                HorizontalDivider(color = Color(0xFF2A2926))
            }
            exercise.sets.forEach { set ->
                Row(Modifier.fillMaxWidth().padding(vertical = if (export) 2.dp else 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("${set.number}", color = ResultMuted, fontSize = 12.sp, modifier = Modifier.width((if (export) 20 else 24).dp))
                    Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
                        Text(resultSetText(set.today, if (export) 10 else 11), color = ResultBone, fontSize = (if (export) 13 else 15).sp, fontWeight = FontWeight.Medium)
                        if (set.record) Text(" 최고", color = ResultMint, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    }
                    if (!export) Text(resultSetText(set.previous,11), color = ResultMuted, fontSize = 12.sp, modifier = Modifier.weight(1f))
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
