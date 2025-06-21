package com.hereliesaz.pwncatharsis.ui.components

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun WifiNetworkCard(ssid: String, bssid: String, level: Int) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        ListItem(
            headlineContent = { Text(ssid.ifEmpty { "(Hidden Network)" }) },
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