package com.practice.routine.ui

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.view.View
import androidx.core.content.res.ResourcesCompat
import com.practice.routine.R
import com.practice.routine.data.RoutineNode
import com.practice.routine.data.RoutineTree
import com.practice.routine.data.totalMinutes

/**
 * 연습 루틴 트리를 마인드맵(자유 캔버스)으로 그리는 커스텀 뷰.
 * - 핀치로 확대/축소, 드래그로 이동(pan)
 * - 노드 하나를 잡고 드래그하면 그 노드만 이동(위치는 화면용, 저장 안 함)
 * - 갈래(CHOICE) 노드 탭 → onChoiceTap, 단계 노드 탭 → onStepTap
 */
class MindMapView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {

    enum class Kind { ROOT, STEP, CHOICE, BRANCH }

    private inner class Node(
        val id: String,
        val baseX: Float,
        val baseY: Float,
        val w: Float,
        val h: Float,
        val title: String,
        val subtitle: String,
        val kind: Kind,
        val choiceItemId: Int = -1,
        val stepName: String = "",
        val stepInfo: String = ""
    ) {
        var dx = 0f
        var dy = 0f
        val cx get() = baseX + dx
        val cy get() = baseY + dy
        val left get() = cx - w / 2
        val top get() = cy - h / 2
        val right get() = cx + w / 2
        val bottom get() = cy + h / 2
        fun contains(x: Float, y: Float) = x in left..right && y in top..bottom
    }

    private data class Edge(val fromId: String, val toId: String)

    private val nodes = mutableListOf<Node>()
    private val edges = mutableListOf<Edge>()
    private val nodeById = HashMap<String, Node>()

    var onChoiceTap: ((choiceItemId: Int) -> Unit)? = null
    var onStepTap: ((name: String, info: String) -> Unit)? = null

    private val density = resources.displayMetrics.density
    private fun dp(v: Float) = v * density

    // view transform
    private var scale = 1f
    private var offsetX = 0f
    private var offsetY = 0f
    private var initialized = false

