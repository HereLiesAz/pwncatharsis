package com.hereliesaz.pwncatharsis.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.ui.graphics.Color

// Define custom colors based on the new palette
val Charcoal = Color(0xFF1A1A1A)
val Ash = Color(0xFF333333)
val Bone = Color(0xFFCCCCCC)
val Blood = Color(0xFF8B0000)

// Custom Dark Color Scheme
val PwncatDarkColorScheme = darkColorScheme(
    primary = Blood,
    onPrimary = Bone,
    primaryContainer = Color(0xFF5D0000),
    onPrimaryContainer = Color(0xFFFFDAD4),

    secondary = Ash,
    onSecondary = Bone,
    secondaryContainer = Color(0xFF4A4443),
    onSecondaryContainer = Color(0xFFE7E0DE),

    tertiary = Ash,
    onTertiary = Bone,
    tertiaryContainer = Color(0xFF524343),
    onTertiaryContainer = Color(0xFFFEDBD9),

    background = Charcoal,
    onBackground = Bone,

    surface = Charcoal,
    onSurface = Bone,

    surfaceVariant = Ash,
    onSurfaceVariant = Bone,

    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),

    outline = Color(0xFF857371)
)