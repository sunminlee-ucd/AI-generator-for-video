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
import android.text.InputType
import android.view.Gravity
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import android.view.ViewGroup
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.Executors
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

class EnhancedMainActivity : Activity() {
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
    private var expandedPanel = "tools"

    private val green = Color.rgb(47, 125, 50)
    private val deepGreen = Color.rgb(25, 79, 42)
    private val yellow = Color.rgb(249, 199, 79)
    private val cream = Color.rgb(255, 249, 230)
    private val muted = Color.rgb(98, 105, 101)
    private val mint = Color.rgb(226, 244, 224)
    private val butter = Color.rgb(255, 244, 190)
    private val softGreen = Color.rgb(205, 232, 204)
    private val softGold = Color.rgb(255, 231, 143)
    private val pale = Color.rgb(250, 251, 247)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildShell()
        showWelcome()
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
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
            setPadding(0, dp(18), 0, dp(14))
        }

        val hero = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(22), dp(22), dp(22))
            background = GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                intArrayOf(green, Color.rgb(103, 162, 76), yellow)
            ).apply { cornerRadius = dp(30).toFloat() }
        }
        hero.addView(TextView(this).apply {
            text = "AI Media Editor"
            textSize = 30f
            setTextColor(Color.WHITE)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }, matchWrap())
        hero.addView(TextView(this).apply {
            text = "Edit directly with simple tools, or ask AI when you want a helping hand."
            textSize = 16f
            setTextColor(Color.WHITE)
            setPadding(0, dp(10), 0, 0)
        }, matchWrap())
        wrap.addView(hero, matchWrap())

        wrap.addView(spacer(16))
        listOf(
            "1  Choose a photo or video",
            "2  Use Quick tools or Ask AI",
            "3  Review, adjust, then render"
        ).forEachIndexed { index, label ->
            val bg = if (index % 2 == 0) Color.WHITE else butter
            wrap.addView(TextView(this).apply {
                text = label
                textSize = 15f
                setTextColor(deepGreen)
                setPadding(dp(16), dp(15), dp(16), dp(15))
                background = rounded(bg, 18f, if (index % 2 == 0) softGreen else softGold)
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
            setPadding(dp(4), dp(4), dp(4), dp(10))
        }
        top.addView(TextView(this).apply {
            text = project?.optString("filename") ?: "Project"
            textSize = 18f
            setTextColor(deepGreen)
            maxLines = 1
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
            setPadding(0, 0, 0, dp(20))
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
        accordion.addView(
            sectionCard("tools", "Quick tools", "Edit directly without asking AI", green, manualToolsPanel()),
            matchWrap().apply { bottomMargin = dp(10) }
        )
        accordion.addView(
            sectionCard("ai", "AI assistant", "Describe an edit in your own words", yellow, aiPanel()),
            matchWrap().apply { bottomMargin = dp(10) }
        )
        accordion.addView(
            sectionCard("edits", "Edit controls", "Fine-tune every active change", green, editsPanel()),
            matchWrap().apply { bottomMargin = dp(10) }
        )
        accordion.addView(
            sectionCard("media", "Media library", "Add another clip, photo, or music", yellow, mediaPanel()),
            matchWrap()
        )
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
            text = if (expandedPanel == key) "⌃" else "⌄"
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

    private fun manualToolsPanel(): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        box.addView(TextView(this).apply {
            text = "Pick a tool, set the values, then render. AI is optional."
            textSize = 14f
            setTextColor(muted)
            setPadding(dp(2), 0, dp(2), dp(10))
        }, matchWrap())

        val tools = listOf(
            ToolSpec("Trim", "Start / end", butter) { showTrimDialog() },
            ToolSpec("Speed", "0.5× – 2×", mint) { showSpeedDialog() },
            ToolSpec("Volume", "Sound level", butter) { showVolumeDialog() },
            ToolSpec("Mute", "Silence source", mint) { addManualOperation(baseOperation("mute")) },
            ToolSpec("Text", "Title / caption", mint) { showTextDialog() },
            ToolSpec("Split", "Two-up layout", butter) { showSplitDialog() },
            ToolSpec("Join", "Clip after clip", mint) { showConcatDialog() },
            ToolSpec("PiP", "Small video/photo", butter) { showPipDialog() },
            ToolSpec("Overlay", "Layer on top", butter) { showOverlayDialog() },
            ToolSpec("Shape", "Star / heart / circle", mint) { showMaskDialog() },
            ToolSpec("Music", "Background audio", butter) { showMusicDialog() },
            ToolSpec("Style", "Generative look", mint) { showStyleDialog() },
        )

        tools.chunked(2).forEach { pair ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                weightSum = 2f
            }
            pair.forEachIndexed { index, tool ->
                row.addView(cuteToolButton(tool), LinearLayout.LayoutParams(0, dp(78), 1f).apply {
                    if (index == 0) marginEnd = dp(6) else marginStart = dp(6)
                })
            }
            if (pair.size == 1) row.addView(View(this), LinearLayout.LayoutParams(0, dp(78), 1f))
            box.addView(row, matchWrap())
            box.addView(spacer(10))
        }
        return box
    }

    private fun cuteToolButton(tool: ToolSpec): Button = Button(this).apply {
        text = "${tool.title}\n${tool.subtitle}"
        textSize = 13f
        gravity = Gravity.CENTER
        setTextColor(deepGreen)
        setPadding(dp(8), dp(8), dp(8), dp(8))
        background = rounded(tool.color, 20f, if (tool.color == mint) softGreen else softGold)
        setOnClickListener { tool.action() }
    }

    private fun aiPanel(): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        box.addView(TextView(this).apply {
            text = "Use AI when it is faster to describe the idea than set every value yourself."
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

        listOf("Trim the beginning", "Add a title", "Join the two videos", "Put the second clip beside the first").forEach { example ->
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
                text = "No edits yet. Add a Quick tool or ask AI."
                gravity = Gravity.CENTER
                setTextColor(muted)
                setPadding(dp(16), dp(24), dp(16), dp(24))
                background = rounded(cream, 16f)
            }, matchWrap())
            return list
        }

        for (i in 0 until operations.length()) {
            list.addView(operationCard(i, operations.getJSONObject(i)), matchWrap())
        }
        list.addView(spacer(6))
        list.addView(primaryButton(if (proposal != null) "Apply AI changes" else "Render my changes") {
            if (proposal != null) applyProposal() else renderChanges()
        }, matchWrap())
        return list
    }

    private fun operationCard(index: Int, op: JSONObject): View {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = rounded(pale, 18f, if (index % 2 == 0) softGreen else softGold)
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
        populateOperationDetails(details, op)
        card.addView(details)

        val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; weightSum = 2f }
        actions.addView(adjustButton("Adjust") { button ->
            details.visibility = if (details.visibility == View.VISIBLE) View.GONE else View.VISIBLE
            button.text = if (details.visibility == View.VISIBLE) "Done" else "Adjust"
        }, LinearLayout.LayoutParams(0, dp(50), 1f).apply { marginEnd = dp(5) })
        actions.addView(secondaryButton("Remove") {
            removeOperation(index)
        }, LinearLayout.LayoutParams(0, dp(50), 1f).apply { marginStart = dp(5) })
        card.addView(actions)
        card.layoutParams = LinearLayout.LayoutParams(-1, -2).apply { setMargins(0, 0, 0, dp(9)) }
        return card
    }

    private fun populateOperationDetails(details: LinearLayout, op: JSONObject) {
        when (op.optString("type")) {
            "trim" -> {
                val row = numericRow(
                    "Start (s)", op.optDoubleOr("start_seconds", 0.0),
                    "End (s)", op.optDoubleOr("end_seconds", projectDuration())
                ) { first, second ->
                    val start = first.toDoubleOrNull()
                    val end = second.toDoubleOrNull()
                    if (start != null) op.put("start_seconds", start.coerceAtLeast(0.0))
                    if (end != null) op.put("end_seconds", end.coerceAtMost(projectDuration()))
                }
                details.addView(row, matchWrap())
            }
            "speed" -> {
                details.addView(labeledSpinner("Speed", arrayOf("0.5×", "0.75×", "1×", "1.25×", "1.5×", "2×"),
                    listOf(0.5, 0.75, 1.0, 1.25, 1.5, 2.0).indexOf(op.optDoubleOr("speed", 1.0)).coerceAtLeast(0)) { pos ->
                    op.put("speed", listOf(0.5, 0.75, 1.0, 1.25, 1.5, 2.0)[pos])
                }, matchWrap())
            }
            "volume" -> {
                details.addView(sliderRow("Volume", (op.optDoubleOr("volume", 1.0) * 100).toInt().coerceIn(0, 400), 400) { progress ->
                    op.put("volume", progress / 100.0)
                }, matchWrap())
            }
            "text_overlay" -> {
                val input = EditText(this).apply {
                    setText(op.optString("text"))
                    hint = "Text"
                    background = rounded(cream, 14f)
                    setPadding(dp(12), dp(10), dp(12), dp(10))
                    setOnFocusChangeListener { _, hasFocus -> if (!hasFocus) op.put("text", text.toString().trim()) }
                }
                details.addView(input, matchWrap())
                details.addView(spacer(7))
                details.addView(labeledSpinner("Position", arrayOf("Top", "Center", "Bottom"),
                    listOf("top", "center", "bottom").indexOf(op.optString("position", "bottom")).coerceAtLeast(0)) { pos ->
                    op.put("position", listOf("top", "center", "bottom")[pos])
                }, matchWrap())
                details.addView(sliderRow("Text size", op.optInt("font_size", 48).coerceIn(8, 120), 120, 8) { value ->
                    op.put("font_size", value)
                }, matchWrap())
            }
            "split_screen" -> {
                details.addView(assetSpinner(op, "secondary_asset_id", visualAssets()), matchWrap())
                details.addView(labeledSpinner("Layout", arrayOf("Side by side", "Stacked"), if (op.optString("layout") == "stacked") 1 else 0) { pos ->
                    op.put("layout", if (pos == 1) "stacked" else "side_by_side")
                }, matchWrap())
            }
            "concat" -> details.addView(assetSpinner(op, "secondary_asset_id", videoAssets()), matchWrap())
            "picture_in_picture", "media_overlay", "masked_media", "masked_video" -> {
                val key = if (op.optString("type") in setOf("media_overlay", "masked_media")) "source_asset_id" else "secondary_asset_id"
                details.addView(assetSpinner(op, key, visualAssets()), matchWrap())
                details.addView(TextView(this).apply {
                    text = "Drag the highlighted layer to move it. Pinch to resize."
                    setTextColor(muted)
                    setPadding(0, dp(7), 0, dp(7))
                })
                details.addView(PlacementView(this, op, projectWidth(), projectHeight()), LinearLayout.LayoutParams(-1, dp(220)))
                if (op.optString("type").startsWith("masked")) {
                    details.addView(spacer(7))
                    details.addView(labeledSpinner("Shape", arrayOf("Star", "Circle", "Heart", "Triangle"),
                        listOf("star", "circle", "heart", "triangle").indexOf(op.optString("shape", "star")).coerceAtLeast(0)) { pos ->
                        op.put("shape", listOf("star", "circle", "heart", "triangle")[pos])
                    }, matchWrap())
                }
            }
            "music" -> {
                details.addView(assetSpinner(op, "source_asset_id", audioAssets()), matchWrap())
                details.addView(sliderRow("Music volume", (op.optDoubleOr("volume", 0.35) * 100).toInt().coerceIn(0, 100), 100) { value ->
                    op.put("volume", value / 100.0)
                }, matchWrap())
                details.addView(Switch(this).apply {
                    text = "Lower music while speech plays"
                    setTextColor(deepGreen)
                    isChecked = op.optBoolean("ducking", false)
                    setOnCheckedChangeListener { _, checked -> op.put("ducking", checked) }
                }, matchWrap())
            }
            "style_transfer" -> {
                details.addView(EditText(this).apply {
                    setText(op.optString("style_prompt"))
                    hint = "Describe the visual style"
                    minLines = 2
                    background = rounded(cream, 14f)
                    setPadding(dp(12), dp(10), dp(12), dp(10))
                    setOnFocusChangeListener { _, hasFocus -> if (!hasFocus) op.put("style_prompt", text.toString().trim()) }
                }, matchWrap())
            }
        }
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
            val label = when (asset.optString("kind")) {
                "image" -> "Photo"
                "video" -> "Video"
                else -> "Audio"
            }
            box.addView(TextView(this).apply {
                text = "$label  ·  ${asset.optString("filename")}"
                textSize = 15f
                setTextColor(deepGreen)
                setPadding(dp(12), dp(12), dp(12), dp(12))
                background = rounded(if (i % 2 == 0) mint else butter, 14f)
            }, matchWrap().apply { bottomMargin = dp(7) })
        }
        return box
    }

    private fun showTrimDialog() {
        val duration = projectDuration()
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(18), dp(8), dp(18), 0) }
        val start = numberInput("Start seconds", "0")
        val end = numberInput("End seconds", formatSeconds(duration))
        content.addView(start, matchWrap()); content.addView(spacer(8)); content.addView(end, matchWrap())
        showToolDialog("Trim clip", content) {
            val s = start.text.toString().toDoubleOrNull() ?: return@showToolDialog showToast("Enter a valid start time")
            val e = end.text.toString().toDoubleOrNull() ?: return@showToolDialog showToast("Enter a valid end time")
            if (s < 0 || e <= s || e > duration + 0.05) return@showToolDialog showToast("Use a range between 0 and ${formatSeconds(duration)} seconds")
            addManualOperation(baseOperation("trim").put("start_seconds", s).put("end_seconds", e))
        }
    }

    private fun showSpeedDialog() {
        val speeds = listOf(0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
        val labels = speeds.map { "${it}×" }.toTypedArray()
        val spinner = Spinner(this).apply { adapter = ArrayAdapter(this@EnhancedMainActivity, android.R.layout.simple_spinner_dropdown_item, labels); setSelection(2) }
        showToolDialog("Playback speed", spinner) {
            addManualOperation(baseOperation("speed").put("speed", speeds[spinner.selectedItemPosition]))
        }
    }

    private fun showVolumeDialog() {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(14), dp(6), dp(14), 0) }
        val label = TextView(this).apply { text = "100%"; gravity = Gravity.CENTER; setTextColor(deepGreen) }
        val seek = SeekBar(this).apply { max = 400; progress = 100 }
        seek.setOnSeekBarChangeListener(SimpleSeek { value -> label.text = "$value%" })
        box.addView(label, matchWrap()); box.addView(seek, matchWrap())
        showToolDialog("Source volume", box) {
            addManualOperation(baseOperation("volume").put("volume", seek.progress / 100.0))
        }
    }

    private fun showTextDialog() {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(6), dp(16), 0) }
        val input = EditText(this).apply { hint = "Text to show"; minLines = 2; background = rounded(cream, 14f); setPadding(dp(12), dp(10), dp(12), dp(10)) }
        val position = Spinner(this).apply { adapter = ArrayAdapter(this@EnhancedMainActivity, android.R.layout.simple_spinner_dropdown_item, arrayOf("Top", "Center", "Bottom")); setSelection(2) }
        val size = SeekBar(this).apply { max = 112; progress = 40 }
        box.addView(input, matchWrap()); box.addView(spacer(8)); box.addView(position, matchWrap()); box.addView(spacer(8)); box.addView(TextView(this).apply { text = "Text size"; setTextColor(deepGreen) }); box.addView(size, matchWrap())
        showToolDialog("Add text", box) {
            val value = input.text.toString().trim()
            if (value.isBlank()) return@showToolDialog showToast("Enter some text")
            addManualOperation(
                baseOperation("text_overlay")
                    .put("text", value)
                    .put("position", listOf("top", "center", "bottom")[position.selectedItemPosition])
                    .put("font_size", size.progress + 8)
                    .put("font_color", "white")
                    .put("text_background_color", "black@0.45")
            )
        }
    }

    private fun showSplitDialog() {
        val assets = visualAssets()
        if (assets.isEmpty()) return requireVisualAsset()
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(12), dp(6), dp(12), 0) }
        val assetSpinner = simpleAssetSpinner(assets)
        val layout = Spinner(this).apply { adapter = ArrayAdapter(this@EnhancedMainActivity, android.R.layout.simple_spinner_dropdown_item, arrayOf("Side by side", "Stacked")) }
        box.addView(assetSpinner, matchWrap()); box.addView(spacer(8)); box.addView(layout, matchWrap())
        showToolDialog("Split screen", box) {
            val asset = assets[assetSpinner.selectedItemPosition]
            addManualOperation(baseOperation("split_screen").put("secondary_asset_id", asset.optString("id")).put("layout", if (layout.selectedItemPosition == 1) "stacked" else "side_by_side").put("ratio", 0.5))
        }
    }

    private fun showConcatDialog() {
        val assets = videoAssets()
        if (assets.isEmpty()) return showToast("Add a second video in Media library first")
        val spinner = simpleAssetSpinner(assets)
        showToolDialog("Join clips", spinner) {
            val asset = assets[spinner.selectedItemPosition]
            addManualOperation(baseOperation("concat").put("secondary_asset_id", asset.optString("id")))
        }
    }

    private fun showPipDialog() {
        val assets = visualAssets()
        if (assets.isEmpty()) return requireVisualAsset()
        val spinner = simpleAssetSpinner(assets)
        showToolDialog("Picture in picture", spinner) {
            val asset = assets[spinner.selectedItemPosition]
            addManualOperation(baseOperation("picture_in_picture").put("secondary_asset_id", asset.optString("id")).put("x", 40).put("y", 40).put("width", 360).put("height", 240))
        }
    }

    private fun showOverlayDialog() {
        val assets = visualAssets()
        if (assets.isEmpty()) return requireVisualAsset()
        val spinner = simpleAssetSpinner(assets)
        showToolDialog("Add media layer", spinner) {
            val asset = assets[spinner.selectedItemPosition]
            addManualOperation(baseOperation("media_overlay").put("source_asset_id", asset.optString("id")).put("x", 40).put("y", 40).put("width", 360).put("height", 240))
        }
    }

    private fun showMaskDialog() {
        val assets = visualAssets()
        if (assets.isEmpty()) return requireVisualAsset()
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(12), dp(6), dp(12), 0) }
        val assetSpinner = simpleAssetSpinner(assets)
        val shapeSpinner = Spinner(this).apply { adapter = ArrayAdapter(this@EnhancedMainActivity, android.R.layout.simple_spinner_dropdown_item, arrayOf("Star", "Circle", "Heart", "Triangle")) }
        box.addView(assetSpinner, matchWrap()); box.addView(spacer(8)); box.addView(shapeSpinner, matchWrap())
        showToolDialog("Shape layer", box) {
            val asset = assets[assetSpinner.selectedItemPosition]
            val shape = listOf("star", "circle", "heart", "triangle")[shapeSpinner.selectedItemPosition]
            addManualOperation(baseOperation("masked_media").put("source_asset_id", asset.optString("id")).put("shape", shape).put("x", 40).put("y", 40).put("width", 360).put("height", 360))
        }
    }

    private fun showMusicDialog() {
        val assets = audioAssets()
        if (assets.isEmpty()) return showToast("Add an audio file in Media library first")
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(12), dp(6), dp(12), 0) }
        val spinner = simpleAssetSpinner(assets)
        val label = TextView(this).apply { text = "Music volume 35%"; setTextColor(deepGreen); gravity = Gravity.CENTER }
        val seek = SeekBar(this).apply { max = 100; progress = 35 }
        seek.setOnSeekBarChangeListener(SimpleSeek { value -> label.text = "Music volume $value%" })
        val duck = Switch(this).apply { text = "Lower music while speech plays"; setTextColor(deepGreen) }
        box.addView(spinner, matchWrap()); box.addView(spacer(8)); box.addView(label, matchWrap()); box.addView(seek, matchWrap()); box.addView(duck, matchWrap())
        showToolDialog("Background music", box) {
            val asset = assets[spinner.selectedItemPosition]
            addManualOperation(baseOperation("music").put("source_asset_id", asset.optString("id")).put("volume", seek.progress / 100.0).put("fade_in_seconds", 0.5).put("fade_out_seconds", 0.5).put("loop", true).put("ducking", duck.isChecked))
        }
    }

    private fun showStyleDialog() {
        val input = EditText(this).apply { hint = "e.g. soft watercolor illustration"; minLines = 3; background = rounded(cream, 14f); setPadding(dp(12), dp(10), dp(12), dp(10)) }
        showToolDialog("Visual style", input) {
            val prompt = input.text.toString().trim()
            if (prompt.isBlank()) return@showToolDialog showToast("Describe a visual style")
            addManualOperation(baseOperation("style_transfer").put("style_prompt", prompt))
        }
    }

    private fun showToolDialog(title: String, view: View, onAdd: () -> Unit) {
        val dialog = AlertDialog.Builder(this)
            .setTitle(title)
            .setView(view)
            .setPositiveButton("Add") { _, _ -> onAdd() }
            .setNegativeButton("Cancel", null)
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE)?.setTextColor(green)
            dialog.getButton(AlertDialog.BUTTON_NEGATIVE)?.setTextColor(deepGreen)
        }
        dialog.show()
    }

    private fun addManualOperation(op: JSONObject) {
        proposal = null
        proposalPrompt = ""
        operations.put(op)
        expandedPanel = "edits"
        refreshAccordion()
        showToast("Added ${opTitle(op.optString("type"))}. Adjust it before rendering if you like.")
    }

    private fun removeOperation(index: Int) {
        if (index !in 0 until operations.length()) return
        operations.remove(index)
        proposal = null
        refreshAccordion()
    }

    private fun baseOperation(type: String) = JSONObject()
        .put("id", UUID.randomUUID().toString().replace("-", ""))
        .put("type", type)
        .put("enabled", true)

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
        validateDraftOperations()
        val start = api.replace(p.getString("id"), operations)
        waitJob(start.getString("job_id"))
        project = api.project(p.getString("id"))
        operations = copyArray(project!!.optJSONArray("operations") ?: JSONArray())
        main.post { playRemotePreview(); switchPanel("edits") }
    }

    private fun validateDraftOperations() {
        val duration = projectDuration()
        val visualIds = visualAssets().map { it.optString("id") }.toSet()
        val videoIds = videoAssets().map { it.optString("id") }.toSet()
        val audioIds = audioAssets().map { it.optString("id") }.toSet()
        for (i in 0 until operations.length()) {
            val op = operations.getJSONObject(i)
            if (!op.optBoolean("enabled", true)) continue
            when (op.optString("type")) {
                "trim" -> {
                    val s = op.optDoubleOr("start_seconds", 0.0)
                    val e = op.optDoubleOr("end_seconds", duration)
                    require(s >= 0 && e > s && e <= duration + 0.05) { "Trim range is outside the clip duration" }
                }
                "speed" -> require(op.optDoubleOr("speed", 1.0) in 0.5..2.0) { "Speed must be between 0.5× and 2×" }
                "volume" -> require(op.optDoubleOr("volume", 1.0) in 0.0..4.0) { "Volume must be between 0% and 400%" }
                "text_overlay" -> require(op.optString("text").isNotBlank()) { "Text cannot be empty" }
                "split_screen", "picture_in_picture" -> require(op.optString("secondary_asset_id") in visualIds) { "Choose a photo or video for ${opTitle(op.optString("type"))}" }
                "concat" -> require(op.optString("secondary_asset_id") in videoIds) { "Join needs a second video" }
                "media_overlay", "masked_media" -> require(op.optString("source_asset_id") in visualIds) { "Choose a photo or video for ${opTitle(op.optString("type"))}" }
                "music" -> require(op.optString("source_asset_id") in audioIds) { "Choose an audio file for Background music" }
                "style_transfer" -> require(op.optString("style_prompt").isNotBlank()) { "Visual style description cannot be empty" }
            }
        }
    }

    private fun waitJob(id: String) {
        val started = System.currentTimeMillis()
        while (true) {
            val job = api.job(id)
            when (job.optString("status")) {
                "completed" -> return
                "failed" -> error(job.optString("error", "Rendering failed"))
            }
            if (System.currentTimeMillis() - started > 10 * 60 * 1000L) error("Rendering timed out. Try a shorter clip or fewer layers.")
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
        runCatching { contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
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
        expandedPanel = "tools"
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
            .setMessage("Cloud Run is configured by default. Change this only for development testing.")
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
        "picture_in_picture" -> "Picture in picture"
        "media_overlay" -> "Media layer"
        "masked_video", "masked_media" -> "Shape layer"
        "concat" -> "Join clips"
        "music" -> "Background music"
        "speed" -> "Speed"
        "mute" -> "Mute"
        "volume" -> "Volume"
        "style_transfer" -> "Visual style"
        else -> type.replace('_', ' ').replaceFirstChar { it.uppercase() }
    }

    private fun summary(op: JSONObject) = when (op.optString("type")) {
        "trim" -> "${formatSeconds(op.optDoubleOr("start_seconds", 0.0))}s → ${formatSeconds(op.optDoubleOr("end_seconds", projectDuration()))}s"
        "speed" -> "${op.optDoubleOr("speed", 1.0)}× playback"
        "volume" -> "${(op.optDoubleOr("volume", 1.0) * 100).toInt()}% source volume"
        "mute" -> "Source audio off"
        "text_overlay" -> op.optString("text", "Text")
        "split_screen" -> if (op.optString("layout") == "stacked") "Two media stacked" else "Two media side by side"
        "concat" -> "Append another video"
        "music" -> "Background audio · ${(op.optDoubleOr("volume", 0.35) * 100).toInt()}%"
        "style_transfer" -> op.optString("style_prompt", "Generative visual style")
        else -> if (isVisual(op)) "Drag to position · ${op.optInt("width", 360)}×${op.optInt("height", 360)}" else "Tap Adjust for details"
    }

    private fun isVisual(op: JSONObject) = op.optString("type") in setOf("picture_in_picture", "media_overlay", "masked_video", "masked_media")
    private fun projectWidth() = project?.optJSONObject("metadata")?.optJSONObject("dimensions")?.optInt("width", 1280) ?: 1280
    private fun projectHeight() = project?.optJSONObject("metadata")?.optJSONObject("dimensions")?.optInt("height", 720) ?: 720
    private fun projectDuration() = project?.optJSONObject("metadata")?.optDouble("duration_seconds", 5.0)?.takeIf { it > 0 } ?: 5.0
    private fun copyArray(array: JSONArray) = JSONArray(array.toString())

    private fun visualAssets(): List<JSONObject> = assetsOfKinds(setOf("video", "image"))
    private fun videoAssets(): List<JSONObject> = assetsOfKinds(setOf("video"))
    private fun audioAssets(): List<JSONObject> = assetsOfKinds(setOf("audio"))
    private fun assetsOfKinds(kinds: Set<String>): List<JSONObject> {
        val array = project?.optJSONArray("assets") ?: return emptyList()
        return (0 until array.length()).map { array.getJSONObject(it) }.filter { it.optString("kind") in kinds }
    }

    private fun requireVisualAsset() = showToast("Add a second photo or video in Media library first")

    private fun simpleAssetSpinner(assets: List<JSONObject>) = Spinner(this).apply {
        adapter = ArrayAdapter(this@EnhancedMainActivity, android.R.layout.simple_spinner_dropdown_item, assets.map {
            val kind = if (it.optString("kind") == "image") "Photo" else if (it.optString("kind") == "video") "Video" else "Audio"
            "$kind · ${it.optString("filename")}"
        })
    }

    private fun assetSpinner(op: JSONObject, key: String, assets: List<JSONObject>): View {
        if (assets.isEmpty()) return TextView(this).apply { text = "No compatible media uploaded"; setTextColor(muted); setPadding(dp(8), dp(8), dp(8), dp(8)) }
        val spinner = simpleAssetSpinner(assets)
        val current = op.optString(key)
        spinner.setSelection(assets.indexOfFirst { it.optString("id") == current }.coerceAtLeast(0))
        spinner.onItemSelectedListener = SimpleItemSelected { pos -> op.put(key, assets[pos].optString("id")) }
        return spinner
    }

    private fun labeledSpinner(label: String, entries: Array<String>, selected: Int, onSelected: (Int) -> Unit): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        box.addView(TextView(this).apply { text = label; setTextColor(deepGreen); textSize = 13f }, matchWrap())
        val spinner = Spinner(this).apply {
            adapter = ArrayAdapter(this@EnhancedMainActivity, android.R.layout.simple_spinner_dropdown_item, entries)
            setSelection(selected.coerceIn(0, entries.lastIndex))
            onItemSelectedListener = SimpleItemSelected(onSelected)
        }
        box.addView(spinner, matchWrap())
        return box
    }

    private fun sliderRow(label: String, initial: Int, max: Int, min: Int = 0, onChange: (Int) -> Unit): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val text = TextView(this).apply { this.text = "$label: $initial"; setTextColor(deepGreen); textSize = 13f }
        val seek = SeekBar(this).apply { this.max = max - min; progress = (initial - min).coerceIn(0, max - min) }
        seek.setOnSeekBarChangeListener(SimpleSeek { raw ->
            val value = raw + min
            text.text = "$label: $value"
            onChange(value)
        })
        box.addView(text, matchWrap()); box.addView(seek, matchWrap())
        return box
    }

    private fun numericRow(label1: String, value1: Double, label2: String, value2: Double, onChanged: (String, String) -> Unit): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; weightSum = 2f }
        fun field(label: String, value: Double): LinearLayout {
            val input = EditText(this).apply {
                setText(formatSeconds(value))
                inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL
                background = rounded(cream, 12f)
                setPadding(dp(8), dp(7), dp(8), dp(7))
            }
            return LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                addView(TextView(this@EnhancedMainActivity).apply { text = label; setTextColor(deepGreen); textSize = 12f })
                addView(input, matchWrap())
                tag = input
            }
        }
        val left = field(label1, value1)
        val right = field(label2, value2)
        box.addView(left, LinearLayout.LayoutParams(0, -2, 1f).apply { marginEnd = dp(5) })
        box.addView(right, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(5) })
        val listener = View.OnFocusChangeListener { _, _ ->
            val a = (left.tag as EditText).text.toString()
            val b = (right.tag as EditText).text.toString()
            onChanged(a, b)
        }
        (left.tag as EditText).onFocusChangeListener = listener
        (right.tag as EditText).onFocusChangeListener = listener
        return box
    }

    private fun numberInput(hintText: String, default: String) = EditText(this).apply {
        hint = hintText
        setText(default)
        inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL
        background = rounded(cream, 14f)
        setPadding(dp(12), dp(10), dp(12), dp(10))
    }

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
        background = rounded(butter, 17f, yellow)
        setOnClickListener { onClick() }
    }

    private fun adjustButton(text: String, onClick: (Button) -> Unit) = Button(this).apply {
        this.text = text
        minimumHeight = dp(50)
        setTextColor(deepGreen)
        background = rounded(mint, 17f, softGreen)
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
    private fun formatSeconds(value: Double) = if (kotlin.math.abs(value - value.toInt()) < 0.001) value.toInt().toString() else String.format(java.util.Locale.US, "%.2f", value)
    private fun showToast(message: String) { Toast.makeText(this, message, Toast.LENGTH_LONG).show() }

    companion object {
        const val REQ_SOURCE = 100
        const val REQ_ASSET = 101
        const val REQ_AUDIO = 102
    }
}

