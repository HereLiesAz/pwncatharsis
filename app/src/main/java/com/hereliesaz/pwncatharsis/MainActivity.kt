package com.hereliesaz.pwncatharsis

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.hereliesaz.pwncatharsis.ui.screens.SessionScreen
import com.hereliesaz.pwncatharsis.ui.screens.SettingsScreen
import com.hereliesaz.pwncatharsis.ui.theme.PwncatharsisTheme
import com.hereliesaz.pwncatharsis.viewmodel.MainViewModel
import kotlin.concurrent.thread
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.models.Session

class MainActivity : ComponentActivity() {

    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Start Python
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        // Start the FastAPI server in a background thread
        thread {
            val py = Python.getInstance()
            val mainModule = py.getModule("main")
            mainModule.callAttr("start")
        }

        setContent {
            var currentScreen by remember { mutableStateOf<Screen>(Screen.Main) }
            var selectedSessionId by remember { mutableStateOf<Int?>(null) }

            PwncatharsisTheme {
                when (val screen = currentScreen) {
                    is Screen.Main -> MainScreen(
                        viewModel = viewModel,
                        onSessionClick = { sessionId ->
                            selectedSessionId = sessionId
                            currentScreen = Screen.Session
                        },
                        onSettingsClick = { currentScreen = Screen.Settings }
                    )
                    is Screen.Session -> SessionScreen(
                        sessionId = selectedSessionId!!,
                        onBack = { currentScreen = Screen.Main }
                    )
                    is Screen.Settings -> SettingsScreen(
                        onBack = { currentScreen = Screen.Main }
                    )
                }
            }
        }
    }
}

sealed class Screen {
    object Main : Screen()
    object Session : Screen()
    object Settings : Screen()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    viewModel: MainViewModel,
    onSessionClick: (Int) -> Unit,
    onSettingsClick: () -> Unit
) {
    val listeners by viewModel.listeners.collectAsState()
    val sessions by viewModel.sessions.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("pwncatharsis") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                actions = {
                    IconButton(onClick = onSettingsClick) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { paddingValues ->
        if (isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else {
            Column(modifier = Modifier.padding(paddingValues).padding(16.dp)) {
                ListenerSection(listeners = listeners, viewModel = viewModel)
                Spacer(modifier = Modifier.height(16.dp))
                SessionSection(sessions = sessions, onSessionClick = onSessionClick)
            }
        }
    }
}

@Composable
fun ListenerSection(listeners: List<Listener>, viewModel: MainViewModel) {
    var showDialog by remember { mutableStateOf(false) }

    if (showDialog) {
        CreateListenerDialog(
            onDismiss = { showDialog = false },
            onCreate = { uri ->
                viewModel.createListener(uri)
                showDialog = false
            }
        )
    }

    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Listeners", style = MaterialTheme.typography.titleLarge)
            Spacer(modifier = Modifier.weight(1f))
            Button(onClick = { showDialog = true }) {
                Text("Create")
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
        LazyColumn {
            items(listeners) { listener ->
                ListItem(
                    headlineContent = { Text(listener.uri) },
                    trailingContent = {
                        IconButton(onClick = { viewModel.deleteListener(listener.id) }) {
                            Icon(Icons.Default.Delete, contentDescription = "Delete Listener")
                        }
                    }
                )
            }
        }
    }
}

@Composable
fun SessionSection(sessions: List<Session>, onSessionClick: (Int) -> Unit) {
    Column {
        Text("Sessions", style = MaterialTheme.typography.titleLarge)
        Spacer(modifier = Modifier.height(8.dp))
        LazyColumn {
            items(sessions) { session ->
                ListItem(
                    modifier = Modifier.clickable { onSessionClick(session.id) },
                    headlineContent = { Text("ID: ${session.id}") },
                    supportingContent = { Text("Platform: ${session.platform}") }
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CreateListenerDialog(onDismiss: () -> Unit, onCreate: (String) -> Unit) {
    var uri by remember { mutableStateOf("tcp://0.0.0.0:4444") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Create Listener") },
        text = {
            OutlinedTextField(
                value = uri,
                onValueChange = { uri = it },
                label = { Text("Listener URI") }
            )
        },
        confirmButton = {
            Button(onClick = { onCreate(uri) }) {
                Text("Create")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}
