package com.sunminlee.aieditor

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.Animatable
import android.view.MotionEvent
import android.widget.ProgressBar
import java.lang.ref.WeakReference

private object UiBusyState {
    private val buttons = mutableListOf<WeakReference<Button>>()
    private var currentLabel: String? = null

    fun register(button: Button) {
        buttons.removeAll { it.get() == null }
        buttons.add(WeakReference(button))
        button.applyBusyState(currentLabel)
    }

    fun update(label: String?) {
        currentLabel = label
        buttons.removeAll { it.get() == null }
        buttons.forEach { it.get()?.applyBusyState(label) }
    }

    fun current(): String? = currentLabel
}

/**
 * Same-package replacement for the programmatically-created android.widget.Button instances
 * in MainActivity. It keeps the existing API while adding clear press feedback and a loading
 * state without requiring every individual button call site to manage animations itself.
 */
class Button(context: Context) : android.widget.Button(context) {
    private var baseLabel = ""
    private var changingInternally = false
    private val spinner = ProgressBar(context).indeterminateDrawable.mutate().apply {
        val size = dp(18)
        setBounds(0, 0, size, size)
    }

    init {
        isAllCaps = false
        setOnTouchListener { _, event ->
            if (!isEnabled) return@setOnTouchListener false
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> animate()
                    .scaleX(0.97f)
                    .scaleY(0.97f)
                    .alpha(0.76f)
                    .setDuration(70)
                    .start()
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> animate()
                    .scaleX(1f)
                    .scaleY(1f)
                    .alpha(1f)
                    .setDuration(110)
                    .start()
            }
            false
        }
        UiBusyState.register(this)
    }

    override fun setText(text: CharSequence?, type: BufferType?) {
        if (!changingInternally) baseLabel = text?.toString().orEmpty()
        super.setText(text, type)
        if (!changingInternally) applyBusyState(UiBusyState.current())
    }

    internal fun applyBusyState(label: String?) {
        val loadingText = loadingTextFor(label, baseLabel)
        changingInternally = true
        if (label == null) {
            isEnabled = true
            alpha = 1f
            scaleX = 1f
            scaleY = 1f
            setCompoundDrawables(null, null, null, null)
            super.setText(baseLabel)
        } else {
            isEnabled = false
            if (loadingText != null) {
                val primary = isPrimaryAction(baseLabel)
                spinner.setTint(if (primary) Color.WHITE else Color.rgb(25, 79, 42))
                setCompoundDrawables(spinner, null, null, null)
                compoundDrawablePadding = dp(9)
                (spinner as? Animatable)?.start()
                super.setText(loadingText)
                alpha = 0.92f
            } else {
                setCompoundDrawables(null, null, null, null)
                super.setText(baseLabel)
                alpha = 0.55f
            }
        }
        changingInternally = false
    }

    private fun loadingTextFor(status: String?, label: String): String? = when (status) {
        "AI is planning" -> if (label == "Ask AI") "AI is planning…" else null
        "Rendering" -> if (label == "Apply AI changes" || label == "Render my changes") "Rendering… Please wait" else null
        "Uploading" -> if (label == "Choose photo or video") "Uploading… Please wait" else null
        "Adding media" -> if (label == "Add photo or video") "Adding media…" else null
        "Adding music" -> if (label == "Add background music") "Adding music…" else null
        else -> null
    }

    private fun isPrimaryAction(label: String) = label in setOf(
        "Choose photo or video",
        "Ask AI",
        "Apply AI changes",
        "Render my changes",
        "Add photo or video"
    )

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}

/**
 * MainActivity creates TextView directly for its status banner. By observing the known async
 * status values here, all action buttons can immediately reflect the same busy state.
 */
class TextView(context: Context) : android.widget.TextView(context) {
    override fun setText(text: CharSequence?, type: BufferType?) {
        val raw = text?.toString().orEmpty()
        val display = when (raw) {
            "AI is planning" -> "AI is planning…"
            "Rendering" -> "Rendering… Please wait"
            "Uploading" -> "Uploading… Please wait"
            "Adding media" -> "Adding media…"
            "Adding music" -> "Adding music…"
            else -> raw
        }
        super.setText(display, type)
        when (raw) {
            "AI is planning", "Rendering", "Uploading", "Adding media", "Adding music" -> UiBusyState.update(raw)
            "Ready", "Failed" -> UiBusyState.update(null)
        }
    }
}