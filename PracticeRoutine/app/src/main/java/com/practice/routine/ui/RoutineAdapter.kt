package com.practice.routine.ui

import android.view.*
import android.widget.*
import androidx.recyclerview.widget.*
import com.practice.routine.R
import com.practice.routine.data.RoutineItem
import java.util.Collections

class RoutineAdapter(
    private val onEdit: (RoutineItem) -> Unit,
    private val onDelete: (RoutineItem) -> Unit,
    private val onReorder: (List<RoutineItem>) -> Unit,
    private val onSelectionChanged: (count: Int) -> Unit = {}
) : RecyclerView.Adapter<RoutineAdapter.VH>() {

    private val items = mutableListOf<RoutineItem>()
    var isSelectionMode = false
        private set
    private val selectedIds = mutableSetOf<Int>()

    fun submitList(newItems: List<RoutineItem>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    fun getCurrentItems(): List<RoutineItem> = items.toList()

    fun moveItem(from: Int, to: Int) {
        if (isSelectionMode) return
        Collections.swap(items, from, to)
        notifyItemMoved(from, to)
    }

    fun notifyReorder() {
        if (!isSelectionMode) onReorder(items.toList())
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
        if (selectedIds.contains(item.id)) selectedIds.remove(item.id)
        else selectedIds.add(item.id)
        notifyDataSetChanged()
        onSelectionChanged(selectedIds.size)
    }

    fun getSelectedItems(): List<RoutineItem> = items.filter { it.id in selectedIds }

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val number: TextView = view.findViewById(R.id.tvNumber)
        val name: TextView = view.findViewById(R.id.tvName)
        val duration: TextView = view.findViewById(R.id.tvDuration)
        val btnEdit: ImageButton = view.findViewById(R.id.btnEdit)
        val btnDelete: ImageButton = view.findViewById(R.id.btnDelete)
        val dragHandle: ImageView = view.findViewById(R.id.dragHandle)
        val checkSelect: CheckBox = view.findViewById(R.id.checkSelect)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_routine, parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.number.text = "${position + 1}"
        holder.name.text = item.name
        holder.duration.text = "${item.durationMinutes}분"

        if (isSelectionMode) {
            holder.checkSelect.visibility = View.VISIBLE
            holder.dragHandle.visibility = View.GONE
            holder.btnEdit.visibility = View.GONE
            holder.btnDelete.visibility = View.GONE
            holder.checkSelect.isChecked = item.id in selectedIds
            holder.itemView.setOnClickListener { toggleSelection(item) }
            holder.itemView.setOnLongClickListener(null)
        } else {
            holder.checkSelect.visibility = View.GONE
            holder.dragHandle.visibility = View.VISIBLE
            holder.btnEdit.visibility = View.VISIBLE
            holder.btnDelete.visibility = View.VISIBLE
            holder.btnEdit.setOnClickListener { onEdit(item) }
            holder.btnDelete.setOnClickListener { onDelete(item) }
            holder.itemView.setOnClickListener(null)
            holder.itemView.setOnLongClickListener {
                enterSelectionMode()
                toggleSelection(item)
                onSelectionChanged(selectedIds.size)
                true
            }
        }
    }

    override fun getItemCount() = items.size
}
