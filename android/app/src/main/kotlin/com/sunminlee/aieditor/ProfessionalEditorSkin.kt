package com.sunminlee.aieditor

import android.app.Activity
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.ViewOutlineProvider
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.VideoView
import java.util.Locale
import java.util.WeakHashMap

/**
 * Premium mobile-editor visual system.
 *
 * The palette is intentionally narrow: near-black work canvas, charcoal surfaces,
 * violet interaction accents and white typography. This keeps the app feeling like
 * a focused editing product instead of a collection of colourful utility cards.
 * Existing editing behaviour is left intact; this class only changes presentation.
 */
object ProfessionalEditorSkin {
    private val styled = WeakHashMap<View, Boolean>()

    private val canvas = Color.rgb(11, 11, 16)          // #0B0B10
    private val surface = Color.rgb(20, 20, 28)         // #14141C
    private val surfaceRaised = Color.rgb(27, 27, 38)   // #1B1B26
    private val surfacePressed = Color.rgb(35, 31, 50)
    private val divider = Color.rgb(42, 42, 56)         // #2A2A38
    private val text = Color.rgb(245, 247, 251)         // #F5F7FB
    private val muted = Color.rgb(183, 184, 201)        // #B7B8C9
    private val purple = Color.rgb(139, 92, 246)        // #8B5CF6
    private val purpleLight = Color.rgb(167, 139, 250)  // #A78BFA
    private val purpleDeep = Color.rgb(50, 31, 91)
    private val danger = Color.rgb(239, 68, 68)

    private val primaryLabels = setOf(
        "Choose photo or video",
        "Ask AI",
        "Apply AI changes",
        "Render my changes",
        "Add photo or video",
        "Create 3D Turn",
    )

    fun apply(activity: Activity, root: View) {
        activity.window.statusBarColor = canvas
        activity.window.navigationBarColor = canvas
        activity.window.decorView.systemUiVisibility =
            activity.window.decorView.systemUiVisibility and View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR.inv()

        // The original activity builds a light root before this skin runs. Force the
        // actual activity content root dark so the welcome screen and editor both use
        // the same premium canvas, not only the editor panel.
        activity.findViewById<ViewGroup>(android.R.id.content)?.let { host ->
            host.setBackgroundColor(canvas)
            if (host.childCount > 0) host.getChildAt(0).setBackgroundColor(canvas)
        }

        styleTree(root)
        descendants(root).filterIsInstance<ScrollView>().forEach {
            it.setBackgroundColor(canvas)
            it.clipToPadding = false
        }

        when (activity) {
            is EnhancedMainActivity -> decorateEditor(activity, root)
            is PhotoTurnActivity -> decoratePhotoTurn(activity, root)
        }
    }

    private fun styleTree(view: View) {
        if (styled.put(view, true) == null) styleOnce(view)
        if (view is TextView && view !is android.widget.Button) refreshTextState(view)
        if (view is ViewGroup) {
            val children = (0 until view.childCount).map { view.getChildAt(it) }
            children.forEach(::styleTree)
        }
    }

