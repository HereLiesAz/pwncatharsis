package com.hereliesaz.pwncatharsis.viewmodel

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.wifi.ScanResult
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hereliesaz.pwncatharsis.data.NetworkManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

data class NetworkUiState(
    val wifiNetworks: List<ScanResult> = emptyList(),
    val permissionGranted: Boolean = false,
    val isScanning: Boolean = false,
)

class NetworkViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(NetworkUiState())
    val uiState: StateFlow<NetworkUiState> = _uiState.asStateFlow()

    fun checkPermissions(context: Context) {
        val hasPermission = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        _uiState.value = _uiState.value.copy(permissionGranted = hasPermission)
    }

    fun startWifiScan(context: Context) {
        if (!uiState.value.permissionGranted) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isScanning = true)
            val networkManager = NetworkManager(context)
            networkManager.getWifiScanResults()
                .catch {
                    // Handle error
                    _uiState.value = _uiState.value.copy(isScanning = false)
                }
                .collect { scanResults ->
                    _uiState.value = _uiState.value.copy(
                        isScanning = false,
                        wifiNetworks = scanResults.sortedByDescending { it.level }
                    )
                }
        }
    }
}