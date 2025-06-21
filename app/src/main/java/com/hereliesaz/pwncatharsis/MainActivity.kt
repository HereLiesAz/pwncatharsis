package com.hereliesaz.pwncatharsis

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.hereliesaz.pwncatharsis.ui.screens.*
import com.hereliesaz.pwncatharsis.ui.theme.PwncatharsisTheme
import com.hereliesaz.pwncatharsis.viewmodel.MainViewModel
import com.hereliesaz.pwncatharsis.viewmodel.SessionViewModel
import com.hereliesaz.pwncatharsis.viewmodel.ViewModelFactory // <-- Using the generic factory

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Start Python
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
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
        BottomNavItem.Dashboard,
        BottomNavItem.Recon,
        BottomNavItem.Exploit,
        BottomNavItem.Pillage,
        BottomNavItem.Chorus
    )
    val mainViewModel: MainViewModel = viewModel()

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
                                popUpTo(navController.graph.startDestinationId) {
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
        NavHost(
            navController,
            startDestination = BottomNavItem.Dashboard.route,
            Modifier.padding(innerPadding)
        ) {
            composable(BottomNavItem.Dashboard.route) { DashboardScreen(viewModel = mainViewModel) } // Pass ViewModel
            composable(BottomNavItem.Recon.route) { ReconScreen(viewModel = mainViewModel) }
            composable(BottomNavItem.Exploit.route) {
                ExploitScreen(
                    viewModel = mainViewModel,
                    onSessionClick = { sessionId ->
                        navController.navigate("session/$sessionId")
                    }
                )
            }
            composable(BottomNavItem.Pillage.route) { PillageScreen(viewModel = mainViewModel) } // Pass ViewModel
            composable(BottomNavItem.Chorus.route) { ChorusScreen() }
            composable("settings") { SettingsScreen(onBack = { navController.popBackStack() }) }
            composable("session/{sessionId}") { backStackEntry ->
                val sessionId = backStackEntry.arguments?.getString("sessionId")?.toIntOrNull()
                if (sessionId != null) {
                    // Use the generic ViewModelFactory to create the SessionViewModel
                    val sessionViewModel: SessionViewModel = viewModel(
                        factory = ViewModelFactory { SessionViewModel(sessionId) }
                    )
                    SessionScreen(
                        viewModel = sessionViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }
            }
        }
    }
}


sealed class BottomNavItem(
    var title: String,
    var icon: ImageVector,
    var route: String,
) {
    object Dashboard : BottomNavItem("Dashboard", Icons.Default.Home, "dashboard")
    object Recon : BottomNavItem("Recon", Icons.Default.Search, "recon")
    object Exploit : BottomNavItem("Exploit", Icons.Default.FlashOn, "exploit")
    object Pillage : BottomNavItem("Pillage", Icons.Default.Archive, "pillage")
    object Chorus : BottomNavItem("Chorus", Icons.Default.PlayArrow, "chorus")
}