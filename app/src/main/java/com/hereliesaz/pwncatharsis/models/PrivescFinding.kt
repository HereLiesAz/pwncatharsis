package com.hereliesaz.pwncatharsis.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Represents a potential privilege escalation finding.
 *
 * @property name The name of the finding.
 * @property description A description of the finding.
 * @property exploitId The identifier for the exploit technique.
 */
@Serializable
data class PrivescFinding(
    val name: String,
    val description: String,
    @SerialName("exploit_id") val exploitId: String,
)