    private fun styleOnce(view: View) {
        when (view) {
            is com.sunminlee.aieditor.Button -> styleButton(view)
            is EditText -> {
                view.setTextColor(text)
                view.setHintTextColor(muted)
                view.background = rounded(view.context, surfaceRaised, 13f, divider)
                view.backgroundTintList = null
                view.elevation = 0f
            }
            is Spinner -> {
                view.backgroundTintList = ColorStateList.valueOf(purpleLight)
                view.setPopupBackgroundDrawable(rounded(view.context, surfaceRaised, 12f, divider))
            }
            is SeekBar -> {
                view.progressTintList = ColorStateList.valueOf(purple)
                view.thumbTintList = ColorStateList.valueOf(purpleLight)
                view.progressBackgroundTintList = ColorStateList.valueOf(divider)
            }
            is FrameLayout -> {
                if (containsMedia(view)) {
                    view.background = rounded(view.context, Color.BLACK, 16f, Color.rgb(61, 47, 92))
                    view.elevation = dp(view.context, 3f)
                    view.outlineProvider = ViewOutlineProvider.BACKGROUND
                    view.clipToOutline = true
                } else if (view.background is GradientDrawable) {
                    view.background = rounded(view.context, surface, 15f, divider)
                    view.elevation = 0f
                }
            }
            is LinearLayout -> {
                if (view.background is GradientDrawable) {
                    val isHero = descendants(view).filterIsInstance<TextView>().any {
                        it.text?.toString() == "AI Media Editor"
                    }
                    view.background = if (isHero) {
                        GradientDrawable(
                            GradientDrawable.Orientation.TL_BR,
                            intArrayOf(Color.rgb(24, 16, 43), purpleDeep, Color.rgb(84, 48, 145))
                        ).apply {
                            cornerRadius = dp(view.context, 24f)
                            setStroke(dpInt(view.context, 1f), Color.rgb(91, 68, 135))
                        }
                    } else {
                        rounded(view.context, surface, 15f, divider)
                    }
                    view.elevation = dp(view.context, if (isHero) 3f else 0f)
                    view.outlineProvider = ViewOutlineProvider.BACKGROUND
                }
            }
        }
    }

    private fun refreshTextState(view: TextView) {
        val value = view.text?.toString().orEmpty()
        val status = value in setOf(
            "Ready", "Failed", "Rendering… Please wait", "AI is planning…", "Uploading… Please wait",
            "Adding media…", "Adding music…", "Choose three photos", "Choose all three photos", "Ready to create"
        )

        when {
            value == "Failed" -> {
                view.setTextColor(Color.rgb(255, 196, 196))
                if (view.background != null) {
                    view.background = rounded(view.context, Color.rgb(48, 22, 28), 12f, Color.rgb(104, 43, 55))
                }
            }
            status -> {
                view.setTextColor(if (value == "Ready") purpleLight else text)
                if (view.background != null) {
                    view.background = rounded(
                        view.context,
                        surfaceRaised,
                        12f,
                        if (value == "Ready") purple else divider,
                    )
                }
                view.gravity = Gravity.CENTER_VERTICAL
            }
            view.textSize >= 18f -> view.setTextColor(text)
            else -> view.setTextColor(muted)
        }

        if (view.background is GradientDrawable && !status) {
            view.background = rounded(view.context, surfaceRaised, 12f, divider)
        }
    }

    private fun styleButton(button: com.sunminlee.aieditor.Button) {
        val label = button.text?.toString().orEmpty()
        button.elevation = 0f
        button.translationZ = 0f
        button.includeFontPadding = false
        button.setPadding(
            dpInt(button.context, 10f),
            dpInt(button.context, 7f),
            dpInt(button.context, 10f),
            dpInt(button.context, 7f),
        )

        val workspace = workspaceSelection(button)
        when {
            workspace == true -> {
                button.setTextColor(text)
                button.background = rounded(button.context, purpleDeep, 13f, purpleLight, 2)
            }
            workspace == false -> {
                button.setTextColor(muted)
                button.background = rounded(button.context, surface, 13f, divider)
            }
            label in primaryLabels -> {
                button.setTextColor(Color.WHITE)
                button.background = GradientDrawable(
                    GradientDrawable.Orientation.LEFT_RIGHT,
                    intArrayOf(Color.rgb(111, 63, 225), purple, purpleLight)
                ).apply {
                    cornerRadius = dp(button.context, 13f)
                    setStroke(dpInt(button.context, 1f), Color.rgb(188, 166, 255))
                }
            }
            label == "Remove" -> {
                button.setTextColor(Color.rgb(255, 213, 213))
                button.background = rounded(button.context, Color.rgb(51, 25, 31), 13f, Color.rgb(110, 48, 59))
            }
            label.contains("3D Turn", ignoreCase = true) || label.startsWith("Style") -> {
                button.setTextColor(text)
                button.background = rounded(button.context, Color.rgb(37, 27, 58), 13f, Color.rgb(101, 70, 156))
            }
            label.contains('\n') -> {
                button.gravity = Gravity.CENTER_VERTICAL or Gravity.START
                button.setTextColor(text)
                button.background = rounded(button.context, surfaceRaised, 13f, divider)
            }
            else -> {
                button.setTextColor(text)
                button.background = rounded(button.context, surfaceRaised, 13f, divider)
            }
        }
    }

