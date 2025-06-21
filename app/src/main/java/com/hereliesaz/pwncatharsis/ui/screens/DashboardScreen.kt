package com.hereliesaz.pwncatharsis.ui.screens

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hereliesaz.pwncatharsis.ui.components.WifiNetworkCard
import com.hereliesaz.pwncatharsis.viewmodel.MainViewModel
import com.hereliesaz.pwncatharsis.viewmodel.NetworkViewModel

@Composable
fun DashboardScreen(
    mainViewModel: MainViewModel,
    networkViewModel: NetworkViewModel = viewModel(),
) {
    val listeners by mainViewModel.listeners.collectAsState()
    val sessions by mainViewModel.sessions.collectAsState()
    val networkUiState by networkViewModel.uiState.collectAsState()
    val context = LocalContext.current

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { isGranted ->
            networkViewModel.checkPermissions(context)
            if (isGranted) {
                networkViewModel.startWifiScan(context)
            }
        }
    )

    LaunchedEffect(key1 = Unit) {
        networkViewModel.checkPermissions(context)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "pwncatharsis",
            style = MaterialTheme.typography.headlineLarge,
            textAlign = TextAlign.Center
        )
        Text(
            text = "A vessel for your digital angst.",
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(16.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            DashboardCard(
                title = "Active Listeners",
                value = listeners.size.toString(),
                modifier = Modifier.weight(1f)
            )
            DashboardCard(
                title = "Active Sessions",
                value = sessions.size.toString(),
                modifier = Modifier.weight(1f)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        Button(
            onClick = {
                if (networkUiState.permissionGranted) {
                    networkViewModel.startWifiScan(context)
                } else {
                    permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                }
            },
            enabled = !networkUiState.isScanning
        ) {
            Text(if (networkUiState.isScanning) "Scanning..." else "Scan for Wi-Fi Networks")
        }

        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(networkUiState.wifiNetworks) { network ->
                WifiNetworkCard(ssid = network.SSID, bssid = network.BSSID, level = network.level)
            }
        }
    }
}

@Composable
fun DashboardCard(title: String, value: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = value,
                style = MaterialTheme.typography.displayMedium
            )
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall
            )
        }
    }
}