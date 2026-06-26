package com.practice.routine

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.LayoutInflater
import android.view.Menu
import android.view.MenuItem
import android.widget.EditText
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.ItemTouchHelper
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.textfield.TextInputEditText
import com.practice.routine.data.RoutineItem
import com.practice.routine.data.RoutinePreset
import com.practice.routine.databinding.ActivityMainBinding
import com.practice.routine.ui.RoutineAdapter
import com.practice.routine.ui.RoutineViewModel
import com.practice.routine.ui.SessionActivity

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: RoutineViewModel by viewModels()
    private lateinit var adapter: RoutineAdapter

    private val notifPermLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            Toast.makeText(this, "알림 권한이 없으면 타이머 알림을 받을 수 없습니다.", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbar)

        requestNotificationPermission()
        setupRecyclerView()
        setupObservers()
        setupButtons()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_main, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_save_preset -> {
                showSavePresetDialog()
                true
            }
            R.id.action_load_preset -> {
                val presets = viewModel.presets.value ?: emptyList()
                showLoadPresetDialog(presets)
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                notifPermLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun setupRecyclerView() {
        adapter = RoutineAdapter(
            onEdit = { showAddEditDialog(it) },
            onDelete = { confirmDelete(it) },
            onReorder = { viewModel.reorder(it) }
        )
        binding.rvRoutines.layoutManager = LinearLayoutManager(this)
        binding.rvRoutines.adapter = adapter

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
        touchHelper.attachToRecyclerView(binding.rvRoutines)
    }

    private fun setupObservers() {
        viewModel.items.observe(this) { items ->
            adapter.submitList(items)
            binding.tvEmptyHint.visibility =
                if (items.isEmpty()) android.view.View.VISIBLE else android.view.View.GONE
        }
    }

    private fun setupButtons() {
        binding.fabAdd.setOnClickListener { showAddEditDialog(null) }
        binding.btnStart.setOnClickListener { startSession() }
    }

    private fun showAddEditDialog(existing: RoutineItem?) {
        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_add_routine, null)
        val etName = dialogView.findViewById<TextInputEditText>(R.id.etRoutineName)
        val etMinutes = dialogView.findViewById<TextInputEditText>(R.id.etMinutes)

        if (existing != null) {
            etName.setText(existing.name)
            etMinutes.setText(existing.durationMinutes.toString())
        }

        MaterialAlertDialogBuilder(this)
            .setTitle(if (existing == null) "루틴 추가" else "루틴 수정")
            .setView(dialogView)
            .setPositiveButton("저장") { _, _ ->
                val name = etName.text?.toString()?.trim() ?: ""
                val mins = etMinutes.text?.toString()?.toIntOrNull() ?: 0
                when {
                    name.isEmpty() -> Toast.makeText(this, "이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
                    mins <= 0 -> Toast.makeText(this, "시간을 1분 이상 입력해주세요.", Toast.LENGTH_SHORT).show()
                    existing == null -> viewModel.add(name, mins)
                    else -> viewModel.update(existing.copy(name = name, durationMinutes = mins))
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun confirmDelete(item: RoutineItem) {
        AlertDialog.Builder(this)
            .setTitle("삭제")
            .setMessage("'${item.name}'을(를) 삭제할까요?")
            .setPositiveButton("삭제") { _, _ -> viewModel.delete(item) }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun showSavePresetDialog() {
        val currentItems = viewModel.items.value
        if (currentItems.isNullOrEmpty()) {
            Toast.makeText(this, "저장할 루틴이 없습니다. 루틴을 먼저 추가해주세요.", Toast.LENGTH_SHORT).show()
            return
        }

        val etName = EditText(this).apply {
            hint = "루틴 이름 (예: 아침 연습)"
            setPadding(48, 24, 48, 8)
        }

        AlertDialog.Builder(this)
            .setTitle("루틴 저장하기")
            .setMessage("현재 루틴 ${currentItems.size}개를 저장합니다.")
            .setView(etName)
            .setPositiveButton("저장") { _, _ ->
                val name = etName.text?.toString()?.trim() ?: ""
                if (name.isEmpty()) {
                    Toast.makeText(this, "이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
                } else {
                    viewModel.saveCurrentAsPreset(name)
                    Toast.makeText(this, "'$name'으로 저장했습니다.", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun showLoadPresetDialog(presets: List<RoutinePreset>) {
        if (presets.isEmpty()) {
            Toast.makeText(this, "저장된 루틴이 없습니다.", Toast.LENGTH_SHORT).show()
            return
        }

        val names = presets.map { it.name }.toTypedArray()

        AlertDialog.Builder(this)
            .setTitle("루틴 불러오기")
            .setItems(names) { _, which ->
                val preset = presets[which]
                AlertDialog.Builder(this)
                    .setTitle("'${preset.name}' 불러오기")
                    .setMessage("현재 루틴 목록이 이 루틴으로 교체됩니다. 계속할까요?")
                    .setPositiveButton("불러오기") { _, _ ->
                        viewModel.loadPreset(preset)
                        Toast.makeText(this, "'${preset.name}'을 불러왔습니다.", Toast.LENGTH_SHORT).show()
                    }
                    .setNegativeButton("취소", null)
                    .show()
            }
            .setNeutralButton("삭제 관리") { _, _ ->
                showDeletePresetDialog(presets)
            }
            .setNegativeButton("닫기", null)
            .show()
    }

    private fun showDeletePresetDialog(presets: List<RoutinePreset>) {
        val names = presets.map { it.name }.toTypedArray()

        AlertDialog.Builder(this)
            .setTitle("저장된 루틴 삭제")
            .setItems(names) { _, which ->
                val preset = presets[which]
                AlertDialog.Builder(this)
                    .setTitle("삭제")
                    .setMessage("'${preset.name}'을(를) 삭제할까요?")
                    .setPositiveButton("삭제") { _, _ ->
                        viewModel.deletePreset(preset)
                        Toast.makeText(this, "삭제했습니다.", Toast.LENGTH_SHORT).show()
                    }
                    .setNegativeButton("취소", null)
                    .show()
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun startSession() {
        val items = viewModel.items.value
        if (items.isNullOrEmpty()) {
            Toast.makeText(this, "루틴을 먼저 추가해주세요.", Toast.LENGTH_SHORT).show()
            return
        }
        val intent = Intent(this, SessionActivity::class.java).apply {
            putParcelableArrayListExtra(SessionActivity.EXTRA_ITEMS, ArrayList(items))
        }
        startActivity(intent)
    }
}
