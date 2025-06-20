package com.hereliesaz.pwncatharsis.data

import com.hereliesaz.pwncatharsis.data.remote.ApiClient
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.models.LootItem
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.WebSocket

class PwncatRepository(private val client: OkHttpClient) {

    private val apiService = ApiClient.apiService
    private val _webSocketEvents = MutableSharedFlow<String>(replay = 1)
    val webSocketEvents: Flow<String> = _webSocketEvents

    // --- Listeners ---
    suspend fun getListeners() = apiService.getListeners()
    suspend fun createListener(listener: Listener) = apiService.createListener(listener)
    suspend fun deleteListener(id: Int) = apiService.deleteListener(id)

    // --- Sessions ---
    suspend fun getSessions() = apiService.getSessions()
    suspend fun getSession(sessionId: Int) = apiService.getSession(sessionId)
    suspend fun deleteSession(sessionId: Int) = apiService.deleteSession(sessionId)


    // --- WebSocket ---
    fun connectToSession(sessionId: Int, listener: SessionWebSocketListener): WebSocket {
        val request = Request.Builder()
            .url("ws://127.0.0.1:8000/api/sessions/$sessionId/ws")
            .build()
        return client.newWebSocket(request, listener)
    }

    // --- Filesystem ---
    suspend fun listFiles(sessionId: Int, path: String) = apiService.listFiles(sessionId, path)
    suspend fun readFile(sessionId: Int, path: String) = apiService.readFile(sessionId, path)
    suspend fun uploadFile(sessionId: Int, path: String, file: MultipartBody.Part) =
        apiService.uploadFile(sessionId, path, file)

    suspend fun downloadFile(sessionId: Int, path: String) =
        apiService.downloadFile(sessionId, path)


    // --- Processes ---
    suspend fun listProcesses(sessionId: Int) = apiService.listProcesses(sessionId)

    // --- Network ---
    suspend fun getNetworkInfo(sessionId: Int) = apiService.getNetworkInfo(sessionId)

    // --- Privesc ---
    suspend fun getPrivescFindings(sessionId: Int) = apiService.getPrivescFindings(sessionId)
    suspend fun runPrivescScan(sessionId: Int) = apiService.runPrivescScan(sessionId)

    // --- Loot ---
    suspend fun getLoot(sessionId: Int) = apiService.getLoot(sessionId)
    suspend fun addLoot(sessionId: Int, loot: LootItem) = apiService.addLoot(sessionId, loot)

    // --- Exploit ---
    suspend fun runExploit(sessionId: Int, technique: String) =
        apiService.runExploit(sessionId, mapOf("technique" to technique))

}