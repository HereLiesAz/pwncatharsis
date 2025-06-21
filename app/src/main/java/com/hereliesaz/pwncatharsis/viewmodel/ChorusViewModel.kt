package com.hereliesaz.pwncatharsis.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hereliesaz.pwncatharsis.data.PwncatRepository
import com.hereliesaz.pwncatharsis.models.Script
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

class ChorusViewModel : ViewModel() {

    private val repository = PwncatRepository()

    private val _scripts = MutableStateFlow<List<Script>>(emptyList())
    val scripts: StateFlow<List<Script>> = _scripts.asStateFlow()

    private val _selectedScriptContent = MutableStateFlow<String?>(null)
    val selectedScriptContent: StateFlow<String?> = _selectedScriptContent.asStateFlow()

    init {
        loadScripts()
    }

    fun loadScripts() {
        viewModelScope.launch {
            repository.getScripts()
                .catch {
                    // Handle error
                }
                .collect { scriptList ->
                    _scripts.value = scriptList
                }
        }
    }

    fun loadScriptContent(name: String) {
        viewModelScope.launch {
            repository.getScriptContent(name)
                .catch { _selectedScriptContent.value = "Error loading script." }
                .collect { script ->
                    _selectedScriptContent.value = script?.content
                }
        }
    }

    fun saveScript(name: String, content: String) {
        viewModelScope.launch {
            repository.saveScript(name, content).collect {
                loadScripts() // Refresh the list after saving
            }
        }
    }

    fun deleteScript(name: String) {
        viewModelScope.launch {
            repository.deleteScript(name).collect {
                loadScripts() // Refresh the list after deleting
            }
        }
    }

    fun runScript(sessionId: Int, name: String) {
        viewModelScope.launch {
            repository.runScript(sessionId, name).collect {
                // We don't need to do anything with the emission, but collect is required
            }
        }
    }

    fun clearSelectedScript() {
        _selectedScriptContent.value = null
    }
}