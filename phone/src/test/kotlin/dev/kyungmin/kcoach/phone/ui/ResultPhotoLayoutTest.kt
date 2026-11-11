package dev.kyungmin.kcoach.phone.ui

import org.junit.Assert.*
import org.junit.Test

class ResultPhotoLayoutTest {
    @Test fun portraitOnlyRemovesSidesOfOriginal() {
        assertEquals(ResultPhotoCrop(150, 0, 900, 1600), ResultPhotoRatio.PORTRAIT.crop(1200, 1600))
    }
    @Test fun squareOnlyRemovesTopAndBottomOfOriginal() {
        assertEquals(ResultPhotoCrop(0, 200, 1200, 1200), ResultPhotoRatio.SQUARE.crop(1200, 1600))
        assertEquals(ResultPhotoCrop(0, 0, 1200, 1600), ResultPhotoRatio.ORIGINAL.crop(1200, 1600))
    }
    @Test fun portraitAndOriginalKeepBothTextCornersStationary() {
        val width = 366f
        val stageCenter = 56f + width * ResultPhotoRatio.PORTRAIT.frameHeight / 2
        val portraitSafeTop = stageCenter - width * ResultPhotoRatio.PORTRAIT.safeHeight / 2
        val originalSafeTop = stageCenter - width * ResultPhotoRatio.ORIGINAL.safeHeight / 2
        val portraitSafeBottom = stageCenter + width * ResultPhotoRatio.PORTRAIT.safeHeight / 2
        val originalSafeBottom = stageCenter + width * ResultPhotoRatio.ORIGINAL.safeHeight / 2
        assertEquals(portraitSafeTop, originalSafeTop, 0f)
        assertEquals(portraitSafeBottom, originalSafeBottom, 0f)
        assertEquals(width * 4 / 3, portraitSafeBottom - portraitSafeTop, .001f)
    }
}
