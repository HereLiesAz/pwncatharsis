package com.hereliesaz.pwncatharsis.models

/**
 * Represents a running process on the target.
 *
 * @property pid The process ID.
 * @property name The name of the process.
 * @property user The user running the process.
 */
data class Process(
    val pid: Int,
    val name: String,
    val user: String,
)
