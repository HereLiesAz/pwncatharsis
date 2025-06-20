package com.hereliesaz.pwncatharsis.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hereliesaz.pwncatharsis.data.PwncatRepository
import com.hereliesaz.pwncatharsis.data.TerminalListener
import com.hereliesaz.pwncatharsis.models.FilesystemItem
import com.hereliesaz.pwncatharsis.models.PrivescFinding
import com.hereliesaz.pwncatharsis.models.Process
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

class SessionViewModel(private val sessionId: Int) : ViewModel() {

    private val repository = PwncatRepository()

    private val _terminalOutput = MutableStateFlow("")
    val terminalOutput: StateFlow<String> = _terminalOutput.asStateFlow()

    private val _filesystemItems = MutableStateFlow<List<FilesystemItem>>(emptyList())
    val filesystemItems: StateFlow<List<FilesystemItem>> = _filesystemItems.asStateFlow()

    private val _currentPath = MutableStateFlow("/")
    val currentPath: StateFlow<String> = _currentPath.asStateFlow()

    // Unused for now, but shows how you'd add them back
    private val _processes = MutableStateFlow<List<Process>>(emptyList())
    val processes: StateFlow<List<Process>> = _processes.asStateFlow()

    private val _privescFindings = MutableStateFlow<List<PrivescFinding>>(emptyList())
    val privescFindings: StateFlow<List<PrivescFinding>> = _privescFindings.asStateFlow()


    init {
        val terminalListener = object : TerminalListener {
            override fun onOutput(data: String) {
                _terminalOutput.value += data
            }

            override fun onClose() {
                _terminalOutput.value += "\n--- SESSION CLOSED ---"
            }
        }
        viewModelScope.launch(Dispatchers.IO) {
            repository.startInteractiveSession(sessionId, terminalListener)
        }
        loadFilesystem()
    }

    fun sendToTerminal(input: String) {
        viewModelScope.launch(Dispatchers.IO) {
            repository.sendToTerminal(sessionId, input)
        }
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
}