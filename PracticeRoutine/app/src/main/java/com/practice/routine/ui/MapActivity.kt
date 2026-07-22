package com.practice.routine.ui

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import com.practice.routine.R
import com.practice.routine.data.RoutineDatabase
import com.practice.routine.data.RoutineItem
import com.practice.routine.data.RoutineRepository
import com.practice.routine.databinding.ActivityMapBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MapActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMapBinding
    private val db by lazy { RoutineDatabase.getInstance(this) }
    private val repo by lazy { RoutineRepository(db.routineDao(), db.presetDao(), db.branchDao()) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMapBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.toolbar.inflateMenu(R.menu.menu_map)
        binding.toolbar.setOnMenuItemClickListener {
            if (it.itemId == R.id.action_reset_view) { binding.mindMap.resetView(); true } else false
        }

        binding.fabAdd.setOnClickListener { showAddMenu() }

        binding.btnEdit.setOnClickListener {
            startActivity(Intent(this, com.practice.routine.MainActivity::class.java))
        }
        binding.btnStart.setOnClickListener {
            startActivity(Intent(this, com.practice.routine.MainActivity::class.java).apply {
                putExtra(com.practice.routine.MainActivity.EXTRA_START_NOW, true)
            })
        }

        binding.mindMap.onChoiceTap = { choiceItemId ->
            startActivity(Intent(this, BranchEditActivity::class.java).apply {
                putExtra(BranchEditActivity.EXTRA_CHOICE_ITEM_ID, choiceItemId)
            })
        }
        binding.mindMap.onStepTap = { itemId -> editStep(itemId) }
    }

    override fun onResume() {
        super.onResume()
        loadTree()
    }

    private fun loadTree() {
        lifecycleScope.launch {
            val tree = withContext(Dispatchers.IO) { repo.buildTree() }
            binding.mindMap.setTree(tree)
        }
    }

    private fun showAddMenu() {
        AlertDialog.Builder(this)
            .setTitle("추가")
            .setItems(arrayOf("단계 추가", "갈래 추가 (선택 노드)")) { _, which ->
                if (which == 0) showStepDialog(null)
                else addChoice()
            }
            .show()
    }

    private fun addChoice() {
        lifecycleScope.launch {
            val id = withContext(Dispatchers.IO) { repo.addChoice() }
            startActivity(Intent(this@MapActivity, BranchEditActivity::class.java).apply {
                putExtra(BranchEditActivity.EXTRA_CHOICE_ITEM_ID, id)
            })
        }
    }

    private fun editStep(itemId: Int) {
        lifecycleScope.launch {
            val item = withContext(Dispatchers.IO) { db.routineDao().getById(itemId) } ?: return@launch
            showStepDialog(item)
        }
    }

    /** existing == null 이면 최상위에 새 단계 추가, 아니면 해당 단계 수정(+삭제). */
    private fun showStepDialog(existing: RoutineItem?) {
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

        val builder = AlertDialog.Builder(this)
            .setTitle(if (existing == null) "단계 추가" else "단계 수정")
            .setView(dialogView)
            .setPositiveButton("저장") { _, _ ->
                val name = etName.text?.toString()?.trim() ?: ""
                val mins = etMinutes.text?.toString()?.toIntOrNull() ?: 0
                val note = etNote.text?.toString()?.trim()?.ifEmpty { null }
                val sets = (etRepeat.text?.toString()?.toIntOrNull() ?: 1).coerceAtLeast(1)
                when {
                    name.isEmpty() -> Toast.makeText(this, "이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
                    mins <= 0 -> Toast.makeText(this, "시간을 1분 이상 입력해주세요.", Toast.LENGTH_SHORT).show()
                    else -> lifecycleScope.launch {
                        withContext(Dispatchers.IO) {
                            if (existing == null) repo.insertStep(name, mins, note, sets, branchId = null)
                            else repo.update(existing.copy(name = name, durationMinutes = mins, note = note, repeatCount = sets))
                        }
                        loadTree()
                    }
                }
            }
            .setNegativeButton("취소", null)

        if (existing != null) {
            builder.setNeutralButton("삭제") { _, _ -> confirmDeleteStep(existing) }
        }
        builder.show()
    }

    private fun confirmDeleteStep(item: RoutineItem) {
        AlertDialog.Builder(this)
            .setTitle("삭제")
            .setMessage("'${item.name}'을(를) 삭제할까요?")
            .setPositiveButton("삭제") { _, _ ->
                lifecycleScope.launch {
                    withContext(Dispatchers.IO) { repo.deleteItem(item) }
                    loadTree()
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }
}
