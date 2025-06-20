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
                if (_isLoading.value) _isLoading.value = false
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
            repository.createListener(uri).collect() // Refresh list after creation
        }
    }

    fun deleteListener(listenerId: Int) {
        viewModelScope.launch {
            repository.deleteListener(listenerId).collect()
        }
    }
}