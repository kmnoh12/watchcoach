package dev.kyungmin.kcoach.phone.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Renders the real result-screen composables (header numbers, heart card, exercise cards) with sample data. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w360dp-h900dp-xxhdpi")
class ResultScreenshotTest {
    @get:Rule
    val compose = createComposeRule()

    private fun set(n: Int, today: String, prev: String, record: Boolean = false) = ResultSet(n, today, prev, record)

    private val data = ResultPresentation(
        "등·이두", "2026년 11월 11일 수요일 · 오전 11:59", "11.11 WED", 62, "7,420",
        listOf(
            ResultExercise("랫풀다운", "55kg × 11회", "+3.2%", 1,
                listOf(set(1, "45kg × 12회", "45kg × 10회"), set(2, "50kg × 12회", "50kg × 11회"), set(3, "55kg × 11회", "55kg × 10회", true), set(4, "55kg × 10회", "55kg × 9회")),
                ResultTempo("2.4초", 1, "후반 +12%"), "추정 1RM 72 → 74kg"),
            ResultExercise("시티드 로우", "50kg × 12회", "유지", 0,
                listOf(set(1, "50kg × 12회", "50kg × 12회"), set(2, "50kg × 12회", "50kg × 12회"), set(3, "50kg × 10회", "50kg × 10회")),
                ResultTempo("2.9초", 0, null), "추정 1RM 70 → 70kg"),
            ResultExercise("케이블 컬", "22.5kg × 10회", "+2.5kg", 1,
                listOf(set(1, "22.5kg × 10회", "20kg × 10회", true), set(2, "22.5kg × 9회", "20kg × 10회"), set(3, "17.5kg × 10회", "20kg × 9회")), null, null),
            ResultExercise("플랭크", "60초", "+10초", 1, listOf(set(1, "60초", "50초"), set(2, "50초", "50초")), null, null),
        ),
        "평균 심박 128 · 최고 156 · 약 310kcal", 1,
        "128", "156", "310",
        (0 until 120).map { i -> (i * 30_000L) to (112 + (22 * Math.sin(i / 14.0)).toInt() + (i / 8) + (i % 7)) },
    )

    @Test
    fun resultScreen() {
        compose.setContent {
            Column(Modifier.fillMaxWidth().background(Color.Black).padding(horizontal = 16.dp)) {
                Text("✕", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(vertical = 4.dp))
                Spacer(Modifier.height(4.dp))
                Column(Modifier.fillMaxWidth().height(132.dp).clip(RoundedCornerShape(10.dp)).background(Color(0xFF3A3833))) {
                    Text("오운완 사진 남기기", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(12.dp))
                }
                Spacer(Modifier.height(18.dp))
                Text("등·이두 완료", color = ResultBone, fontSize = 26.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(12.dp))
                ResultNumbers(data)
                Column(Modifier.padding(top = 8.dp, bottom = 4.dp).fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(Color(0xFF0F2A22)).padding(13.dp, 11.dp)) {
                    Text(data.verdict, color = ResultMint, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                    Text(data.comparison, color = ResultMuted, fontSize = 12.sp)
                }
                data.exercises.forEachIndexed { i, e -> ExerciseResultCard(e, initiallyExpanded = i == 0) }
            }
        }
        compose.onRoot().captureRoboImage("build/outputs/roborazzi/result_screen.png")
    }
}
