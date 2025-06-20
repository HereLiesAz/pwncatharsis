package com.hereliesaz.pwncatharsis.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Represents the content of a file.
 *
 * @property content The text content of the file.
 */
@JsonClass(generateAdapter = true)
data class FileContent(
    @Json(name = "content") val content: String,
)
