package com.hereliesaz.pwncatharsis.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.chaquo.python.PyObject
import com.hereliesaz.pwncatharsis.data.EnumerationListener
import com.hereliesaz.pwncatharsis.data.PwncatRepository
import com.hereliesaz.pwncatharsis.data.TerminalListener
import com.hereliesaz.pwncatharsis.models.LootItem
import com.hereliesaz.pwncatharsis.models.PrivescFinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SessionViewModel(private val sessionId: Int) : ViewModel() {

    private val repository = PwncatRepository()

    // --- State for the Command-less UI ---
    private val _loot = MutableStateFlow<List<LootItem>>(emptyList())
    val loot: StateFlow<List<LootItem>> = _loot.asStateFlow()

    private val _privescFindings = MutableStateFlow<List<PrivescFinding>>(emptyList())
    val privescFindings: StateFlow<List<PrivescFinding>> = _privescFindings.asStateFlow()

    // --- State for the Terminal (still available as a tool) ---
    private val _terminalOutput = MutableStateFlow("")
    val terminalOutput: StateFlow<String> = _terminalOutput.asStateFlow()

    init {
        // Define the enumeration listener
        val enumerationListener = object : EnumerationListener {
            override fun onNewLoot(lootData: PyObject) {
                val lootMap = lootData.asMap()
                val newItem = LootItem(
                    type = lootMap[PyObject.fromString("type")].toString(),
                    source = lootMap[PyObject.fromString("source")].toString(),
                    content = lootMap[PyObject.fromString("content")].toString()
                )
                _loot.value = _loot.value + newItem
            }

            override fun onNewPrivescFinding(findingData: PyObject) {
                val findingMap = findingData.asMap()
                val newItem = PrivescFinding(
                    name = findingMap[PyObject.fromString("name")].toString(),
                    description = findingMap[PyObject.fromString("description")].toString(),
                    exploitId = findingMap[PyObject.fromString("exploit_id")].toString()
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
    }

    fun sendToTerminal(input: String) {
        viewModelScope.launch(Dispatchers.IO) {
            repository.sendToTerminal(sessionId, input)
        }
    }
}

class SessionViewModelFactory(private val sessionId: Int) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(SessionViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return SessionViewModel(sessionId) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
