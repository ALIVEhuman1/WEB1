package com.practice.routine.ui

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.practice.routine.R
import com.practice.routine.data.PracticeLog
import com.practice.routine.databinding.ActivityStatsBinding

class StatsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityStatsBinding
    private val viewModel: StatsViewModel by viewModels()
    private lateinit var adapter: PracticeLogAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityStatsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.toolbar.inflateMenu(R.menu.menu_stats)
        binding.toolbar.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_clear_all -> { confirmClearAll(); true }
                else -> false
            }
        }

        adapter = PracticeLogAdapter(onLongPress = { confirmDelete(it) })
        binding.rvLogs.layoutManager = LinearLayoutManager(this)
        binding.rvLogs.adapter = adapter

        observe()
    }

    private fun observe() {
        viewModel.recentLogs.observe(this) { logs ->
            adapter.submitList(logs)
            val empty = logs.isEmpty()
            binding.emptyState.visibility = if (empty) View.VISIBLE else View.GONE
            binding.scrollContent.visibility = if (empty) View.GONE else View.VISIBLE
        }
        viewModel.weekCount.observe(this) { binding.tvWeekCount.text = "${it}회" }
        viewModel.weekSeconds.observe(this) {
            binding.tvWeekTime.text = PracticeLogAdapter.formatDuration(it)
        }
        viewModel.totalCount.observe(this) { binding.tvTotalCount.text = "${it}회" }
        viewModel.totalSeconds.observe(this) {
            binding.tvTotalTime.text = PracticeLogAdapter.formatDuration(it)
        }
    }

    private fun confirmDelete(log: PracticeLog) {
        AlertDialog.Builder(this)
            .setTitle("기록 삭제")
            .setMessage("'${log.routineName}' 기록을 삭제할까요?")
            .setPositiveButton("삭제") { _, _ -> viewModel.delete(log) }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun confirmClearAll() {
        if (viewModel.totalCount.value == 0 || viewModel.totalCount.value == null) {
            Toast.makeText(this, "삭제할 기록이 없습니다.", Toast.LENGTH_SHORT).show()
            return
        }
        AlertDialog.Builder(this)
            .setTitle("전체 삭제")
            .setMessage("모든 연습 기록을 삭제할까요? 이 작업은 되돌릴 수 없어요.")
            .setPositiveButton("전체 삭제") { _, _ -> viewModel.deleteAll() }
            .setNegativeButton("취소", null)
            .show()
    }
}
