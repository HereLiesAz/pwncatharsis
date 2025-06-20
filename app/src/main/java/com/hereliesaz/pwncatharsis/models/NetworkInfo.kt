package com.hereliesaz.pwncatharsis.models

import com.squareup.moshi.JsonClass

/**
 * Represents network interface information.
 *
 * @property name The name of the interface.
 * @property address The IP address of the interface.
 * @property netmask The netmask of the interface.
 * @property broadcast The broadcast address of the interface.
 */
@JsonClass(generateAdapter = true)
data class NetworkInfo(
    val name: String,
    val address: String,
    val netmask: String,
    val broadcast: String,
)
