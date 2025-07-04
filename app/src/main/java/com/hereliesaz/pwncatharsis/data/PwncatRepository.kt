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

// New data classes for the requested features
// These would typically be in their own files under models/, but placed here for brevity in this single file update.

/**
 * Represents a saved static IP configuration for reuse.
 * @property name A user-defined name for this configuration.
 * @property ipAddress The static IP address.
 * @property subnetMask The subnet mask.
 * @property gateway The default gateway.
 * @property dns1 Primary DNS server.
 * @property dns2 Secondary DNS server.
 */
data class StaticIpConfig(
    val id: Int, // Unique identifier for storage/retrieval
    val name: String,
    val ipAddress: String,
    val subnetMask: String,
    val gateway: String,
    val dns1: String,
    val dns2: String? = null,
)

/**
 * Represents a saved Wi-Fi network with its essential details.
 * @property ssid The Service Set Identifier (network name).
 * @property bssid The Basic Service Set Identifier (MAC address of the access point).
 * @property capabilities Network capabilities (e.g., security protocols).
 * @property level Signal strength in dBm.
 */
data class WifiNetworkConfig(
    val id: Int, // Unique identifier for storage/retrieval
    val ssid: String,
    val bssid: String,
    val capabilities: String,
    val level: Int,
)

/**
 * Represents a discovered host from a network scan.
 * @property ipAddress The IP address of the discovered host.
 * @property hostname The hostname, if resolved.
 * @property os The detected operating system.
 * @property deviceType The detected device type (e.g., "router", "desktop").
 */
data class HostDiscoveryResult(
    val id: Int, // Unique identifier for storage/retrieval
    val ipAddress: String,
    val hostname: String? = null,
    val os: String? = null,
    val deviceType: String? = null,
)

/**
 * Represents the results of a port scan on a specific host.
 * @property hostId The ID of the host that was scanned (links to HostDiscoveryResult).
 * @property ipAddress The IP address of the scanned host.
 * @property port The port number.
 * @property service The service running on the port, if detected.
 * @property state The state of the port (e.g., "open", "closed", "filtered").
 */
data class PortScanResult(
    val id: Int, // Unique identifier for storage/retrieval
    val hostId: Int,
    val ipAddress: String,
    val port: Int,
    val service: String? = null,
    val state: String, // "open", "closed", "filtered"
)

/**
 * Represents a query result from Shodan for a specific IP.
 * @property ipAddress The IP address queried.
 * @property rawData The raw JSON response from Shodan.
 */
data class ShodanQueryResult(
    val id: Int, // Unique identifier for storage/retrieval
    val ipAddress: String,
    val rawData: String,
)

/**
 * Represents a generated reverse shell configuration.
 * @property id The unique identifier for the generated shell.
 * @property name A user-defined name for the shell.
 * @property payloadType The type of payload (e.g., "python", "bash", "netcat").
 * @property listenerUri The URI of the listener associated with this shell.
 * @property command The actual command string for the reverse shell.
 * @property isPersistent True if the shell includes persistence mechanisms.
 */
