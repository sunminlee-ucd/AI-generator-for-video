package com.sunminlee.aieditor

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import android.view.ViewGroup
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

class MainActivity : Activity() {
    private val api by lazy { ApiClient(this) }
    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    private lateinit var root: LinearLayout
    private lateinit var previewBox: FrameLayout
    private lateinit var imagePreview: ImageView
    private lateinit var videoPreview: VideoView
    private lateinit var accordion: LinearLayout
    private lateinit var status: TextView

    private var project: JSONObject? = null
    private var operations = JSONArray()
    private var proposal: JSONObject? = null
    private var proposalPrompt = ""
    private var sourceUri: Uri? = null
    private var sourceKind = "video"
    private var expandedPanel = "ai"

    private val green = Color.rgb(47, 125, 50)
    private val deepGreen = Color.rgb(25, 79, 42)
    private val yellow = Color.rgb(249, 199, 79)
    private val cream = Color.rgb(255, 249, 230)
    private val muted = Color.rgb(98, 105, 101)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildShell()
        showWelcome()
    }

    private fun buildShell() {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(cream)
            setOnApplyWindowInsetsListener { view, insets ->
                view.setPadding(
                    dp(14),
                    insets.systemWindowInsetTop + dp(8),
                    dp(14),
                    insets.systemWindowInsetBottom + dp(18)
                )
                insets
            }
        }
        status = TextView(this).apply {
            text = "Ready"
            textSize = 14f
            setTextColor(deepGreen)
            setPadding(dp(14), dp(10), dp(14), dp(10))
            background = rounded(Color.WHITE, 16f, yellow)
        }
    }

    private fun showWelcome() {
        root.removeAllViews()
        root.addView(status, matchWrap())

        val scroll = ScrollView(this).apply { isFillViewport = true }
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(18), 0, dp(12))
        }

        val hero = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(22), dp(22), dp(22))
            background = GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                intArrayOf(green, Color.rgb(93, 154, 72), yellow)
            ).apply { cornerRadius = dp(28).toFloat() }
        }
        hero.addView(TextView(this).apply {
            text = "AI Media Editor"
            textSize = 30f
            setTextColor(Color.WHITE)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }, matchWrap())
        hero.addView(TextView(this).apply {
            text = "Start with a photo or video. Chat with AI, review the plan, then fine-tune only what you need."
            textSize = 16f
            setTextColor(Color.WHITE)
            setPadding(0, dp(10), 0, 0)
        }, matchWrap())
        wrap.addView(hero, matchWrap())

        wrap.addView(spacer(16))
        listOf(
            "1  Choose a photo or video",
            "2  Tell AI what you want",
            "3  Open only the section you need"
        ).forEach { label ->
            wrap.addView(TextView(this).apply {
                text = label
                textSize = 15f
                setTextColor(deepGreen)
                setPadding(dp(16), dp(15), dp(16), dp(15))
                background = rounded(Color.WHITE, 18f)
            }, matchWrap().apply { bottomMargin = dp(9) })
        }

        wrap.addView(spacer(8))
        wrap.addView(primaryButton("Choose photo or video") { pickVisual(REQ_SOURCE) }, matchWrap())
        wrap.addView(spacer(10))
        wrap.addView(secondaryButton("Server settings") { serverSettings() }, matchWrap())

        scroll.addView(wrap)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
        root.requestApplyInsets()
    }

    private fun showEditor() {
        root.removeAllViews()

        val top = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(4), dp(6), dp(4), dp(10))
        }
        top.addView(TextView(this).apply {
            text = project?.optString("filename") ?: "Project"
            textSize = 18f
            setTextColor(deepGreen)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }, LinearLayout.LayoutParams(0, dp(48), 1f))
        top.addView(secondaryButton("Settings") { serverSettings() }, LinearLayout.LayoutParams(dp(108), dp(48)))
        root.addView(top)

        previewBox = FrameLayout(this).apply {
            background = rounded(Color.BLACK, 24f, yellow)
        }
        imagePreview = ImageView(this).apply {
            scaleType = ImageView.ScaleType.FIT_CENTER
            visibility = View.GONE
        }
        videoPreview = VideoView(this).apply { visibility = View.GONE }
        previewBox.addView(imagePreview, FrameLayout.LayoutParams(-1, -1))
        previewBox.addView(videoPreview, FrameLayout.LayoutParams(-1, -1))
        root.addView(previewBox, LinearLayout.LayoutParams(-1, dp(220)))
        showLocalSource()

        root.addView(spacer(10))
        root.addView(status, matchWrap())
        root.addView(spacer(10))

        val scroll = ScrollView(this).apply {
            isFillViewport = true
            clipToPadding = false
            setPadding(0, 0, 0, dp(14))
        }
        accordion = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 0, 0, dp(18))
        }
        scroll.addView(accordion)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))

        refreshAccordion()
        setContentView(root)
        root.requestApplyInsets()
    }

    private fun refreshAccordion() {
        if (!::accordion.isInitialized) return
        accordion.removeAllViews()
        accordion.addView(sectionCard("ai", "AI assistant", "Chat first, then review the plan", green, aiPanel()), matchWrap().apply { bottomMargin = dp(10) })
        accordion.addView(sectionCard("edits", "Edit controls", "Review and fine-tune AI changes", yellow, editsPanel()), matchWrap().apply { bottomMargin = dp(10) })
        accordion.addView(sectionCard("media", "Media library", "Add photo, video, or music", green, mediaPanel()), matchWrap())
    }

    private fun sectionCard(key: String, title: String, subtitle: String, accent: Int, body: View): View {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = rounded(Color.WHITE, 22f, accent)
        }
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(15), dp(16), dp(15))
        }
        val textColumn = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, -2, 1f)
        }
        textColumn.addView(TextView(this).apply {
            text = title
            textSize = 18f
            setTextColor(deepGreen)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        })
        textColumn.addView(TextView(this).apply {
            text = subtitle
            textSize = 12f
            setTextColor(muted)
        })
        header.addView(textColumn)
        header.addView(TextView(this).apply {
            this.text = if (expandedPanel == key) "⌃" else "⌄"
            textSize = 24f
            setTextColor(accent)
            gravity = Gravity.CENTER
        }, LinearLayout.LayoutParams(dp(42), dp(42)))
        header.setOnClickListener {
            expandedPanel = if (expandedPanel == key) "" else key
            refreshAccordion()
        }
        card.addView(header, matchWrap())
        if (expandedPanel == key) {
            val holder = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(14), 0, dp(14), dp(14))
            }
            holder.addView(body, matchWrap())
            card.addView(holder, matchWrap())
        }
        return card
    }

    private fun switchPanel(panel: String) {
        expandedPanel = panel
        refreshAccordion()
    }

    private fun aiPanel(): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        box.addView(TextView(this).apply {
            text = "Tell AI what you want. You will review every change before rendering."
            textSize = 14f
            setTextColor(muted)
            setPadding(dp(2), 0, dp(2), dp(10))
        }, matchWrap())

        val prompt = EditText(this).apply {
            hint = "Describe the edit you want"
            minHeight = dp(76)
            maxLines = 4
            setTextColor(deepGreen)
            setHintTextColor(muted)
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = rounded(cream, 16f)
        }

        listOf("Trim the beginning", "Add a title", "Put a photo in a star", "Add background music").forEach { example ->
            box.addView(secondaryButton(example) { prompt.setText(example) }, matchWrap().apply { bottomMargin = dp(7) })
        }
        box.addView(spacer(4))
        box.addView(prompt, matchWrap())
        box.addView(spacer(10))
        box.addView(primaryButton("Ask AI") {
            val p = prompt.text.toString().trim()
            if (p.isNotEmpty()) askAI(p)
        }, matchWrap())
        return box
    }

    private fun editsPanel(): View {
        val list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        if (operations.length() == 0) {
            list.addView(TextView(this).apply {
                text = "No edits yet. Ask AI for a change first."
                gravity = Gravity.CENTER
                setTextColor(muted)
                setPadding(dp(16), dp(28), dp(16), dp(28))
            }, matchWrap())
        }
        for (i in 0 until operations.length()) list.addView(operationCard(operations.getJSONObject(i)), matchWrap())
        if (operations.length() > 0) {
            list.addView(primaryButton(if (proposal != null) "Apply AI changes" else "Render my changes") {
                if (proposal != null) applyProposal() else renderChanges()
            }, matchWrap())
        }
        return list
    }

    private fun operationCard(op: JSONObject): View {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = rounded(Color.rgb(250, 251, 247), 17f)
        }
        val head = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val title = TextView(this).apply {
            text = opTitle(op.optString("type"))
            textSize = 17f
            setTextColor(deepGreen)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        val enabled = Switch(this).apply {
            isChecked = op.optBoolean("enabled", true)
            text = "Use"
            setTextColor(deepGreen)
            setOnCheckedChangeListener { _, value -> op.put("enabled", value) }
        }
        head.addView(title, LinearLayout.LayoutParams(0, dp(48), 1f))
        head.addView(enabled)
        card.addView(head)
        card.addView(TextView(this).apply {
            text = summary(op)
            setTextColor(muted)
            setPadding(0, 0, 0, dp(8))
        })

        val details = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; visibility = View.GONE }
        if (isVisual(op)) {
            details.addView(TextView(this).apply {
                text = "Drag to move. Pinch to resize."
                setTextColor(muted)
                setPadding(0, 0, 0, dp(7))
            })
            details.addView(PlacementView(this@MainActivity, op, projectWidth(), projectHeight()), LinearLayout.LayoutParams(-1, dp(220)))
        }
        if (op.optString("type") == "text_overlay") {
            details.addView(EditText(this).apply {
                setText(op.optString("text"))
                hint = "Text"
                background = rounded(cream, 14f)
                setPadding(dp(12), dp(10), dp(12), dp(10))
                setOnFocusChangeListener { _, hasFocus -> if (!hasFocus) op.put("text", text.toString()) }
            }, matchWrap())
        }
        if (op.optString("type").startsWith("masked")) {
            val spinner = Spinner(this)
            val shapes = arrayOf("star", "circle", "heart", "triangle")
            spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, shapes)
            spinner.setSelection(shapes.indexOf(op.optString("shape", "star")).coerceAtLeast(0))
            spinner.onItemSelectedListener = SimpleItemSelected { op.put("shape", shapes[it]) }
            details.addView(spinner, matchWrap())
        }
        card.addView(details)
        card.addView(adjustButton("Adjust") { button ->
            details.visibility = if (details.visibility == View.VISIBLE) View.GONE else View.VISIBLE
            button.text = if (details.visibility == View.VISIBLE) "Done" else "Adjust"
        }, matchWrap())
        card.layoutParams = LinearLayout.LayoutParams(-1, -2).apply { setMargins(0, 0, 0, dp(9)) }
        return card
    }

    private fun mediaPanel(): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        box.addView(primaryButton("Add photo or video") { pickVisual(REQ_ASSET) }, matchWrap())
        box.addView(spacer(8))
        box.addView(secondaryButton("Add background music") { pickAudio() }, matchWrap())
        val assets = project?.optJSONArray("assets") ?: JSONArray()
        if (assets.length() > 0) box.addView(spacer(10))
        for (i in 0 until assets.length()) {
            val asset = assets.getJSONObject(i)
            box.addView(TextView(this).apply {
                text = "${if (asset.optString("kind") == "image") "Photo" else asset.optString("kind").replaceFirstChar { it.uppercase() }}  ·  ${asset.optString("filename")}"
                textSize = 15f
                setTextColor(deepGreen)
                setPadding(dp(12), dp(12), dp(12), dp(12))
                background = rounded(cream, 14f)
            }, matchWrap().apply { bottomMargin = dp(7) })
        }
        return box
    }

    private fun askAI(prompt: String) = runAsync("AI is planning") {
        val p = project ?: return@runAsync
        val result = api.propose(p.getString("id"), prompt)
        proposal = result.getJSONObject("plan")
        proposalPrompt = prompt
        operations = copyArray(p.optJSONArray("operations") ?: JSONArray())
        val proposed = proposal!!.getJSONArray("operations")
        for (i in 0 until proposed.length()) operations.put(proposed.getJSONObject(i))
        main.post { switchPanel("edits") }
    }

    private fun applyProposal() = runAsync("Rendering") {
        val p = project ?: return@runAsync
        val existing = p.optJSONArray("operations")?.length() ?: 0
        val proposed = JSONArray()
        for (i in existing until operations.length()) proposed.put(operations.getJSONObject(i))
        val start = api.apply(p.getString("id"), proposalPrompt, proposal!!.optString("assistant_message", "Apply changes"), proposed)
        waitJob(start.getString("job_id"))
        project = api.project(p.getString("id"))
        operations = copyArray(project!!.optJSONArray("operations") ?: JSONArray())
        proposal = null
        main.post { playRemotePreview(); switchPanel("edits") }
    }

    private fun renderChanges() = runAsync("Rendering") {
        val p = project ?: return@runAsync
        val start = api.replace(p.getString("id"), operations)
        waitJob(start.getString("job_id"))
        project = api.project(p.getString("id"))
        operations = copyArray(project!!.optJSONArray("operations") ?: JSONArray())
        main.post { playRemotePreview(); switchPanel("edits") }
    }

    private fun waitJob(id: String) {
        while (true) {
            val job = api.job(id)
            if (job.optString("status") == "completed") return
            if (job.optString("status") == "failed") error(job.optString("error", "Rendering failed"))
            Thread.sleep(850)
        }
    }

    private fun pickVisual(code: Int) {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("image/*", "video/*"))
        }, code)
    }

    private fun pickAudio() {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "audio/*"
        }, REQ_AUDIO)
    }

    @Deprecated("Deprecated in Android framework but kept for broad device compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        when (requestCode) {
            REQ_SOURCE -> { sourceUri = uri; uploadSource(uri) }
            REQ_ASSET -> uploadAsset(uri)
            REQ_AUDIO -> uploadAsset(uri)
        }
    }

    private fun uploadSource(uri: Uri) = runAsync("Uploading") {
        val media = MediaUtils.prepare(this, uri)
        sourceKind = media.kind
        project = api.createProject(media.file, media.mime)
        operations = JSONArray()
        proposal = null
        expandedPanel = "ai"
        main.post { showEditor() }
    }

    private fun uploadAsset(uri: Uri) = runAsync("Adding media") {
        val p = project ?: return@runAsync
        val media = MediaUtils.prepare(this, uri)
        api.addAsset(p.getString("id"), media.file, media.mime, media.kind)
        project = api.project(p.getString("id"))
        main.post { switchPanel("media") }
    }

    private fun showLocalSource() {
        val uri = sourceUri ?: return
        imagePreview.visibility = if (sourceKind == "image") View.VISIBLE else View.GONE
        videoPreview.visibility = if (sourceKind == "video") View.VISIBLE else View.GONE
        if (sourceKind == "image") {
            imagePreview.setImageURI(uri)
        } else {
            videoPreview.setVideoURI(uri)
            videoPreview.setOnPreparedListener { it.isLooping = true; videoPreview.start() }
        }
    }

    private fun playRemotePreview() {
        val path = project?.optString("preview_url")?.takeIf { it.isNotBlank() } ?: return
        imagePreview.visibility = View.GONE
        videoPreview.visibility = View.VISIBLE
        videoPreview.setVideoURI(Uri.parse(api.absolute(path) + "?t=${System.nanoTime()}"))
        videoPreview.setOnPreparedListener { it.isLooping = true; videoPreview.start() }
    }

    private fun serverSettings() {
        val prefs = getSharedPreferences("settings", MODE_PRIVATE)
        val raw = prefs.getString("server", null)
        val current = ApiClient.normalizeServer(raw)
        if (raw != current) prefs.edit().putString("server", current).apply()
        val input = EditText(this).apply {
            setText(current)
            hint = ApiClient.DEFAULT_SERVER
            setSingleLine(false)
            setPadding(dp(12), dp(10), dp(12), dp(10))
        }
        AlertDialog.Builder(this)
            .setTitle("Backend server")
            .setMessage("Cloud Run is the default. You normally do not need to change this.")
            .setView(input)
            .setPositiveButton("Save") { _, _ ->
                prefs.edit().putString("server", ApiClient.normalizeServer(input.text.toString())).apply()
            }
            .setNeutralButton("Use Cloud Run") { _, _ ->
                prefs.edit().putString("server", ApiClient.DEFAULT_SERVER).apply()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun runAsync(label: String, block: () -> Unit) {
        main.post { status.text = label }
        executor.execute {
            try {
                block()
                main.post { status.text = "Ready" }
            } catch (e: Exception) {
                main.post {
                    status.text = "Failed"
                    Toast.makeText(this, e.message ?: "Error", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun opTitle(type: String) = when (type) {
        "trim" -> "Trim"
        "text_overlay" -> "Text"
        "split_screen" -> "Split screen"
        "picture_in_picture", "media_overlay" -> "Media layer"
        "masked_video", "masked_media" -> "Shape layer"
        "music" -> "Background music"
        else -> type.replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    private fun summary(op: JSONObject) = if (isVisual(op)) {
        "Drag to position · ${op.optInt("width", 360)}×${op.optInt("height", 360)}"
    } else if (op.optString("type") == "text_overlay") {
        op.optString("text", "Text")
    } else {
        "Tap Adjust for details"
    }

    private fun isVisual(op: JSONObject) = op.optString("type") in setOf("picture_in_picture", "media_overlay", "masked_video", "masked_media")
    private fun projectWidth() = project?.optJSONObject("metadata")?.optJSONObject("dimensions")?.optInt("width", 1280) ?: 1280
    private fun projectHeight() = project?.optJSONObject("metadata")?.optJSONObject("dimensions")?.optInt("height", 720) ?: 720
    private fun copyArray(array: JSONArray) = JSONArray(array.toString())

    private fun primaryButton(text: String, onClick: () -> Unit) = Button(this).apply {
        this.text = text
        minimumHeight = dp(54)
        setTextColor(Color.WHITE)
        setTypeface(typeface, android.graphics.Typeface.BOLD)
        background = rounded(green, 17f)
        setOnClickListener { onClick() }
    }

    private fun secondaryButton(text: String, onClick: () -> Unit) = Button(this).apply {
        this.text = text
        minimumHeight = dp(50)
        setTextColor(deepGreen)
        background = rounded(Color.rgb(255, 242, 184), 17f, yellow)
        setOnClickListener { onClick() }
    }

    private fun adjustButton(text: String, onClick: (Button) -> Unit) = Button(this).apply {
        this.text = text
        minimumHeight = dp(50)
        setTextColor(deepGreen)
        background = rounded(Color.rgb(255, 242, 184), 17f, yellow)
        setOnClickListener { onClick(this) }
    }

    private fun rounded(fill: Int, radius: Float, stroke: Int? = null) = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = dp(radius.toInt()).toFloat()
        setColor(fill)
        if (stroke != null) setStroke(dp(1), stroke)
    }

    private fun spacer(height: Int) = View(this).apply { layoutParams = LinearLayout.LayoutParams(-1, dp(height)) }
    private fun matchWrap() = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    companion object {
        const val REQ_SOURCE = 100
        const val REQ_ASSET = 101
        const val REQ_AUDIO = 102
    }
}

private class SimpleItemSelected(val onSelect: (Int) -> Unit) : android.widget.AdapterView.OnItemSelectedListener {
    override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: View?, position: Int, id: Long) = onSelect(position)
    override fun onNothingSelected(parent: android.widget.AdapterView<*>?) {}
}

class PlacementView(context: android.content.Context, private val op: JSONObject, private val canvasW: Int, private val canvasH: Int) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(90, 70, 160, 80) }
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(249, 199, 79); style = Paint.Style.STROKE; strokeWidth = 4f }
    private var lastX = 0f
    private var lastY = 0f
    private val scaleDetector = ScaleGestureDetector(context, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
        override fun onScale(detector: ScaleGestureDetector): Boolean {
            op.put("width", (op.optInt("width", 360) * detector.scaleFactor).toInt().coerceIn(32, 4096))
            op.put("height", (op.optInt("height", 360) * detector.scaleFactor).toInt().coerceIn(32, 4096))
            invalidate()
            return true
        }
    })

    init {
        setBackgroundColor(Color.rgb(25, 25, 28))
        minimumHeight = 180
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val scale = min(width.toFloat() / canvasW, height.toFloat() / canvasH)
        val x = op.optInt("x", 40) * scale
        val y = op.optInt("y", 40) * scale
        val w = op.optInt("width", 360) * scale
        val h = op.optInt("height", 360) * scale
        canvas.drawRoundRect(x, y, x + w, y + h, 24f, 24f, paint)
        canvas.drawRoundRect(x, y, x + w, y + h, 24f, 24f, stroke)
        if (op.optString("shape") == "star") canvas.drawPath(star(x + w / 2, y + h / 2, min(w, h) * .42f), stroke)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        scaleDetector.onTouchEvent(event)
        if (event.pointerCount > 1) return true
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                lastX = event.x
                lastY = event.y
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                val scale = min(width.toFloat() / canvasW, height.toFloat() / canvasH)
                op.put("x", op.optInt("x", 40) + ((event.x - lastX) / scale).toInt())
                op.put("y", op.optInt("y", 40) + ((event.y - lastY) / scale).toInt())
                lastX = event.x
                lastY = event.y
                invalidate()
                return true
            }
        }
        return true
    }

    private fun star(cx: Float, cy: Float, radius: Float): Path {
        val path = Path()
        for (i in 0 until 10) {
            val r = if (i % 2 == 0) radius else radius * .43f
            val angle = -Math.PI / 2 + i * Math.PI / 5
            val x = cx + (cos(angle) * r).toFloat()
            val y = cy + (sin(angle) * r).toFloat()
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        path.close()
        return path
    }
}
