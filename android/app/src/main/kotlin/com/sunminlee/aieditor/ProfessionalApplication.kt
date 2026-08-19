package com.sunminlee.aieditor

import android.app.Activity
import android.app.Application
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.ViewTreeObserver
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import java.util.WeakHashMap

/**
 * Application-level UI coordinator. It keeps the existing programmatic activities intact,
 * compacts the workspace selector, adds Photo 3D Turn to Quick tools, and applies the
 * professional editor skin to views created later by accordion refreshes and dialogs.
 */
class ProfessionalApplication : Application(), Application.ActivityLifecycleCallbacks {
    private val listeners = WeakHashMap<Activity, ViewTreeObserver.OnGlobalLayoutListener>()

    override fun onCreate() {
        super.onCreate()
        registerActivityLifecycleCallbacks(this)
    }

    override fun onActivityCreated(activity: Activity, state: Bundle?) {
        activity.window.statusBarColor = Color.rgb(11, 11, 16)
        activity.window.navigationBarColor = Color.rgb(11, 11, 16)
    }

    override fun onActivityResumed(activity: Activity) {
        val root = activity.window.decorView
        if (!listeners.containsKey(activity)) {
            val listener = ViewTreeObserver.OnGlobalLayoutListener { enhance(activity, root) }
            root.viewTreeObserver.addOnGlobalLayoutListener(listener)
            listeners[activity] = listener
        }
        root.post { enhance(activity, root) }
    }

    override fun onActivityDestroyed(activity: Activity) {
        val listener = listeners.remove(activity) ?: return
        val root = activity.window.decorView
        if (root.viewTreeObserver.isAlive) root.viewTreeObserver.removeOnGlobalLayoutListener(listener)
    }

    private fun enhance(activity: Activity, root: View) {
        val layouts = descendants(root).filterIsInstance<LinearLayout>().toList()
        layouts.forEach(::injectPhotoTurnTool)
        layouts.forEach(::compactAccordion)
        ProfessionalEditorSkin.apply(activity, root)
    }

    private fun compactAccordion(container: LinearLayout) {
        if (container.childCount != 4) return
        val cards = (0 until 4).map { container.getChildAt(it) as? LinearLayout ?: return }
        val titles = cards.map { sectionTitle(it) ?: return }
        val expected = listOf("Quick tools", "AI assistant", "Edit controls", "Media library")
        if (titles != expected) return

        val headers = cards.map { it.getChildAt(0) as? LinearLayout ?: return }
        val activeCard = cards.firstOrNull { it.childCount > 1 }
        val activeTitle = activeCard?.let(::sectionTitle)
        val subtitles = listOf("Direct edit", "Ask AI", "Fine-tune", "Add media")

        val grid = LinearLayout(container.context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(2), 0, dp(5))
            tag = "compact-section-grid"
        }

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
                    textSize = 11.8f
                    gravity = Gravity.CENTER
                    includeFontPadding = false
                    minHeight = 0
                    minimumHeight = 0
                    setTextColor(if (selected) Color.WHITE else Color.rgb(183, 184, 201))
                    setPadding(dp(7), dp(4), dp(7), dp(4))
                    // Marker colours are read once by ProfessionalEditorSkin before it
                    // replaces these with the final premium workspace tile styling.
                    background = rounded(
                        if (selected) Color.rgb(66, 43, 111)
                        else Color.rgb(27, 27, 38),
                        14f,
                        if (selected) Color.rgb(167, 139, 250) else Color.rgb(42, 42, 56),
                        if (selected) 2 else 1,
                    )
                    setOnClickListener { headers[index].performClick() }
                }
                row.addView(button, LinearLayout.LayoutParams(0, dp(52), 1f).apply {
                    if (column == 0) marginEnd = dp(3) else marginStart = dp(3)
                })
            }
            grid.addView(row, LinearLayout.LayoutParams(-1, -2).apply {
                if (rowIndex == 0) bottomMargin = dp(5)
            })
        }

        container.removeAllViews()
        container.addView(grid, LinearLayout.LayoutParams(-1, -2))
        if (activeCard != null) {
            activeCard.getChildAt(0).visibility = View.GONE
            activeCard.layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(3) }
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
                    val label = (child.getChildAt(j) as? Button)?.text?.toString().orEmpty()
                    if (label.startsWith("Trim\n")) hasTrim = true
                    if (label.startsWith("3D Turn\n")) hasPhotoTurn = true
                }
            }
        }
        if (!hasTrim || hasPhotoTurn) return

        val row = LinearLayout(container.context).apply {
            orientation = LinearLayout.HORIZONTAL
            weightSum = 2f
        }
        val button = com.sunminlee.aieditor.Button(container.context).apply {
            text = "3D Turn\nPhoto turntable"
            textSize = 12.5f
            gravity = Gravity.CENTER_VERTICAL or Gravity.START
            includeFontPadding = false
            setTextColor(Color.WHITE)
            setPadding(dp(10), dp(5), dp(10), dp(5))
            background = rounded(Color.rgb(37, 27, 58), 14f, Color.rgb(101, 70, 156), 1)
            setOnClickListener {
                container.context.startActivity(Intent(container.context, PhotoTurnActivity::class.java))
            }
        }
        row.addView(button, LinearLayout.LayoutParams(0, dp(62), 1f).apply { marginEnd = dp(4) })
        row.addView(View(container.context).apply { setBackgroundColor(Color.TRANSPARENT) }, LinearLayout.LayoutParams(0, dp(62), 1f).apply { marginStart = dp(4) })
        container.addView(row, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(2) })
        container.tag = "photo-turn-injected"
    }

    private fun descendants(root: View): Sequence<View> = sequence {
        yield(root)
        if (root is ViewGroup) {
            for (index in 0 until root.childCount) yieldAll(descendants(root.getChildAt(index)))
        }
    }

    private fun rounded(fill: Int, radius: Float, stroke: Int? = null, strokeWidth: Int = 1): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = radius * resources.displayMetrics.density
            setColor(fill)
            if (stroke != null) setStroke((strokeWidth * resources.displayMetrics.density).toInt().coerceAtLeast(1), stroke)
        }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    override fun onActivityStarted(activity: Activity) = Unit
    override fun onActivityPaused(activity: Activity) = Unit
    override fun onActivityStopped(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
}
