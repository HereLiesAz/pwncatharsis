package com.hereliesaz.pwncatharsis.models

import androidx.compose.ui.graphics.vector.ImageVector
import com.hereliesaz.pwncatharsis.ui.theme.AppIcons

/**
 * Represents a piece of discovered loot, enriched with a specific icon.
 *
 * @property type The type of loot (e.g., "ssh_key", "password_hash").
 * @property source The path or source from which the loot was obtained.
 * @property content A snippet or the full content of the loot.
 * @property icon The Material icon associated with the loot type for UI display.
 */
data class LootItem(
    val type: String,
    val source: String,
    val content: String,
) {
    val icon: ImageVector
        get() = AppIcons.forLootType(this.type)
}
