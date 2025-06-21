package com.hereliesaz.pwncatharsis.data

import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.hereliesaz.pwncatharsis.models.FilesystemItem
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.models.LootItem
import com.hereliesaz.pwncatharsis.models.Script
import com.hereliesaz.pwncatharsis.models.Session
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.serialization.json.Json

class PwncatRepository {

    private val python = Python.getInstance()
    private val sessionManager: PyObject = python.getModule("session_manager")
    private val json = Json { ignoreUnknownKeys = true }

    init {
        sessionManager.callAttr("initialize_manager")
    }

    fun getListeners(): Flow<List<Listener>> = flow {
        val listenersPy = sessionManager.callAttr("get_listeners").asList()
        val listeners = listenersPy.map { pyObj ->
            json.decodeFromString<Listener>(pyObj.toString())
        }
        emit(listeners)
    }.flowOn(Dispatchers.IO)

    fun createListener(uri: String): Flow<Unit> = flow {
        sessionManager.callAttr("create_listener", uri)
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    fun deleteListener(listenerId: Int): Flow<Unit> = flow {
        sessionManager.callAttr("remove_listener", listenerId)
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    fun getSessions(): Flow<List<Session>> = flow {
        val sessionsPy = sessionManager.callAttr("get_sessions").asList()
        val sessions = sessionsPy.map { pyObj ->
            json.decodeFromString<Session>(pyObj.toString())
        }
        emit(sessions)
    }.flowOn(Dispatchers.IO)

    fun startInteractiveSession(sessionId: Int, listener: TerminalListener) {
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
            json.decodeFromString<FilesystemItem>(pyObj.toString())
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

    fun getAllLoot(): Flow<List<LootItem>> = flow {
        val lootPy = sessionManager.callAttr("get_all_loot").asList()
        val lootItems = lootPy.map { pyObj ->
            json.decodeFromString<LootItem>(pyObj.toString())
        }
        emit(lootItems)
    }.flowOn(Dispatchers.IO)

    fun generatePhishingSite(targetUrl: String, payload: String): Flow<String> = flow {
        val result = sessionManager.callAttr("generate_phishing_site", targetUrl, payload).asMap()
        val error = result[PyObject.fromJava("error")]
        if (error != null) {
            throw Exception(error.toString())
        } else {
            emit(result[PyObject.fromJava("path")].toString())
        }
    }.flowOn(Dispatchers.IO)

    fun getScripts(): Flow<List<Script>> = flow {
        val scriptsPy = sessionManager.callAttr("get_scripts").asList()
        val scripts = scriptsPy.map { pyObj ->
            json.decodeFromString<Script>(pyObj.toString())
        }
        emit(scripts)
    }.flowOn(Dispatchers.IO)

    fun getScriptContent(name: String): Flow<Script?> = flow {
        val result = sessionManager.callAttr("get_script_content", name).asMap()
        if (result.containsKey(PyObject.fromJava("error"))) {
            emit(null)
        } else {
            emit(json.decodeFromString<Script>(result.toString()))
        }
    }.flowOn(Dispatchers.IO)

    fun saveScript(name: String, content: String): Flow<Unit> = flow {
        sessionManager.callAttr("save_script", name, content)
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    fun deleteScript(name: String): Flow<Unit> = flow {
        sessionManager.callAttr("delete_script", name)
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    fun runScript(sessionId: Int, name: String): Flow<Unit> = flow {
        sessionManager.callAttr("run_script", sessionId, name)
        emit(Unit)
    }.flowOn(Dispatchers.IO)
}