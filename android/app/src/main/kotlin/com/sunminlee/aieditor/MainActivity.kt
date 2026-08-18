package com.sunminlee.aieditor

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
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
    private lateinit var content: FrameLayout
    private lateinit var status: TextView
    private var project: JSONObject? = null
    private var operations = JSONArray()
    private var proposal: JSONObject? = null
    private var proposalPrompt = ""
    private var sourceUri: Uri? = null
    private var sourceKind = "video"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildShell()
        showWelcome()
    }

    private fun buildShell() {
        root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.rgb(248,248,250)) }
        status = TextView(this).apply { text = "Ready"; setPadding(dp(16), dp(10), dp(16), dp(10)); setTextColor(Color.DKGRAY) }
    }

    private fun showWelcome() {
        root.removeAllViews()
        val wrap = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setPadding(dp(24), dp(40), dp(24), dp(40)) }
        wrap.addView(TextView(this).apply { text = "AI Video Editor"; textSize = 30f; setTextColor(Color.BLACK); gravity = Gravity.CENTER }, matchWrap())
        wrap.addView(TextView(this).apply { text = "Start with a photo or video. AI makes the first edit; you stay in control."; textSize = 16f; setTextColor(Color.DKGRAY); gravity = Gravity.CENTER; setPadding(0,dp(12),0,dp(28)) }, matchWrap())
        wrap.addView(primaryButton("Choose photo or video") { pickVisual(REQ_SOURCE) }, matchWrap())
        wrap.addView(Button(this).apply { text = "Server settings"; setOnClickListener { serverSettings() } }, matchWrap())
        root.addView(wrap, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        root.addView(status, matchWrap())
        setContentView(root)
    }

    private fun showEditor() {
        root.removeAllViews()
        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(dp(12),dp(8),dp(8),dp(8)) }
        top.addView(TextView(this).apply { text = project?.optString("filename") ?: "Project"; textSize = 17f; setTextColor(Color.BLACK) }, LinearLayout.LayoutParams(0, dp(48), 1f))
        top.addView(Button(this).apply { text = "Settings"; setOnClickListener { serverSettings() } }, LinearLayout.LayoutParams(dp(100), dp(48)))
        root.addView(top)

        previewBox = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        imagePreview = ImageView(this).apply { scaleType = ImageView.ScaleType.FIT_CENTER; visibility = View.GONE }
        videoPreview = VideoView(this).apply { visibility = View.GONE }
        previewBox.addView(imagePreview, FrameLayout.LayoutParams(-1,-1)); previewBox.addView(videoPreview, FrameLayout.LayoutParams(-1,-1))
        root.addView(previewBox, LinearLayout.LayoutParams(-1, 0, 0.38f))
        showLocalSource()

        content = FrameLayout(this)
        root.addView(content, LinearLayout.LayoutParams(-1, 0, 0.62f))
        val nav = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(dp(8),dp(6),dp(8),dp(8)) }
        listOf("ai" to "AI", "edits" to "Edits", "media" to "Media").forEach { (key,label) ->
            nav.addView(Button(this).apply { text = label; minimumHeight = dp(52); setOnClickListener { switchPanel(key) } }, LinearLayout.LayoutParams(0,dp(56),1f))
        }
        root.addView(status, matchWrap()); root.addView(nav, matchWrap())
        switchPanel("ai")
    }

    private fun switchPanel(panel: String) {
        content.removeAllViews()
        content.addView(when(panel) { "edits" -> editsPanel(); "media" -> mediaPanel(); else -> aiPanel() }, FrameLayout.LayoutParams(-1,-1))
    }

    private fun aiPanel(): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(14),dp(10),dp(14),dp(10)) }
        val tips = HorizontalScrollView(this)
        val tipRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val prompt = EditText(this).apply { hint = "Describe the edit you want"; minHeight = dp(56); maxLines = 4 }
        listOf("Trim the beginning","Add a title","Put a photo in a star","Add background music").forEach { text -> tipRow.addView(Button(this).apply { this.text = text; setOnClickListener { prompt.setText(text) } }) }
        tips.addView(tipRow); box.addView(tips, matchWrap())
        box.addView(TextView(this).apply { text = "Tell AI what you want. You will review every change before rendering."; setTextColor(Color.DKGRAY); setPadding(0,dp(10),0,dp(10)) }, matchWrap())
        box.addView(prompt, matchWrap())
        box.addView(primaryButton("Ask AI") { val p = prompt.text.toString().trim(); if(p.isNotEmpty()) askAI(p) }, matchWrap())
        return box
    }

    private fun editsPanel(): View {
        val outer = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val scroll = ScrollView(this); val list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(12),dp(8),dp(12),dp(8)) }
        if (operations.length() == 0) list.addView(TextView(this).apply { text = "No edits yet. Ask AI for a change first."; gravity = Gravity.CENTER; setPadding(dp(16),dp(40),dp(16),dp(40)) })
        for (i in 0 until operations.length()) list.addView(operationCard(operations.getJSONObject(i)), matchWrap())
        scroll.addView(list); outer.addView(scroll, LinearLayout.LayoutParams(-1,0,1f))
        if (operations.length() > 0) outer.addView(primaryButton(if (proposal != null) "Apply AI changes" else "Render my changes") { if (proposal != null) applyProposal() else renderChanges() }, LinearLayout.LayoutParams(-1,dp(60)).apply { setMargins(dp(12),dp(8),dp(12),dp(8)) })
        return outer
    }

    private fun operationCard(op: JSONObject): View {
        val card = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(14),dp(12),dp(14),dp(12)); setBackgroundColor(Color.WHITE) }
        val head = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val title = TextView(this).apply { text = opTitle(op.optString("type")); textSize = 17f; setTextColor(Color.BLACK) }
        val enabled = Switch(this).apply { isChecked = op.optBoolean("enabled", true); text = "Use"; setOnCheckedChangeListener { _,v -> op.put("enabled",v) } }
        head.addView(title, LinearLayout.LayoutParams(0,dp(48),1f)); head.addView(enabled); card.addView(head)
        card.addView(TextView(this).apply { text = summary(op); setTextColor(Color.DKGRAY); setPadding(0,0,0,dp(8)) })
        val details = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; visibility = View.GONE }
        if (isVisual(op)) {
            details.addView(TextView(this).apply { text = "Drag to move. Pinch to resize."; setTextColor(Color.DKGRAY) })
            details.addView(PlacementView(this@MainActivity, op, projectWidth(), projectHeight()), LinearLayout.LayoutParams(-1,dp(220)))
        }
        if (op.optString("type") == "text_overlay") {
            details.addView(EditText(this).apply { setText(op.optString("text")); hint = "Text"; setOnFocusChangeListener { _,has -> if(!has) op.put("text",text.toString()) } }, matchWrap())
        }
        if (op.optString("type").startsWith("masked")) {
            val spinner = Spinner(this); val shapes = arrayOf("star","circle","heart","triangle")
            spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, shapes)
            spinner.setSelection(shapes.indexOf(op.optString("shape","star")).coerceAtLeast(0))
            spinner.onItemSelectedListener = SimpleItemSelected { op.put("shape", shapes[it]) }
            details.addView(spinner,matchWrap())
        }
        card.addView(details)
        card.addView(Button(this).apply { text = "Adjust"; setOnClickListener { details.visibility = if(details.visibility==View.VISIBLE) View.GONE else View.VISIBLE; text = if(details.visibility==View.VISIBLE) "Done" else "Adjust" } }, matchWrap())
        val lp = LinearLayout.LayoutParams(-1,-2); lp.setMargins(0,0,0,dp(10)); card.layoutParams = lp
        return card
    }

    private fun mediaPanel(): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(14),dp(10),dp(14),dp(10)) }
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        buttons.addView(primaryButton("Add photo/video") { pickVisual(REQ_ASSET) }, LinearLayout.LayoutParams(0,dp(56),1f))
        buttons.addView(Button(this).apply { text = "Add music"; minimumHeight=dp(56); setOnClickListener { pickAudio() } }, LinearLayout.LayoutParams(0,dp(56),1f))
        box.addView(buttons)
        val assets = project?.optJSONArray("assets") ?: JSONArray()
        for(i in 0 until assets.length()) {
            val a=assets.getJSONObject(i)
            box.addView(TextView(this).apply { text = "${if(a.optString("kind")=="image") "Photo" else a.optString("kind").replaceFirstChar{it.uppercase()}}  ·  ${a.optString("filename")}"; textSize=16f; setPadding(dp(10),dp(14),dp(10),dp(14)); setBackgroundColor(Color.WHITE) }, matchWrap())
        }
        return ScrollView(this).apply { addView(box) }
    }

    private fun askAI(prompt: String) = runAsync("AI is planning") {
        val p = project ?: return@runAsync
        val result = api.propose(p.getString("id"), prompt)
        proposal = result.getJSONObject("plan"); proposalPrompt = prompt
        operations = copyArray(p.optJSONArray("operations") ?: JSONArray())
        val proposed = proposal!!.getJSONArray("operations"); for(i in 0 until proposed.length()) operations.put(proposed.getJSONObject(i))
        main.post { switchPanel("edits") }
    }

    private fun applyProposal() = runAsync("Rendering") {
        val p=project ?: return@runAsync
        val existing=p.optJSONArray("operations")?.length() ?: 0
        val proposed=JSONArray(); for(i in existing until operations.length()) proposed.put(operations.getJSONObject(i))
        val start=api.apply(p.getString("id"),proposalPrompt,proposal!!.optString("assistant_message","Apply changes"),proposed)
        waitJob(start.getString("job_id")); project=api.project(p.getString("id")); operations=copyArray(project!!.optJSONArray("operations")?:JSONArray()); proposal=null
        main.post { playRemotePreview(); switchPanel("edits") }
    }

    private fun renderChanges() = runAsync("Rendering") {
        val p=project ?: return@runAsync
        val start=api.replace(p.getString("id"),operations); waitJob(start.getString("job_id")); project=api.project(p.getString("id")); operations=copyArray(project!!.optJSONArray("operations")?:JSONArray())
        main.post { playRemotePreview(); switchPanel("edits") }
    }

    private fun waitJob(id:String) {
        while(true) {
            val j=api.job(id)
            if(j.optString("status")=="completed") return
            if(j.optString("status")=="failed") error(j.optString("error","Rendering failed"))
            Thread.sleep(850)
        }
    }

    private fun pickVisual(code:Int) { startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { addCategory(Intent.CATEGORY_OPENABLE); type="*/*"; putExtra(Intent.EXTRA_MIME_TYPES,arrayOf("image/*","video/*")) },code) }
    private fun pickAudio() { startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { addCategory(Intent.CATEGORY_OPENABLE); type="audio/*" },REQ_AUDIO) }

    @Deprecated("Deprecated in Android framework but kept for broad device compatibility")
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if(resultCode!=RESULT_OK) return
        val uri=data?.data?:return
        when(requestCode){REQ_SOURCE->{sourceUri=uri; uploadSource(uri)};REQ_ASSET->uploadAsset(uri);REQ_AUDIO->uploadAsset(uri)}
    }

    private fun uploadSource(uri:Uri)=runAsync("Uploading") { val m=MediaUtils.prepare(this,uri); sourceKind=m.kind; project=api.createProject(m.file,m.mime); operations=JSONArray(); main.post { showEditor() } }
    private fun uploadAsset(uri:Uri)=runAsync("Adding media") { val p=project?:return@runAsync; val m=MediaUtils.prepare(this,uri); api.addAsset(p.getString("id"),m.file,m.mime,m.kind); project=api.project(p.getString("id")); main.post { switchPanel("media") } }

    private fun showLocalSource() {
        val uri=sourceUri ?: return
        imagePreview.visibility=if(sourceKind=="image")View.VISIBLE else View.GONE
        videoPreview.visibility=if(sourceKind=="video")View.VISIBLE else View.GONE
        if(sourceKind=="image") imagePreview.setImageURI(uri) else { videoPreview.setVideoURI(uri); videoPreview.setOnPreparedListener { it.isLooping=true; videoPreview.start() } }
    }
    private fun playRemotePreview() {
        val path=project?.optString("preview_url")?.takeIf{it.isNotBlank()}?:return
        imagePreview.visibility=View.GONE; videoPreview.visibility=View.VISIBLE
        videoPreview.setVideoURI(Uri.parse(api.absolute(path)+"?t=${System.nanoTime()}")); videoPreview.setOnPreparedListener { it.isLooping=true; videoPreview.start() }
    }

    private fun serverSettings() {
        val prefs=getSharedPreferences("settings",MODE_PRIVATE)
        val input=EditText(this).apply { setText(prefs.getString("server","http://10.0.2.2:8000")); hint="https://your-backend" }
        AlertDialog.Builder(this).setTitle("Backend server").setMessage("Use your Cloud Run HTTPS URL on a physical Android phone.").setView(input)
            .setPositiveButton("Save") { _,_->prefs.edit().putString("server",input.text.toString().trim()).apply()}.setNegativeButton("Cancel",null).show()
    }

    private fun runAsync(label:String,block:()->Unit) {
        status.text=label
        executor.execute { try { block(); main.post { status.text="Ready" } } catch(e:Exception) { main.post { status.text="Failed"; Toast.makeText(this,e.message?:"Error",Toast.LENGTH_LONG).show() } } }
    }
    private fun opTitle(t:String)=when(t){"trim"->"Trim";"text_overlay"->"Text";"split_screen"->"Split screen";"picture_in_picture","media_overlay"->"Media layer";"masked_video","masked_media"->"Shape layer";"music"->"Background music";else->t.replace('_',' ').replaceFirstChar{it.uppercase()}}
    private fun summary(op:JSONObject)=if(isVisual(op))"Drag to position · ${op.optInt("width",360)}×${op.optInt("height",360)}" else if(op.optString("type")=="text_overlay")op.optString("text","Text") else "Tap Adjust for details"
    private fun isVisual(op:JSONObject)=op.optString("type") in setOf("picture_in_picture","media_overlay","masked_video","masked_media")
    private fun projectWidth()=project?.optJSONObject("metadata")?.optJSONObject("dimensions")?.optInt("width",1280)?:1280
    private fun projectHeight()=project?.optJSONObject("metadata")?.optJSONObject("dimensions")?.optInt("height",720)?:720
    private fun copyArray(a:JSONArray)=JSONArray(a.toString())
    private fun primaryButton(text:String,onClick:()->Unit)=Button(this).apply { this.text=text; minimumHeight=dp(52); setOnClickListener{onClick()} }
    private fun matchWrap()=LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT)
    private fun dp(v:Int)=(v*resources.displayMetrics.density).toInt()

    companion object { const val REQ_SOURCE=100; const val REQ_ASSET=101; const val REQ_AUDIO=102 }
}