private data class ToolSpec(val title: String, val subtitle: String, val color: Int, val action: () -> Unit)

private fun JSONObject.optDoubleOr(key: String, fallback: Double): Double = if (has(key) && !isNull(key)) optDouble(key, fallback) else fallback

private class SimpleItemSelected(val onSelect: (Int) -> Unit) : android.widget.AdapterView.OnItemSelectedListener {
    override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: View?, position: Int, id: Long) = onSelect(position)
    override fun onNothingSelected(parent: android.widget.AdapterView<*>?) {}
}

private class SimpleSeek(val onChange: (Int) -> Unit) : SeekBar.OnSeekBarChangeListener {
    override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) { if (fromUser) onChange(progress) }
    override fun onStartTrackingTouch(seekBar: SeekBar?) {}
    override fun onStopTrackingTouch(seekBar: SeekBar?) {}
}

class PlacementView(context: android.content.Context, private val op: JSONObject, private val canvasW: Int, private val canvasH: Int) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(95, 70, 160, 80) }
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
        val scale = min(width.toFloat() / canvasW.coerceAtLeast(1), height.toFloat() / canvasH.coerceAtLeast(1))
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
                val scale = min(width.toFloat() / canvasW.coerceAtLeast(1), height.toFloat() / canvasH.coerceAtLeast(1)).coerceAtLeast(0.0001f)
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
