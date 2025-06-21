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

class PwncatRepository {

    private val python = Python.getInstance()
    private val sessionManager: PyObject = python.getModule("session_manager")

    init {
        sessionManager.callAttr("initialize_manager")
    }

    /**
     * Fetches a list of pwncat listeners from the Python backend.
     * Maps PyObject dictionaries to Listener data class instances.
     *
     * @return A Flow emitting a list of Listener objects.
     */
    fun getListeners(): Flow<List<Listener>> = flow {
        val listenersPy = sessionManager.callAttr("get_listeners").asList()
        val listeners = listenersPy.mapNotNull { pyObj ->
            pyObj.asMap().let { map ->
                val id = (map[PyObject.fromJava("id")] as? PyObject)?.toInt()
                val uri = (map[PyObject.fromJava("uri")] as? PyObject)?.toString()
                if (id != null && uri != null) {
                    Listener(id = id, uri = uri)
                } else {
                    // Log or handle the case where mapping fails for an item
                    null
                }
            }
        }
        emit(listeners)
    }.flowOn(Dispatchers.IO)

    /**
     * Creates a new pwncat listener on the Python backend.
     *
     * @param uri The URI for the new listener.
     * @return A Flow emitting Unit upon completion.
     */
    fun createListener(uri: String): Flow<Unit> = flow {
        sessionManager.callAttr("create_listener", uri)
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Deletes a pwncat listener from the Python backend.
     *
     * @param listenerId The ID of the listener to delete.
     * @return A Flow emitting Unit upon completion.
     */
    fun deleteListener(listenerId: Int): Flow<Unit> = flow {
        sessionManager.callAttr("remove_listener", listenerId)
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches a list of pwncat sessions from the Python backend.
     * Maps PyObject dictionaries to Session data class instances.
     *
     * @return A Flow emitting a list of Session objects.
     */
    fun getSessions(): Flow<List<Session>> = flow {
        val sessionsPy = sessionManager.callAttr("get_sessions").asList()
        val sessions = sessionsPy.mapNotNull { pyObj ->
            pyObj.asMap().let { map ->
                val id = (map[PyObject.fromJava("id")] as? PyObject)?.toInt()
                val platform = (map[PyObject.fromJava("platform")] as? PyObject)?.toString()
                if (id != null && platform != null) {
                    Session(id = id, platform = platform)
                } else {
                    null
                }
            }
        }
        emit(sessions)
    }.flowOn(Dispatchers.IO)

    /**
     * Starts an interactive session for a given session ID.
     *
     * @param sessionId The ID of the session.
     * @param listener The TerminalListener for interactive output.
     */
    fun startInteractiveSession(sessionId: Int, listener: TerminalListener) {
        sessionManager.callAttr("start_interactive_session", sessionId, PyObject.fromJava(listener))
    }

    /**
     * Starts persistent enumeration for a given session ID.
     *
     * @param sessionId The ID of the session.
     * @param listener The EnumerationListener for enumeration updates.
     */
    fun startPersistentEnumeration(sessionId: Int, listener: EnumerationListener) {
        sessionManager.callAttr(
            "start_persistent_enumeration",
            sessionId,
            PyObject.fromJava(listener)
        )
    }

    /**
     * Sends a command to the terminal of an interactive session.
     *
     * @param sessionId The ID of the session.
     * @param command The command string to send.
     */
    fun sendToTerminal(sessionId: Int, command: String) {
        sessionManager.callAttr("send_to_terminal", sessionId, command)
    }

    /**
     * Lists files in a given path for a session.
     * Maps PyObject dictionaries to FilesystemItem data class instances.
     *
     * @param sessionId The ID of the session.
     * @param path The path to list.
     * @return A Flow emitting a list of FilesystemItem objects.
     */
    fun listFiles(sessionId: Int, path: String): Flow<List<FilesystemItem>> = flow {
        val filesPy = sessionManager.callAttr("list_files", sessionId, path).asList()
        val files = filesPy.mapNotNull { pyObj ->
            pyObj.asMap().let { map ->
                val name = (map[PyObject.fromJava("name")] as? PyObject)?.toString()
                val itemPath = (map[PyObject.fromJava("path")] as? PyObject)?.toString()
                val isDirectory = (map[PyObject.fromJava("is_directory")] as? PyObject)?.toBoolean()
                // Removed size, permissions, owner, group as they are not in FilesystemItem data class
                // val size = (map[PyObject.fromJava("size")] as? PyObject)?.toLong()
                // val permissions = (map[PyObject.fromJava("permissions")] as? PyObject)?.toString()
                // val owner = (map[PyObject.fromJava("owner")] as? PyObject)?.toString()
                // val group = (map[PyObject.fromJava("group")] as? PyObject)?.toString()

                if (name != null && itemPath != null && isDirectory != null) {
                    FilesystemItem(
                        name = name,
                        path = itemPath,
                        isDir = isDirectory, // Correct parameter name
                        // size = size, // Removed
                        // permissions = permissions, // Removed
                        // owner = owner, // Removed
                        // group = group // Removed
                    )
                } else {
                    null
                }
            }
        }
        emit(files)
    }.flowOn(Dispatchers.IO)

    /**
     * Reads the content of a file for a given session.
     *
     * @param sessionId The ID of the session.
     * @param path The path of the file to read.
     * @return A Flow emitting the file content as a String, or throwing an exception on error.
     */
    fun readFile(sessionId: Int, path: String): Flow<String> = flow {
        val result = sessionManager.callAttr("read_file", sessionId, path).asMap()
        val error = result[PyObject.fromJava("error")]
        if (error != null) {
            throw Exception(error.toString())
        } else {
            emit(result[PyObject.fromJava("content")].toString())
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Downloads a file from the remote session to a local path.
     *
     * @param sessionId The ID of the session.
     * @param remotePath The remote path of the file.
     * @param localPath The local path to save the file.
     * @return A Flow emitting the local path of the downloaded file, or throwing an exception on error.
     */
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

    /**
     * Runs an exploit on a given session.
     *
     * @param sessionId The ID of the session.
     * @param exploitId The ID of the exploit to run.
     * @return A Flow emitting the output of the exploit, or throwing an exception on error.
     */
    fun runExploit(sessionId: Int, exploitId: String): Flow<String> = flow {
        val result = sessionManager.callAttr("run_exploit", sessionId, exploitId).asMap()
        val error = result[PyObject.fromJava("error")]
        if (error != null) {
            throw Exception(error.toString())
        } else {
            emit(result[PyObject.fromJava("output")].toString())
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches all loot items from the Python backend.
     * Maps PyObject dictionaries to LootItem data class instances.
     *
     * @return A Flow emitting a list of LootItem objects.
     */
    fun getAllLoot(): Flow<List<LootItem>> = flow {
        val lootPy = sessionManager.callAttr("get_all_loot").asList()
        val lootItems = lootPy.mapNotNull { pyObj ->
            pyObj.asMap().let { map ->
                // The LootItem data class does not have an 'id' parameter.
                // It has 'type', 'source', and 'content'.
                val type = (map[PyObject.fromJava("type")] as? PyObject)?.toString()
                val source = (map[PyObject.fromJava("source")] as? PyObject)?.toString()
                val content = (map[PyObject.fromJava("content")] as? PyObject)?.toString()
                if (type != null && source != null && content != null) {
                    LootItem(
                        type = type,
                        source = source,
                        content = content
                    ) // Corrected parameter names
                } else {
                    null
                }
            }
        }
        emit(lootItems)
    }.flowOn(Dispatchers.IO)

    /**
     * Generates a phishing site using the Python backend.
     *
     * @param targetUrl The target URL for the phishing site.
     * @param payload The payload to embed.
     * @return A Flow emitting the path to the generated site, or throwing an exception on error.
     */
    fun generatePhishingSite(targetUrl: String, payload: String): Flow<String> = flow {
        val result = sessionManager.callAttr("generate_phishing_site", targetUrl, payload).asMap()
        val error = result[PyObject.fromJava("error")]
        if (error != null) {
            throw Exception(error.toString())
        } else {
            emit(result[PyObject.fromJava("path")].toString())
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches a list of available scripts from the Python backend.
     * Maps PyObject dictionaries to Script data class instances.
     *
     * @return A Flow emitting a list of Script objects.
     */
    fun getScripts(): Flow<List<Script>> = flow {
        val scriptsPy = sessionManager.callAttr("get_scripts").asList()
        val scripts = scriptsPy.mapNotNull { pyObj ->
            pyObj.asMap().let { map ->
                val name = (map[PyObject.fromJava("name")] as? PyObject)?.toString()
                val content = (map[PyObject.fromJava("content")] as? PyObject)?.toString()
                if (name != null && content != null) {
                    Script(name = name, content = content)
                } else {
                    null
                }
            }
        }
        emit(scripts)
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches the content of a specific script.
     *
     * @param name The name of the script.
     * @return A Flow emitting the Script object, or null if not found or an error occurs.
     */
    fun getScriptContent(name: String): Flow<Script?> = flow {
        val result = sessionManager.callAttr("get_script_content", name).asMap()
        if (result.containsKey(PyObject.fromJava("error"))) {
            emit(null)
        } else {
            val scriptName = (result[PyObject.fromJava("name")] as? PyObject)?.toString()
            val content = (result[PyObject.fromJava("content")] as? PyObject)?.toString()
            if (scriptName != null && content != null) {
                emit(Script(name = scriptName, content = content))
            } else {
                emit(null)
            }
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Saves a script to the Python backend.
     *
     * @param name The name of the script.
     * @param content The content of the script.
     * @return A Flow emitting Unit upon completion.
     */
    fun saveScript(name: String, content: String): Flow<Unit> = flow {
        sessionManager.callAttr("save_script", name, content)
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Deletes a script from the Python backend.
     *
     * @param name The name of the script.
     * @return A Flow emitting Unit upon completion.
     */
    fun deleteScript(name: String): Flow<Unit> = flow {
        sessionManager.callAttr("delete_script", name)
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Runs a script on a given session.
     *
     * @param sessionId The ID of the session.
     * @param name The name of the script to run.
     * @return A Flow emitting Unit upon completion.
     */
    fun runScript(sessionId: Int, name: String): Flow<Unit> = flow {
        sessionManager.callAttr("run_script", sessionId, name)
        emit(Unit)
    }.flowOn(Dispatchers.IO)
}
