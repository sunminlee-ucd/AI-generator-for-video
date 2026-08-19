package com.sunminlee.aieditor

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.ArrayAdapter
import android.widget.VideoView
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.Executors

class PhotoTurnActivity : Activity() {
    private val api by lazy { ApiClient(this) }
    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    private var frontUri: Uri? = null
    private var sideUri: Uri? = null
    private var backUri: Uri? = null

    private lateinit var root: LinearLayout
    private lateinit var status: TextView
    private lateinit var frontButton: Button
    private lateinit var sideButton: Button
    private lateinit var backButton: Button
    private lateinit var renderButton: Button
    private lateinit var preview: VideoView
    private lateinit var durationSpinner: Spinner
    private lateinit var directionSpinner: Spinner

    private val green = Color.rgb(47, 125, 50)
    private val deepGreen = Color.rgb(25, 79, 42)
    private val yellow = Color.rgb(249, 199, 79)
    private val cream = Color.rgb(255, 249, 230)
    private val mint = Color.rgb(226, 244, 224)
    private val butter = Color.rgb(255, 244, 190)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildUi()
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun buildUi() {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(cream)
            setOnApplyWindowInsetsListener { view, insets ->
                view.setPadding(dp(16), insets.systemWindowInsetTop + dp(10), dp(16), insets.systemWindowInsetBottom + dp(22))
                insets
            }
        }

        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        top.addView(TextView(this).apply {
            text = "Photo 3D Turn"
            textSize = 22f
            setTextColor(deepGreen)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }, LinearLayout.LayoutParams(0, dp(52), 1f))
        top.addView(Button(this).apply {
            text = "Close"
            background = rounded(butter, 16f, yellow)
            setTextColor(deepGreen)
            setOnClickListener { finish() }
        }, LinearLayout.LayoutParams(dp(92), dp(48)))
        root.addView(top)

