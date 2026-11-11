package dev.kyungmin.kcoach.phone.ui

/** Source is always portrait 3:4. Ratios only change the visible crop, never the source. */
internal enum class ResultPhotoRatio(val label: String, val frameHeight: Float, val imageWidth: Float, val safeHeight: Float) {
    PORTRAIT("9:16", 16 / 9f, 4 / 3f, 4 / 3f),
    SQUARE("1:1", 1f, 1f, 1f),
    ORIGINAL("3:4", 4 / 3f, 1f, 4 / 3f);

    fun crop(width: Int, height: Int): ResultPhotoCrop {
        val w = if (this == PORTRAIT) height * 9 / 16 else width
        val h = if (this == SQUARE) width else height
        return ResultPhotoCrop((width - w) / 2, (height - h) / 2, w, h)
    }
}
internal data class ResultPhotoCrop(val left: Int, val top: Int, val width: Int, val height: Int)
