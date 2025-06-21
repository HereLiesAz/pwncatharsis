package com.hereliesaz.pwncatharsis.ui.screens

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hereliesaz.pwncatharsis.viewmodel.NetworkViewModel

@Composable
fun NetworkScreen(viewModel: NetworkViewModel = viewModel()) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { isGranted ->
            viewModel.checkPermissions(context)
            if (isGranted) {
                viewModel.startWifiScan(context)
            }
        }
    )

    LaunchedEffect(key1 = Unit) {
        viewModel.checkPermissions(context)
    }

    Column(modifier = Modifier.padding(16.dp)) {
        Text("Network Intelligence", style = MaterialTheme.typography.headlineLarge)
        Spacer(modifier = Modifier.height(16.dp))

        Button(
            onClick = {
                if (uiState.permissionGranted) {
                    viewModel.startWifiScan(context)
                } else {
                    permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                }
            },
            enabled = !uiState.isScanning
        ) {
            Text(if (uiState.isScanning) "Scanning..." else "Scan for Wi-Fi Networks")
        }

        Spacer(modifier = Modifier.height(16.dp))

        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(uiState.wifiNetworks) { network ->
                WifiNetworkCard(ssid = network.SSID, bssid = network.BSSID, level = network.level)
            }
        }
    }
}

@Composable
fun WifiNetworkCard(ssid: String, bssid: String, level: Int) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        ListItem(
            headlineContent = { Text(if (ssid.isNotEmpty()) ssid else "(Hidden Network)") },
            supportingContent = { Text(bssid.uppercase()) },
            trailingContent = {
                Row {
                    Text("$level dBm")
                    Icon(
                        if (level > -70) Icons.Default.Wifi else Icons.Default.WifiOff,
                        contentDescription = "Signal Strength"
                    )
                }
            }
        )
    }
}