package com.hereliesaz.pwncatharsis.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Represents the content of a file.
 *
 * @property content The text content of the file.
 */
@Serializable
data class FileContent(
    @SerialName("content") val content: String,
)