        val scroll = ScrollView(this).apply { isFillViewport = true; clipToPadding = false }
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, dp(10), 0, dp(20)) }

        content.addView(TextView(this).apply {
            text = "Front + side + back photos become a short 3D-like turn clip. Backgrounds are removed first, then the object is centred and matched in size."
            textSize = 14f
            setTextColor(deepGreen)
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = rounded(Color.WHITE, 18f, Color.rgb(205, 232, 204))
        }, matchWrap())
        content.addView(space(12))

        val imageGrid = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val row1 = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; weightSum = 2f }
        frontButton = photoButton("Front photo\nRequired", mint) { pickImage(REQ_FRONT) }
        sideButton = photoButton("Side photo\nRequired", butter) { pickImage(REQ_SIDE) }
        row1.addView(frontButton, LinearLayout.LayoutParams(0, dp(78), 1f).apply { marginEnd = dp(5) })
        row1.addView(sideButton, LinearLayout.LayoutParams(0, dp(78), 1f).apply { marginStart = dp(5) })
        imageGrid.addView(row1, matchWrap())
        imageGrid.addView(space(10))
        val row2 = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; weightSum = 2f }
        backButton = photoButton("Back photo\nRequired", mint) { pickImage(REQ_BACK) }
        row2.addView(backButton, LinearLayout.LayoutParams(0, dp(78), 1f).apply { marginEnd = dp(5) })
        row2.addView(TextView(this).apply {
            text = "AUTO\nBackground cleanup"
            gravity = Gravity.CENTER
            textSize = 13f
            setTextColor(deepGreen)
            background = rounded(butter, 18f, yellow)
        }, LinearLayout.LayoutParams(0, dp(78), 1f).apply { marginStart = dp(5) })
        imageGrid.addView(row2, matchWrap())
        content.addView(imageGrid, matchWrap())

        content.addView(space(14))
        val optionRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; weightSum = 2f }
        durationSpinner = optionSpinner(arrayOf("3 sec", "4 sec", "5 sec"), 1)
        directionSpinner = optionSpinner(arrayOf("Turn left", "Turn right"), 0)
        optionRow.addView(optionCard("Length", durationSpinner), LinearLayout.LayoutParams(0, -2, 1f).apply { marginEnd = dp(5) })
        optionRow.addView(optionCard("Direction", directionSpinner), LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(5) })
        content.addView(optionRow, matchWrap())

        content.addView(space(14))
        renderButton = Button(this).apply {
            text = "Create 3D Turn"
            setTextColor(Color.WHITE)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            background = rounded(green, 18f)
            minimumHeight = dp(56)
            setOnClickListener { createTurn() }
        }
        content.addView(renderButton, matchWrap())
        content.addView(space(10))

        status = TextView(this).apply {
            text = "Choose three photos"
            textSize = 14f
            setTextColor(deepGreen)
            setPadding(dp(14), dp(11), dp(14), dp(11))
            background = rounded(Color.WHITE, 16f, yellow)
        }
        content.addView(status, matchWrap())
        content.addView(space(12))

        val previewCard = FrameLayout(this).apply { background = rounded(Color.BLACK, 22f, yellow) }
        preview = VideoView(this).apply { visibility = View.INVISIBLE }
        previewCard.addView(preview, FrameLayout.LayoutParams(-1, -1))
        previewCard.addView(TextView(this).apply {
            text = "Your turn clip will appear here"
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            textSize = 14f
        }, FrameLayout.LayoutParams(-1, -1))
        content.addView(previewCard, LinearLayout.LayoutParams(-1, dp(230)))

        scroll.addView(content)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
        root.requestApplyInsets()
    }

    private fun createTurn() {
        val front = frontUri ?: return toast("Choose a front photo")
        val side = sideUri ?: return toast("Choose a side photo")
        val back = backUri ?: return toast("Choose a back photo")
        val duration = listOf(3.0, 4.0, 5.0)[durationSpinner.selectedItemPosition]
        val direction = if (directionSpinner.selectedItemPosition == 1) "right" else "left"

        status.text = "Rendering"
        executor.execute {
            try {
                val frontMedia = MediaUtils.prepare(this, front)
                val sideMedia = MediaUtils.prepare(this, side)
                val backMedia = MediaUtils.prepare(this, back)
                require(frontMedia.kind == "image" && sideMedia.kind == "image" && backMedia.kind == "image") { "Photo 3D Turn needs three image files" }

                val project = api.createProject(frontMedia.file, frontMedia.mime)
                val projectId = project.getString("id")
                val sideAsset = api.addAsset(projectId, sideMedia.file, sideMedia.mime, "image")
                val backAsset = api.addAsset(projectId, backMedia.file, backMedia.mime, "image")
                val operation = JSONObject()
                    .put("id", UUID.randomUUID().toString().replace("-", ""))
                    .put("type", "photo_turn_3d")
                    .put("enabled", true)
                    .put("secondary_asset_id", sideAsset.getString("id"))
                    .put("tertiary_asset_id", backAsset.getString("id"))
                    .put("turn_duration_seconds", duration)
                    .put("turn_direction", direction)
                    .put("remove_background", true)
                val start = api.replace(projectId, JSONArray().put(operation))
                waitJob(start.getString("job_id"))
                val updated = api.project(projectId)
                val previewPath = updated.optString("preview_url")
                if (previewPath.isBlank()) error("3D Turn preview was not created")
                main.post {
                    status.text = "Ready"
                    preview.visibility = View.VISIBLE
                    preview.setVideoURI(Uri.parse(api.absolute(previewPath) + "?t=${System.nanoTime()}"))
                    preview.setOnPreparedListener { player -> player.isLooping = true; preview.start() }
                    toast("3D Turn ready")
                }
            } catch (error: Exception) {
                main.post {
                    status.text = "Failed"
                    toast(error.message ?: "Could not create 3D Turn")
                }
            }
        }
    }

    private fun waitJob(id: String) {
        val started = System.currentTimeMillis()
        while (true) {
            val job = api.job(id)
            when (job.optString("status")) {
                "completed" -> return
                "failed" -> error(job.optString("error", "3D Turn failed"))
            }
            if (System.currentTimeMillis() - started > 6 * 60 * 1000L) error("3D Turn timed out")
            Thread.sleep(800)
        }
    }

    private fun pickImage(code: Int) {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "image/*"
        }, code)
    }

    @Deprecated("Framework callback kept for broad Android compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        runCatching { contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
        when (requestCode) {
            REQ_FRONT -> { frontUri = uri; frontButton.text = "Front photo\nSelected ✓" }
            REQ_SIDE -> { sideUri = uri; sideButton.text = "Side photo\nSelected ✓" }
            REQ_BACK -> { backUri = uri; backButton.text = "Back photo\nSelected ✓" }
        }
        status.text = if (frontUri != null && sideUri != null && backUri != null) "Ready to create" else "Choose all three photos"
    }

    private fun photoButton(label: String, fill: Int, action: () -> Unit) = Button(this).apply {
        text = label
        textSize = 13f
        gravity = Gravity.CENTER
        setTextColor(deepGreen)
        background = rounded(fill, 18f, if (fill == mint) Color.rgb(205, 232, 204) else yellow)
        setOnClickListener { action() }
    }

    private fun optionSpinner(entries: Array<String>, selected: Int) = Spinner(this).apply {
        adapter = ArrayAdapter(this@PhotoTurnActivity, android.R.layout.simple_spinner_dropdown_item, entries)
        setSelection(selected)
    }

    private fun optionCard(title: String, spinner: Spinner) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(12), dp(10), dp(12), dp(10))
        background = rounded(Color.WHITE, 17f, Color.rgb(205, 232, 204))
        addView(TextView(this@PhotoTurnActivity).apply { text = title; textSize = 12f; setTextColor(deepGreen) }, matchWrap())
        addView(spinner, matchWrap())
    }

    private fun rounded(fill: Int, radius: Float, stroke: Int? = null) = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = dp(radius.toInt()).toFloat()
        setColor(fill)
        if (stroke != null) setStroke(dp(1), stroke)
    }

    private fun matchWrap() = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    private fun space(height: Int) = View(this).apply { layoutParams = LinearLayout.LayoutParams(-1, dp(height)) }
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    private fun toast(message: String) { android.widget.Toast.makeText(this, message, android.widget.Toast.LENGTH_LONG).show() }

    companion object {
        private const val REQ_FRONT = 501
        private const val REQ_SIDE = 502
        private const val REQ_BACK = 503
    }
}
