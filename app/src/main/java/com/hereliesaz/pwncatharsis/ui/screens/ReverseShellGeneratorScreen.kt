package com.hereliesaz.pwncatharsis.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hereliesaz.pwncatharsis.viewmodel.ReverseShellViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReverseShellGeneratorScreen(
    onBack: () -> Unit,
    viewModel: ReverseShellViewModel = viewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val clipboardManager = LocalClipboardManager.current
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.snackbarMessage) {
        uiState.snackbarMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.onSnackbarShown()
        }
    }

    val generatedCommand = remember(uiState.lhost, uiState.lport, uiState.shellType) {
        viewModel.generateShellCommand(uiState.lhost, uiState.lport, uiState.shellType)
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("Payload Generator") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .padding(paddingValues)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // --- Reverse Shell Section ---
            Text("Reverse Shell", style = MaterialTheme.typography.titleLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                OutlinedTextField(
                    value = uiState.lhost,
                    onValueChange = viewModel::onLhostChanged,
                    label = { Text("LHOST") },
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = uiState.lport,
                    onValueChange = viewModel::onLportChanged,
                    label = { Text("LPORT") },
                    modifier = Modifier.weight(0.5f)
                )
            }
            OutlinedTextField(
                value = uiState.shellType,
                onValueChange = viewModel::onShellTypeChanged,
                label = { Text("Shell Type") },
                modifier = Modifier.fillMaxWidth()
            )

            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = generatedCommand,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 14.sp,
                        modifier = Modifier.weight(1f)
                    )
                    IconButton(onClick = { clipboardManager.setText(AnnotatedString(generatedCommand)) }) {
                        Icon(
                            Icons.Default.ContentCopy,
                            "Copy"
                        )
                    }
                }
            }

            Divider(modifier = Modifier.padding(vertical = 16.dp))

            // --- Website Cloner Section ---
            Text("Website Cloner (MakePhish)", style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(
                value = uiState.urlToClone,
                onValueChange = viewModel::onUrlToCloneChanged,
                label = { Text("URL to Clone") },
                modifier = Modifier.fillMaxWidth()
            )
            Button(
                onClick = viewModel::generatePhishingSite,
                enabled = !uiState.isLoading,
                modifier = Modifier.fillMaxWidth()
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Text("Generate Phishing Site")
                }
            }
        }
    }
}