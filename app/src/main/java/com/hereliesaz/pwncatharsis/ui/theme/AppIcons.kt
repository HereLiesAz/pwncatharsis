package com.hereliesaz.pwncatharsis.ui.theme

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.Lan
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.QuestionMark
import androidx.compose.material.icons.filled.SnippetFolder
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Custom application icons for different loot types.
 */
object AppIcons {
    fun forLootType(type: String): ImageVector {
        return when (type.lowercase()) {
            "ssh_key" -> Icons.Default.Key
            "password_hash" -> Icons.Default.Lock
            "credential_file" -> Icons.Default.SnippetFolder
            "os_info" -> Icons.Default.Info
            "processes" -> Icons.Default.List
            "netstat" -> Icons.Default.Lan
            else -> Icons.Default.QuestionMark
        }
    }
}