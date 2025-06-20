package com.hereliesaz.pwncatharsis.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import com.hereliesaz.pwncatharsis.models.LootItem
import com.hereliesaz.pwncatharsis.models.PrivescFinding
import com.hereliesaz.pwncatharsis.viewmodel.SessionViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionScreen(viewModel: SessionViewModel, onBack: () -> Unit) {

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Session") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        // The main layout is now a single column
        Column(modifier = Modifier.padding(paddingValues)) {
            // The command-less, perpetual enumeration view
            PerpetualEnumerationPane(viewModel = viewModel, modifier = Modifier.weight(1f))
            // The interactive terminal, still available as a tool
            TerminalPane(viewModel = viewModel, modifier = Modifier.height(200.dp))
        }
    }
}

@Composable
fun PerpetualEnumerationPane(viewModel: SessionViewModel, modifier: Modifier = Modifier) {
    val loot by viewModel.loot.collectAsState()
    val privesc by viewModel.privescFindings.collectAsState()

    LazyColumn(
        modifier = modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        if (privesc.isNotEmpty()) {
            item {
                Text("Privilege Escalation", style = MaterialTheme.typography.titleLarge)
            }
            items(privesc) { finding ->
                PrivescCard(finding = finding)
            }
        }

        if (loot.isNotEmpty()) {
            item {
                Spacer(modifier = Modifier.height(16.dp))
                Text("Loot", style = MaterialTheme.typography.titleLarge)
            }
            items(loot) { item ->
                LootCard(loot = item)
            }
        }
    }
}

@Composable
fun PrivescCard(finding: PrivescFinding) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        ListItem(
            headlineContent = { Text(finding.name, style = MaterialTheme.typography.titleMedium) },
            supportingContent = { Text(finding.description) },
            leadingContent = {
                Icon(
                    Icons.Default.BugReport,
                    contentDescription = "Privesc Finding"
                )
            }
        )
    }
}

@Composable
fun LootCard(loot: LootItem) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        ListItem(
            headlineContent = { Text(loot.type) },
            supportingContent = { Text(loot.source, fontFamily = FontFamily.Monospace) },
            leadingContent = { Icon(loot.icon, contentDescription = loot.type) }
        )
    }
}

@Composable
fun TerminalPane(viewModel: SessionViewModel, modifier: Modifier = Modifier) {
    val terminalOutput by viewModel.terminalOutput.collectAsState()
    var textState by remember { mutableStateOf(TextFieldValue("")) }
    val scrollState = rememberScrollState()
    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(terminalOutput) {
        coroutineScope.launch {
            scrollState.animateScrollTo(scrollState.maxValue)
        }
    }

    Column(modifier = modifier.fillMaxWidth()) {
        Text(
            text = terminalOutput,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(scrollState)
                .padding(8.dp),
            fontFamily = FontFamily.Monospace
        )
        OutlinedTextField(
            value = textState,
            onValueChange = { textState = it },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            label = { Text("Command") },
            singleLine = true,
            trailingIcon = {
                IconButton(onClick = {
                    viewModel.sendToTerminal(textState.text + "\n")
                    textState = TextFieldValue("")
                }) {
                    Icon(Icons.Default.Terminal, contentDescription = "Send")
                }
            }
        )
    }
}
