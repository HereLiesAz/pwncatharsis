package com.hereliesaz.pwncatharsis.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = pwn_catharsis_expressive_theme_dark_primary,
    onPrimary = pwn_catharsis_expressive_theme_dark_onPrimary,
    primaryContainer = pwn_catharsis_expressive_theme_dark_primaryContainer,
    onPrimaryContainer = pwn_catharsis_expressive_theme_dark_onPrimaryContainer,
    secondary = pwn_catharsis_expressive_theme_dark_secondary,
    onSecondary = pwn_catharsis_expressive_theme_dark_onSecondary,
    secondaryContainer = pwn_catharsis_expressive_theme_dark_secondaryContainer,
    onSecondaryContainer = pwn_catharsis_expressive_theme_dark_onSecondaryContainer,
    tertiary = pwn_catharsis_expressive_theme_dark_tertiary,
    onTertiary = pwn_catharsis_expressive_theme_dark_onTertiary,
    tertiaryContainer = pwn_catharsis_expressive_theme_dark_tertiaryContainer,
    onTertiaryContainer = pwn_catharsis_expressive_theme_dark_onTertiaryContainer,
    error = pwn_catharsis_expressive_theme_dark_error,
    errorContainer = pwn_catharsis_expressive_theme_dark_errorContainer,
    onError = pwn_catharsis_expressive_theme_dark_onError,
    onErrorContainer = pwn_catharsis_expressive_theme_dark_onErrorContainer,
    background = pwn_catharsis_expressive_theme_dark_background,
    onBackground = pwn_catharsis_expressive_theme_dark_onBackground,
    surface = pwn_catharsis_expressive_theme_dark_surface,
    onSurface = pwn_catharsis_expressive_theme_dark_onSurface,
    surfaceVariant = pwn_catharsis_expressive_theme_dark_surfaceVariant,
    onSurfaceVariant = pwn_catharsis_expressive_theme_dark_onSurfaceVariant,
    outline = pwn_catharsis_expressive_theme_dark_outline,
    inverseOnSurface = pwn_catharsis_expressive_theme_dark_inverseOnSurface,
    inverseSurface = pwn_catharsis_expressive_theme_dark_inverseSurface,
    inversePrimary = pwn_catharsis_expressive_theme_dark_inversePrimary,
    surfaceTint = pwn_catharsis_expressive_theme_dark_surfaceTint,
)

private val LightColorScheme = lightColorScheme(
    primary = pwn_catharsis_expressive_theme_light_primary,
    onPrimary = pwn_catharsis_expressive_theme_light_onPrimary,
    primaryContainer = pwn_catharsis_expressive_theme_light_primaryContainer,
    onPrimaryContainer = pwn_catharsis_expressive_theme_light_onPrimaryContainer,
    secondary = pwn_catharsis_expressive_theme_light_secondary,
    onSecondary = pwn_catharsis_expressive_theme_light_onSecondary,
    secondaryContainer = pwn_catharsis_expressive_theme_light_secondaryContainer,
    onSecondaryContainer = pwn_catharsis_expressive_theme_light_onSecondaryContainer,
    tertiary = pwn_catharsis_expressive_theme_light_tertiary,
    onTertiary = pwn_catharsis_expressive_theme_light_onTertiary,
    tertiaryContainer = pwn_catharsis_expressive_theme_light_tertiaryContainer,
    onTertiaryContainer = pwn_catharsis_expressive_theme_light_onTertiaryContainer,
    error = pwn_catharsis_expressive_theme_light_error,
    errorContainer = pwn_catharsis_expressive_theme_light_errorContainer,
    onError = pwn_catharsis_expressive_theme_light_onError,
    onErrorContainer = pwn_catharsis_expressive_theme_light_onErrorContainer,
    background = pwn_catharsis_expressive_theme_light_background,
    onBackground = pwn_catharsis_expressive_theme_light_onBackground,
    surface = pwn_catharsis_expressive_theme_light_surface,
    onSurface = pwn_catharsis_expressive_theme_light_onSurface,
    surfaceVariant = pwn_catharsis_expressive_theme_light_surfaceVariant,
    onSurfaceVariant = pwn_catharsis_expressive_theme_light_onSurfaceVariant,
    outline = pwn_catharsis_expressive_theme_light_outline,
    inverseOnSurface = pwn_catharsis_expressive_theme_light_inverseOnSurface,
    inverseSurface = pwn_catharsis_expressive_theme_light_inverseSurface,
    inversePrimary = pwn_catharsis_expressive_theme_light_inversePrimary,
    surfaceTint = pwn_catharsis_expressive_theme_light_surfaceTint,
)

@Composable
fun PwncatharsisTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // Dynamic color is available on Android 12+
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }

        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primary.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}