    private fun workspaceSelection(button: View): Boolean? {
        val row = button.parent as? LinearLayout ?: return null
        val grid = row.parent as? LinearLayout ?: return null
        if (grid.tag != "compact-section-grid") return null
        val drawable = button.background as? GradientDrawable ?: return false
        val oldFill = drawable.color?.defaultColor
        // Support both the original green marker and the new purple marker so the
        // runtime skin remains compatible with already-created workspace views.
        return oldFill == Color.rgb(205, 232, 204) || oldFill == Color.rgb(66, 43, 111)
    }

    private fun decorateEditor(activity: EnhancedMainActivity, root: View) {
        val content = findEditorContainer(root)
        if (content != null) {
            content.setBackgroundColor(canvas)

            val preview = directChildren(content).filterIsInstance<FrameLayout>().firstOrNull { containsMedia(it) }
            val video = preview?.let { descendants(it).filterIsInstance<VideoView>().firstOrNull() }
            if (preview != null) {
                val params = preview.layoutParams
                if (params != null && params.height in 1 until dpInt(activity, 248f)) {
                    params.height = dpInt(activity, 248f)
                    preview.layoutParams = params
                }
                preview.background = rounded(activity, Color.BLACK, 16f, Color.rgb(73, 52, 112))
            }

            if (preview != null && video != null && content.findViewWithTag<View>("editor-timeline") == null) {
                val index = content.indexOfChild(preview)
                val timeline = EditorTimelineBar(activity, video).apply { tag = "editor-timeline" }
                content.addView(
                    timeline,
                    (index + 1).coerceAtMost(content.childCount),
                    LinearLayout.LayoutParams(-1, dpInt(activity, 48f)).apply {
                        topMargin = dpInt(activity, 7f)
                        bottomMargin = dpInt(activity, 3f)
                    },
                )
            }
        }
    }

    private fun decoratePhotoTurn(activity: PhotoTurnActivity, root: View) {
        val content = descendants(root).filterIsInstance<LinearLayout>().firstOrNull { layout ->
            descendants(layout).filterIsInstance<TextView>().any { it.text?.toString() == "Photo 3D Turn" }
        } ?: return
        content.setBackgroundColor(canvas)

        descendants(content).filterIsInstance<FrameLayout>().firstOrNull { containsMedia(it) }?.let { preview ->
            val params = preview.layoutParams
            if (params != null && params.height in 1 until dpInt(activity, 248f)) {
                params.height = dpInt(activity, 248f)
                preview.layoutParams = params
            }
            preview.background = rounded(activity, Color.BLACK, 16f, Color.rgb(73, 52, 112))
        }
    }

    private fun findEditorContainer(root: View): LinearLayout? = descendants(root)
        .filterIsInstance<LinearLayout>()
        .firstOrNull { layout ->
            directChildren(layout).any { it is FrameLayout && containsMedia(it) } &&
                descendants(layout).filterIsInstance<ScrollView>().any()
        }

    private fun containsMedia(group: ViewGroup): Boolean = descendants(group).any {
        it is VideoView || it is ImageView
    }

    private fun directChildren(group: ViewGroup): List<View> =
        (0 until group.childCount).map { group.getChildAt(it) }

    private fun descendants(root: View): Sequence<View> = sequence {
        yield(root)
        if (root is ViewGroup) {
            for (index in 0 until root.childCount) yieldAll(descendants(root.getChildAt(index)))
        }
    }

