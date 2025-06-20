package com.hereliesaz.pwncatharsis.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val ExpressiveDarkColorScheme = darkColorScheme(
    primary = CyberGreen,
    onPrimary = Color.Black,
    secondary = CyberPurple,
    onSecondary = Color.Black,
    background = Charcoal,
    onBackground = LightGray,
    surface = DarkGray,
    onSurface = LightGray,
    error = ErrorRed,
    onError = Color.Black
)

@Composable
fun PwncatharsisTheme(
    content: @Composable () -> Unit,
) {
    val colorScheme = ExpressiveDarkColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.surface.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}