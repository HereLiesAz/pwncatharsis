package com.hereliesaz.pwncatharsis

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.hereliesaz.pwncatharsis.ui.theme.PwncatharsisTheme

class MainActivity : ComponentActivity() {

    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Start Python
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        // The background server thread is no longer needed.

        setContent {
            PwncatharsisTheme {
                AppNavigation()
            }
        }
    }
}
// The rest of MainActivity remains the same (AppNavigation, etc.)