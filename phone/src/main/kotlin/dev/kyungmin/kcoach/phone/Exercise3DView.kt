package dev.kyungmin.kcoach.phone

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.view.MotionEvent
import android.view.ViewGroup
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import org.json.JSONObject
import kotlin.math.abs

/**
 * Plays the machine-viewer 3D rep for one exercise from the bundled assets/viewer3d page (three.js,
 * no network); [page] shows another bundled page instead, such as the statistics body figure. One finger drag turns the camera; a mostly vertical drag is left to the page scroll.
 */
@SuppressLint("SetJavaScriptEnabled", "ViewConstructor")
class Exercise3DView(
    context: Context, exerciseId: String, page: String? = null, background: Int = Color.rgb(52, 50, 46),
    /** A kept view is reused by its owner across screens: leaving the window only pauses it, [destroyNow] ends it. */
    private val keepAlive: Boolean = false,
) : FrameLayout(context) {
    private val web = WebView(context)
    private var fatigueJson: String? = null
    private var pageReady = false
    private var destroyed = false

    /** Keep the latest value even when Compose updates before the page finishes loading. */
    fun setFatigue(fatigue: Map<String, Double>) {
        val json = JSONObject(fatigue).toString()
        if (fatigueJson == json) return
        fatigueJson = json
        paintFatigue()
    }

    private fun paintFatigue() {
        if (pageReady && !destroyed) fatigueJson?.let { web.evaluateJavascript("window.setFatigue && window.setFatigue($it)", null) }
    }

    private var downX = 0f
    private var downY = 0f

    init {
        web.setBackgroundColor(background)
        web.settings.apply {
            javaScriptEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            domStorageEnabled = false
        }
        web.isVerticalScrollBarEnabled = false
        web.isHorizontalScrollBarEnabled = false
        web.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String) {
                if (destroyed) return
                pageReady = true
                paintFatigue()
            }

            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                if (request.url.host != HOST) return null
                val path = request.url.path.orEmpty().trimStart('/')
                return runCatching {
                    WebResourceResponse(mimeOf(path), null, context.assets.open("viewer3d/$path"))
                }.getOrElse { WebResourceResponse("text/plain", null, 404, "Not Found", emptyMap(), "".byteInputStream()) }
            }
        }
        web.setOnTouchListener { v, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { downX = e.x; downY = e.y }
                MotionEvent.ACTION_MOVE -> if (abs(e.x - downX) > abs(e.y - downY)) v.parent?.requestDisallowInterceptTouchEvent(true)
            }
            false
        }
        addView(web, LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        web.loadUrl(if (page != null) "https://$HOST/$page" else "https://$HOST/index.html?ex=$exerciseId")
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        if (keepAlive && !destroyed) web.onResume()
    }

    override fun onDetachedFromWindow() {
        super.onDetachedFromWindow()
        if (keepAlive) { if (!destroyed) web.onPause(); return }
        destroyNow()
    }

    /**
     * Tears the page down once. Rapid tab switching used to create and destroy a WebView several times a second, and a
     * destroy that raced a page still loading (or a callback arriving after it) could take the whole app down.
     */
    fun destroyNow() {
        if (destroyed) return
        destroyed = true
        web.stopLoading()
        web.webViewClient = WebViewClient()
        web.setOnTouchListener(null)
        removeView(web)
        web.destroy()
    }

    companion object {
        private const val HOST = "app3d.local"

        private fun mimeOf(path: String) = when (path.substringAfterLast('.', "")) {
            "html" -> "text/html"
            "js" -> "text/javascript"
            "json" -> "application/json"
            else -> "application/octet-stream"
        }

        private var ids: Set<String>? = null

        /** Exercises that have a bundled 3D model. */
        fun has(context: Context, exerciseId: String): Boolean {
            val known = ids ?: runCatching {
                JSONObject(context.assets.open("viewer3d/exercise_models.json").bufferedReader().use { it.readText() })
                    .keys().asSequence().toSet()
            }.getOrDefault(emptySet()).also { ids = it }
            return exerciseId in known
        }
    }
}
