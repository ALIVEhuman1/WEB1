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
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.GravityCompat
import androidx.drawerlayout.widget.DrawerLayout
import androidx.recyclerview.widget.ItemTouchHelper
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.textfield.TextInputEditText
import com.practice.routine.data.RoutineItem
import com.practice.routine.databinding.ActivityMainBinding
import com.practice.routine.ui.PresetListActivity
import com.practice.routine.ui.RoutineAdapter
import com.practice.routine.ui.RoutineViewModel
import com.practice.routine.ui.SessionActivity
import com.practice.routine.ui.SettingsActivity

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: RoutineViewModel by viewModels()
    private lateinit var adapter: RoutineAdapter

    private var isSelectionMode = false
    private val backCallback = object : OnBackPressedCallback(false) {
        override fun handleOnBackPressed() {
            if (binding.drawerLayout.isDrawerOpen(GravityCompat.START)) {
                binding.drawerLayout.closeDrawer(GravityCompat.START)
            } else {
                exitSelectionMode()
            }
        }
    }

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
        onBackPressedDispatcher.addCallback(this, backCallback)

        requestNotificationPermission()
        setupDrawer()
        setupRecyclerView()
        setupObservers()
        setupButtons()
    }

    private fun setupDrawer() {
        // Set drawer width to 1/3 of screen width
        val drawerWidth = resources.displayMetrics.widthPixels / 3
        val params = binding.navDrawer.layoutParams as DrawerLayout.LayoutParams
        params.width = drawerWidth
        binding.navDrawer.layoutParams = params

        // Hamburger icon opens drawer
        binding.toolbar.setNavigationOnClickListener {
            if (!isSelectionMode) {
                binding.drawerLayout.openDrawer(GravityCompat.START)
            }
        }

        // Close drawer on background touch is default DrawerLayout behavior

        // Drawer item click handlers
        binding.drawerItemSelect.setOnClickListener {
            binding.drawerLayout.closeDrawer(GravityCompat.START)
            enterSelectionMode()
        }
        binding.drawerItemSave.setOnClickListener {
            binding.drawerLayout.closeDrawer(GravityCompat.START)
            showSavePresetDialog()
        }
        binding.drawerItemLoad.setOnClickListener {
            binding.drawerLayout.closeDrawer(GravityCompat.START)
            startActivity(Intent(this, PresetListActivity::class.java))
        }
        binding.drawerItemSettings.setOnClickListener {
            binding.drawerLayout.closeDrawer(GravityCompat.START)
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        // Back press closes drawer if open
        binding.drawerLayout.addDrawerListener(object : DrawerLayout.SimpleDrawerListener() {
            override fun onDrawerOpened(drawerView: android.view.View) {
                backCallback.isEnabled = true
            }
            override fun onDrawerClosed(drawerView: android.view.View) {
                if (!isSelectionMode) backCallback.isEnabled = false
            }
        })
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_main, menu)
        return true
    }

    override fun onPrepareOptionsMenu(menu: Menu): Boolean {
        menu.findItem(R.id.action_delete_selected)?.isVisible = isSelectionMode
        menu.findItem(R.id.action_cancel_select)?.isVisible = isSelectionMode
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_delete_selected -> {
                val selected = adapter.getSelectedItems()
                if (selected.isEmpty()) {
                    Toast.makeText(this, "선택된 항목이 없습니다.", Toast.LENGTH_SHORT).show()
                } else {
                    confirmDeleteMultiple(selected)
                }
                true
            }
            R.id.action_cancel_select -> {
                exitSelectionMode()
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
            onReorder = { viewModel.reorder(it) },
            onSelectionChanged = { count ->
                if (!isSelectionMode && count >= 0) {
                    // Long-press triggered selection mode from adapter
                    isSelectionMode = true
                    backCallback.isEnabled = true
                    binding.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_LOCKED_CLOSED)
                    binding.toolbar.setNavigationIcon(R.drawable.ic_close)
                    supportActionBar?.title = "0개 선택됨"
                    invalidateOptionsMenu()
                }
                if (count >= 0) {
                    supportActionBar?.title = "${count}개 선택됨"
                }
            }
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

    private fun enterSelectionMode() {
        isSelectionMode = true
        backCallback.isEnabled = true
        adapter.enterSelectionMode()
        binding.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_LOCKED_CLOSED)
        binding.toolbar.setNavigationIcon(R.drawable.ic_close)
        supportActionBar?.title = "0개 선택됨"
        invalidateOptionsMenu()
    }

    private fun exitSelectionMode() {
        isSelectionMode = false
        backCallback.isEnabled = false
        adapter.exitSelectionMode()
        binding.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_UNLOCKED)
        binding.toolbar.setNavigationIcon(R.drawable.ic_menu)
        supportActionBar?.title = getString(R.string.app_name)
        invalidateOptionsMenu()
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

    private fun confirmDeleteMultiple(items: List<RoutineItem>) {
        AlertDialog.Builder(this)
            .setTitle("삭제")
            .setMessage("선택한 ${items.size}개 항목을 삭제할까요?")
            .setPositiveButton("삭제") { _, _ ->
                viewModel.deleteMultiple(items)
                exitSelectionMode()
            }
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