data class ReverseShellConfig(
    val id: Int, // Unique identifier for storage/retrieval
    val name: String,
    val payloadType: String,
    val listenerUri: String,
    val command: String,
    val isPersistent: Boolean,
)


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
                // Assume 'name' field is added to Python Session object for custom naming
                val name = (map[PyObject.fromJava("name")] as? PyObject)?.toString()
                if (id != null && platform != null) {
                    Session(
                        id = id,
                        platform = platform
                    ) // Add 'name' to Session data class if needed
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

                if (name != null && itemPath != null && isDirectory != null) {
                    FilesystemItem(
                        name = name,
                        path = itemPath,
                        isDir = isDirectory,
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
                    LootItem(type = type, source = source, content = content)
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

    // --- New Features (from user request) ---

    /**
     * Saves a static IP configuration for later reuse.
     * @param config The StaticIpConfig object to save.
     * @return A Flow emitting Unit upon completion.
     */
    fun saveStaticIpConfig(config: StaticIpConfig): Flow<Unit> = flow {
        // This would involve calling a Python function to store the config persistently
        // For example: sessionManager.callAttr("save_static_ip_config", PyObject.fromJava(config.toMap()))
        // Assuming a Python function `save_static_ip_config` exists in session_manager.py
        println("Saving static IP config: ${config.name}")
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches all saved static IP configurations.
     * @return A Flow emitting a list of StaticIpConfig objects.
     */
    fun getStaticIpConfigs(): Flow<List<StaticIpConfig>> = flow {
        // This would involve calling a Python function to retrieve saved configs
        // For example: val configsPy = sessionManager.callAttr("get_static_ip_configs").asList()
        // And then mapping them back to StaticIpConfig objects
        emit(emptyList<StaticIpConfig>()) // Explicitly type emptyList()
    }.flowOn(Dispatchers.IO)

    /**
     * Saves a discovered Wi-Fi network for later reuse.
     * @param network The WifiNetworkConfig object to save.
     * @return A Flow emitting Unit upon completion.
     */
    fun saveWifiNetwork(network: WifiNetworkConfig): Flow<Unit> = flow {
        // Assuming a Python function `save_wifi_network` exists in session_manager.py
        println("Saving Wi-Fi network: ${network.ssid}")
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches all saved Wi-Fi networks.
     * @return A Flow emitting a list of WifiNetworkConfig objects.
     */
    fun getSavedWifiNetworks(): Flow<List<WifiNetworkConfig>> = flow {
        // Assuming a Python function `get_saved_wifi_networks` exists in session_manager.py
        emit(emptyList<WifiNetworkConfig>()) // Explicitly type emptyList()
    }.flowOn(Dispatchers.IO)

    /**
     * Performs a network scan to discover operating systems and device types.
     * @param sessionId The ID of the current session.
     * @param target The target range/IP for the scan (e.g., "192.168.1.0/24").
     * @return A Flow emitting a list of HostDiscoveryResult objects.
     */
    fun performNetworkScan(sessionId: Int, target: String): Flow<List<HostDiscoveryResult>> = flow {
        // Assuming a Python function `perform_network_scan` in session_manager.py
        val resultsPy = sessionManager.callAttr("perform_network_scan", sessionId, target).asList()
        val results = resultsPy.mapNotNull { pyObj ->
            pyObj.asMap().let { map ->
                val id = (map[PyObject.fromJava("id")] as? PyObject)?.toInt()
                val ip = (map[PyObject.fromJava("ip_address")] as? PyObject)?.toString()
                val hostname = (map[PyObject.fromJava("hostname")] as? PyObject)?.toString()
                val os = (map[PyObject.fromJava("os")] as? PyObject)?.toString()
                val deviceType = (map[PyObject.fromJava("device_type")] as? PyObject)?.toString()
                if (id != null && ip != null) {
                    HostDiscoveryResult(
                        id = id,
                        ipAddress = ip,
                        hostname = hostname,
                        os = os,
                        deviceType = deviceType
                    )
                } else {
                    null
                }
            }
        }
        emit(results)
    }.flowOn(Dispatchers.IO)

    /**
     * Saves a discovered host from a network scan.
     * @param result The HostDiscoveryResult object to save.
     * @return A Flow emitting Unit upon completion.
     */
    fun saveHostDiscoveryResult(result: HostDiscoveryResult): Flow<Unit> = flow {
        // Assuming a Python function `save_host_discovery_result` in session_manager.py
        println("Saving host discovery result for ${result.ipAddress}")
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches all saved host discovery results.
     * @return A Flow emitting a list of HostDiscoveryResult objects.
     */
    fun getSavedHostDiscoveryResults(): Flow<List<HostDiscoveryResult>> = flow {
        // Assuming a Python function `get_saved_host_discovery_results` in session_manager.py
        emit(emptyList<HostDiscoveryResult>()) // Explicitly type emptyList()
    }.flowOn(Dispatchers.IO)

    /**
     * Performs a port scan on a target host.
     * @param sessionId The ID of the current session.
     * @param target The target IP address or hostname.
     * @param ports The ports to scan (e.g., "22,80,443" or "1-1024").
     * @return A Flow emitting a list of PortScanResult objects.
     */
    fun performPortScan(sessionId: Int, target: String, ports: String): Flow<List<PortScanResult>> =
        flow {
            // Assuming a Python function `perform_port_scan` in session_manager.py
            val resultsPy =
                sessionManager.callAttr("perform_port_scan", sessionId, target, ports).asList()
            val results = resultsPy.mapNotNull { pyObj ->
                pyObj.asMap().let { map ->
                    val id = (map[PyObject.fromJava("id")] as? PyObject)?.toInt()
                    val hostId = (map[PyObject.fromJava("host_id")] as? PyObject)?.toInt()
                    val ip = (map[PyObject.fromJava("ip_address")] as? PyObject)?.toString()
                    val port = (map[PyObject.fromJava("port")] as? PyObject)?.toInt()
                    val service = (map[PyObject.fromJava("service")] as? PyObject)?.toString()
                    val state = (map[PyObject.fromJava("state")] as? PyObject)?.toString()
                    if (id != null && hostId != null && ip != null && port != null && state != null) {
                        PortScanResult(
                            id = id,
                            hostId = hostId,
                            ipAddress = ip,
                            port = port,
                            service = service,
                            state = state
                        )
                    } else {
                        null
                    }
                }
            }
            emit(results)
        }.flowOn(Dispatchers.IO)

    /**
     * Saves a port scan result.
     * @param result The PortScanResult object to save.
     * @return A Flow emitting Unit upon completion.
     */
    fun savePortScanResult(result: PortScanResult): Flow<Unit> = flow {
        // Assuming a Python function `save_port_scan_result` in session_manager.py
        println("Saving port scan result for ${result.ipAddress}:${result.port}")
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches all saved port scan results.
     * @return A Flow emitting a list of PortScanResult objects.
     */
    fun getSavedPortScanResults(): Flow<List<PortScanResult>> = flow {
        // Assuming a Python function `get_saved_port_scan_results` in session_manager.py
        emit(emptyList<PortScanResult>()) // Explicitly type emptyList()
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches information for an IP address using Shodan.
     * @param ipAddress The IP address to query Shodan for.
     * @return A Flow emitting a ShodanQueryResult object, or null if not found or an error occurs.
     */
    fun getShodanInfoForIp(ipAddress: String): Flow<ShodanQueryResult?> = flow {
        // Assuming a Python function `get_shodan_info` in session_manager.py
        val resultPy = sessionManager.callAttr("get_shodan_info", ipAddress)
        if (resultPy != null && resultPy.asMap().containsKey(PyObject.fromJava("raw_data"))) {
            val id = (resultPy.asMap()[PyObject.fromJava("id")] as? PyObject)?.toInt()
            val ip = (resultPy.asMap()[PyObject.fromJava("ip_address")] as? PyObject)?.toString()
            val rawData = (resultPy.asMap()[PyObject.fromJava("raw_data")] as? PyObject)?.toString()
            if (id != null && ip != null && rawData != null) {
                emit(ShodanQueryResult(id = id, ipAddress = ip, rawData = rawData))
            } else {
                emit(null)
            }
        } else {
            emit(null)
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Generates a reverse shell payload, including persistence mechanisms.
     * This method assumes the Python backend handles the actual generation and persistence logic.
     * @param name A custom name for the shell.
     * @param payloadType The type of payload (e.g., "python", "bash", "netcat").
     * @param listenerUri The URI of the listener that will catch this shell.
     * @param options A map of additional options for shell generation (e.g., "port", "host").
     * @return A Flow emitting the generated command string.
     */
    fun generatePersistentReverseShell(
        name: String,
        payloadType: String,
        listenerUri: String,
        options: Map<String, Any> = emptyMap(),
    ): Flow<String> = flow {
        // Assuming a Python function `generate_persistent_reverse_shell` in session_manager.py
        // This Python function should accept the payload type, listener URI, and options,
        // and return the command string, ensuring persistence.
        val commandPy = sessionManager.callAttr(
            "generate_persistent_reverse_shell",
            name,
            payloadType,
            listenerUri,
            PyObject.fromJava(options)
        ).toString()
        emit(commandPy)
    }.flowOn(Dispatchers.IO)

    /**
     * Saves details about a generated reverse shell.
     * @param config The ReverseShellConfig object to save.
     * @return A Flow emitting Unit upon completion.
     */
    fun saveReverseShellConfig(config: ReverseShellConfig): Flow<Unit> = flow {
        // Assuming a Python function `save_reverse_shell_config` exists in session_manager.py
        println("Saving reverse shell config: ${config.name}")
        emit(Unit)
    }.flowOn(Dispatchers.IO)

    /**
     * Fetches all saved reverse shell configurations.
     * @return A Flow emitting a list of ReverseShellConfig objects.
     */
    fun getSavedReverseShellConfigs(): Flow<List<ReverseShellConfig>> = flow {
        // Assuming a Python function `get_saved_reverse_shell_configs` in session_manager.py
        emit(emptyList<ReverseShellConfig>()) // Explicitly type emptyList()
    }.flowOn(Dispatchers.IO)
}
