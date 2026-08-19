package com.sunminlee.aieditor

import android.animation.ObjectAnimator
import android.animation.StateListAnimator
import android.app.Activity
import android.app.Application
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
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
 * Applies a soft, playful 3D treatment to the programmatic Android UI without
 * changing the editor's layout or behaviour. Newly created accordion content is
 * picked up automatically through a global-layout listener.
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
            val listener = ViewTreeObserver.OnGlobalLayoutListener {
                applyDepth(root)
            }
            root.viewTreeObserver.addOnGlobalLayoutListener(listener)
            listeners[activity] = listener
        }
        root.post { applyDepth(root) }
    }

    override fun onActivityDestroyed(activity: Activity) {
        val listener = listeners.remove(activity) ?: return
        val root = activity.window.decorView
        if (root.viewTreeObserver.isAlive) {
            root.viewTreeObserver.removeOnGlobalLayoutListener(listener)
        }
    }

    private fun applyDepth(view: View) {
        if (styled.put(view, true) == null) {
            style(view)
        }
        if (view is ViewGroup) {
            for (index in 0 until view.childCount) {
                applyDepth(view.getChildAt(index))
            }
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
                MotionEvent.ACTION_DOWN -> {
                    target.animate()
                        .scaleX(0.965f)
                        .scaleY(0.965f)
                        .translationY(dp(2f))
                        .setDuration(70)
                        .start()
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    target.animate()
                        .scaleX(1f)
                        .scaleY(1f)
                        .translationY(0f)
                        .setDuration(110)
                        .start()
                }
            }
            false
        }
    }

    private fun dp(value: Float): Float = value * resources.displayMetrics.density

    override fun onActivityCreated(activity: Activity, state: Bundle?) = Unit
    override fun onActivityStarted(activity: Activity) = Unit
    override fun onActivityPaused(activity: Activity) = Unit
    override fun onActivityStopped(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
}
