package com.hereliesaz.pwncatharsis.viewmodel

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.wifi.ScanResult
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hereliesaz.pwncatharsis.data.NetworkManager
import com.hereliesaz.pwncatharsis.data.PwncatRepository
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.models.LootItem
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

    private val _allLoot = MutableStateFlow<List<LootItem>>(emptyList())
    val allLoot: StateFlow<List<LootItem>> = _allLoot.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    // --- Network Analysis State (merged from NetworkViewModel) ---
    private val _wifiNetworks = MutableStateFlow<List<ScanResult>>(emptyList())
    val wifiNetworks: StateFlow<List<ScanResult>> = _wifiNetworks.asStateFlow()

    private val _permissionGranted = MutableStateFlow(false)
    val permissionGranted: StateFlow<Boolean> = _permissionGranted.asStateFlow()

    private val _isScanning = MutableStateFlow(false)
    val isScanning: StateFlow<Boolean> = _isScanning.asStateFlow()

    init {
        viewModelScope.launch {
            while (true) {
                fetchListeners()
                fetchSessions()
                fetchAllLoot()
                if (_isLoading.value) _isLoading.value = false
                delay(2000) // Poll every 2 seconds
            }
        }
    }

    private fun fetchListeners() {
        viewModelScope.launch {
            repository.getListeners()
                .catch { e -> /* Handle error */ }
                .collect { listenerList -> _listeners.value = listenerList }
        }
    }

    private fun fetchSessions() {
        viewModelScope.launch {
            repository.getSessions()
                .catch { e -> /* Handle error */ }
                .collect { sessionList -> _sessions.value = sessionList }
        }
    }

    private fun fetchAllLoot() {
        viewModelScope.launch {
            repository.getAllLoot()
                .catch { e -> /* Handle error */ }
                .collect { lootList -> _allLoot.value = lootList }
        }
    }

    fun createListener(uri: String) {
        viewModelScope.launch {
            repository.createListener(uri).collect {}
        }
    }

    fun deleteListener(listenerId: Int) {
        viewModelScope.launch {
            repository.deleteListener(listenerId).collect {}
        }
    }

    // --- Network Analysis Functions ---
    fun checkPermissions(context: Context) {
        val hasPermission = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        _permissionGranted.value = hasPermission
    }

    fun startWifiScan(context: Context) {
        if (!_permissionGranted.value) return

        viewModelScope.launch {
            _isScanning.value = true
            val networkManager = NetworkManager(context)
            networkManager.getWifiScanResults()
                .catch {
                    _isScanning.value = false
                }
                .collect { scanResults ->
                    _isScanning.value = false
                    _wifiNetworks.value = scanResults.sortedByDescending { it.level }
                }
        }
    }
}
