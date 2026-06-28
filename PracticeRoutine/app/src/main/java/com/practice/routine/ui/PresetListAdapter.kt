package com.practice.routine.ui

import android.view.*
import android.widget.*
import androidx.recyclerview.widget.RecyclerView
import com.practice.routine.R
import com.practice.routine.data.PresetSummary

class PresetListAdapter(
    private val onLoad: (PresetSummary) -> Unit,
    private val onEdit: (PresetSummary) -> Unit,
    private val onDelete: (PresetSummary) -> Unit,
    private val onSelectionChanged: (count: Int) -> Unit = {}
) : RecyclerView.Adapter<PresetListAdapter.VH>() {

    private val items = mutableListOf<PresetSummary>()
    var isSelectionMode = false
        private set
    private val selectedIds = mutableSetOf<Int>()

    fun submitList(newItems: List<PresetSummary>) {
        items.clear()
        items.addAll(newItems)
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

    fun toggleSelection(item: PresetSummary) {
        if (selectedIds.contains(item.id)) selectedIds.remove(item.id)
        else selectedIds.add(item.id)
        notifyDataSetChanged()
        onSelectionChanged(selectedIds.size)
    }

    fun getSelectedItems(): List<PresetSummary> = items.filter { it.id in selectedIds }

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.tvPresetName)
        val info: TextView = view.findViewById(R.id.tvPresetInfo)
        val btnLoad: Button = view.findViewById(R.id.btnLoad)
        val btnEdit: ImageButton = view.findViewById(R.id.btnEdit)
        val btnDelete: ImageButton = view.findViewById(R.id.btnDelete)
        val actionRow: View = view.findViewById(R.id.actionRow)
        val checkSelect: CheckBox = view.findViewById(R.id.checkSelect)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_preset, parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.name.text = item.name
        holder.info.text = "${item.itemCount}개 · 총 ${item.totalMinutes}분"

        if (isSelectionMode) {
            holder.checkSelect.visibility = View.VISIBLE
            holder.checkSelect.isChecked = item.id in selectedIds
            holder.actionRow.visibility = View.GONE
            holder.itemView.setOnClickListener { toggleSelection(item) }
            holder.itemView.setOnLongClickListener(null)
        } else {
            holder.checkSelect.visibility = View.GONE
            holder.actionRow.visibility = View.VISIBLE
            holder.btnLoad.setOnClickListener { onLoad(item) }
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
