package com.sunminlee.aieditor

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class ApiClient(private val context: Context) {
    private val base: String get() = context.getSharedPreferences("settings", Context.MODE_PRIVATE).getString("server", "http://10.0.2.2:8000")!!.trimEnd('/')

    fun absolute(path: String): String = if (path.startsWith("http")) path else base + path

    fun createProject(file: File, mime: String): JSONObject = multipart("/api/projects", file, mime, mapOf("still_duration_seconds" to "5"))
    fun addAsset(projectId: String, file: File, mime: String, kind: String): JSONObject = multipart("/api/projects/$projectId/assets", file, mime, mapOf("kind" to kind, "still_duration_seconds" to "5"))
    fun project(id: String): JSONObject = request("GET", "/api/projects/$id")
    fun propose(id: String, prompt: String): JSONObject = request("POST", "/api/projects/$id/commands", JSONObject().put("prompt", prompt).toString())
    fun apply(id: String, prompt: String, message: String, operations: JSONArray): JSONObject = request("POST", "/api/projects/$id/apply-plan", JSONObject().put("prompt", prompt).put("assistant_message", message).put("operations", operations).toString())
    fun replace(id: String, operations: JSONArray): JSONObject = request("PUT", "/api/projects/$id/operations", JSONObject().put("operations", operations).toString())
    fun job(id: String): JSONObject = request("GET", "/api/jobs/$id")

    private fun request(method: String, path: String, body: String? = null): JSONObject {
        val conn = URL(absolute(path)).openConnection() as HttpURLConnection
        conn.requestMethod = method
        conn.connectTimeout = 30000
        conn.readTimeout = 120000
        if (body != null) {
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.outputStream.use { it.write(body.toByteArray()) }
        }
        val code = conn.responseCode
        val text = (if (code in 200..299) conn.inputStream else conn.errorStream).bufferedReader().use { it.readText() }
        if (code !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrDefault("Request failed ($code)"))
        return JSONObject(text)
    }

    private fun multipart(path: String, file: File, mime: String, fields: Map<String, String>): JSONObject {
        val boundary = "Boundary-${System.nanoTime()}"
        val conn = URL(absolute(path)).openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.doOutput = true
        conn.connectTimeout = 30000
        conn.readTimeout = 120000
        conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        conn.outputStream.buffered().use { out ->
            fun line(s: String) { out.write(s.toByteArray()) }
            fields.forEach { (key, value) -> line("--$boundary\r\nContent-Disposition: form-data; name=\"$key\"\r\n\r\n$value\r\n") }
            line("--$boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"${file.name}\"\r\nContent-Type: $mime\r\n\r\n")
            file.inputStream().use { it.copyTo(out) }
            line("\r\n--$boundary--\r\n")
        }
        val code = conn.responseCode
        val text = (if (code in 200..299) conn.inputStream else conn.errorStream).bufferedReader().use { it.readText() }
        if (code !in 200..299) throw IllegalStateException(runCatching { JSONObject(text).optString("detail") }.getOrDefault("Upload failed ($code)"))
        return JSONObject(text)
    }
}
