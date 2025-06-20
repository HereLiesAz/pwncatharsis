package com.hereliesaz.pwncatharsis.data

import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.hereliesaz.pwncatharsis.models.FilesystemItem
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.models.Session
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn

class PwncatRepository {

    private val python = Python.getInstance()
    private val sessionManager: PyObject = python.getModule("session_manager")

    init {
        // Initialize the pwncat manager once
        sessionManager.callAttr("initialize_manager")
    }

    private fun <T> toKotlinObject(pyObject: PyObject, clazz: Class<T>): T {
        return pyObject.toJava(clazz)
    }

    fun getListeners(): Flow<List<Listener>> = flow {
        val listenersPy = sessionManager.callAttr("get_listeners").asList()
        val listeners = listenersPy.map { pyObj ->
            val listenerMap = pyObj.asMap()
            Listener(
                id = listenerMap[PyObject.fromInt("id")]?.toInt() ?: -1,
                uri = listenerMap[PyObject.fromString("uri")].toString()
            )
        }
        emit(listeners)
    }.flowOn(Dispatchers.IO)

    fun createListener(uri: String) = flow {
        sessionManager.callAttr("create_listener", uri)
        emit(Unit) // We just trigger a refresh, could also return the new listener
    }.flowOn(Dispatchers.IO)


    fun deleteListener(listenerId: Int) = flow {
        sessionManager.callAttr("remove_listener", listenerId)
        emit(Unit)
    }.flowOn(Dispatchers.IO)


    fun getSessions(): Flow<List<Session>> = flow {
        val sessionsPy = sessionManager.callAttr("get_sessions").asList()
        val sessions = sessionsPy.map { pyObj ->
            val sessionMap = pyObj.asMap()
            Session(
                id = sessionMap[PyObject.fromString("id")]!!.toInt(),
                platform = sessionMap[PyObject.fromString("platform")].toString()
            )
        }
        emit(sessions)
    }.flowOn(Dispatchers.IO)

    fun startInteractiveSession(sessionId: Int, listener: TerminalListener) {
        // Pass the Kotlin object directly to Python
        sessionManager.callAttr("start_interactive_session", sessionId, PyObject.fromJava(listener))
    }

    fun sendToTerminal(sessionId: Int, command: String) {
        sessionManager.callAttr("send_to_terminal", sessionId, command)
    }

    fun listFiles(sessionId: Int, path: String): Flow<List<FilesystemItem>> = flow {
        val filesPy = sessionManager.callAttr("list_files", sessionId, path).asList()
        val files = filesPy.map { pyObj ->
            val fileMap = pyObj.asMap()
            FilesystemItem(
                name = fileMap[PyObject.fromString("name")].toString(),
                path = fileMap[PyObject.fromString("path")].toString(),
                isDir = fileMap[PyObject.fromString("is_dir")]!!.toBoolean()
            )
        }
        emit(files)
    }.flowOn(Dispatchers.IO)
}