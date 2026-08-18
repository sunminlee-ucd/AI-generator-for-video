package com.sunminlee.aieditor

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.OpenableColumns
import java.io.File
import java.io.FileOutputStream

object MediaUtils {
    data class Prepared(val file: File, val mime: String, val kind: String)

    fun prepare(context: Context, uri: Uri): Prepared {
        val resolver = context.contentResolver
        val mime = resolver.getType(uri) ?: "application/octet-stream"
        return if (mime.startsWith("image/")) prepareImage(context, uri)
        else copy(context, uri, mime, if (mime.startsWith("video/")) "video" else "audio")
    }

    private fun prepareImage(context: Context, uri: Uri): Prepared {
        val resolver = context.contentResolver
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)!!.use { BitmapFactory.decodeStream(it, null, bounds) }
        var sample = 1
        while (maxOf(bounds.outWidth / sample, bounds.outHeight / sample) > 2048) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        val bitmap = resolver.openInputStream(uri)!!.use { BitmapFactory.decodeStream(it, null, options) }
            ?: error("Could not decode image")
        val out = File(context.cacheDir, "photo-${System.nanoTime()}.jpg")
        FileOutputStream(out).use { bitmap.compress(Bitmap.CompressFormat.JPEG, 90, it) }
        bitmap.recycle()
        return Prepared(out, "image/jpeg", "image")
    }

    private fun copy(context: Context, uri: Uri, mime: String, kind: String): Prepared {
        val name = displayName(context, uri) ?: "$kind-${System.nanoTime()}"
        val ext = name.substringAfterLast('.', if (kind == "video") "mp4" else "m4a")
        val out = File(context.cacheDir, "$kind-${System.nanoTime()}.$ext")
        context.contentResolver.openInputStream(uri)!!.use { input ->
            out.outputStream().use { input.copyTo(it) }
        }
        return Prepared(out, mime, kind)
    }

    private fun displayName(context: Context, uri: Uri): String? =
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }
}