    // ---- paints ----
    private val edgePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = dp(2.5f)
        color = Color.parseColor("#CBD5E1")
        strokeCap = Paint.Cap.ROUND
    }
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = dp(1.5f)
    }
    private val titlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = dp(14f); typeface = font(R.font.pretendard_bold)
    }
    private val subPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = dp(11.5f); typeface = font(R.font.pretendard_medium); color = Color.parseColor("#64748B")
    }
    private val hintPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = dp(15f); typeface = font(R.font.pretendard_medium)
        color = Color.parseColor("#94A3B8"); textAlign = Paint.Align.CENTER
    }

    private fun font(res: Int) = try { ResourcesCompat.getFont(context, res) } catch (e: Exception) { Typeface.DEFAULT }

    init {
        setLayerType(LAYER_TYPE_SOFTWARE, null) // 그림자 렌더링
    }

    fun setTree(tree: RoutineTree) {
        buildLayout(tree)
        initialized = false
        invalidate()
    }

    // ---- layout ----
    private fun buildLayout(tree: RoutineTree) {
        nodes.clear(); edges.clear(); nodeById.clear()
        val nodeW = dp(168f)
        val nodeH = dp(58f)
        val gapY = dp(34f)
        val branchGapX = dp(24f)
        val cx = 0f
        var y = 0f
        var idc = 0

        fun add(n: Node) { nodes.add(n); nodeById[n.id] = n }

        // root
        val rootId = "root"
        add(Node(rootId, cx, y, nodeW, nodeH, "연습 루틴", "", Kind.ROOT))
        y += nodeH + gapY
        var prevIds = listOf(rootId)

        for (node in tree.nodes) {
            when (node) {
                is RoutineNode.Step -> {
                    val id = "s${idc++}"
                    val sub = if (node.item.repeatCount > 1)
                        "${node.item.durationMinutes}분 · ${node.item.repeatCount}세트"
                    else "${node.item.durationMinutes}분"
                    add(Node(id, cx, y, nodeW, nodeH, node.item.name, sub, Kind.STEP,
                        stepName = node.item.name, stepInfo = node.item.note ?: sub))
                    prevIds.forEach { edges.add(Edge(it, id)) }
                    prevIds = listOf(id)
                    y += nodeH + gapY
                }
                is RoutineNode.Choice -> {
                    val cid = "c${idc++}"
                    add(Node(cid, cx, y, nodeW, nodeH, if (node.item.name.isBlank()) "선택" else node.item.name,
                        "${node.branches.size}개 갈래", Kind.CHOICE, choiceItemId = node.item.id))
                    prevIds.forEach { edges.add(Edge(it, cid)) }
                    y += nodeH + gapY
                    val branchTop = y
                    val n = node.branches.size
                    val branchEndIds = mutableListOf<String>()
                    var deepest = branchTop
                    node.branches.forEachIndexed { i, bn ->
                        val bx = cx + (i - (n - 1) / 2f) * (nodeW + branchGapX)
                        var by = branchTop
                        val bhId = "b${idc++}"
                        add(Node(bhId, bx, by, nodeW, nodeH, bn.branch.label,
                            "${bn.totalMinutes()}분" + (if (bn.branch.isDefault) " · 기본" else ""), Kind.BRANCH))
                        edges.add(Edge(cid, bhId))
                        by += nodeH + gapY
                        var lastId = bhId
                        bn.steps.forEach { s ->
                            val sid = "bs${idc++}"
                            val sub = if (s.repeatCount > 1) "${s.durationMinutes}분 · ${s.repeatCount}세트" else "${s.durationMinutes}분"
                            add(Node(sid, bx, by, nodeW, nodeH, s.name, sub, Kind.STEP,
                                stepName = s.name, stepInfo = s.note ?: sub))
                            edges.add(Edge(lastId, sid))
                            lastId = sid
                            by += nodeH + gapY
                        }
                        branchEndIds.add(lastId)
                        if (by > deepest) deepest = by
                    }
                    prevIds = branchEndIds
                    y = deepest + gapY
                }
            }
        }
    }

    // ---- drawing ----
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.drawColor(Color.parseColor("#0F172A")) // 어두운 캔버스 배경

        if (nodes.size <= 1) {
            hintPaint.color = Color.parseColor("#64748B")
            canvas.drawText("표시할 루틴이 없어요", width / 2f, height / 2f, hintPaint)
            return
        }

        if (!initialized) centerContent()

        canvas.save()
        canvas.translate(offsetX, offsetY)
        canvas.scale(scale, scale)

        for (e in edges) {
            val a = nodeById[e.fromId] ?: continue
            val b = nodeById[e.toId] ?: continue
            drawEdge(canvas, a, b)
        }
        for (n in nodes) drawNode(canvas, n)

        canvas.restore()
    }

    private fun drawEdge(canvas: Canvas, a: Node, b: Node) {
        val sx = a.cx; val sy = a.bottom
        val ex = b.cx; val ey = b.top
        val path = Path()
        path.moveTo(sx, sy)
        val midY = (sy + ey) / 2
        path.cubicTo(sx, midY, ex, midY, ex, ey)
        canvas.drawPath(path, edgePaint)
    }

    private fun drawNode(canvas: Canvas, n: Node) {
        val r = dp(16f)
        val rect = RectF(n.left, n.top, n.right, n.bottom)
        val (bg, border, title) = when (n.kind) {
            Kind.ROOT -> Triple("#2563EB", "#2563EB", "#FFFFFF")
            Kind.CHOICE -> Triple("#2A2140", "#7C3AED", "#C4B5FD")
            Kind.BRANCH -> Triple("#152238", "#2563EB", "#93C5FD")
            Kind.STEP -> Triple("#1E293B", "#334155", "#E2E8F0")
        }
        fillPaint.color = Color.parseColor(bg)
        fillPaint.setShadowLayer(dp(8f), 0f, dp(3f), Color.parseColor("#66000000"))
        canvas.drawRoundRect(rect, r, r, fillPaint)
        fillPaint.clearShadowLayer()
        strokePaint.color = Color.parseColor(border)
        canvas.drawRoundRect(rect, r, r, strokePaint)

        titlePaint.color = Color.parseColor(title)
        val pad = dp(14f)
        val maxW = n.w - pad * 2
        val titleText = ellipsize(n.title, titlePaint, maxW)
        val hasSub = n.subtitle.isNotEmpty()
        if (hasSub) {
            canvas.drawText(titleText, n.left + pad, n.cy - dp(3f), titlePaint)
            val subText = ellipsize(n.subtitle, subPaint, maxW)
            subPaint.color = if (n.kind == Kind.ROOT) Color.parseColor("#DBEAFE") else Color.parseColor("#94A3B8")
            canvas.drawText(subText, n.left + pad, n.cy + dp(15f), subPaint)
        } else {
            val fm = titlePaint.fontMetrics
            val baseline = n.cy - (fm.ascent + fm.descent) / 2
            canvas.drawText(titleText, n.left + pad, baseline, titlePaint)
        }
    }

    private fun ellipsize(text: String, paint: Paint, maxWidth: Float): String {
        if (paint.measureText(text) <= maxWidth) return text
        var end = text.length
        while (end > 0 && paint.measureText(text.substring(0, end) + "…") > maxWidth) end--
        return text.substring(0, end.coerceAtLeast(0)) + "…"
    }

    private fun centerContent() {
        if (nodes.isEmpty()) return
        val minX = nodes.minOf { it.left }
        val maxX = nodes.maxOf { it.right }
        val minY = nodes.minOf { it.top }
        val contentW = (maxX - minX).coerceAtLeast(1f)
        scale = ((width - dp(40f)) / contentW).coerceIn(0.4f, 1.2f)
        offsetX = width / 2f - ((minX + maxX) / 2f) * scale
        offsetY = dp(24f) - minY * scale
        initialized = true
    }

    fun resetView() { initialized = false; invalidate() }

    // ---- gestures ----
    private var dragNode: Node? = null
    private var lastX = 0f
    private var lastY = 0f
    private var moved = false

    private val scaleDetector = ScaleGestureDetector(context, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
        override fun onScale(detector: ScaleGestureDetector): Boolean {
            val factor = detector.scaleFactor
            val fx = detector.focusX; val fy = detector.focusY
            // zoom around focus
            offsetX = fx - (fx - offsetX) * factor
            offsetY = fy - (fy - offsetY) * factor
            scale = (scale * factor).coerceIn(0.25f, 3f)
            invalidate()
            return true
        }
    })

    private val tapDetector = GestureDetector(context, object : GestureDetector.SimpleOnGestureListener() {
        override fun onSingleTapUp(e: MotionEvent): Boolean {
            val wx = (e.x - offsetX) / scale
            val wy = (e.y - offsetY) / scale
            val hit = nodes.lastOrNull { it.contains(wx, wy) } ?: return false
            when (hit.kind) {
                Kind.CHOICE -> onChoiceTap?.invoke(hit.choiceItemId)
                Kind.STEP -> onStepTap?.invoke(hit.stepName, hit.stepInfo)
                else -> {}
            }
            return true
        }
    })

    override fun onTouchEvent(event: MotionEvent): Boolean {
        scaleDetector.onTouchEvent(event)
        tapDetector.onTouchEvent(event)

        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                lastX = event.x; lastY = event.y; moved = false
                val wx = (event.x - offsetX) / scale
                val wy = (event.y - offsetY) / scale
                dragNode = nodes.lastOrNull { it.contains(wx, wy) && it.kind != Kind.ROOT }
            }
            MotionEvent.ACTION_MOVE -> {
                if (scaleDetector.isInProgress) { dragNode = null; return true }
                val dxS = event.x - lastX
                val dyS = event.y - lastY
                if (kotlin.math.abs(dxS) > 6 || kotlin.math.abs(dyS) > 6) moved = true
                val node = dragNode
                if (node != null) {
                    node.dx += dxS / scale
                    node.dy += dyS / scale
                } else {
                    offsetX += dxS
                    offsetY += dyS
                }
                lastX = event.x; lastY = event.y
                invalidate()
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                dragNode = null
            }
        }
        return true
    }
}