    private fun rounded(
        context: Context,
        fill: Int,
        radius: Float,
        stroke: Int? = null,
        strokeWidth: Int = 1,
    ): GradientDrawable = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = dp(context, radius)
        setColor(fill)
        if (stroke != null) setStroke(dpInt(context, strokeWidth.toFloat()).coerceAtLeast(1), stroke)
    }

    private fun dp(context: Context, value: Float): Float = value * context.resources.displayMetrics.density
    private fun dpInt(context: Context, value: Float): Int = dp(context, value).toInt()
}

/** Functional scrub strip matching the black/purple editor theme. */
private class EditorTimelineBar(context: Context, private val video: VideoView) : LinearLayout(context) {
    private val handler = Handler(Looper.getMainLooper())
    private val play = com.sunminlee.aieditor.Button(context)
    private val current = TextView(context)
    private val total = TextView(context)
    private val seek = SeekBar(context)
    private var userSeeking = false

    private val ticker = object : Runnable {
        override fun run() {
            if (!isAttachedToWindow) return
            val duration = runCatching { video.duration }.getOrDefault(0).coerceAtLeast(0)
            val position = runCatching { video.currentPosition }.getOrDefault(0).coerceAtLeast(0)
            if (!userSeeking && duration > 0) {
                seek.max = duration
                seek.progress = position.coerceAtMost(duration)
            }
            current.text = formatTime(position)
            total.text = if (duration > 0) formatTime(duration) else "--:--"
            play.text = if (video.isPlaying) "Ⅱ" else "▶"
            handler.postDelayed(this, 250)
        }
    }

    init {
        orientation = HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(8), dp(4), dp(8), dp(4))
        background = skinRounded(Color.rgb(20, 20, 28), 13f, Color.rgb(42, 42, 56))

        play.apply {
            text = "▶"
            textSize = 12f
            gravity = Gravity.CENTER
            setTextColor(Color.rgb(245, 247, 251))
            background = skinRounded(Color.rgb(35, 31, 50), 11f, Color.rgb(84, 60, 126))
            setOnClickListener {
                if (video.isPlaying) video.pause() else runCatching { video.start() }
            }
        }
        addView(play, LayoutParams(dp(38), dp(34)).apply { marginEnd = dp(7) })

        current.apply {
            text = "00:00"
            textSize = 11f
            gravity = Gravity.CENTER
            setTextColor(Color.rgb(231, 229, 241))
        }
        addView(current, LayoutParams(dp(48), -2))

        seek.apply {
            max = 1000
            progressTintList = ColorStateList.valueOf(Color.rgb(139, 92, 246))
            thumbTintList = ColorStateList.valueOf(Color.rgb(167, 139, 250))
            progressBackgroundTintList = ColorStateList.valueOf(Color.rgb(42, 42, 56))
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                    if (fromUser) current.text = formatTime(progress)
                }

                override fun onStartTrackingTouch(seekBar: SeekBar?) {
                    userSeeking = true
                }

                override fun onStopTrackingTouch(seekBar: SeekBar?) {
                    val value = seekBar?.progress ?: 0
                    runCatching { video.seekTo(value) }
                    userSeeking = false
                }
            })
        }
        addView(seek, LayoutParams(0, dp(36), 1f))

        total.apply {
            text = "--:--"
            textSize = 11f
            gravity = Gravity.CENTER
            setTextColor(Color.rgb(183, 184, 201))
        }
        addView(total, LayoutParams(dp(48), -2))
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        handler.removeCallbacks(ticker)
        handler.post(ticker)
    }

    override fun onDetachedFromWindow() {
        handler.removeCallbacks(ticker)
        super.onDetachedFromWindow()
    }

    private fun formatTime(milliseconds: Int): String {
        val totalSeconds = (milliseconds / 1000).coerceAtLeast(0)
        return String.format(Locale.US, "%02d:%02d", totalSeconds / 60, totalSeconds % 60)
    }

    private fun skinRounded(fill: Int, radius: Float, stroke: Int): GradientDrawable = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = radius * resources.displayMetrics.density
        setColor(fill)
        setStroke((resources.displayMetrics.density).toInt().coerceAtLeast(1), stroke)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
