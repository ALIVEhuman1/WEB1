package com.practice.routine.ui

import android.os.Bundle
import android.view.LayoutInflater
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.ItemTouchHelper
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.textfield.TextInputEditText
import com.practice.routine.R
import com.practice.routine.data.RoutineDatabase
import com.practice.routine.data.RoutineItem
import com.practice.routine.data.RoutineRepository
import com.practice.routine.databinding.ActivityPresetEditBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class PresetEditActivity : AppCompatActivity() {

    private lateinit var binding: ActivityPresetEditBinding
    private lateinit var adapter: RoutineAdapter
    private val workingItems = mutableListOf<RoutineItem>()
    private var presetId: Int = -1
    private var presetHasTree = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityPresetEditBinding.inflate(layoutInflater)
        setContentView(binding.root)

        presetId = intent.getIntExtra(EXTRA_PRESET_ID, -1)
        val presetName = intent.getStringExtra(EXTRA_PRESET_NAME) ?: ""
        binding.etPresetName.setText(presetName)

        binding.toolbar.setNavigationOnClickListener { finish() }

        setupRecyclerView()
        loadItems()

        binding.fabAddItem.setOnClickListener { showAddEditDialog(null, -1) }
        binding.btnSave.setOnClickListener { saveChanges() }
    }

    private fun setupRecyclerView() {
        adapter = RoutineAdapter(
            onEdit = { item ->
                val idx = workingItems.indexOfFirst { it === item || (it.name == item.name && it.durationMinutes == item.durationMinutes && it.order == item.order) }
                if (idx >= 0) showAddEditDialog(item, idx)
            },
            onDelete = { item ->
                val idx = workingItems.indexOf(item)
                if (idx >= 0) {
                    workingItems.removeAt(idx)
                    reindexItems()
                    adapter.submitList(workingItems.toList())
                }
            },
            onReorder = { reorderedItems ->
                workingItems.clear()
                workingItems.addAll(reorderedItems)
                reindexItems()
            }
        )
        binding.rvItems.layoutManager = LinearLayoutManager(this)
        binding.rvItems.adapter = adapter

        val touchHelper = ItemTouchHelper(object : ItemTouchHelper.SimpleCallback(
            ItemTouchHelper.UP or ItemTouchHelper.DOWN, 0
        ) {
            override fun onMove(rv: RecyclerView, vh: RecyclerView.ViewHolder, target: RecyclerView.ViewHolder): Boolean {
                adapter.moveItem(vh.adapterPosition, target.adapterPosition)
                return true
            }
            override fun onSwiped(vh: RecyclerView.ViewHolder, direction: Int) {}
            override fun clearView(rv: RecyclerView, vh: RecyclerView.ViewHolder) {
                super.clearView(rv, vh)
                adapter.notifyReorder()
            }
        })
        touchHelper.attachToRecyclerView(binding.rvItems)
    }

    private fun loadItems() {
        if (presetId < 0) return
        lifecycleScope.launch {
            val presetItems = withContext(Dispatchers.IO) {
                RoutineDatabase.getInstance(this@PresetEditActivity).presetDao().getPresetItems(presetId)
            }
            // 갈래(CHOICE)가 포함된 프리셋은 이 단순 편집 화면에서 다루지 않는다(트리 손상 방지).
            presetHasTree = presetItems.any { it.type == com.practice.routine.data.ItemType.CHOICE }
            if (presetHasTree) {
                binding.btnSave.isEnabled = false
                Toast.makeText(
                    this@PresetEditActivity,
                    "갈래가 포함된 프리셋은 여기서 편집할 수 없어요. 불러온 뒤 메인에서 수정해 다시 저장하세요.",
                    Toast.LENGTH_LONG
                ).show()
            }
            val topSteps = presetItems.filter {
                it.branchId == null && it.type == com.practice.routine.data.ItemType.STEP
            }.sortedBy { it.order }
            workingItems.clear()
            topSteps.forEachIndexed { index, pi ->
                workingItems.add(RoutineItem(name = pi.name, durationMinutes = pi.durationMinutes, order = index, note = pi.note, repeatCount = pi.repeatCount))
            }
            adapter.submitList(workingItems.toList())
        }
    }

    private fun showAddEditDialog(existing: RoutineItem?, existingIndex: Int) {
        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_add_routine, null)
        val etName = dialogView.findViewById<TextInputEditText>(R.id.etRoutineName)
        val etMinutes = dialogView.findViewById<TextInputEditText>(R.id.etMinutes)
        val etNote = dialogView.findViewById<TextInputEditText>(R.id.etNote)
        val etRepeat = dialogView.findViewById<TextInputEditText>(R.id.etRepeat)

        if (existing != null) {
            etName.setText(existing.name)
            etMinutes.setText(existing.durationMinutes.toString())
            etNote.setText(existing.note)
            etRepeat.setText(existing.repeatCount.toString())
        }

        AlertDialog.Builder(this)
            .setTitle(if (existing == null) "항목 추가" else "항목 수정")
            .setView(dialogView)
            .setPositiveButton("확인") { _, _ ->
                val name = etName.text?.toString()?.trim() ?: ""
                val mins = etMinutes.text?.toString()?.toIntOrNull() ?: 0
                val note = etNote.text?.toString()?.trim()?.ifEmpty { null }
                val sets = (etRepeat.text?.toString()?.toIntOrNull() ?: 1).coerceAtLeast(1)
                when {
                    name.isEmpty() -> Toast.makeText(this, "이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
                    mins <= 0 -> Toast.makeText(this, "시간을 1분 이상 입력해주세요.", Toast.LENGTH_SHORT).show()
                    existingIndex >= 0 -> {
                        workingItems[existingIndex] = workingItems[existingIndex].copy(name = name, durationMinutes = mins, note = note, repeatCount = sets)
                        adapter.submitList(workingItems.toList())
                    }
                    else -> {
                        workingItems.add(RoutineItem(name = name, durationMinutes = mins, order = workingItems.size, note = note, repeatCount = sets))
                        adapter.submitList(workingItems.toList())
                    }
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun reindexItems() {
        workingItems.forEachIndexed { index, item ->
            workingItems[index] = item.copy(order = index)
        }
    }

    private fun saveChanges() {
        if (presetHasTree) {
            Toast.makeText(this, "갈래가 포함된 프리셋은 여기서 저장할 수 없어요.", Toast.LENGTH_SHORT).show()
            return
        }
        val newName = binding.etPresetName.text?.toString()?.trim() ?: ""
        if (newName.isEmpty()) {
            Toast.makeText(this, "루틴 이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
            return
        }
        if (workingItems.isEmpty()) {
            Toast.makeText(this, "항목을 하나 이상 추가해주세요.", Toast.LENGTH_SHORT).show()
            return
        }

        lifecycleScope.launch {
            val db = RoutineDatabase.getInstance(this@PresetEditActivity)
            val repo = RoutineRepository(db.routineDao(), db.presetDao(), db.branchDao())
            withContext(Dispatchers.IO) {
                db.presetDao().updatePresetNameById(presetId, newName)
                repo.replacePresetItems(presetId, workingItems)
            }
            Toast.makeText(this@PresetEditActivity, "저장했습니다.", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    companion object {
        const val EXTRA_PRESET_ID = "EXTRA_PRESET_ID"
        const val EXTRA_PRESET_NAME = "EXTRA_PRESET_NAME"
    }
}
