package com.hereliesaz.pwncatharsis

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.*
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.hereliesaz.pwncatharsis.ui.screens.*
import com.hereliesaz.pwncatharsis.ui.theme.PwncatharsisTheme
import kotlin.concurrent.thread

class MainActivity : ComponentActivity() {

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
            PwncatharsisTheme {
                AppNavigation()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppNavigation() {
    val navController = rememberNavController()
    val screens = listOf(
        BottomNavItem.Main,
        BottomNavItem.Transform,
        BottomNavItem.Reflow,
        BottomNavItem.Slideshow
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("pwncatharsis") },
                actions = {
                    IconButton(onClick = { navController.navigate("settings") }) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination

                screens.forEach { screen ->
                    NavigationBarItem(
                        icon = { Icon(screen.icon, contentDescription = null) },
                        label = { Text(screen.title) },
                        selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(navController, startDestination = BottomNavItem.Main.route, Modifier.padding(innerPadding)) {
            composable(BottomNavItem.Main.route) {
                val mainViewModel: MainViewModel = viewModel()
                MainScreen(
                    viewModel = mainViewModel,
                    onSessionClick = { sessionId ->
                        navController.navigate("session/$sessionId")
                    }
                )
            }
            composable(BottomNavItem.Transform.route) { TransformScreen() }
            composable(BottomNavItem.Reflow.route) { ReflowScreen() }
            composable(BottomNavItem.Slideshow.route) { SlideshowScreen() }
            composable("settings") { SettingsScreen(onBack = { navController.popBackStack() }) }
            composable("session/{sessionId}") { backStackEntry ->
                val sessionId = backStackEntry.arguments?.getString("sessionId")?.toIntOrNull()
                if (sessionId != null) {
                    SessionScreen(
                        sessionId = sessionId,
                        onBack = { navController.popBackStack() }
                    )
                }
            }
        }
    }
}


sealed class BottomNavItem(var title: String, var icon: androidx.compose.ui.graphics.vector.ImageVector, var route: String) {
    object Main : BottomNavItem("Main", Icons.Default.Home, "main")
    object Transform : BottomNavItem("Transform", Icons.Default.Camera, "transform")
    object Reflow : BottomNavItem("Reflow", Icons.Default.Filter, "reflow")
    object Slideshow : BottomNavItem("Slideshow", Icons.Default.Slideshow, "slideshow")
}