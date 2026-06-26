package com.practice.routine.ui

import android.view.*
import android.widget.*
import androidx.recyclerview.widget.RecyclerView
import com.practice.routine.R
import com.practice.routine.data.PresetSummary

class PresetListAdapter(
    private val onLoad: (PresetSummary) -> Unit,
    private val onEdit: (PresetSummary) -> Unit,
    private val onDelete: (PresetSummary) -> Unit
) : RecyclerView.Adapter<PresetListAdapter.VH>() {

    private val items = mutableListOf<PresetSummary>()

    fun submitList(newItems: List<PresetSummary>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.tvPresetName)
        val info: TextView = view.findViewById(R.id.tvPresetInfo)
        val btnLoad: Button = view.findViewById(R.id.btnLoad)
        val btnEdit: ImageButton = view.findViewById(R.id.btnEdit)
        val btnDelete: ImageButton = view.findViewById(R.id.btnDelete)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_preset, parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.name.text = item.name
        holder.info.text = "${item.itemCount}개 · 총 ${item.totalMinutes}분"
        holder.btnLoad.setOnClickListener { onLoad(item) }
        holder.btnEdit.setOnClickListener { onEdit(item) }
        holder.btnDelete.setOnClickListener { onDelete(item) }
    }

    override fun getItemCount() = items.size
}
