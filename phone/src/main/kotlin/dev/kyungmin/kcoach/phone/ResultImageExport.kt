package dev.kyungmin.kcoach.phone

import android.app.Activity
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.Environment
import android.provider.MediaStore
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Hands a rendered result screen to the share sheet or the phone's gallery as a PNG. */
internal object ResultImageExport {
    private fun fileName(title: String): String {
        val safe = title.trim().replace(Regex("[\\\\/:*?\"<>|\\s]+"), "-").take(24).ifBlank { "운동" }
        return "워치짐-$safe-${SimpleDateFormat("yyyyMMdd-HHmmss-SSS", Locale.KOREA).format(Date())}"
    }

    fun share(context: Context, bitmap: Bitmap, title: String, targetPackage: String? = null, instagramStory: Boolean = false): Boolean = runCatching {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val file = File(dir, fileName(title) + ".png")
        FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.updates", file)
        val appInfo = context.packageManager.getApplicationInfo(context.packageName, android.content.pm.PackageManager.GET_META_DATA)
        val metaAppId = appInfo.metaData?.get("com.facebook.sdk.ApplicationId")?.let { value ->
            if (value is Int) runCatching { context.getString(value) }.getOrNull() else value.toString()
        }?.removePrefix("fb")?.takeIf { it.matches(Regex("[0-9]+")) }
        val directStory = instagramStory && metaAppId != null
        val send = Intent(if (directStory) "com.instagram.share.ADD_TO_STORY" else Intent.ACTION_SEND).apply {
            type = "image/png"
            if (directStory) setDataAndType(uri, "image/png") else putExtra(Intent.EXTRA_STREAM, uri)
            clipData = android.content.ClipData.newRawUri("운동 사진", uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            targetPackage?.let { setPackage(it); runCatching { context.grantUriPermission(it, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } }
            if (directStory) putExtra("source_application", metaAppId)
        }
        fun launch(intent: Intent) {
            context.startActivity(if (context is Activity) intent else intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        try { launch(if (targetPackage == null) Intent.createChooser(send, "운동 결과 공유") else send) }
        catch (_: android.content.ActivityNotFoundException) {
            launch(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                type = "image/png"; putExtra(Intent.EXTRA_STREAM, uri)
                clipData = android.content.ClipData.newRawUri("운동 사진", uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }, "운동 결과 공유"))
        }
        true
    }.getOrDefault(false)

    fun save(context: Context, bitmap: Bitmap, title: String): Boolean = runCatching {
        val resolver = context.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, fileName(title) + ".png")
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/워치짐")
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values) ?: error("image insert failed")
        try {
            resolver.openOutputStream(uri)?.use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) } ?: error("image stream missing")
            check(resolver.update(uri, ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }, null, null) > 0)
            true
        } catch (error: Exception) {
            resolver.delete(uri, null, null)
            throw error
        }
    }.getOrDefault(false)
}
