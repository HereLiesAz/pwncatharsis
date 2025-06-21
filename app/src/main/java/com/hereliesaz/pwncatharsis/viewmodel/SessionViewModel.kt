package com.hereliesaz.pwncatharsis.viewmodel

import android.content.Context
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chaquo.python.PyObject
import com.hereliesaz.pwncatharsis.data.EnumerationListener
import com.hereliesaz.pwncatharsis.data.PwncatRepository
import com.hereliesaz.pwncatharsis.data.TerminalListener
import com.hereliesaz.pwncatharsis.models.FilesystemItem
import com.hereliesaz.pwncatharsis.models.LootItem
import com.hereliesaz.pwncatharsis.models.PrivescFinding
import com.hereliesaz.pwncatharsis.models.Script
import com.hereliesaz.pwncatharsis.utils.AppSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.io.File

class SessionViewModel(private val sessionId: Int) : ViewModel() {

    private val repository = PwncatRepository()

    // --- State for UI Feedback ---
    private val _snackbarMessage = MutableStateFlow<String?>(null)
    val snackbarMessage: StateFlow<String?> = _snackbarMessage.asStateFlow()

    // --- State for Core Session Data ---
    private val _loot = MutableStateFlow<List<LootItem>>(emptyList())
    val loot: StateFlow<List<LootItem>> = _loot.asStateFlow()

    private val _privescFindings = MutableStateFlow<List<PrivescFinding>>(emptyList())
    val privescFindings: StateFlow<List<PrivescFinding>> = _privescFindings.asStateFlow()

    private val _terminalOutput = MutableStateFlow("")
    val terminalOutput: StateFlow<String> = _terminalOutput.asStateFlow()

    // --- State for Filesystem ---
    private val _filesystemItems = MutableStateFlow<List<FilesystemItem>>(emptyList())
    val filesystemItems: StateFlow<List<FilesystemItem>> = _filesystemItems.asStateFlow()

    private val _currentPath = MutableStateFlow("/")
    val currentPath: StateFlow<String> = _currentPath.asStateFlow()

    private val _fileContent = MutableStateFlow<String?>(null)
    val fileContent: StateFlow<String?> = _fileContent.asStateFlow()

    // --- State for Chorus Scripts ---
    private val _scripts = MutableStateFlow<List<Script>>(emptyList())
    val scripts: StateFlow<List<Script>> = _scripts.asStateFlow()


    init {
        // Define the enumeration listener
        val enumerationListener = object : EnumerationListener {
            override fun onNewLoot(lootData: PyObject) {
                val lootMap = lootData.asMap()
                val newItem = LootItem(
                    type = lootMap[PyObject.fromJava("type")].toString(),
                    source = lootMap[PyObject.fromJava("source")].toString(),
                    content = lootMap[PyObject.fromJava("content")].toString()
                )
                _loot.value = _loot.value + newItem
            }

            override fun onNewPrivescFinding(findingData: PyObject) {
                val findingMap = findingData.asMap()
                val newItem = PrivescFinding(
                    name = findingMap[PyObject.fromJava("name")].toString(),
                    description = findingMap[PyObject.fromJava("description")].toString(),
                    exploitId = findingMap[PyObject.fromJava("exploit_id")].toString()
                )
                _privescFindings.value = _privescFindings.value + newItem
            }
        }

        // Define the terminal listener
        val terminalListener = object : TerminalListener {
            override fun onOutput(data: String) {
                _terminalOutput.value += data
            }
            override fun onClose() {
                _terminalOutput.value += "\n--- SESSION CLOSED ---"
            }
        }

        // Start both background processes
        viewModelScope.launch(Dispatchers.IO) {
            repository.startInteractiveSession(sessionId, terminalListener)
            repository.startPersistentEnumeration(sessionId, enumerationListener)
        }

        browseDirectory("/")
        loadScripts()
    }

    fun sendToTerminal(input: String) {
        viewModelScope.launch(Dispatchers.IO) {
            repository.sendToTerminal(sessionId, input)
        }
    }

    fun browseDirectory(path: String) {
        viewModelScope.launch {
            _currentPath.value = path
            repository.listFiles(sessionId, path)
                .catch { Log.e("SessionViewModel", "Failed to list files for path $path", it) }
                .collect { items -> _filesystemItems.value = items }
        }
    }

    fun runExploit(exploitId: String) {
        viewModelScope.launch {
            repository.runExploit(sessionId, exploitId)
                .catch { Log.e("SessionViewModel", "Failed to run exploit $exploitId", it) }
                .collect { output -> _terminalOutput.value += "\n--- EXPLOIT: $exploitId ---\n$output\n" }
        }
    }

    fun readFile(path: String) {
        viewModelScope.launch {
            repository.readFile(sessionId, path)
                .catch { _fileContent.value = "Error reading file: ${it.message}" }
                .collect { content -> _fileContent.value = content }
        }
    }

    fun downloadFile(context: Context, remotePath: String) {
        viewModelScope.launch {
            val appSettings = AppSettings(context)
            val saveDir = appSettings.lootSaveDirectory.first()
            val localFile = File(saveDir, remotePath.substringAfterLast('/'))

            repository.downloadFile(sessionId, remotePath, localFile.absolutePath)
                .catch { _snackbarMessage.value = "Download failed: ${it.message}" }
                .collect { _snackbarMessage.value = "Downloaded to ${localFile.name}" }
        }
    }

    fun loadScripts() {
        viewModelScope.launch {
            repository.getScripts().collect { _scripts.value = it }
        }
    }

    fun runScript(name: String) {
        viewModelScope.launch {
            repository.runScript(sessionId, name)
                .catch { _snackbarMessage.value = "Failed to run script: $name" }
                .collect { _snackbarMessage.value = "Executed script: $name" }
        }
    }

    fun onSnackbarShown() {
        _snackbarMessage.value = null
    }

    fun clearFileContent() {
        _fileContent.value = null
    }
}