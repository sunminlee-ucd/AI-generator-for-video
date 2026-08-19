package com.sunminlee.aieditor

import android.animation.ObjectAnimator
import android.animation.StateListAnimator
import android.app.Activity
import android.app.Application
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.ViewOutlineProvider
import android.view.ViewTreeObserver
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import java.util.WeakHashMap

/**
 * Applies a soft, playful 3D treatment to the programmatic Android UI.
 * It also turns the four oversized accordion headers into a compact two-column
 * selector grid while preserving the selected panel as a full-width surface.
 */
class DepthApplication : Application(), Application.ActivityLifecycleCallbacks {
    private val styled = WeakHashMap<View, Boolean>()
    private val listeners = WeakHashMap<Activity, ViewTreeObserver.OnGlobalLayoutListener>()

    override fun onCreate() {
        super.onCreate()
        registerActivityLifecycleCallbacks(this)
    }

    override fun onActivityResumed(activity: Activity) {
        val root = activity.window.decorView
        if (!listeners.containsKey(activity)) {
            val listener = ViewTreeObserver.OnGlobalLayoutListener { applyDepth(root) }
            root.viewTreeObserver.addOnGlobalLayoutListener(listener)
            listeners[activity] = listener
        }
        root.post { applyDepth(root) }
    }

    override fun onActivityDestroyed(activity: Activity) {
        val listener = listeners.remove(activity) ?: return
        val root = activity.window.decorView
        if (root.viewTreeObserver.isAlive) root.viewTreeObserver.removeOnGlobalLayoutListener(listener)
    }

    private fun applyDepth(view: View) {
        if (styled.put(view, true) == null) style(view)
        if (view is ViewGroup) {
            val children = (0 until view.childCount).map { view.getChildAt(it) }
            children.forEach { applyDepth(it) }
        }
        if (view is LinearLayout) {
            injectPhotoTurnTool(view)
            compactAccordion(view)
        }
    }

    private fun style(view: View) {
        when {
            view is Button -> styleButton(view)
            view is EditText -> {
                view.elevation = dp(1.5f)
                view.outlineProvider = ViewOutlineProvider.BACKGROUND
            }
            view is FrameLayout && view.background != null -> styleSurface(view, 8f)
            view is LinearLayout && view.background is GradientDrawable -> styleSurface(view, 5f)
            view is TextView && view.background is GradientDrawable -> styleSurface(view, 2.5f)
        }
    }

    private fun compactAccordion(container: LinearLayout) {
        if (container.childCount != 4) return
        val cards = (0 until 4).map { container.getChildAt(it) as? LinearLayout ?: return }
        val titles = cards.map { sectionTitle(it) ?: return }
        val expected = listOf("Quick tools", "AI assistant", "Edit controls", "Media library")
        if (titles != expected) return

        val headers = cards.map { it.getChildAt(0) as? LinearLayout ?: return }
        val activeCard = cards.firstOrNull { it.childCount > 1 }
        val activeTitle = activeCard?.let { sectionTitle(it) }

        val grid = LinearLayout(container.context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dpInt(2f), 0, dpInt(8f))
            tag = "compact-section-grid"
        }
        val subtitles = listOf("Direct edit", "Ask AI", "Fine-tune", "Add media")
        for (rowIndex in 0 until 2) {
            val row = LinearLayout(container.context).apply {
                orientation = LinearLayout.HORIZONTAL
                weightSum = 2f
            }
            for (column in 0 until 2) {
                val index = rowIndex * 2 + column
                val selected = titles[index] == activeTitle
                val button = com.sunminlee.aieditor.Button(container.context).apply {
                    text = "${titles[index]}\n${subtitles[index]}"
                    textSize = 12.5f
                    gravity = Gravity.CENTER
                    setTextColor(Color.rgb(25, 79, 42))
                    minHeight = 0
                    minimumHeight = 0
                    setPadding(dpInt(8f), dpInt(7f), dpInt(8f), dpInt(7f))
                    background = rounded(
                        if (selected) Color.rgb(205, 232, 204) else if (index % 2 == 0) Color.rgb(226, 244, 224) else Color.rgb(255, 244, 190),
                        17f,
                        if (selected) Color.rgb(47, 125, 50) else Color.rgb(249, 199, 79),
                        if (selected) 2 else 1,
                    )
                    setOnClickListener { headers[index].performClick() }
                }
                row.addView(button, LinearLayout.LayoutParams(0, dpInt(62f), 1f).apply {
                    if (column == 0) marginEnd = dpInt(5f) else marginStart = dpInt(5f)
                })
            }
            grid.addView(row, LinearLayout.LayoutParams(-1, -2).apply {
                if (rowIndex == 0) bottomMargin = dpInt(8f)
            })
        }

