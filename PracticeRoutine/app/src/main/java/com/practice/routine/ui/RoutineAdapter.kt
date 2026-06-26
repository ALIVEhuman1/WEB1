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
    private val onReorder: (List<RoutineItem>) -> Unit
) : RecyclerView.Adapter<RoutineAdapter.VH>() {

    private val items = mutableListOf<RoutineItem>()

    fun submitList(newItems: List<RoutineItem>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    fun getCurrentItems(): List<RoutineItem> = items.toList()

    fun moveItem(from: Int, to: Int) {
        Collections.swap(items, from, to)
        notifyItemMoved(from, to)
    }

    fun notifyReorder() = onReorder(items.toList())

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val number: TextView = view.findViewById(R.id.tvNumber)
        val name: TextView = view.findViewById(R.id.tvName)
        val duration: TextView = view.findViewById(R.id.tvDuration)
        val btnEdit: ImageButton = view.findViewById(R.id.btnEdit)
        val btnDelete: ImageButton = view.findViewById(R.id.btnDelete)
        val dragHandle: ImageView = view.findViewById(R.id.dragHandle)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_routine, parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.number.text = "${position + 1}."
        holder.name.text = item.name
        holder.duration.text = "${item.durationMinutes}분"
        holder.btnEdit.setOnClickListener { onEdit(item) }
        holder.btnDelete.setOnClickListener { onDelete(item) }
    }

    override fun getItemCount() = items.size
}
