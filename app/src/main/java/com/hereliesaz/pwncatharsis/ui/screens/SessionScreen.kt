package com.hereliesaz.pwncatharsis.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hereliesaz.pwncatharsis.models.FilesystemItem
import com.hereliesaz.pwncatharsis.models.PrivescFinding
import com.hereliesaz.pwncatharsis.models.Process
import com.hereliesaz.pwncatharsis.viewmodel.SessionViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionScreen(sessionId: Int, onBack: () -> Unit) {

    // Custom ViewModelFactory to pass sessionId
    val viewModel: SessionViewModel = viewModel(
        factory = object : ViewModelProvider.Factory {
            override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T {
                @Suppress("UNCHECKED_CAST")
                return SessionViewModel(sessionId) as T
            }
        }
    )

    var selectedTabIndex by remember { mutableStateOf(0) }
    val tabs = listOf("Terminal", "Filesystem", "Processes", "Privesc")

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Session $sessionId") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(modifier = Modifier.padding(paddingValues)) {
            TabRow(selectedTabIndex = selectedTabIndex) {
                tabs.forEachIndexed { index, title ->
                    Tab(
                        selected = selectedTabIndex == index,
                        onClick = { selectedTabIndex = index },
                        text = { Text(title) }
                    )
                }
            }
            when (selectedTabIndex) {
                0 -> TerminalTab(viewModel)
                1 -> FilesystemTab(viewModel)
                2 -> ProcessTab(viewModel)
                3 -> PrivescTab(viewModel)
            }
        }
    }
}

@Composable
fun TerminalTab(viewModel: SessionViewModel) {
    val terminalOutput by viewModel.terminalOutput.collectAsState()
    var textState by remember { mutableStateOf(TextFieldValue("")) }
    val scrollState = rememberScrollState()
    val coroutineScope = rememberCoroutineScope()

    // Scroll to the bottom whenever the terminal output changes
    LaunchedEffect(terminalOutput) {
        coroutineScope.launch {
            scrollState.animateScrollTo(scrollState.maxValue)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            text = terminalOutput,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(scrollState)
                .padding(8.dp),
            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace
        )
        OutlinedTextField(
            value = textState,
            onValueChange = { textState = it },
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            label = { Text("Input") },
            singleLine = true,
            trailingIcon = {
                IconButton(onClick = {
                    viewModel.sendToTerminal(textState.text + "\n")
                    textState = TextFieldValue("") // Clear input
                }) {
                    Icon(Icons.Default.Terminal, contentDescription = "Send")
                }
            }
        )
    }
}

@Composable
fun FilesystemTab(viewModel: SessionViewModel) {
    val items by viewModel.filesystemItems.collectAsState()
    val currentPath by viewModel.currentPath.collectAsState()

    val displayItems = remember(items, currentPath) {
        if (currentPath != "/") {
            listOf(FilesystemItem("..", "UP", isDir = true)) + items
        } else {
            items
        }
    }

    Column {
        Text(text = "Current Path: $currentPath", modifier = Modifier.padding(8.dp))
        LazyColumn {
            items(displayItems) { item ->
                FilesystemListItem(item = item) { selectedItem ->
                    if (selectedItem.name == "..") {
                        viewModel.navigateUp()
                    } else {
                        viewModel.navigate(selectedItem)
                    }
                }
            }
        }
    }
}

@Composable
fun FilesystemListItem(item: FilesystemItem, onNavigate: (FilesystemItem) -> Unit) {
    ListItem(
        headlineContent = { Text(item.name) },
        leadingContent = {
            Icon(
                if (item.isDir) Icons.Default.Folder else Icons.Default.Description,
                contentDescription = null
            )
        },
        modifier = Modifier.clickable(enabled = item.isDir) {
            onNavigate(item)
        }
    )
}

@Composable
fun ProcessTab(viewModel: SessionViewModel) {
    val processes by viewModel.processes.collectAsState()
    LazyColumn {
        items(processes) { process ->
            ProcessListItem(process = process)
        }
    }
}

@Composable
fun ProcessListItem(process: Process) {
    ListItem(
        headlineContent = { Text(process.name) },
        supportingContent = { Text("PID: ${process.pid} | User: ${process.user}") }
    )
}

@Composable
fun PrivescTab(viewModel: SessionViewModel) {
    val findings by viewModel.privescFindings.collectAsState()
    LazyColumn {
        items(findings) { finding ->
            PrivescListItem(finding = finding)
        }
    }
}

@Composable
fun PrivescListItem(finding: PrivescFinding) {
    ListItem(
        headlineContent = { Text(finding.name) },
        supportingContent = { Text(finding.description) },
        leadingContent = { Icon(Icons.Default.Security, contentDescription = null) }
    )
}