        container.removeAllViews()
        container.addView(grid, LinearLayout.LayoutParams(-1, -2))
        if (activeCard != null) {
            activeCard.getChildAt(0).visibility = View.GONE
            activeCard.layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dpInt(2f) }
            container.addView(activeCard)
        }
    }

    private fun sectionTitle(card: LinearLayout): String? {
        val header = card.getChildAt(0) as? LinearLayout ?: return null
        val textColumn = header.getChildAt(0) as? LinearLayout ?: return null
        val title = textColumn.getChildAt(0) as? TextView ?: return null
        return title.text?.toString()
    }

    private fun injectPhotoTurnTool(container: LinearLayout) {
        if (container.tag == "photo-turn-injected") return
        var hasTrim = false
        var hasPhotoTurn = false
        for (index in 0 until container.childCount) {
            val child = container.getChildAt(index)
            if (child is ViewGroup) {
                for (j in 0 until child.childCount) {
                    val text = (child.getChildAt(j) as? Button)?.text?.toString().orEmpty()
                    if (text.startsWith("Trim\n")) hasTrim = true
                    if (text.startsWith("3D Turn\n")) hasPhotoTurn = true
                }
            }
        }
        if (!hasTrim || hasPhotoTurn) return

        val row = LinearLayout(container.context).apply {
            orientation = LinearLayout.HORIZONTAL
            weightSum = 2f
        }
        val button = com.sunminlee.aieditor.Button(container.context).apply {
            text = "3D Turn\nFront · side · back"
            textSize = 13f
            gravity = Gravity.CENTER
            setTextColor(Color.rgb(25, 79, 42))
            setPadding(dpInt(8f), dpInt(8f), dpInt(8f), dpInt(8f))
            background = rounded(Color.rgb(255, 244, 190), 20f, Color.rgb(249, 199, 79), 1)
            setOnClickListener {
                container.context.startActivity(Intent(container.context, PhotoTurnActivity::class.java))
            }
        }
        row.addView(button, LinearLayout.LayoutParams(0, dpInt(78f), 1f).apply { marginEnd = dpInt(6f) })
        row.addView(View(container.context), LinearLayout.LayoutParams(0, dpInt(78f), 1f).apply { marginStart = dpInt(6f) })
        container.addView(row, LinearLayout.LayoutParams(-1, -2))
        container.tag = "photo-turn-injected"
    }

    private fun styleSurface(view: View, elevationDp: Float) {
        view.elevation = dp(elevationDp)
        view.translationZ = dp(0.5f)
        view.outlineProvider = ViewOutlineProvider.BACKGROUND
        view.clipToOutline = false
    }

    private fun styleButton(button: Button) {
        button.elevation = dp(5.5f)
        button.translationZ = dp(1.5f)
        button.outlineProvider = ViewOutlineProvider.BACKGROUND
        button.clipToOutline = false

        val stateAnimator = StateListAnimator().apply {
            addState(
                intArrayOf(android.R.attr.state_pressed),
                ObjectAnimator.ofFloat(button, "translationZ", dp(0f)).apply { duration = 70 }
            )
            addState(
                intArrayOf(),
                ObjectAnimator.ofFloat(button, "translationZ", dp(1.5f)).apply { duration = 120 }
            )
        }
        button.stateListAnimator = stateAnimator

        button.setOnTouchListener { target, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> target.animate().scaleX(0.965f).scaleY(0.965f).translationY(dp(2f)).setDuration(70).start()
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> target.animate().scaleX(1f).scaleY(1f).translationY(0f).setDuration(110).start()
            }
            false
        }
    }

    private fun rounded(fill: Int, radius: Float, stroke: Int? = null, strokeWidth: Int = 1) = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = dp(radius)
        setColor(fill)
        if (stroke != null) setStroke(dpInt(strokeWidth.toFloat()), stroke)
    }

    private fun dp(value: Float): Float = value * resources.displayMetrics.density
    private fun dpInt(value: Float): Int = dp(value).toInt()

    override fun onActivityCreated(activity: Activity, state: Bundle?) = Unit
    override fun onActivityStarted(activity: Activity) = Unit
    override fun onActivityPaused(activity: Activity) = Unit
    override fun onActivityStopped(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
}
