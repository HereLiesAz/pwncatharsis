package com.hereliesaz.pwncatharsis.ui.screens

import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Card
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.ui.components.ConfirmationDialog
import com.hereliesaz.pwncatharsis.viewmodel.MainViewModel

@Composable
fun ReconScreen(viewModel: MainViewModel) {
    val listeners by viewModel.listeners.collectAsState()
    var showDialog by remember { mutableStateOf(false) }
    var listenerToDelete by remember { mutableStateOf<Listener?>(null) }
    var showCreateListenerDialog by remember { mutableStateOf(false) }

    if (showDialog && listenerToDelete != null) {
        ConfirmationDialog(
            onDismissRequest = { showDialog = false },
            onConfirm = {
                listenerToDelete?.let { viewModel.deleteListener(it.id) }
                showDialog = false
            },
            title = "Delete Listener",
            text = { Text("Are you sure you want to delete this listener?") }
        )
    }

    if (showCreateListenerDialog) {
        var uri by remember { mutableStateOf("tcp://0.0.0.0:4444") }
        ConfirmationDialog(
            onDismissRequest = { showCreateListenerDialog = false },
            onConfirm = {
                viewModel.createListener(uri)
                showCreateListenerDialog = false
            },
            title = "Create Listener",
            text = {
                OutlinedTextField(
                    value = uri,
                    onValueChange = { uri = it },
                    label = { Text("Listener URI") }
                )
            }
        )
    }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = { showCreateListenerDialog = true }) {
                Icon(Icons.Default.Add, contentDescription = "Create Listener")
            }
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.padding(paddingValues),
            contentPadding = paddingValues
        ) {
            items(listeners) { listener ->
                ListenerCard(
                    listener = listener,
                    onDelete = {
                        listenerToDelete = it
                        showDialog = true
                    }
                )
            }
        }
    }
}

@Composable
fun ListenerCard(listener: Listener, onDelete: (Listener) -> Unit) {
    Card(
        modifier = Modifier
            .padding(horizontal = 16.dp, vertical = 4.dp)
    ) {
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