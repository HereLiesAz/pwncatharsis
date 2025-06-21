package com.hereliesaz.pwncatharsis.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.InsertDriveFile
import androidx.compose.material.icons.filled.PlayCircleOutline
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import com.hereliesaz.pwncatharsis.models.FilesystemItem
import com.hereliesaz.pwncatharsis.models.LootItem
import com.hereliesaz.pwncatharsis.models.PrivescFinding
import com.hereliesaz.pwncatharsis.models.Script
import com.hereliesaz.pwncatharsis.viewmodel.SessionViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionScreen(viewModel: SessionViewModel, onBack: () -> Unit) {
    var tabIndex by remember { mutableStateOf(0) }
    val tabs = listOf("Overview", "Terminal", "Filesystem")
    val fileContent by viewModel.fileContent.collectAsState()
    val scripts by viewModel.scripts.collectAsState()

    val snackbarHostState = remember { SnackbarHostState() }
    val snackbarMessage by viewModel.snackbarMessage.collectAsState()

    var showRunScriptDialog by remember { mutableStateOf(false) }

    LaunchedEffect(snackbarMessage) {
        snackbarMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.onSnackbarShown()
        }
    }

    if (fileContent != null) {
        FileContentDialog(
            content = fileContent!!,
            onDismiss = { viewModel.clearFileContent() }
        )
    }

    if (showRunScriptDialog) {
        RunScriptDialog(
            scripts = scripts,
            onDismiss = { showRunScriptDialog = false },
            onScriptSelected = { scriptName ->
                viewModel.runScript(scriptName)
                showRunScriptDialog = false
            }
        )
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("Session ${viewModel.currentPath.collectAsState().value}") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { showRunScriptDialog = true }) {
                        Icon(Icons.Default.PlayCircleOutline, contentDescription = "Run Script")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(modifier = Modifier.padding(paddingValues)) {
            TabRow(selectedTabIndex = tabIndex) {
                tabs.forEachIndexed { index, title ->
                    Tab(
                        text = { Text(title) },
                        selected = tabIndex == index,
                        onClick = { tabIndex = index }
                    )
                }
            }
            when (tabIndex) {
                0 -> OverviewPane(viewModel = viewModel)
                1 -> TerminalPane(viewModel = viewModel)
                2 -> FilesystemPane(viewModel = viewModel)
            }
        }
    }
}

@Composable
fun OverviewPane(viewModel: SessionViewModel) {
    val loot by viewModel.loot.collectAsState()
    val privesc by viewModel.privescFindings.collectAsState()

    LazyColumn(
        modifier = Modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        if (privesc.isNotEmpty()) {
            item {
                Text("Privilege Escalation", style = MaterialTheme.typography.titleLarge)
            }
            items(privesc) { finding ->
                PrivescCard(
                    finding = finding,
                    onRunExploit = { viewModel.runExploit(finding.exploitId) })
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
fun TerminalPane(viewModel: SessionViewModel) {
    val terminalOutput by viewModel.terminalOutput.collectAsState()
    var textState by remember { mutableStateOf(TextFieldValue("")) }
    val scrollState = rememberScrollState()
    val coroutineScope = rememberCoroutineScope()

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

@Composable
fun FilesystemPane(viewModel: SessionViewModel) {
    val files by viewModel.filesystemItems.collectAsState()
    val currentPath by viewModel.currentPath.collectAsState()
    val context = LocalContext.current

    Column {
        Text(
            text = "Current Path: $currentPath",
            modifier = Modifier.padding(16.dp),
            style = MaterialTheme.typography.titleMedium
        )
        LazyColumn {
            items(files) { item ->
                FilesystemItemRow(
                    item = item,
                    onItemClick = {
                        if (item.isDir) {
                            viewModel.browseDirectory(item.path)
                        } else {
                            viewModel.readFile(item.path)
                        }
                    },
                    onDownloadClick = {
                        viewModel.downloadFile(context, item.path)
                    }
                )
            }
        }
    }
}

@Composable
fun FilesystemItemRow(
    item: FilesystemItem,
    onItemClick: () -> Unit,
    onDownloadClick: () -> Unit,
) {
    ListItem(
        headlineContent = { Text(item.name) },
        leadingContent = {
            Icon(
                if (item.isDir) Icons.Default.Folder else Icons.Default.InsertDriveFile,
                contentDescription = null
            )
        },
        trailingContent = {
            if (!item.isDir) {
                IconButton(onClick = onDownloadClick) {
                    Icon(Icons.Default.Download, contentDescription = "Download File")
                }
            }
        },
        modifier = Modifier.clickable(onClick = onItemClick)
    )
}

@Composable
fun FileContentDialog(content: String, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("File Content") },
        text = {
            Box(modifier = Modifier.fillMaxHeight(0.7f)) {
                val scrollState = rememberScrollState()
                Text(
                    text = content,
                    modifier = Modifier.verticalScroll(scrollState),
                    fontFamily = FontFamily.Monospace
                )
            }
        },
        confirmButton = {
            Button(onClick = onDismiss) {
                Text("Close")
            }
        }
    )
}

@Composable
fun PrivescCard(finding: PrivescFinding, onRunExploit: () -> Unit) {
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
            },
            trailingContent = {
                Button(onClick = onRunExploit) {
                    Text("Run")
                }
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
fun RunScriptDialog(
    scripts: List<Script>,
    onDismiss: () -> Unit,
    onScriptSelected: (String) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Run Script") },
        text = {
            LazyColumn {
                items(scripts) { script ->
                    ListItem(
                        headlineContent = { Text(script.name) },
                        modifier = Modifier.clickable { onScriptSelected(script.name) }
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}