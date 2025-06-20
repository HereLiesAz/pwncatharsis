package com.hereliesaz.pwncatharsis.models

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Represents a potential privilege escalation finding.
 *
 * @property name The name of the finding.
 * @property description A description of the finding.
 * @property exploitId The identifier for the exploit technique.
 */
@JsonClass(generateAdapter = true)
data class PrivescFinding(
    val name: String,
    val description: String,
    @Json(name = "exploit_id") val exploitId: String,
)
