package com.practice.routine.ui

import android.view.*
import android.widget.*
import androidx.recyclerview.widget.RecyclerView
import com.practice.routine.R
import com.practice.routine.data.ItemType
import com.practice.routine.data.RoutineItem
import java.util.Collections

/**
 * 메인 루틴 리스트 어댑터. STEP 카드와 CHOICE(갈래) 카드 두 가지 뷰타입을 다룬다.
 * 드래그 정렬/다중선택은 최상위 컨테이너 안에서만 동작한다.
 */
class MainListAdapter(
    private val onStepEdit: (RoutineItem) -> Unit,
    private val onDelete: (RoutineItem) -> Unit,
    private val onChoiceTap: (RoutineItem) -> Unit,
    private val onReorder: (List<RoutineItem>) -> Unit,
    private val onSelectionChanged: (count: Int) -> Unit = {}
) : RecyclerView.Adapter<RecyclerView.ViewHolder>() {

    private val items = mutableListOf<RoutineItem>()
    private var summaries: Map<Int, String> = emptyMap()

    var isSelectionMode = false
        private set
    private val selectedIds = mutableSetOf<Int>()

    companion object {
        private const val TYPE_STEP = 0
        private const val TYPE_CHOICE = 1
    }

    fun submitList(newItems: List<RoutineItem>, choiceSummaries: Map<Int, String>) {
        items.clear()
        items.addAll(newItems)
        summaries = choiceSummaries
        notifyDataSetChanged()
    }

    fun enterSelectionMode() {
        isSelectionMode = true
        selectedIds.clear()
        notifyDataSetChanged()
    }

    fun exitSelectionMode() {
        isSelectionMode = false
        selectedIds.clear()
        notifyDataSetChanged()
    }

    fun toggleSelection(item: RoutineItem) {
        if (selectedIds.contains(item.id)) selectedIds.remove(item.id) else selectedIds.add(item.id)
        notifyDataSetChanged()
        onSelectionChanged(selectedIds.size)
    }

    fun getSelectedItems(): List<RoutineItem> = items.filter { it.id in selectedIds }

    fun moveItem(from: Int, to: Int) {
        if (isSelectionMode) return
        Collections.swap(items, from, to)
        notifyItemMoved(from, to)
    }

    fun notifyReorder() {
        if (!isSelectionMode) onReorder(items.toList())
    }

    override fun getItemViewType(position: Int): Int =
        if (items[position].type == ItemType.CHOICE) TYPE_CHOICE else TYPE_STEP

    override fun getItemCount() = items.size

    // ---- STEP ----
    inner class StepVH(view: View) : RecyclerView.ViewHolder(view) {
        val number: TextView = view.findViewById(R.id.tvNumber)
        val name: TextView = view.findViewById(R.id.tvName)
        val duration: TextView = view.findViewById(R.id.tvDuration)
        val btnEdit: ImageButton = view.findViewById(R.id.btnEdit)
        val btnDelete: ImageButton = view.findViewById(R.id.btnDelete)
        val dragHandle: ImageView = view.findViewById(R.id.dragHandle)
        val checkSelect: CheckBox = view.findViewById(R.id.checkSelect)
    }

    // ---- CHOICE ----
    inner class ChoiceVH(view: View) : RecyclerView.ViewHolder(view) {
        val title: TextView = view.findViewById(R.id.tvChoiceTitle)
        val summary: TextView = view.findViewById(R.id.tvChoiceSummary)
        val btnDelete: ImageButton = view.findViewById(R.id.btnDelete)
        val dragHandle: ImageView = view.findViewById(R.id.dragHandle)
        val checkSelect: CheckBox = view.findViewById(R.id.checkSelect)
        val chevron: ImageView = view.findViewById(R.id.chevron)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inflater = LayoutInflater.from(parent.context)
        return if (viewType == TYPE_CHOICE)
            ChoiceVH(inflater.inflate(R.layout.item_choice, parent, false))
        else
            StepVH(inflater.inflate(R.layout.item_routine, parent, false))
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        val item = items[position]
        if (holder is StepVH) bindStep(holder, item, position)
        else if (holder is ChoiceVH) bindChoice(holder, item)
    }

    private fun bindStep(holder: StepVH, item: RoutineItem, position: Int) {
        holder.number.text = "${position + 1}"
        holder.name.text = item.name
        holder.duration.text = if (item.repeatCount > 1)
            "${item.durationMinutes}분 · ${item.repeatCount}세트" else "${item.durationMinutes}분"

        if (isSelectionMode) {
            holder.checkSelect.visibility = View.VISIBLE
            holder.checkSelect.isChecked = item.id in selectedIds
            holder.dragHandle.visibility = View.GONE
            holder.btnEdit.visibility = View.GONE
            holder.btnDelete.visibility = View.GONE
            holder.itemView.setOnClickListener { toggleSelection(item) }
            holder.itemView.setOnLongClickListener(null)
        } else {
            holder.checkSelect.visibility = View.GONE
            holder.dragHandle.visibility = View.VISIBLE
            holder.btnEdit.visibility = View.VISIBLE
            holder.btnDelete.visibility = View.VISIBLE
            holder.btnEdit.setOnClickListener { onStepEdit(item) }
            holder.btnDelete.setOnClickListener { onDelete(item) }
            holder.itemView.setOnClickListener(null)
            holder.itemView.setOnLongClickListener {
                enterSelectionMode(); toggleSelection(item); onSelectionChanged(selectedIds.size); true
            }
        }
    }

    private fun bindChoice(holder: ChoiceVH, item: RoutineItem) {
        holder.title.text = if (item.name.isBlank()) "선택" else item.name
        holder.summary.text = summaries[item.id] ?: "갈래를 편집하세요"

        if (isSelectionMode) {
            holder.checkSelect.visibility = View.VISIBLE
            holder.checkSelect.isChecked = item.id in selectedIds
            holder.dragHandle.visibility = View.GONE
            holder.btnDelete.visibility = View.GONE
            holder.chevron.visibility = View.GONE
            holder.itemView.setOnClickListener { toggleSelection(item) }
            holder.itemView.setOnLongClickListener(null)
        } else {
            holder.checkSelect.visibility = View.GONE
            holder.dragHandle.visibility = View.VISIBLE
            holder.btnDelete.visibility = View.VISIBLE
            holder.chevron.visibility = View.VISIBLE
            holder.btnDelete.setOnClickListener { onDelete(item) }
            holder.itemView.setOnClickListener { onChoiceTap(item) }
            holder.itemView.setOnLongClickListener {
                enterSelectionMode(); toggleSelection(item); onSelectionChanged(selectedIds.size); true
            }
        }
    }
}
