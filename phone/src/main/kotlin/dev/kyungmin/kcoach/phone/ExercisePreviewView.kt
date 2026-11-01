package dev.kyungmin.kcoach.phone

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.ImageDecoder
import android.graphics.drawable.AnimatedImageDrawable
import android.graphics.drawable.GradientDrawable
import android.view.ViewOutlineProvider
import android.util.LruCache
import android.widget.ImageView
import java.nio.ByteBuffer
import java.util.concurrent.Executors

/**
 * Small looping 3D previews for the exercise lists (assets/previews/<exerciseId>.webp, 192px, 24 frames).
 * The first frame is shown at once from a memory cache; the animation starts only for rows that stay on screen.
 * Live 3D (Exercise3DView) is for the detail screen only, never for a list row.
 */
object ExercisePreviews {
    private const val BG = 0xFF34322E.toInt()
    private val worker = Executors.newSingleThreadExecutor { Thread(it, "exercise-preview").apply { isDaemon = true } }
    private val bytes = object : LruCache<String, ByteArray>(4 * 1024 * 1024) {
        override fun sizeOf(key: String, value: ByteArray) = value.size
    }
    private val firstFrames = object : LruCache<String, Bitmap>(16 * 1024 * 1024) {
        override fun sizeOf(key: String, value: Bitmap) = value.byteCount
    }
    @Volatile private var known: Set<String>? = null

    fun has(context: Context, id: String): Boolean {
        val set = known ?: runCatching { context.assets.list("previews").orEmpty().map { it.removeSuffix(".webp") }.toSet() }
            .getOrDefault(emptySet()).also { known = it }
        return id in set
    }

    private fun load(context: Context, id: String): ByteArray? =
        bytes.get(id) ?: runCatching { context.assets.open("previews/$id.webp").use { it.readBytes() } }.getOrNull()?.also { bytes.put(id, it) }

    private fun decodeFirstFrame(context: Context, id: String): Bitmap? {
        val data = load(context, id) ?: return null
        return runCatching { ImageDecoder.decodeBitmap(ImageDecoder.createSource(ByteBuffer.wrap(data))) }.getOrNull()
            ?.also { firstFrames.put(id, it) }
    }

    /** Cached first frame, or a decode on the calling thread (about a millisecond for 192px). */
    fun firstFrame(context: Context, id: String): Bitmap? = firstFrames.get(id) ?: decodeFirstFrame(context, id)

    /** Reads and decodes the previews for these ids in the background, so scrolling finds them ready. */
    fun prefetch(context: Context, ids: Collection<String>) {
        val app = context.applicationContext
        ids.filter { has(app, it) && firstFrames.get(it) == null }.forEach { id -> worker.execute { if (firstFrames.get(id) == null) decodeFirstFrame(app, id) } }
        ids.filter { has(app, it) && bytes.get(it) == null }.forEach { id -> worker.execute { load(app, id) } }
    }

    /** Decodes a fresh animated drawable off the main thread; one per view, as sharing one decoder crashes. */
    fun animated(context: Context, id: String, ready: (AnimatedImageDrawable) -> Unit) {
        val app = context.applicationContext
        worker.execute {
            val data = load(app, id) ?: return@execute
            val drawable = runCatching { ImageDecoder.decodeDrawable(ImageDecoder.createSource(ByteBuffer.wrap(data))) }.getOrNull()
            if (drawable is AnimatedImageDrawable) ready(drawable)
        }
    }

    fun backgroundColor() = BG
}

/** One list thumbnail: still frame immediately, animation after the row has stayed on screen a moment. */
class ExercisePreviewView(context: Context, private val exerciseId: String) : ImageView(context) {
    private var attached = false
    private val startAnimation = Runnable {
        ExercisePreviews.animated(context, exerciseId) { drawable ->
            post {
                if (attached) {
                    setImageDrawable(drawable)
                    drawable.repeatCount = AnimatedImageDrawable.REPEAT_INFINITE
                    drawable.start()
                } else drawable.stop()
            }
        }
    }

    init {
        scaleType = ScaleType.CENTER_CROP
        background = GradientDrawable().apply { setColor(ExercisePreviews.backgroundColor()); cornerRadius = 12f * context.resources.displayMetrics.density }
        outlineProvider = ViewOutlineProvider.BACKGROUND
        clipToOutline = true
        ExercisePreviews.firstFrame(context, exerciseId)?.let { setImageBitmap(it) }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        attached = true
        postDelayed(startAnimation, START_DELAY_MS)
    }

    override fun onDetachedFromWindow() {
        attached = false
        removeCallbacks(startAnimation)
        (drawable as? AnimatedImageDrawable)?.stop()
        ExercisePreviews.firstFrame(context, exerciseId)?.let { setImageBitmap(it) }
        super.onDetachedFromWindow()
    }

    private companion object { const val START_DELAY_MS = 140L }
}
