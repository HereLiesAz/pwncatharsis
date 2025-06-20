package com.hereliesaz.pwncatharsis.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Represents an item in a remote filesystem.
 *
 * @property name The name of the file or directory.
 * @property path The full path to the item.
 * @property isDir Whether the item is a directory.
 */
@JsonClass(generateAdapter = true)
data class FilesystemItem(
    val name: String,
    val path: String,
    @Json(name = "is_dir") val isDir: Boolean,
)
