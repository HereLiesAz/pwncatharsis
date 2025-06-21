package com.hereliesaz.pwncatharsis.utils

import android.content.Context
import android.os.Environment
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.map
import java.io.File

/**
 * Manages persistent application settings using Jetpack DataStore.
 */
class AppSettings(private val context: Context) {

    companion object {
        private val Context.dataStore: DataStore<Preferences> by preferencesDataStore("settings")
        val LOOT_SAVE_DIRECTORY_KEY = stringPreferencesKey("loot_save_directory")
    }

    // Default to a dedicated directory inside the public Downloads folder.
    private val defaultLootDir = File(
        Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
        "pwncatharsis"
    ).absolutePath

    val lootSaveDirectory = context.dataStore.data.map { preferences ->
        preferences[LOOT_SAVE_DIRECTORY_KEY] ?: defaultLootDir
    }

    suspend fun setLootSaveDirectory(directory: String) {
        // Ensure the directory exists
        val dir = File(directory)
        if (!dir.exists()) {
            dir.mkdirs()
        }
        context.dataStore.edit { settings ->
            settings[LOOT_SAVE_DIRECTORY_KEY] = directory
        }
    }
}