package com.sunminlee.aieditor

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.Animatable
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.animation.OvershootInterpolator
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

/** Adds unmistakable press feedback and a shared loading state to editor buttons. */
class Button(context: Context) : android.widget.Button(context) {
    private var baseLabel = ""
    private var changingInternally = false
    private val spinner = ProgressBar(context).indeterminateDrawable.mutate().apply {
        val size = dp(18)
        setBounds(0, 0, size, size)
    }

    init {
        isAllCaps = false
        isHapticFeedbackEnabled = true
        isSoundEffectsEnabled = true
        setOnTouchListener { _, event ->
            if (!isEnabled) return@setOnTouchListener false
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    animate().cancel()
                    performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                    animate()
                        .scaleX(0.92f)
                        .scaleY(0.92f)
                        .translationY(dp(3).toFloat())
                        .alpha(0.68f)
                        .setDuration(45)
                        .setInterpolator(null)
                        .start()
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    animate().cancel()
                    animate()
                        .scaleX(1f)
                        .scaleY(1f)
                        .translationY(0f)
                        .alpha(1f)
                        .setDuration(150)
                        .setInterpolator(OvershootInterpolator(1.7f))
                        .start()
                }
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
            translationY = 0f
            setCompoundDrawables(null, null, null, null)
            super.setText(baseLabel)
        } else {
            isEnabled = false
            scaleX = 1f
            scaleY = 1f
            translationY = 0f
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
                alpha = 0.52f
            }
        }
        changingInternally = false
    }

    private fun loadingTextFor(status: String?, label: String): String? = when (status) {
        "AI is planning" -> if (label == "Ask AI") "AI is planning…" else null
        "Rendering" -> when (label) {
            "Apply AI changes", "Render my changes" -> "Rendering… Please wait"
            "Create 3D Turn" -> "Creating 3D Turn…"
            else -> null
        }
        "Uploading" -> if (label == "Choose photo or video") "Uploading… Please wait" else null
        "Adding media" -> when (label) {
            "Add photo or video" -> "Adding media…"
            "Add background music" -> "Adding music…"
            else -> null
        }
        "Adding music" -> if (label == "Add background music") "Adding music…" else null
        else -> null
    }

    private fun isPrimaryAction(label: String) = label in setOf(
        "Choose photo or video",
        "Ask AI",
        "Apply AI changes",
        "Render my changes",
        "Add photo or video",
        "Create 3D Turn"
    )

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}

/** Mirrors async status values into the banner and shared button busy state. */
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
            "Ready", "Failed", "Edit added", "Edit removed", "Choose three photos", "Choose all three photos", "Ready to create" -> UiBusyState.update(null)
        }
    }
}
