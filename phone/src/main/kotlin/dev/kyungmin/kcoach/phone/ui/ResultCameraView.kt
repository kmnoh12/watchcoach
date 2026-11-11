package dev.kyungmin.kcoach.phone.ui

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.*
import android.os.Build
import android.os.SystemClock
import android.view.MotionEvent
import android.view.ViewGroup
import android.view.animation.PathInterpolator
import android.widget.FrameLayout
import android.widget.Toast
import androidx.camera.core.*
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import dev.kyungmin.kcoach.phone.ResultImageExport
import java.util.concurrent.Executors
import kotlin.math.*

/** One PreviewView survives the card/fullscreen transition. No camera rebind occurs on opening. */
internal class ResultCameraView(context: Context, private val owner: LifecycleOwner) : FrameLayout(context) {
    private val d = resources.displayMetrics.density
    private val preview = PreviewView(context).apply {
        implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        scaleType = PreviewView.ScaleType.FILL_CENTER
    }
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val worker = Executors.newSingleThreadExecutor()
    private val main = ContextCompat.getMainExecutor(context)
    private var provider: ProcessCameraProvider? = null
    private var capture: ImageCapture? = null
    private var camera: androidx.camera.core.Camera? = null
    private var focusAt = 0L
    private var focusX = 0f
    private var focusY = 0f
    private var ownUseCases: List<UseCase> = emptyList()
    private var front = false
    private var released = false
    private var binding = false
    private var progress = 0f
    private var blur = 1f
    private var controls = 0f
    private var ratio = 0
    private var ratioMotion = 0f
    private var frameRatio = ResultPhotoRatio.PORTRAIT.frameHeight
    private var imageRatio = ResultPhotoRatio.PORTRAIT.imageWidth
    private var safeRatio = ResultPhotoRatio.PORTRAIT.safeHeight
    private var opening = false
    private var animation: ValueAnimator? = null
    private var ratioAnimation: ValueAnimator? = null
    private var flashAt = 0L
    private var taking = false
    private var shotAt = 0L
    private var photoSaved = false
    private var exporting = false
    private var photo: Bitmap? = null
    private var sample: Bitmap? = null
    private var sampleAt = 0L
    private var toneSampleAt = 0L
    private var blurredSample: Bitmap? = null
    private var closeSample: Bitmap? = null
    private var galleryThumb: Bitmap? = null
    private val tones = FloatArray(3) { 1f }
    private val targetTones = FloatArray(3) { 1f }
    private val startTones = FloatArray(3) { 1f }
    private var toneAt = 0L
    private val curve = PathInterpolator(.2f, .8f, .2f, 1f)
    private val frame = RectF()
    private val clipPath = Path()
    private val taps = mutableListOf<Pair<RectF, () -> Unit>>()
    var onClosed: () -> Unit = {}
    var onGallery: () -> Unit = {}
    var presentation: ResultPresentation? = null
    var cardBounds: androidx.compose.ui.geometry.Rect = androidx.compose.ui.geometry.Rect.Zero
        set(value) { field = value; invalidate(); requestLayout() }
    var cardFade = 0f
        set(value) { field = value; invalidate() }

    init { setWillNotDraw(false); addView(preview, LayoutParams(1, 1)) }

