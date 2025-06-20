package com.hereliesaz.pwncatharsis.data

// This interface is the contract for Python-to-Kotlin callbacks.
interface TerminalListener {
    fun onOutput(data: String)
    fun onClose()
}