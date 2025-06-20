package com.hereliesaz.pwncatharsis.models

/**
 * Represents a pwncat listener.
 *
 * @property id The unique identifier for the listener.
 * @property uri The listening URI (e.g., "tcp://0.0.0.0:4444").
 */
data class Listener(
    val id: Int,
    val uri: String,
)
