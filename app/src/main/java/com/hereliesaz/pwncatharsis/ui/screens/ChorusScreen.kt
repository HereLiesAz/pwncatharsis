package com.hereliesaz.pwncatharsis.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hereliesaz.pwncatharsis.models.Script
import com.hereliesaz.pwncatharsis.viewmodel.ChorusViewModel

@Composable
fun ChorusScreen(viewModel: ChorusViewModel = viewModel()) {
    val scripts by viewModel.scripts.collectAsState()
    var showEditDialog by remember { mutableStateOf(false) }
    var scriptToEdit by remember { mutableStateOf<Script?>(null) }

    if (showEditDialog) {
        ScriptEditDialog(
            script = scriptToEdit,
            onDismiss = { showEditDialog = false },
            onSave = { name, content ->
                viewModel.saveScript(name, content)
                showEditDialog = false
            }
        )
    }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = {
                scriptToEdit = null // Create new script
                showEditDialog = true
            }) {
                Icon(Icons.Default.Add, contentDescription = "Add Script")
            }
        }
    ) { paddingValues ->
        LazyColumn(modifier = Modifier.padding(paddingValues)) {
            items(scripts) { script ->
                ScriptCard(
                    script = script,
                    onEdit = {
                        scriptToEdit = it
                        showEditDialog = true
                    },
                    onDelete = { viewModel.deleteScript(it.name) }
                )
            }
        }
    }
}

@Composable
fun ScriptCard(script: Script, onEdit: (Script) -> Unit, onDelete: (Script) -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp)
            .clickable { onEdit(script) },
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        ListItem(
            headlineContent = { Text(script.name) },
            trailingContent = {
                IconButton(onClick = { onDelete(script) }) {
                    Icon(Icons.Default.Delete, contentDescription = "Delete Script")
                }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScriptEditDialog(
    script: Script?,
    onDismiss: () -> Unit,
    onSave: (String, String) -> Unit,
) {
    var name by remember { mutableStateOf(script?.name ?: "") }
    var content by remember { mutableStateOf(script?.content ?: "") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (script == null) "New Script" else "Edit Script") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Script Name") },
                    singleLine = true,
                    enabled = script == null // Can't rename existing scripts for simplicity
                )
                OutlinedTextField(
                    value = content,
                    onValueChange = { content = it },
                    label = { Text("Script Content") },
                    modifier = Modifier.height(200.dp)
                )
            }
        },
        confirmButton = {
            Button(onClick = { onSave(name, content) }) {
                Text("Save")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}