package com.goreecloud.tasks.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            GlazeTasksTheme {
                TasksDevelopmentScreen()
            }
        }
    }
}

private data class CapabilityRow(
    val label: String,
    val state: NativeCapabilityState,
    val explanation: String,
)

@Composable
private fun TasksDevelopmentScreen() {
    val snapshot = TasksNativeClientContract.capabilitySnapshot()
    val rows = listOf(
        CapabilityRow("Native read API contract", snapshot.readApiContract, "List and detail request schemas are source-ready."),
        CapabilityRow("Native response acceptance", snapshot.responseAcceptanceContract, "List/detail response invariants and exact field allowlists are source-ready; no transport is enabled."),
        CapabilityRow("Glaze UI V1.4", snapshot.glazeUiV14, "Targeting 1.4.0; native conformance evidence is not accepted yet."),
        CapabilityRow("Identity session exchange", snapshot.identitySessionExchange, "Required before native authenticated transport is enabled."),
        CapabilityRow("Remote task list", snapshot.remoteListRead, "Blocked until Identity/session exchange and transport are accepted."),
        CapabilityRow("Remote task detail", snapshot.remoteDetailRead, "Blocked until Identity/session exchange and transport are accepted."),
        CapabilityRow("Protected local cache", snapshot.localCache, "Not implemented in this first Android tranche."),
        CapabilityRow("Task mutations", snapshot.mutations, "Read-only API boundary remains authoritative for this tranche."),
        CapabilityRow("Background sync", snapshot.backgroundSync, "Not implemented until identity, cursor, revocation, and conflict semantics exist."),
    )

    Scaffold { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    tonalElevation = 2.dp,
                    shape = MaterialTheme.shapes.large,
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text("GoreeCloud Tasks", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                        Text("Android Development", style = MaterialTheme.typography.labelLarge)
                        Text(
                            "Native client foundation for the shared GoreeCloud Tasks model. No separate Android task authority is created.",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
            item {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.large,
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text("Current boundary", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                        Text(
                            "Native request and response contracts are source-ready, but this APK intentionally has no network permission. Native GoreeCloud Identity/session exchange must be defined and accepted before remote task data can be requested.",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            "Glaze UI ${TasksNativeClientContract.GLAZE_UI_VERSION} target · source revision ${TasksNativeClientContract.GLAZE_UI_REFERENCE_REVISION.take(12)}",
                            style = MaterialTheme.typography.labelMedium,
                        )
                    }
                }
            }
            item {
                Text("Capability evidence", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            }
            items(rows) { row ->
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.medium,
                ) {
                    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(row.label, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Medium)
                            Text(row.state.name.replace('_', ' '), style = MaterialTheme.typography.labelMedium)
                        }
                        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
                        Text(row.explanation, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}
