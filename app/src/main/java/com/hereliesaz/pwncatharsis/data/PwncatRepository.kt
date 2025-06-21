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
        // Initialize the pwncat manager once when the repository is created
        sessionManager.callAttr("initialize_manager")
    }

    fun getListeners(): Flow<List<Listener>> = flow {
        val listenersPy = sessionManager.callAttr("get_listeners").asList()
        val listeners = listenersPy.map { pyObj ->
            val listenerMap = pyObj.asMap()
            Listener(
                id = listenerMap[PyObject.fromJava("id")]?.toInt() ?: -1,
                uri = listenerMap[PyObject.fromJava("uri")].toString()
            )
        }
        emit(listeners)
    }.flowOn(Dispatchers.IO) // Run Python calls off the main thread

    fun createListener(uri: String): Flow<Unit> = flow {
        sessionManager.callAttr("create_listener", uri)
        emit(Unit) // Emit a signal to trigger a refresh
    }.flowOn(Dispatchers.IO)


    fun deleteListener(listenerId: Int): Flow<Unit> = flow {
        sessionManager.callAttr("remove_listener", listenerId)
        emit(Unit)
    }.flowOn(Dispatchers.IO)


    fun getSessions(): Flow<List<Session>> = flow {
        val sessionsPy = sessionManager.callAttr("get_sessions").asList()
        val sessions = sessionsPy.map { pyObj ->
            val sessionMap = pyObj.asMap()
            Session(
                id = sessionMap[PyObject.fromJava("id")]!!.toInt(),
                platform = sessionMap[PyObject.fromJava("platform")].toString()
            )
        }
        emit(sessions)
    }.flowOn(Dispatchers.IO)

    fun startInteractiveSession(sessionId: Int, listener: TerminalListener) {
        // Pass the Kotlin callback object directly to the Python function
        sessionManager.callAttr("start_interactive_session", sessionId, PyObject.fromJava(listener))
    }

    fun startPersistentEnumeration(sessionId: Int, listener: EnumerationListener) {
        sessionManager.callAttr(
            "start_persistent_enumeration",
            sessionId,
            PyObject.fromJava(listener)
        )
    }

    fun sendToTerminal(sessionId: Int, command: String) {
        sessionManager.callAttr("send_to_terminal", sessionId, command)
    }

    fun listFiles(sessionId: Int, path: String): Flow<List<FilesystemItem>> = flow {
        val filesPy = sessionManager.callAttr("list_files", sessionId, path).asList()
        val files = filesPy.map { pyObj ->
            val fileMap = pyObj.asMap()
            FilesystemItem(
                name = fileMap[PyObject.fromJava("name")].toString(),
                path = fileMap[PyObject.fromJava("path")].toString(),
                isDir = fileMap[PyObject.fromJava("is_dir")]!!.toBoolean()
            )
        }
        emit(files)
    }.flowOn(Dispatchers.IO)

    fun readFile(sessionId: Int, path: String): Flow<String> = flow {
        val result = sessionManager.callAttr("read_file", sessionId, path).asMap()
        val error = result[PyObject.fromJava("error")]
        if (error != null) {
            throw Exception(error.toString())
        } else {
            emit(result[PyObject.fromJava("content")].toString())
        }
    }.flowOn(Dispatchers.IO)

    fun downloadFile(sessionId: Int, remotePath: String, localPath: String): Flow<String> = flow {
        val result =
            sessionManager.callAttr("download_file", sessionId, remotePath, localPath).asMap()
        val error = result[PyObject.fromJava("error")]
        if (error != null) {
            throw Exception(error.toString())
        } else {
            emit(result[PyObject.fromJava("path")].toString())
        }
    }.flowOn(Dispatchers.IO)

    fun runExploit(sessionId: Int, exploitId: String): Flow<String> = flow {
        val result = sessionManager.callAttr("run_exploit", sessionId, exploitId).asMap()
        val error = result[PyObject.fromJava("error")]
        if (error != null) {
            throw Exception(error.toString())
        } else {
            emit(result[PyObject.fromJava("output")].toString())
        }
    }.flowOn(Dispatchers.IO)
}