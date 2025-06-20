package com.hereliesaz.pwncatharsis.ui.components

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable

/**
 * A generic confirmation dialog.
 *
 * @param onDismissRequest Called when the user dismisses the dialog.
 * @param onConfirm Called when the user confirms the action.
 * @param title The title of the dialog.
 * @param text The descriptive text within the dialog.
 */
@Composable
fun ConfirmationDialog(
    onDismissRequest: () -> Unit,
    onConfirm: () -> Unit,
    title: String,
    text: String,
) {
    AlertDialog(
        onDismissRequest = onDismissRequest,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = {
            Button(onClick = {
                onConfirm()
                onDismissRequest()
            }) {
                Text("Confirm")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismissRequest) {
                Text("Cancel")
            }
        }
    )
}
