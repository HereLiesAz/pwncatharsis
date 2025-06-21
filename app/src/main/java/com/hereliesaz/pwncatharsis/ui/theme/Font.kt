package com.hereliesaz.pwncatharsis.ui.theme

import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import com.hereliesaz.pwncatharsis.R

/**
 * Defines the custom Hack font family.
 *
 * This assumes you have placed font files like `hack_regular.ttf`
 * and `hack_bold.ttf` in the `app/src/main/res/font` directory.
 */
val HackFontFamily = FontFamily(
    Font(R.font.hack_regular, FontWeight.Normal),
    Font(R.font.hack_bold, FontWeight.Bold),
    Font(R.font.hack_italic, FontWeight.Normal),
    Font(R.font.hack_bolditalic, FontWeight.Bold)
)