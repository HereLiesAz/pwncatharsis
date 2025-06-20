package com.hereliesaz.pwncatharsis.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hereliesaz.pwncatharsis.data.PwncatRepository
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.models.Session
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

/**
 * ViewModel for the main screen, managing UI state for listeners and sessions.
 */
class MainViewModel : ViewModel() {

    private val repository = PwncatRepository()

    private val _listeners = MutableStateFlow<List<Listener>>(emptyList())
    val listeners: StateFlow<List<Listener>> = _listeners.asStateFlow()

    private val _sessions = MutableStateFlow<List<Session>>(emptyList())
    val sessions: StateFlow<List<Session>> = _sessions.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    init {
        // Start polling for listeners and sessions
        viewModelScope.launch {
            while (true) {
                fetchListeners()
                fetchSessions()
                _isLoading.value = false
                delay(2000) // Poll every 2 seconds
            }
        }
    }

    private fun fetchListeners() {
        viewModelScope.launch {
            repository.getListeners()
                .catch { e ->
                    // Handle error, e.g., log it or show a message
                }
                .collect { listenerList ->
                    _listeners.value = listenerList
                }
        }
    }

    private fun fetchSessions() {
        viewModelScope.launch {
            repository.getSessions()
                .catch { e ->
                    // Handle error
                }
                .collect { sessionList ->
                    _sessions.value = sessionList
                }
        }
    }

    fun createListener(uri: String) {
        viewModelScope.launch {
            try {
                repository.createListener(uri)
                fetchListeners() // Refresh list after creation
            } catch (e: Exception) {
                // Handle error
            }
        }
    }

    fun deleteListener(listenerId: Int) {
        viewModelScope.launch {
            try {
                repository.deleteListener(listenerId)
                fetchListeners() // Refresh list after deletion
            } catch (e: Exception) {
                // Handle error
            }
        }
    }
}