private class SimpleItemSelected(val onSelect:(Int)->Unit): android.widget.AdapterView.OnItemSelectedListener {
    override fun onItemSelected(parent:android.widget.AdapterView<*>?,view:View?,position:Int,id:Long)=onSelect(position)
    override fun onNothingSelected(parent:android.widget.AdapterView<*>?){}
}

class PlacementView(context: android.content.Context, private val op: JSONObject, private val canvasW:Int, private val canvasH:Int): View(context) {
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG).apply { color=Color.argb(90,70,120,255) }
    private val stroke=Paint(Paint.ANTI_ALIAS_FLAG).apply { color=Color.WHITE; style=Paint.Style.STROKE; strokeWidth=4f }
    private var lastX=0f; private var lastY=0f
    private val scaleDetector=ScaleGestureDetector(context,object:ScaleGestureDetector.SimpleOnScaleGestureListener(){
        override fun onScale(detector:ScaleGestureDetector):Boolean {
            op.put("width",(op.optInt("width",360)*detector.scaleFactor).toInt().coerceIn(32,4096))
            op.put("height",(op.optInt("height",360)*detector.scaleFactor).toInt().coerceIn(32,4096))
            invalidate(); return true
        }
    })
    init { setBackgroundColor(Color.rgb(25,25,28)); minimumHeight=180 }
    override fun onDraw(c:Canvas) {
        super.onDraw(c)
        val sx=width.toFloat()/canvasW; val sy=height.toFloat()/canvasH; val s=min(sx,sy)
        val x=op.optInt("x",40)*s; val y=op.optInt("y",40)*s; val w=op.optInt("width",360)*s; val h=op.optInt("height",360)*s
        c.drawRoundRect(x,y,x+w,y+h,24f,24f,paint); c.drawRoundRect(x,y,x+w,y+h,24f,24f,stroke)
        if(op.optString("shape")=="star") c.drawPath(star(x+w/2,y+h/2,min(w,h)*.42f),stroke)
    }
    override fun onTouchEvent(e:MotionEvent):Boolean {
        scaleDetector.onTouchEvent(e)
        if(e.pointerCount>1)return true
        when(e.actionMasked){
            MotionEvent.ACTION_DOWN->{lastX=e.x;lastY=e.y;return true}
            MotionEvent.ACTION_MOVE->{val s=min(width.toFloat()/canvasW,height.toFloat()/canvasH);op.put("x",op.optInt("x",40)+((e.x-lastX)/s).toInt());op.put("y",op.optInt("y",40)+((e.y-lastY)/s).toInt());lastX=e.x;lastY=e.y;invalidate();return true}
        }
        return true
    }
    private fun star(cx:Float,cy:Float,r:Float):Path {
        val p=Path()
        for(i in 0 until 10){
            val rr=if(i%2==0)r else r*.43f
            val a=-Math.PI/2+i*Math.PI/5
            val x=cx+(cos(a)*rr).toFloat(); val y=cy+(sin(a)*rr).toFloat()
            if(i==0)p.moveTo(x,y)else p.lineTo(x,y)
        }
        p.close(); return p
    }
}
