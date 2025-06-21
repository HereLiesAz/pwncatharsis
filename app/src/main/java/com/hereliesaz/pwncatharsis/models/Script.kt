package com.hereliesaz.pwncatharsis.models

import kotlinx.serialization.Serializable

/**
 * Represents an automation script for the Chorus engine.
 *
 * @property name The unique name of the script.
 * @property content The body of the script, containing commands.
 */
@Serializable
data class Script(
    val name: String,
    val content: String = "", // Default content is empty
)