    fun bind() {
        if (released || binding) return
        binding = true
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            binding = false
            if (!released) runCatching {
                val p = future.get(); provider = p
                if (ownUseCases.isNotEmpty()) p.unbind(*ownUseCases.toTypedArray())
                fun resolution(width: Int, height: Int) = ResolutionSelector.Builder()
                    .setAspectRatioStrategy(AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY)
                    .setResolutionStrategy(ResolutionStrategy(android.util.Size(width,height), ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER)).build()
                val live = Preview.Builder().setResolutionSelector(resolution(1280,960)).build().also { it.surfaceProvider = preview.surfaceProvider }
                capture = ImageCapture.Builder().setResolutionSelector(resolution(1920,1440)).setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build()
                ownUseCases = listOf(live, capture!!)
                val group = UseCaseGroup.Builder().addUseCase(live).addUseCase(capture!!)
                    .setViewPort(ViewPort.Builder(android.util.Rational(3, 4), android.view.Surface.ROTATION_0).build()).build()
                focusAt = 0L
                camera = p.bindToLifecycle(owner, if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA, group)
            }.onFailure { toast("카메라를 열지 못했어요") }
        }, main)
    }

    fun release() {
        released = true; animation?.cancel(); ratioAnimation?.cancel()
        provider?.unbind(*ownUseCases.toTypedArray()); worker.shutdown()
        photo?.recycle(); sample?.recycle(); blurredSample?.recycle(); closeSample?.recycle(); galleryThumb?.recycle()
    }

    fun open() {
        if (opening) return
        opening = true
        ratioAnimation?.cancel(); ratio = 0; ratioMotion = 0f; frameRatio = 16/9f; imageRatio = 4/3f; safeRatio = 4/3f
        animateOpen(true)
    }
    fun close() {
        if (!opening) return
        ratioAnimation?.cancel(); ratio = 0; ratioMotion = 0f; frameRatio = 16/9f; imageRatio = 4/3f; safeRatio = 4/3f
        animateOpen(false)
    }
    private fun animateOpen(forward: Boolean) {
        animation?.cancel()
        val from = progress
        animation = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 460
            interpolator = android.view.animation.LinearInterpolator()
            addUpdateListener {
                val t = it.animatedValue as Float
                progress = from + ((if (forward) 1f else 0f) - from) * curve.getInterpolation(t)
                blur = if (forward) 1 - ((t * 460 - 150) / 300).coerceIn(0f, 1f) else (t * 460 / 300).coerceIn(0f, 1f)
                controls = if (forward) ((t * 460 - 280) / 180).coerceIn(0f, 1f) else 1 - (t * 460 / 280).coerceIn(0f, 1f)
                if (Build.VERSION.SDK_INT >= 31) preview.setRenderEffect(if (blur > .001f) RenderEffect.createBlurEffect(16 * d * blur, 16 * d * blur, Shader.TileMode.CLAMP) else null)
                requestLayout(); invalidate()
                if (t == 1f && !forward) { opening = false; photo?.recycle(); photo = null; front = false; bind(); onClosed() }
            }
            start()
        }
    }

    private fun chooseRatio(index: Int) {
        ratio = index
        ratioAnimation?.cancel()
        val target = ResultPhotoRatio.entries[index]
        val startTab = ratioMotion
        val startFrame = frameRatio
        val startImage = imageRatio
        val startSafe = safeRatio
        ratioAnimation = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 420; interpolator = curve
            addUpdateListener {
                val t = it.animatedValue as Float
                ratioMotion = mix(startTab, index.toFloat(), t)
                frameRatio = mix(startFrame, target.frameHeight, t)
                imageRatio = mix(startImage, target.imageWidth, t)
                safeRatio = mix(startSafe, target.safeHeight, t)
                requestLayout(); invalidate()
            }; start()
        }
    }
    private fun mix(a: Float, b: Float, t: Float) = a + (b - a) * t
    private fun geometry(): Pair<RectF, RectF> {
        val w = measuredWidth - 22 * d
        // Preserve the reference's 9:16 stage; scale the complete camera composition on short screens.
        val scale = min(1f, (measuredHeight - ResultCameraTop * d - ResultCameraControls * d) / (w * 16 / 9)).coerceAtLeast(.1f)
        val fw = w * scale
        val stageHeight = fw * 16 / 9
        val top = ResultCameraTop * d
        val fh = fw * frameRatio
        val full = RectF((measuredWidth - fw) / 2, top + (stageHeight - fh) / 2, (measuredWidth + fw) / 2, top + (stageHeight + fh) / 2)
        val dx = cardBounds.left - full.left
        val dy = cardBounds.top - (top + (stageHeight - stageHeight) / 2)
        val factor = if (full.width() > 0 && cardBounds.width > 0) cardBounds.width / full.width() else 1f
        val f = mix(factor, 1f, progress)
        frame.set(full.left + dx * (1 - progress), full.top + dy * (1 - progress), 0f, 0f)
        frame.right = frame.left + fw * f; frame.bottom = frame.top + fh * f
        val iw = fw * imageRatio * f
        val ih = iw * 4 / 3
        return frame to RectF(frame.centerX() - iw / 2, frame.centerY() - ih / 2, frame.centerX() + iw / 2, frame.centerY() + ih / 2)
    }
    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        setMeasuredDimension(MeasureSpec.getSize(widthMeasureSpec), MeasureSpec.getSize(heightMeasureSpec))
        val (_, image) = geometry()
        preview.measure(MeasureSpec.makeMeasureSpec(image.width().roundToInt().coerceAtLeast(1), MeasureSpec.EXACTLY), MeasureSpec.makeMeasureSpec(image.height().roundToInt().coerceAtLeast(1), MeasureSpec.EXACTLY))
    }
    override fun onLayout(changed: Boolean, l: Int, t: Int, r: Int, b: Int) {
        val (_, image) = geometry()
        preview.layout(image.left.roundToInt(), image.top.roundToInt(), image.right.roundToInt(), image.bottom.roundToInt())
        if (!opening && Build.VERSION.SDK_INT >= 31) preview.setRenderEffect(RenderEffect.createBlurEffect(16 * d, 16 * d, Shader.TileMode.CLAMP))
    }
    override fun dispatchDraw(canvas: Canvas) {
        if (width == 0 || cardBounds.width == 0f) return
        taps.clear()
        val (f, image) = geometry()
        refreshSample(image.width())
        val cardShift = cardFade * 10 * d
        val cardScale = 1 - cardFade * .04f
        val card = RectF(cardBounds.left + cardBounds.width * (1 - cardScale) / 2, cardBounds.top + cardShift,
            cardBounds.right - cardBounds.width * (1 - cardScale) / 2, cardBounds.top + cardShift + cardBounds.height * cardScale)
        val reveal = RectF(mix(card.left, 0f, progress), mix(card.top, 0f, progress), mix(card.right, width.toFloat(), progress), mix(card.bottom, height.toFloat(), progress))
        val save = canvas.saveLayerAlpha(0f, 0f, width.toFloat(), height.toFloat(), (255 * mix(1 - cardFade, 1f, progress)).toInt())
        clipPath.reset(); clipPath.addRoundRect(reveal, ResultCameraRadius * d * (1 - progress), ResultCameraRadius * d * (1 - progress), Path.Direction.CW); canvas.clipPath(clipPath)
        if (progress > 0) canvas.drawColor(Color.BLACK)
        val clipped = canvas.save()
        clipPath.reset(); clipPath.addRoundRect(f, ResultCameraRadius * d, ResultCameraRadius * d, Path.Direction.CW); canvas.clipPath(clipPath)
        canvas.drawColor(Color.rgb(17, 17, 17))
        if (photo == null) super.dispatchDraw(canvas) else canvas.drawBitmap(photo!!, null, image, paint.apply { alpha = 255 })
        if (blur > 0 && (Build.VERSION.SDK_INT < 31 || photo != null)) blurredSample?.let {
            canvas.drawBitmap(it, null, image, paint.apply { alpha = (255 * blur).toInt() })
        }
        // The dim is removed across the whole frame at once, after the specified 150 ms delay.
        canvas.drawColor(Color.argb((255 * .45f * blur).toInt(), 0, 0, 0))
        if (controls > 0) {
            val sw = f.width()
            val safeHeight = sw * safeRatio
            val safe = RectF(f.left, f.centerY() - safeHeight / 2, f.right, f.centerY() + safeHeight / 2)
            updateTones(image, safe)
            RecordBitmapRenderer().draw(canvas, safe, presentation, tones, controls)
        }
        val elapsed = SystemClock.uptimeMillis() - flashAt
        if (elapsed in 0..300 && flashAt != 0L) canvas.drawColor(Color.argb((204 * if (elapsed < 45) elapsed / 45f else (300 - elapsed) / 255f).toInt().coerceIn(0, 255), 255, 255, 255))
        drawFocus(canvas)
        canvas.restoreToCount(clipped)
        if (controls > 0) drawControls(canvas, f)
        canvas.restoreToCount(save)
        if (opening || progress > 0 || cardFade < 1) postInvalidateDelayed(33)
    }

    private fun text(canvas: Canvas, value: String, x: Float, y: Float, size: Float, color: Int, bold: Boolean = false, right: Boolean = false, opacity: Float = 1f) {
        paint.apply { this.color = color; alpha = (255 * opacity).toInt(); textSize = size; typeface = if (bold) Typeface.create("sans-serif", Typeface.BOLD) else Typeface.create("sans-serif", Typeface.NORMAL); textAlign = if (right) Paint.Align.RIGHT else Paint.Align.LEFT; style = Paint.Style.FILL }
        canvas.drawText(value, x, y - paint.fontMetrics.ascent, paint)
    }
    private fun ink(t: Float): Int { val v = (11 + (255 - 11) * t).toInt().coerceIn(0,255); return Color.rgb(v, v, (10 + 245 * t).toInt().coerceIn(0,255)) }
    @Suppress("DEPRECATION")
    private fun blurred(bitmap: Bitmap, radius: Float): Bitmap {
        val rs = android.renderscript.RenderScript.create(context)
        val input = android.renderscript.Allocation.createFromBitmap(rs, bitmap)
        val output = android.renderscript.Allocation.createTyped(rs, input.type)
        val script = android.renderscript.ScriptIntrinsicBlur.create(rs, android.renderscript.Element.U8_4(rs))
        return try {
            val result = Bitmap.createBitmap(bitmap.width, bitmap.height, Bitmap.Config.ARGB_8888)
            script.setRadius(radius.coerceIn(.1f,25f)); script.setInput(input); script.forEach(output); output.copyTo(result)
            result
        } finally { script.destroy(); output.destroy(); input.destroy(); rs.destroy() }
    }
    private fun refreshSample(imageWidth: Float) {
        val now = SystemClock.uptimeMillis()
        if (now - sampleAt < 333) return
        sampleAt = now
        val raw = photo ?: preview.bitmap ?: return
        val scaled = Bitmap.createScaledBitmap(raw,72,96,false)
        val small = if (scaled === raw) scaled.copy(Bitmap.Config.ARGB_8888,false) else scaled
        if (raw !== photo && raw !== small) raw.recycle()
        sample?.recycle(); sample = small
        blurredSample?.recycle(); closeSample?.recycle()
        blurredSample = runCatching { blurred(small,16*d*72/imageWidth.coerceAtLeast(1f)) }.getOrNull()
        closeSample = runCatching { blurred(small,12*d*72/imageWidth.coerceAtLeast(1f)) }.getOrNull()
    }

    private fun updateTones(image: RectF, safe: RectF) {
        val now = SystemClock.uptimeMillis()
        if (now - toneSampleAt > 333) {
            toneSampleAt = now
            val bitmap = sample ?: return
            val areas = RecordBitmapRenderer().regions(safe, presentation ?: return)
            val nextTones = FloatArray(3)
            areas.forEachIndexed { i, area ->
                var sum = 0.0; var n = 0
                for (yy in 0 until 96) for (xx in 0 until 72) {
                    if (area.contains(image.left+(xx+.5f)/72*image.width(),image.top+(yy+.5f)/96*image.height())) {
                        val p = bitmap.getPixel(xx,yy); sum += .2126*Color.red(p)+.7152*Color.green(p)+.0722*Color.blue(p); n++
                    }
                }
                nextTones[i] = if (n > 0 && sum/n > 150) 0f else 1f
            }
            if (!nextTones.contentEquals(targetTones)) {
                startTones.indices.forEach { startTones[it] = tones[it]; targetTones[it] = nextTones[it] }
                toneAt = now
            }
        }
        val t = curve.getInterpolation(((now-toneAt)/420f).coerceIn(0f,1f))
        tones.indices.forEach { tones[it] = mix(startTones[it],targetTones[it],t) }
    }

    private fun drawControls(c: Canvas, f: RectF) {
        val stageBottom = ResultCameraTop*d + (width-22*d)*min(1f,(height-(ResultCameraTop+ResultCameraControls)*d)/((width-22*d)*16/9))*16/9
        val tabsY = stageBottom+10*d
        val center = width/2f
        val labels = listOf("9:16","1:1","3:4")
        // Reference track: each tab is its text width + 4dp, 24dp apart, and the chosen tab's centre sits on the screen centre.
        paint.textSize=13*d; paint.typeface=Typeface.create("sans-serif", Typeface.BOLD)
        val widths = labels.map { paint.measureText(it) + 4*d }
        val centres = widths.indices.map { i -> widths.take(i).sum() + 24*d*i + widths[i]/2 }
        val lo = ratioMotion.toInt().coerceIn(0, labels.size-1); val hi = (lo+1).coerceAtMost(labels.size-1)
        val shift = center - (centres[lo] + (centres[hi]-centres[lo])*(ratioMotion-lo))
        labels.forEachIndexed { i,label ->
            val x = shift+centres[i]
            text(c,label,x-(widths[i]-4*d)/2,tabsY,13*d,if (ratio==i) Color.WHITE else Color.rgb(143,139,130),true,opacity=controls)
            taps += RectF(x-widths[i]/2-12*d,tabsY-4*d,x+widths[i]/2+12*d,tabsY+30*d) to { chooseRatio(i) }
        }
        paint.color=Color.rgb(118,219,185); paint.alpha=(255*controls).toInt(); c.drawCircle(center,tabsY+28*d,2*d,paint)
        val cy = tabsY+40*d+35*d
        fun circle(x: Float, radius: Float, color: Int, atY: Float = cy, opacity: Float = controls) { paint.color=color; paint.alpha=(255*opacity).toInt(); paint.style=Paint.Style.FILL; c.drawCircle(x,atY,radius*d,paint) }
        val closeRect = RectF(f.left+11*d,f.top+10*d,f.left+48.4f*d,f.top+47.4f*d)
        val closeSave = c.save()
        clipPath.reset(); clipPath.addRoundRect(closeRect,18.7f*d,18.7f*d,Path.Direction.CW); c.clipPath(clipPath)
        val (_, image) = geometry()
        val backdrop = c.save(); c.clipRect(frame)
        closeSample?.let { c.drawBitmap(it,null,image,paint.apply { alpha = (255*controls).toInt() }) }
        c.restoreToCount(backdrop)
        c.drawColor(Color.argb((255*.45f*controls).toInt(),0,0,0)); c.restoreToCount(closeSave)
        paint.color=Color.WHITE; paint.alpha=(255*controls).toInt(); paint.strokeWidth=2*d; paint.strokeCap=Paint.Cap.ROUND
        val cc=closeRect.centerX(); val yy=closeRect.centerY()
        if (photo == null) {
            val a=17.6f*d*9/32
            c.drawLine(cc-a,yy-a,cc+a,yy+a,paint); c.drawLine(cc+a,yy-a,cc-a,yy+a,paint)
            taps += closeRect to { close() }
            circle(center,35f,Color.WHITE); circle(center,31f,Color.BLACK); circle(center,28f,Color.WHITE)
            taps += RectF(center-40*d,cy-40*d,center+40*d,cy+40*d) to { shoot() }
            val left=55*d; val thumb=RectF(left-21*d,cy-21*d,left+21*d,cy+21*d)
            paint.color=Color.rgb(28,27,25); c.drawRoundRect(thumb,10*d,10*d,paint)
            val thumbSave = c.save(); clipPath.reset();clipPath.addRoundRect(thumb,10*d,10*d,Path.Direction.CW);c.clipPath(clipPath)
            galleryThumb?.let { c.drawBitmap(it,null,thumb,paint.apply { alpha=255 }) }
                ?: drawIcon(c,5,left,cy,22*d,Color.WHITE,controls)
            c.restoreToCount(thumbSave)
            paint.color=Color.argb((217*controls).toInt(),255,255,255);paint.style=Paint.Style.STROKE;paint.strokeWidth=2*d;c.drawRoundRect(thumb,10*d,10*d,paint);paint.style=Paint.Style.FILL
            taps += thumb to { onGallery() }
            val right=width-55*d; circle(right,21f,Color.rgb(28,27,25)); drawIcon(c, 4, right, cy, 20*d, Color.rgb(237,232,220), controls)
            taps += RectF(right-25*d,cy-25*d,right+25*d,cy+25*d) to { if (!taking) { front=!front; bind() } }
        } else {
            // Retake: the same smoked circle as close, with a counter-clockwise arrow in it.
            // Thick counter-clockwise ring (butt ends) from -51° to 15°, with an upward filled head standing on the ring at 19°.
            val r=9f*d; val oldCap=paint.strokeCap; val oldW=paint.strokeWidth
            paint.style=Paint.Style.STROKE; paint.strokeWidth=3.6f*d; paint.strokeCap=Paint.Cap.BUTT
            c.drawArc(RectF(cc-r,yy-r,cc+r,yy+r),-51f,-294f,false,paint)
            paint.strokeWidth=oldW; paint.strokeCap=oldCap
            val endA=Math.toRadians(19.0)
            val ex=cc+r*kotlin.math.cos(endA).toFloat(); val ey=yy+r*kotlin.math.sin(endA).toFloat()
            clipPath.reset(); clipPath.moveTo(ex,ey-8f*d); clipPath.lineTo(ex-4.5f*d,ey); clipPath.lineTo(ex+4.5f*d,ey); clipPath.close()
            paint.style=Paint.Style.FILL; c.drawPath(clipPath,paint)
            paint.style=Paint.Style.FILL
            taps += closeRect to { if (!exporting) { photo?.recycle();photo=null;photoSaved=false;sampleAt=0;invalidate() } }
            listOf("사진 저장","인스타 스토리","카카오톡","더보기").forEachIndexed { i,label ->
                val x=width*(i+.5f)/4
                val pop = curve.getInterpolation(((SystemClock.uptimeMillis()-shotAt-i*30)/280f).coerceIn(0f,1f))
                val actionY = cy+10*d*(1-pop)
                val opacity = controls*pop
                circle(x,27f,if(i==0) Color.rgb(118,219,185) else Color.rgb(28,27,25),actionY,opacity)
                drawIcon(c,if(i==0 && photoSaved) 6 else i,x,actionY,22*d,if(i==0) Color.rgb(4,20,14) else Color.rgb(237,232,220),opacity)
                paint.textSize=11*d; paint.typeface=Typeface.DEFAULT
                text(c,label,x-paint.measureText(label)/2,actionY+34*d,11*d,Color.rgb(237,232,220),right=false,opacity=opacity)
                taps += RectF(x-width/8,cy-30*d,x+width/8,cy+60*d) to { export(i) }
            }
        }
    }
    private fun drawIcon(c: Canvas, kind: Int, x: Float, y: Float, size: Float, color: Int, opacity: Float) {
        val state = c.save(); c.translate(x-size/2,y-size/2); c.scale(size/24,size/24)
        val p = Paint(Paint.ANTI_ALIAS_FLAG).apply { this.color=color; alpha=(255*opacity).toInt(); style=Paint.Style.STROKE;strokeWidth=2f;strokeCap=Paint.Cap.ROUND;strokeJoin=Paint.Join.ROUND }
        fun path(vararg points: Float) { val q=Path();q.moveTo(points[0],points[1]);for(i in 2 until points.size step 2)q.lineTo(points[i],points[i+1]);c.drawPath(q,p) }
        when(kind) {
            0 -> { path(12f,4f,12f,15f);path(7f,10f,12f,15f,17f,10f);path(5f,20f,19f,20f) }
            1 -> { c.drawRoundRect(4f,4f,20f,20f,5f,5f,p);c.drawCircle(12f,12f,3.6f,p) }
            2 -> { val q=Path();q.moveTo(12f,5f);q.cubicTo(7.6f,5f,4f,7.7f,4f,11f);q.cubicTo(4f,13f,5.4f,14.8f,7.6f,15.9f);q.lineTo(6.7f,20f);q.lineTo(11.2f,17f);q.lineTo(12f,17f);q.cubicTo(16.4f,17f,20f,14.3f,20f,11f);q.cubicTo(20f,7.7f,16.4f,5f,12f,5f);c.drawPath(q,p) }
            3 -> { c.drawCircle(6f,12f,2f,p);c.drawCircle(18f,6f,2f,p);c.drawCircle(18f,18f,2f,p);path(8f,11f,16f,7f);path(8f,13f,16f,17f) }
            4 -> { c.drawArc(4f,3f,20f,19f,180f,150f,false,p);path(4f,3f,4f,8f,9f,8f);c.drawArc(4f,5f,20f,21f,0f,150f,false,p);path(20f,21f,20f,16f,15f,16f) }
            6 -> path(5f,12.5f,9.5f,17f,19f,7.5f)
            5 -> { c.drawRoundRect(3f,4f,21f,20f,2f,2f,p);c.drawCircle(8f,9f,1.5f,p);path(4f,18f,10f,12f,14f,16f,17f,13f,21f,17f) }
        }
        c.restoreToCount(state)
    }
    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (!opening) return false
        if (event.action == MotionEvent.ACTION_UP) {
            val hit = taps.lastOrNull { it.first.contains(event.x,event.y) }
            if (hit != null) hit.second.invoke() else focusAtPoint(event.x, event.y)
        }
        return true
    }
    /** Tap-to-focus like a camera app: autofocus, exposure and white balance are metered at the tapped point. */
    private fun focusAtPoint(x: Float, y: Float) {
        if (photo != null || taking || controls < 1f || !frame.contains(x, y)) return
        val cam = camera ?: return
        runCatching {
            val point = preview.meteringPointFactory.createPoint(x - preview.left, y - preview.top)
            val action = FocusMeteringAction.Builder(point, FocusMeteringAction.FLAG_AF or FocusMeteringAction.FLAG_AE or FocusMeteringAction.FLAG_AWB)
                .setAutoCancelDuration(4, java.util.concurrent.TimeUnit.SECONDS).build()
            cam.cameraControl.startFocusAndMetering(action)
            focusX = x; focusY = y; focusAt = SystemClock.uptimeMillis(); invalidate()
        }
    }
    private fun drawFocus(c: Canvas) {
        if (focusAt == 0L || photo != null) return
        val t = SystemClock.uptimeMillis() - focusAt
        if (t > 1100) { focusAt = 0L; return }
        val settle = curve.getInterpolation((t / 220f).coerceIn(0f, 1f))
        val alpha = if (t < 700) 1f else 1f - (t - 700) / 400f
        val r = 31f * d * (1.3f - .3f * settle)
        paint.style = Paint.Style.STROKE; paint.strokeWidth = 1.6f * d; paint.color = Color.rgb(255, 255, 255); paint.alpha = (255 * alpha).toInt()
        c.drawCircle(focusX, focusY, r, paint)
        paint.style = Paint.Style.FILL; paint.alpha = (255 * alpha * .9f).toInt(); c.drawCircle(focusX, focusY, 2.2f * d, paint)
        postInvalidateOnAnimation()
    }
    private fun shoot() {
        val camera = capture ?: return
        if (taking) return
        taking = true
        camera.takePicture(worker, object : ImageCapture.OnImageCapturedCallback() {
            override fun onCaptureSuccess(image: ImageProxy) {
                val result = runCatching {
                    val raw = image.toBitmap()
                    val matrix = Matrix().apply { postRotate(image.imageInfo.rotationDegrees.toFloat()); if(front) postScale(-1f,1f) }
                    val rotated = Bitmap.createBitmap(raw,0,0,raw.width,raw.height,matrix,true)
                    val normalized = normalize(rotated)
                    if (rotated !== normalized) rotated.recycle(); if (raw !== rotated && raw !== normalized) raw.recycle()
                    normalized
                }
                image.close()
                main.execute { taking=false; result.onSuccess { if(released) it.recycle() else { photo?.recycle(); photo=it; photoSaved=false;shotAt=SystemClock.uptimeMillis();sampleAt=0; galleryThumb?.recycle();galleryThumb=thumbnail(it);flashAt=SystemClock.uptimeMillis();invalidate() } }.onFailure { toast("촬영하지 못했어요") } }
            }
            override fun onError(exception: ImageCaptureException) { main.execute { taking=false;toast("촬영하지 못했어요") } }
        })
    }
    fun importPhoto(bitmap: Bitmap) { photo?.recycle(); photo=normalize(bitmap);photoSaved=false;shotAt=SystemClock.uptimeMillis();sampleAt=0; galleryThumb?.recycle();galleryThumb=thumbnail(photo!!);if(photo !== bitmap) bitmap.recycle(); invalidate() }
    private fun thumbnail(bitmap: Bitmap): Bitmap {
        val scaled=Bitmap.createScaledBitmap(bitmap,84,112,false)
        return if (scaled === bitmap) scaled.copy(Bitmap.Config.ARGB_8888,false) else scaled
    }
    private fun normalize(bitmap: Bitmap): Bitmap {
        val w=min(bitmap.width,bitmap.height*3/4); val h=w*4/3
        return Bitmap.createBitmap(bitmap,(bitmap.width-w)/2,(bitmap.height-h)/2,w,h)
    }
    private fun export(target: Int) {
        if (exporting || ratioAnimation?.isRunning == true) return
        val source=photo?.copy(Bitmap.Config.ARGB_8888,false) ?: return
        val data=presentation ?: run { source.recycle(); return }
        exporting=true
        val selected=ratio
        worker.execute {
            val rendered=runCatching {
                val outW= min(1440,if(selected==0) source.height*9/16 else source.width)
                val outH=when(selected) { 0 -> outW*16/9;1 -> outW;else -> outW*4/3 }
                val out=Bitmap.createBitmap(outW,outH,Bitmap.Config.ARGB_8888)
                val canvas=Canvas(out)
                val cropSpec = ResultPhotoRatio.entries[selected].crop(source.width, source.height)
                val crop=Rect(cropSpec.left,cropSpec.top,cropSpec.left+cropSpec.width,cropSpec.top+cropSpec.height)
                canvas.drawBitmap(source,crop,Rect(0,0,outW,outH),Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG))
                val safeH=if(selected==1) outW.toFloat() else outW*4/3f
                // Same percentages and safe rectangle as the live drawing; sample each exported block locally.
                val safe=RectF(0f,(outH-safeH)/2,outW.toFloat(),(outH+safeH)/2)
                val colors=FloatArray(3)
                val renderer=RecordBitmapRenderer()
                renderer.regions(safe,data).forEachIndexed { i,r ->
                    var sum=0.0;var n=0
                    for(y in r.top.toInt().coerceAtLeast(0) until r.bottom.toInt().coerceAtMost(outH) step 8)
                        for(x in r.left.toInt().coerceAtLeast(0) until r.right.toInt().coerceAtMost(outW) step 8) {
                            val p=out.getPixel(x,y);sum+=.2126*Color.red(p)+.7152*Color.green(p)+.0722*Color.blue(p);n++
                        }
                    colors[i]=if(n>0 && sum/n>150) 0f else 1f
                }
                // Canvas and Paint are local to this task: export never races the preview painter.
                renderer.draw(canvas,safe,data,colors)
                out
            }
            source.recycle()
            main.execute {
                if (released) { rendered.getOrNull()?.recycle(); return@execute }
                rendered.onSuccess { bitmap ->
                    if(target==0) worker.execute { val ok=ResultImageExport.save(context,bitmap,data.title);bitmap.recycle();main.execute {exporting=false;if(ok)photoSaved=true;toast(if(ok) "갤러리에 저장됨" else "사진 저장 실패")} }
                    else worker.execute {
                        val ok=ResultImageExport.share(context,bitmap,data.title,when(target){1->"com.instagram.android";2->"com.kakao.talk";else->null},target==1)
                        bitmap.recycle(); main.execute { exporting=false; if(!ok)toast("공유할 앱을 열지 못했어요") }
                    }
                }.onFailure { exporting=false;toast("이미지를 만들지 못했어요") }
            }
        }
    }
    private fun toast(message: String) = Toast.makeText(context,message,Toast.LENGTH_SHORT).show()

    private class RecordBitmapRenderer {
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        fun regions(safe: RectF, data: ResultPresentation): List<RectF> {
            val u=safe.width()/100
            fun width(value: String, size: Float): Float {
                paint.textSize=size*u;paint.typeface=Typeface.DEFAULT_BOLD
                return paint.measureText(value)
            }
            val headWidth=maxOf(width("${data.photoDate} · ${data.title}",2.8f),
                width("${data.minutes}",11.8f)+width("분",4.6f)+.5f*u,
                width("${data.volume}kg · ${data.setCount}세트",3.1f),width(data.verdict,2.8f)+3.6f*u)
            val markWidth=width("WATCHGYM",2.6f)
            val listWidth=data.exercises.maxOfOrNull { width("${it.name} · ${it.sets.size}세트",3.1f) } ?: 0f
            return listOf(RectF(safe.left+4.2f*u,safe.top+4*u,safe.left+4.2f*u+headWidth,safe.top+32.58f*u),
                RectF(safe.right-3.6f*u-markWidth,safe.top+4.2f*u,safe.right-3.6f*u,safe.top+7.84f*u),
                RectF(safe.right-4.2f*u-listWidth,safe.bottom-3.6f*u-data.exercises.size*4.805f*u,safe.right-4.2f*u,safe.bottom-3.6f*u))
        }
    private fun text(canvas: Canvas, value: String, x: Float, y: Float, size: Float, color: Int, bold: Boolean = false, right: Boolean = false, opacity: Float = 1f) {
        paint.apply { this.color = color; alpha = (255 * opacity).toInt(); textSize = size; typeface = if (bold) Typeface.create("sans-serif", Typeface.BOLD) else Typeface.create("sans-serif", Typeface.NORMAL); textAlign = if (right) Paint.Align.RIGHT else Paint.Align.LEFT; style = Paint.Style.FILL }
        canvas.drawText(value, x, y - paint.fontMetrics.ascent, paint)
    }
    private fun ink(t: Float): Int { val v = (11 + (255 - 11) * t).toInt().coerceIn(0,255); return Color.rgb(v, v, (10 + 245 * t).toInt().coerceIn(0,255)) }
    fun draw(c: Canvas, safe: RectF, data: ResultPresentation?, colors: FloatArray, opacity: Float = 1f) {
        if (data == null) return
        val u = safe.width() / 100
        val x = safe.left + 4.2f * u; val y = safe.top + 4 * u
        text(c, "${data.photoDate} · ${data.title}", x, y, 2.8f*u, ink(colors[0]), true, opacity = opacity)
        text(c, "${data.minutes}", x, y+4.92f*u, 11.8f*u, ink(colors[0]), true, opacity = opacity)
        paint.textSize = 11.8f*u; paint.typeface = Typeface.DEFAULT_BOLD
        val numWidth = paint.measureText("${data.minutes}")
        text(c, "분", x+numWidth+.5f*u, y+10.8f*u, 4.6f*u, ink(colors[0]), true, opacity = opacity)
        text(c, "${data.volume}kg · ${data.setCount}세트", x, y+17.72f*u, 3.1f*u, ink(colors[0]), true, opacity = opacity)
        paint.textSize = 2.8f*u; paint.typeface = Typeface.DEFAULT_BOLD
        val badge = RectF(x, y+23.66f*u, x+paint.measureText(data.verdict)+3.6f*u, y+28.58f*u)
        paint.color = Color.rgb(118,219,185); paint.alpha = (255*opacity).toInt(); c.drawRoundRect(badge, u, u, paint)
        text(c, data.verdict, x+1.8f*u, badge.top+.5f*u, 2.8f*u, Color.rgb(11,11,10), true, opacity = opacity)
        text(c, "WATCHGYM", safe.right-3.6f*u, y+.2f*u, 2.6f*u, ink(colors[1]), true, true, opacity*.85f)
        val line = 3.1f*u*1.55f
        data.exercises.forEachIndexed { i,e ->
            text(c, "${e.name} · ${e.sets.size}세트", safe.right-4.2f*u, safe.bottom-3.6f*u-line*(data.exercises.size-i), 3.1f*u, ink(colors[2]), true, true, opacity)
        }
    }
    }
}
