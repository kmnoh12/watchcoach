package dev.kyungmin.watchcoach.phone.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Keep phone spacing while centering readable content in an expanded window. */
internal fun Modifier.centeredContent(maxWidth: Dp = 600.dp): Modifier =
    wrapContentSize(Alignment.TopCenter).widthIn(max = maxWidth).fillMaxWidth()
