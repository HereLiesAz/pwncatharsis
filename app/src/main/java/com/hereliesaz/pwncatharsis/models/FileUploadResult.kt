package com.hereliesaz.pwncatharsis.models

import com.squareup.moshi.JsonClass

/**
 * Represents the result of a file upload operation.
 *
 * @property message A status message.
 * @property path The path where the file was uploaded.
 */
@JsonClass(generateAdapter = true)
data class FileUploadResult(
    val message: String,
    val path: String,
)
