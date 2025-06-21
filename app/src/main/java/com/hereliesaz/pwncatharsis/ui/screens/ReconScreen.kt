package com.hereliesaz.pwncatharsis.ui.screens

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.ui.components.ConfirmationDialog
import com.hereliesaz.pwncatharsis.viewmodel.MainViewModel


@Composable
fun ReconScreen(viewModel: MainViewModel) {
    var showDialog by remember { mutableStateOf(false) }
    var listenerToDelete by remember { mutableStateOf<Listener?>(null) }

    val listeners by viewModel.listeners.collectAsState()
    val wifiNetworks by viewModel.wifiNetworks.collectAsState()
    val isScanning by viewModel.isScanning.collectAsState()
    val permissionGranted by viewModel.permissionGranted.collectAsState()

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

    LaunchedEffect(key1 = true) {
        viewModel.checkPermissions(context)
    }

    if (showDialog && listenerToDelete != null) {
        ConfirmationDialog(
            onDismissRequest = {
                showDialog = false
                listenerToDelete = null
            },
            onConfirm = {
                viewModel.deleteListener(listenerToDelete!!.id)
                showDialog = false
                listenerToDelete = null
            },
            title = "Delete Listener",
            text = { Text("Are you sure you want to delete the listener on ${listenerToDelete?.uri}?") }
        )
    }

    LazyColumn(
        modifier = Modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            Text("Listeners", style = MaterialTheme.typography.headlineMedium)
        }
        items(listeners) { listener ->
            ListenerCard(
                listener = listener,
                onDelete = {
                    listenerToDelete = it
                    showDialog = true
                }
            )
        }
        item {
            Button(
                onClick = { viewModel.createListener("tcp://0.0.0.0:4444") },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(
                    Icons.Default.Add,
                    contentDescription = null,
                    modifier = Modifier.size(ButtonDefaults.IconSize)
                )
                Spacer(Modifier.size(ButtonDefaults.IconSpacing))
                Text("Add Listener")
            }
        }

        item {
            Divider(modifier = Modifier.padding(vertical = 16.dp))
            Text("Wi-Fi Scan", style = MaterialTheme.typography.headlineMedium)
            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = {
                    if (permissionGranted) {
                        viewModel.startWifiScan(context)
                    } else {
                        permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                    }
                },
                enabled = !isScanning,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(if (isScanning) "Scanning..." else "Scan for Wi-Fi Networks")
            }
        }

        items(wifiNetworks) { network ->
            // Access properties directly from the ScanResult object
            WifiNetworkCard(ssid = network.SSID, bssid = network.BSSID, level = network.level)
        }
    }
}

@Composable
fun ListenerCard(listener: Listener, onDelete: (Listener) -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        ListItem(
            headlineContent = { Text(listener.uri) },
            trailingContent = {
                IconButton(onClick = { onDelete(listener) }) {
                    Icon(Icons.Default.Delete, contentDescription = "Delete Listener")
                }
            }
        )
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
