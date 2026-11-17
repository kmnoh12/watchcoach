package dev.kyungmin.watchcoach.phone

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import dev.kyungmin.watchcoach.core.ProgressionSettings
import dev.kyungmin.watchcoach.phone.ui.ChoiceSheet
import dev.kyungmin.watchcoach.phone.ui.Overlay
import dev.kyungmin.watchcoach.phone.ui.OverlayHost
import dev.kyungmin.watchcoach.phone.ui.OverlayState
import dev.kyungmin.watchcoach.phone.ui.SettingsActions
import dev.kyungmin.watchcoach.phone.ui.SettingsScreen

class SettingsActivity : ComponentActivity() {
    private val saveDiagnostics = registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri ->
        if (uri != null) lifecycleScope.launch {
            val saved = withContext(Dispatchers.IO) {
                runCatching {
                    val output = contentResolver.openOutputStream(uri, "wt") ?: error("Cannot open selected document")
                    output.use { DiagnosticsExport.write(applicationContext, it) }
                }
            }
            Toast.makeText(this@SettingsActivity,
                if (saved.isSuccess) "오류 기록 저장 완료. 저장한 ZIP 파일을 채팅에 첨부해 주세요."
                else "오류 기록 저장 실패. 저장 위치를 바꿔 다시 시도해 주세요.", Toast.LENGTH_LONG).show()
        }
    }

    private val saveSensorLogs = registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri ->
        if (uri != null) lifecycleScope.launch {
            val saved = withContext(Dispatchers.IO) {
                runCatching {
                    val output = contentResolver.openOutputStream(uri, "wt") ?: error("Cannot open selected document")
                    output.use {
                        CaptureInbox(applicationContext, applicationContext.getSharedPreferences("wear-sync", MODE_PRIVATE)).exportAll(it)
                    }
                }
            }
            Toast.makeText(this@SettingsActivity,
                saved.getOrNull()?.let { "센서 기록 ${it}개 저장 완료. 저장한 ZIP 파일을 채팅에 첨부해 주세요." }
                    ?: "센서 기록 저장 실패. 저장 위치를 바꿔 다시 시도해 주세요.", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val actions = SettingsActions(back = ::finish,
            tempo = { startActivity(Intent(this, WorkoutTempoSettingsActivity::class.java)) },
            posture = { startActivity(Intent(this, WorkoutPostureActivity::class.java)) },
            profile = { startActivity(Intent(this, WorkoutProfileActivity::class.java)) },
            diagnostics = { saveDiagnostics.launch("watchcoach-errors-${System.currentTimeMillis()}.zip") },
            sensorLogs = { saveSensorLogs.launch("watchcoach-sensor-logs-${System.currentTimeMillis()}.zip") })
        val store = ProgressionSettingsStore(this)
        val progression = store.load().getOrElse {
            Log.w("WatchCoachEvent", "progression settings unreadable; using defaults", it)
            ProgressionSettings()
        }
        setContent {
            val overlays = remember { OverlayState() }
            var restSeconds by remember { mutableStateOf(RestMuscleGroup.entries.associateWith {
                DefaultRestSetting.seconds(this@SettingsActivity, it)
            }) }
            Box {
                SettingsScreen(
                    actions = actions,
                    progression = progression,
                    personalization = PersonalizationSetting.isEnabled(this@SettingsActivity),
                    onPersonalizationChange = { on ->
                        if (PersonalizationSetting.setEnabled(this@SettingsActivity, on)) PersonalizationSetting.pushToWatch(this@SettingsActivity)
                        else Toast.makeText(this@SettingsActivity, "설정 저장 실패. 다시 시도해 주세요.", Toast.LENGTH_LONG).show()
                    },
                    oneArmOnly = OneArmSetting.isEnabled(this@SettingsActivity),
                    onOneArmOnlyChange = { on ->
                        if (!OneArmSetting.setEnabled(this@SettingsActivity, on))
                            Toast.makeText(this@SettingsActivity, "설정 저장 실패. 다시 시도해 주세요.", Toast.LENGTH_LONG).show()
                    },
                    manualAutoFinish = ManualAutoFinishSetting.isEnabled(this@SettingsActivity),
                    onManualAutoFinishChange = { on -> ManualAutoFinishSetting.setEnabled(this@SettingsActivity, on) },
                    restSeconds = restSeconds,
                    onRestClick = { group ->
                        overlays.show(Overlay(true) { dismiss ->
                            ChoiceSheet(
                                title = "${group.label} 기본 휴식 시간",
                                items = DefaultRestSetting.choices.map { "${it}초" to "" },
                                selected = "${restSeconds.getValue(group)}초",
                            ) { value ->
                                val seconds = value.removeSuffix("초").toInt()
                                if (DefaultRestSetting.save(this@SettingsActivity, group, seconds)) {
                                    restSeconds = restSeconds + (group to seconds)
                                    dismiss()
                                } else {
                                    Toast.makeText(this@SettingsActivity, "설정 저장 실패. 다시 시도해 주세요.", Toast.LENGTH_LONG).show()
                                }
                            }
                        })
                    },
                    onProgressionChange = { next ->
                        store.save(next).onFailure { Log.e("WatchCoachEvent", "progression settings not saved", it) }
                    },
                )
                OverlayHost(overlays)
            }
        }
    }
}
