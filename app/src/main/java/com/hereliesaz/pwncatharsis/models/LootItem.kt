package com.hereliesaz.pwncatharsis.models

import com.squareup.moshi.JsonClass

/**
 * Represents a piece of discovered loot.
 *
 * @property type The type of loot (e.g., "ssh_key", "password_hash", "credential_file").
 * @property source The path or source from which the loot was obtained.
 * @property content A snippet or the full content of the loot.
 */
@JsonClass(generateAdapter = true)
data class LootItem(
    val type: String,
    val source: String,
    val content: String,
)
