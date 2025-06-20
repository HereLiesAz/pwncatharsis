package com.hereliesaz.pwncatharsis.models

/**
 * Represents a pwncat session.
 *
 * @property id The unique identifier for the session.
 * @property platform The target platform (e.g., "linux", "windows").
 */
data class Session(
    val id: Int,
    val platform: String,
)
