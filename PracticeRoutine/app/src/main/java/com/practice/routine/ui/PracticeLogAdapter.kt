package com.practice.routine.ui

import android.view.*
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.practice.routine.R
import com.practice.routine.data.PracticeLog
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class PracticeLogAdapter(
    private val onLongPress: (PracticeLog) -> Unit
) : RecyclerView.Adapter<PracticeLogAdapter.VH>() {

    private val items = mutableListOf<PracticeLog>()
    private val dateFmt = SimpleDateFormat("M월 d일 (E) HH:mm", Locale.getDefault())

    fun submitList(newItems: List<PracticeLog>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.tvLogName)
        val date: TextView = view.findViewById(R.id.tvLogDate)
        val duration: TextView = view.findViewById(R.id.tvLogDuration)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_practice_log, parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.name.text = item.routineName
        holder.date.text = dateFmt.format(Date(item.completedAt))
        holder.duration.text = formatDuration(item.durationSeconds)
        holder.itemView.setOnLongClickListener { onLongPress(item); true }
    }

    override fun getItemCount() = items.size

    companion object {
        fun formatDuration(totalSeconds: Int): String {
            val totalMin = totalSeconds / 60
            val h = totalMin / 60
            val m = totalMin % 60
            return if (h > 0) "${h}시간 ${m}분" else "${m}분"
        }
    }
}
