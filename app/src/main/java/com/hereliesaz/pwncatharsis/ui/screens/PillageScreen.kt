package com.hereliesaz.pwncatharsis.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.hereliesaz.pwncatharsis.viewmodel.MainViewModel

@Composable
fun PillageScreen(viewModel: MainViewModel) {
    val allLoot by viewModel.allLoot.collectAsState()

    LazyColumn(
        modifier = Modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(allLoot) { lootItem ->
            LootCard(loot = lootItem)
        }
    }
}