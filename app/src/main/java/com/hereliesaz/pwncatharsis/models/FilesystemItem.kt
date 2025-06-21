package com.hereliesaz.pwncatharsis.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Represents an item in a remote filesystem.
 *
 * @property name The name of the file or directory.
 * @property path The full path to the item.
 * @property isDir Whether the item is a directory.
 */
@Serializable
data class FilesystemItem(
    val name: String,
    val path: String,
    @SerialName("is_dir") val isDir: Boolean,
)