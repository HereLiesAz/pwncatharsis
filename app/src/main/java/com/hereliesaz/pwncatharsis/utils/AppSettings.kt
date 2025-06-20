package com.hereliesaz.pwncatharsis.utils

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.map

/**
 * Manages persistent application settings using Jetpack DataStore.
 */
class AppSettings(private val context: Context) {

    companion object {
        private val Context.dataStore: DataStore<Preferences> by preferencesDataStore("settings")
        val LOOT_SAVE_DIRECTORY_KEY = stringPreferencesKey("loot_save_directory")
    }

    val lootSaveDirectory = context.dataStore.data.map { preferences ->
        preferences[LOOT_SAVE_DIRECTORY_KEY] ?: android.os.Environment.DIRECTORY_DOWNLOADS
    }

    suspend fun setLootSaveDirectory(directory: String) {
        context.dataStore.edit { settings ->
            settings[LOOT_SAVE_DIRECTORY_KEY] = directory
        }
    }
}
