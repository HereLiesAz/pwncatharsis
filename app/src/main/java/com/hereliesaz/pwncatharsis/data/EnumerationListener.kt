package com.hereliesaz.pwncatharsis.data

import com.chaquo.python.PyObject

/**
 * Defines the contract for the perpetual enumeration engine to call
 * back from Python into Kotlin.
 */
interface EnumerationListener {
    fun onNewLoot(lootData: PyObject)
    fun onNewPrivescFinding(findingData: PyObject)
}
