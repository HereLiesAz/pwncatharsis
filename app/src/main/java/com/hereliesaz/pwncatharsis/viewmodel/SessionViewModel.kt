package com.hereliesaz.pwncatharsis.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hereliesaz.pwncatharsis.data.PwncatRepository
import com.hereliesaz.pwncatharsis.data.SessionWebSocketListener
import com.hereliesaz.pwncatharsis.models.FilesystemItem
import com.hereliesaz.pwncatharsis.models.PrivescFinding
import com.hereliesaz.pwncatharsis.models.Process
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch
import okhttp3.WebSocket

/**
 * ViewModel for the session interaction screen.
 */
class SessionViewModel(private val sessionId: Int) : ViewModel() {

    private val repository = PwncatRepository()
    private val webSocketListener = SessionWebSocketListener()
    private lateinit var webSocket: WebSocket

    val terminalOutput: StateFlow<String> = webSocketListener.socketFlow.asStateFlow()

    private val _filesystemItems = MutableStateFlow<List<FilesystemItem>>(emptyList())
    val filesystemItems: StateFlow<List<FilesystemItem>> = _filesystemItems.asStateFlow()

    private val _processes = MutableStateFlow<List<Process>>(emptyList())
    val processes: StateFlow<List<Process>> = _processes.asStateFlow()

    private val _privescFindings = MutableStateFlow<List<PrivescFinding>>(emptyList())
    val privescFindings: StateFlow<List<PrivescFinding>> = _privescFindings.asStateFlow()

    private val _currentPath = MutableStateFlow("/")
    val currentPath: StateFlow<String> = _currentPath.asStateFlow()

    init {
        viewModelScope.launch {
            webSocket = repository.connectToSession(sessionId, webSocketListener)
            loadFilesystem()
            loadProcesses()
            loadPrivesc()
        }
    }

    fun sendToTerminal(input: String) {
        webSocket.send(input)
    }

    fun navigate(item: FilesystemItem) {
        if (item.isDir) {
            _currentPath.value = item.path
            loadFilesystem()
        }
    }

    fun navigateUp() {
        val current = _currentPath.value
        if (current != "/") {
            var parent = current.removeSuffix("/").substringBeforeLast('/', "/")
            if (parent.isEmpty()) parent = "/"
            _currentPath.value = parent
            loadFilesystem()
        }
    }

    private fun loadFilesystem() {
        viewModelScope.launch {
            repository.listFiles(sessionId, _currentPath.value)
                .catch { /* Handle error */ }
                .collect { _filesystemItems.value = it }
        }
    }

    private fun loadProcesses() {
        viewModelScope.launch {
            repository.listProcesses(sessionId)
                .catch { /* Handle error */ }
                .collect { _processes.value = it }
        }
    }

    private fun loadPrivesc() {
        viewModelScope.launch {
            repository.checkPrivesc(sessionId)
                .catch { /* Handle error */ }
                .collect { _privescFindings.value = it }
        }
    }

    override fun onCleared() {
        super.onCleared()
        webSocket.close(1000, "Screen Closed")
    }
}
