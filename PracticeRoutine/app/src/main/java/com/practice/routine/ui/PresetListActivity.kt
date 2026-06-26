package com.practice.routine.ui

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.practice.routine.data.RoutinePreset
import com.practice.routine.data.PresetSummary
import com.practice.routine.databinding.ActivityPresetListBinding

class PresetListActivity : AppCompatActivity() {

    private lateinit var binding: ActivityPresetListBinding
    private val viewModel: RoutineViewModel by viewModels()
    private lateinit var adapter: PresetListAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityPresetListBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.toolbar.setNavigationOnClickListener { finish() }

        adapter = PresetListAdapter(
            onLoad = { summary -> confirmLoad(summary) },
            onEdit = { summary -> openEditScreen(summary) },
            onDelete = { summary -> confirmDelete(summary) }
        )
        binding.rvPresets.layoutManager = LinearLayoutManager(this)
        binding.rvPresets.adapter = adapter

        viewModel.presetSummaries.observe(this) { summaries ->
            adapter.submitList(summaries)
            binding.tvEmpty.visibility = if (summaries.isEmpty()) View.VISIBLE else View.GONE
        }
    }

    private fun confirmLoad(summary: PresetSummary) {
        AlertDialog.Builder(this)
            .setTitle("'${summary.name}' 불러오기")
            .setMessage("현재 루틴 목록이 이 루틴으로 교체됩니다. 계속할까요?")
            .setPositiveButton("불러오기") { _, _ ->
                val preset = RoutinePreset(id = summary.id, name = summary.name, createdAt = summary.createdAt)
                viewModel.loadPreset(preset)
                Toast.makeText(this, "'${summary.name}'을 불러왔습니다.", Toast.LENGTH_SHORT).show()
                finish()
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun openEditScreen(summary: PresetSummary) {
        val intent = Intent(this, PresetEditActivity::class.java).apply {
            putExtra(PresetEditActivity.EXTRA_PRESET_ID, summary.id)
            putExtra(PresetEditActivity.EXTRA_PRESET_NAME, summary.name)
        }
        startActivity(intent)
    }

    private fun confirmDelete(summary: PresetSummary) {
        AlertDialog.Builder(this)
            .setTitle("삭제")
            .setMessage("'${summary.name}'을(를) 삭제할까요?")
            .setPositiveButton("삭제") { _, _ ->
                val preset = RoutinePreset(id = summary.id, name = summary.name, createdAt = summary.createdAt)
                viewModel.deletePreset(preset)
            }
            .setNegativeButton("취소", null)
            .show()
    }
}
