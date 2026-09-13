package com.goreecloud.tasks.android

import android.content.res.Configuration
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalConfiguration

/**
 * Repository-local Android adaptation target for GLAZE UI V1.4 / 1.4.0.
 *
 * This first Development shell deliberately keeps reading/decision surfaces solid and uses only
 * bounded tonal chrome. It does not claim native Optical Engine acceptance, environmental tinting,
 * reduced-transparency integration, physical-device qualification, or downstream conformance.
 */
@Composable
fun GlazeTasksTheme(content: @Composable () -> Unit) {
    val dark = (LocalConfiguration.current.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    MaterialTheme(
        colorScheme = if (dark) darkColorScheme() else lightColorScheme(),
        content = content,
    )
}
