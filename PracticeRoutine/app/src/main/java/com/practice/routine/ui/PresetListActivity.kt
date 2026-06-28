package com.practice.routine.ui

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.practice.routine.R
import com.practice.routine.data.PresetSummary
import com.practice.routine.data.RoutinePreset
import com.practice.routine.databinding.ActivityPresetListBinding

class PresetListActivity : AppCompatActivity() {

    private lateinit var binding: ActivityPresetListBinding
    private val viewModel: RoutineViewModel by viewModels()
    private lateinit var adapter: PresetListAdapter

    private var isSelectionMode = false
    private val backCallback = object : OnBackPressedCallback(false) {
        override fun handleOnBackPressed() {
            exitSelectionMode()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityPresetListBinding.inflate(layoutInflater)
        setContentView(binding.root)

        onBackPressedDispatcher.addCallback(this, backCallback)

        binding.toolbar.setNavigationOnClickListener {
            if (isSelectionMode) exitSelectionMode() else finish()
        }

        binding.toolbar.inflateMenu(R.menu.menu_preset_list)
        binding.toolbar.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.action_select_mode -> { enterSelectionMode(); true }
                R.id.action_delete_selected -> {
                    val selected = adapter.getSelectedItems()
                    if (selected.isEmpty()) {
                        Toast.makeText(this, "선택된 항목이 없습니다.", Toast.LENGTH_SHORT).show()
                    } else {
                        confirmDeleteMultiple(selected)
                    }
                    true
                }
                R.id.action_cancel_select -> { exitSelectionMode(); true }
                else -> false
            }
        }

        adapter = PresetListAdapter(
            onLoad = { summary -> confirmLoad(summary) },
            onEdit = { summary -> openEditScreen(summary) },
            onDelete = { summary -> confirmDelete(summary) },
            onSelectionChanged = { count ->
                if (!isSelectionMode) {
                    isSelectionMode = true
                    backCallback.isEnabled = true
                    binding.toolbar.navigationIcon = null
                    updateMenuVisibility()
                }
                binding.toolbar.title = "${count}개 선택됨"
            }
        )
        binding.rvPresets.layoutManager = LinearLayoutManager(this)
        binding.rvPresets.adapter = adapter

        viewModel.presetSummaries.observe(this) { summaries ->
            adapter.submitList(summaries)
            binding.tvEmpty.visibility = if (summaries.isEmpty()) View.VISIBLE else View.GONE
            updateMenuVisibility(summaries.size)
        }

        updateMenuVisibility(0)
    }

    private fun updateMenuVisibility(itemCount: Int = adapter.itemCount) {
        val menu = binding.toolbar.menu
        menu.findItem(R.id.action_select_mode)?.isVisible = !isSelectionMode && itemCount > 0
        menu.findItem(R.id.action_delete_selected)?.isVisible = isSelectionMode
        menu.findItem(R.id.action_cancel_select)?.isVisible = isSelectionMode
    }

    private fun enterSelectionMode() {
        isSelectionMode = true
        backCallback.isEnabled = true
        adapter.enterSelectionMode()
        binding.toolbar.title = "0개 선택됨"
        binding.toolbar.navigationIcon = null
        updateMenuVisibility()
    }

    private fun exitSelectionMode() {
        isSelectionMode = false
        backCallback.isEnabled = false
        adapter.exitSelectionMode()
        binding.toolbar.title = "프리셋 불러오기"
        binding.toolbar.setNavigationIcon(R.drawable.ic_arrow_back)
        updateMenuVisibility()
    }

    private fun confirmDeleteMultiple(summaries: List<PresetSummary>) {
        AlertDialog.Builder(this)
            .setTitle("삭제")
            .setMessage("선택한 ${summaries.size}개 프리셋을 삭제할까요?")
            .setPositiveButton("삭제") { _, _ ->
                val presets = summaries.map { RoutinePreset(id = it.id, name = it.name, createdAt = it.createdAt) }
                viewModel.deleteMultiplePresets(presets)
                exitSelectionMode()
            }
            .setNegativeButton("취소", null)
            .show()
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
