package com.hereliesaz.pwncatharsis.data.remote

import com.hereliesaz.pwncatharsis.models.ExploitResult
import com.hereliesaz.pwncatharsis.models.FileContent
import com.hereliesaz.pwncatharsis.models.FileUploadResult
import com.hereliesaz.pwncatharsis.models.FilesystemItem
import com.hereliesaz.pwncatharsis.models.Listener
import com.hereliesaz.pwncatharsis.models.LootItem
import com.hereliesaz.pwncatharsis.models.NetworkInfo
import com.hereliesaz.pwncatharsis.models.PrivescFinding
import com.hereliesaz.pwncatharsis.models.Session
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    // Listeners
    @GET("listeners")
    suspend fun getListeners(): Response<List<Listener>>

    @POST("listeners")
    suspend fun createListener(@Body listener: Listener): Response<Listener>

    @DELETE("listeners/{id}")
    suspend fun deleteListener(@Path("id") id: Int): Response<Unit>

    // Sessions
    @GET("sessions")
    suspend fun getSessions(): Response<List<Session>>

    @GET("sessions/{id}")
    suspend fun getSession(@Path("id") id: Int): Response<Session>

    @DELETE("sessions/{id}")
    suspend fun deleteSession(@Path("id") id: Int): Response<Unit>

    // Filesystem
    @GET("sessions/{id}/fs")
    suspend fun listFiles(
        @Path("id") sessionId: Int,
        @Query("path") path: String,
    ): Response<List<FilesystemItem>>

    @GET("sessions/{id}/fs/cat")
    suspend fun readFile(
        @Path("id") sessionId: Int,
        @Query("path") path: String,
    ): Response<FileContent>

    @Multipart
    @POST("sessions/{id}/fs/upload")
    suspend fun uploadFile(
        @Path("id") sessionId: Int,
        @Query("path") path: String,
        @Part file: MultipartBody.Part,
    ): Response<FileUploadResult>

    @GET("sessions/{id}/fs/download")
    suspend fun downloadFile(
        @Path("id") sessionId: Int,
        @Query("path") path: String,
    ): Response<ResponseBody>

    // Processes
    @GET("sessions/{id}/ps")
    suspend fun listProcesses(@Path("id") sessionId: Int): Response<List<com.hereliesaz.pwncatharsis.models.Process>>

    // Network
    @GET("sessions/{id}/net")
    suspend fun getNetworkInfo(@Path("id") sessionId: Int): Response<NetworkInfo>

    // Privesc
    @GET("sessions/{id}/privesc")
    suspend fun getPrivescFindings(@Path("id") sessionId: Int): Response<List<PrivescFinding>>

    @POST("sessions/{id}/privesc")
    suspend fun runPrivescScan(@Path("id") sessionId: Int): Response<List<PrivescFinding>>

    // Loot
    @GET("sessions/{id}/loot")
    suspend fun getLoot(@Path("id") sessionId: Int): Response<List<LootItem>>

    @POST("sessions/{id}/loot")
    suspend fun addLoot(@Path("id") sessionId: Int, @Body loot: LootItem): Response<LootItem>

    // Exploit
    @POST("sessions/{id}/exploit")
    suspend fun runExploit(
        @Path("id") sessionId: Int,
        @Body technique: Map<String, String>,
    ): Response<ExploitResult>
}