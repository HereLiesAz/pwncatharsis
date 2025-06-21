package com.hereliesaz.pwncatharsis.models

import kotlinx.serialization.Serializable

/**
 * Represents the result of a file upload operation.
 *
 * @property message A status message.
 * @property path The path where the file was uploaded.
 */
@Serializable
data class FileUploadResult(
    val message: String,
    val path: String,
)