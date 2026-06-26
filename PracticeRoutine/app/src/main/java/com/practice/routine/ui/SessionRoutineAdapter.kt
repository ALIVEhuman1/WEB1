package com.practice.routine.ui

import android.graphics.Paint
import android.view.*
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.practice.routine.R
import com.practice.routine.data.RoutineItem

class SessionRoutineAdapter(private val items: List<RoutineItem>) :
    RecyclerView.Adapter<SessionRoutineAdapter.VH>() {

    private val doneSet = mutableSetOf<Int>()

    fun markDone(index: Int) {
        doneSet.add(index)
        notifyItemChanged(index)
    }

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val tvNum: TextView = view.findViewById(R.id.tvSessionNum)
        val tvName: TextView = view.findViewById(R.id.tvSessionName)
        val tvDur: TextView = view.findViewById(R.id.tvSessionDuration)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_session_routine, parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        val isDone = doneSet.contains(position)
        holder.tvNum.text = "${position + 1}."
        holder.tvName.text = item.name
        holder.tvDur.text = "${item.durationMinutes}분"

        val alpha = if (isDone) 0.4f else 1.0f
        holder.tvNum.alpha = alpha
        holder.tvName.alpha = alpha
        holder.tvDur.alpha = alpha

        if (isDone) {
            holder.tvName.paintFlags = holder.tvName.paintFlags or Paint.STRIKE_THRU_TEXT_FLAG
        } else {
            holder.tvName.paintFlags = holder.tvName.paintFlags and Paint.STRIKE_THRU_TEXT_FLAG.inv()
        }
    }

    override fun getItemCount() = items.size
}
