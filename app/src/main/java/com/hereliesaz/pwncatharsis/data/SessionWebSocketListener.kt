package com.hereliesaz.pwncatharsis.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * A WebSocketListener that exposes incoming messages as a StateFlow.
 */
class SessionWebSocketListener : WebSocketListener() {

    private val _socketFlow = MutableStateFlow<String>("")
    val socketFlow = _socketFlow.asStateFlow()

    override fun onMessage(webSocket: WebSocket, text: String) {
        super.onMessage(webSocket, text)
        _socketFlow.value += text
    }

    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        super.onFailure(webSocket, t, response)
        _socketFlow.value += "\n--- WebSocket Failure: ${t.message} ---\n"
    }

    override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
        super.onClosing(webSocket, code, reason)
        _socketFlow.value += "\n--- WebSocket Closed ---"
    }
}
