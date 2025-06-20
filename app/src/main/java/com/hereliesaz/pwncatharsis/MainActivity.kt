package com.hereliesaz.pwncartharsis

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.hereliesaz.pwncartharsis.ui.screens.MainScreen
import com.hereliesaz.pwncartharsis.ui.screens.SessionScreen
import com.hereliesaz.pwncartharsis.ui.theme.PwncatharsisTheme
import com.hereliesaz.pwncartharsis.viewmodel.ViewModelFactory
import kotlin.concurrent.thread

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        thread {
            val python = Python.getInstance()
            val mainModule = python.getModule("main")
            mainModule.callAttr("start")
        }

        setContent {
            PwncatharsisTheme {
                AppNavigator()
            }
        }
    }
}

@Composable
fun AppNavigator() {
    val navController = rememberNavController()
    val factory = ViewModelFactory(navController.context)

    NavHost(navController = navController, startDestination = "main") {
        composable("main") {
            MainScreen(
                mainViewModel = viewModel(factory = factory),
                onSessionClick = { sessionId ->
                    navController.navigate("session/$sessionId")
                }
            )
        }
        composable("session/{sessionId}") { backStackEntry ->
            val sessionId = backStackEntry.arguments?.getString("sessionId")?.toIntOrNull()
            if (sessionId != null) {
                SessionScreen(
                    sessionId = sessionId,
                    sessionViewModel = viewModel(factory = factory),
                    onBack = { navController.popBackStack() }
                )
            } else {
                // Handle error, e.g., navigate back or show an error message
                navController.popBackStack()
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun DefaultPreview() {
    PwncatharsisTheme {
        Text("Preview of App Navigator requires context.")
    }
}