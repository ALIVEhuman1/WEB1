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
import com.practice.routine.data.*
import com.practice.routine.databinding.ActivityMainBinding
import com.practice.routine.ui.BranchEditActivity
import com.practice.routine.ui.MainListAdapter
import com.practice.routine.ui.MapActivity
import com.practice.routine.ui.PresetListActivity
import com.practice.routine.ui.RoutineViewModel
import com.practice.routine.ui.SessionActivity
import com.practice.routine.ui.SettingsActivity
import com.practice.routine.ui.StatsActivity

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: RoutineViewModel by viewModels()
    private lateinit var adapter: MainListAdapter

    private var isSelectionMode = false
    private var lastTree: RoutineTree? = null

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

        // 지도(홈)에서 '연습 시작'으로 진입한 경우 바로 시작 플로우 실행
        if (savedInstanceState == null && intent.getBooleanExtra(EXTRA_START_NOW, false)) {
            startSession()
        }
    }

    private fun setupDrawer() {
        val drawerWidth = resources.displayMetrics.widthPixels / 3
        val params = binding.navDrawer.layoutParams as DrawerLayout.LayoutParams
        params.width = drawerWidth
        binding.navDrawer.layoutParams = params

        binding.toolbar.setNavigationIcon(R.drawable.ic_menu)
        binding.toolbar.setNavigationOnClickListener {
            if (!isSelectionMode) binding.drawerLayout.openDrawer(GravityCompat.START)
        }

        binding.drawerItemMap.setOnClickListener {
            // 지도가 홈이므로 편집 화면을 닫고 지도로 돌아간다
            binding.drawerLayout.closeDrawer(GravityCompat.START)
            finish()
        }
        binding.drawerItemStats.setOnClickListener {
            binding.drawerLayout.closeDrawer(GravityCompat.START)
            startActivity(Intent(this, StatsActivity::class.java))
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

        binding.drawerLayout.addDrawerListener(object : DrawerLayout.SimpleDrawerListener() {
            override fun onDrawerOpened(drawerView: android.view.View) { backCallback.isEnabled = true }
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
        val hasItems = (viewModel.topLevelItems.value?.isNotEmpty() == true)
        menu.findItem(R.id.action_select_mode)?.isVisible = !isSelectionMode && hasItems
        menu.findItem(R.id.action_delete_selected)?.isVisible = isSelectionMode
        menu.findItem(R.id.action_cancel_select)?.isVisible = isSelectionMode
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_select_mode -> { enterSelectionMode(); true }
            R.id.action_delete_selected -> {
                val selected = adapter.getSelectedItems()
                if (selected.isEmpty()) Toast.makeText(this, "선택된 항목이 없습니다.", Toast.LENGTH_SHORT).show()
                else confirmDeleteMultiple(selected)
                true
            }
            R.id.action_cancel_select -> { exitSelectionMode(); true }
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
        adapter = MainListAdapter(
            onStepEdit = { showAddEditDialog(it) },
            onDelete = { confirmDelete(it) },
            onChoiceTap = { openBranchEditor(it) },
            onReorder = { viewModel.reorder(it) },
            onSelectionChanged = { count ->
                if (!isSelectionMode && count >= 0) {
                    isSelectionMode = true
                    backCallback.isEnabled = true
                    binding.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_LOCKED_CLOSED)
                    binding.toolbar.setNavigationIcon(R.drawable.ic_close)
                    supportActionBar?.title = "0개 선택됨"
                    invalidateOptionsMenu()
                }
                if (count >= 0) supportActionBar?.title = "${count}개 선택됨"
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
        viewModel.topLevelItems.observe(this) { items ->
            binding.tvEmptyHint.visibility =
                if (items.isEmpty()) android.view.View.VISIBLE else android.view.View.GONE
            invalidateOptionsMenu()
            // 트리를 로드해 CHOICE 요약과 총 시간 범위를 갱신
            viewModel.loadTree { tree ->
                lastTree = tree
                val summaries = tree.nodes.filterIsInstance<RoutineNode.Choice>().associate { node ->
                    node.item.id to node.branches.joinToString(" / ") { bn ->
                        "${bn.branch.label}(${bn.totalMinutes()}분)"
                    }
                }
                adapter.submitList(items, summaries)
                updateTotalTime(tree)
            }
        }
    }

    private fun updateTotalTime(tree: RoutineTree) {
        if (tree.nodes.isEmpty()) {
            binding.tvTotalTime.visibility = android.view.View.GONE
            return
        }
        val (min, max) = timeRange(tree)
        binding.tvTotalTime.visibility = android.view.View.VISIBLE
        binding.tvTotalTime.text = if (min == max) "예상 시간 · ${min}분" else "예상 시간 · ${min}~${max}분"
    }

    private fun setupButtons() {
        binding.fabAdd.setOnClickListener { showAddMenu() }
        binding.btnStart.setOnClickListener { startSession() }
    }

    private fun showAddMenu() {
        AlertDialog.Builder(this)
            .setTitle("추가")
            .setItems(arrayOf("단계 추가", "갈래 추가 (선택 노드)")) { _, which ->
                if (which == 0) showAddEditDialog(null)
                else viewModel.addChoice { choiceId -> openBranchEditor(choiceId) }
            }
            .show()
    }

    private fun openBranchEditor(item: RoutineItem) = openBranchEditor(item.id)
    private fun openBranchEditor(choiceItemId: Int) {
        startActivity(Intent(this, BranchEditActivity::class.java).apply {
            putExtra(BranchEditActivity.EXTRA_CHOICE_ITEM_ID, choiceItemId)
        })
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
        val etNote = dialogView.findViewById<TextInputEditText>(R.id.etNote)
        val etRepeat = dialogView.findViewById<TextInputEditText>(R.id.etRepeat)

        if (existing != null) {
            etName.setText(existing.name)
            etMinutes.setText(existing.durationMinutes.toString())
            etNote.setText(existing.note)
            etRepeat.setText(existing.repeatCount.toString())
        }

        MaterialAlertDialogBuilder(this)
            .setTitle(if (existing == null) "루틴 추가" else "루틴 수정")
            .setView(dialogView)
            .setPositiveButton("저장") { _, _ ->
                val name = etName.text?.toString()?.trim() ?: ""
                val mins = etMinutes.text?.toString()?.toIntOrNull() ?: 0
                val note = etNote.text?.toString()?.trim()?.ifEmpty { null }
                val sets = (etRepeat.text?.toString()?.toIntOrNull() ?: 1).coerceAtLeast(1)
                when {
                    name.isEmpty() -> Toast.makeText(this, "이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
                    mins <= 0 -> Toast.makeText(this, "시간을 1분 이상 입력해주세요.", Toast.LENGTH_SHORT).show()
                    existing == null -> viewModel.add(name, mins, note, sets)
                    else -> viewModel.update(existing.copy(name = name, durationMinutes = mins, note = note, repeatCount = sets))
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun confirmDelete(item: RoutineItem) {
        if (item.type == ItemType.CHOICE) {
            val node = lastTree?.nodes?.filterIsInstance<RoutineNode.Choice>()?.firstOrNull { it.item.id == item.id }
            val branchCount = node?.branches?.size ?: 0
            val stepCount = node?.branches?.sumOf { it.steps.size } ?: 0
            AlertDialog.Builder(this)
                .setTitle("선택(갈래) 삭제")
                .setMessage("이 선택과 하위 갈래 ${branchCount}개, 항목 ${stepCount}개가 함께 삭제됩니다. 계속할까요?")
                .setPositiveButton("삭제") { _, _ -> viewModel.delete(item) }
                .setNegativeButton("취소", null)
                .show()
        } else {
            AlertDialog.Builder(this)
                .setTitle("삭제")
                .setMessage("'${item.name}'을(를) 삭제할까요?")
                .setPositiveButton("삭제") { _, _ -> viewModel.delete(item) }
                .setNegativeButton("취소", null)
                .show()
        }
    }

    private fun confirmDeleteMultiple(items: List<RoutineItem>) {
        val hasChoice = items.any { it.type == ItemType.CHOICE }
        val msg = if (hasChoice)
            "선택한 ${items.size}개 항목을 삭제할까요? 갈래가 포함된 경우 하위 단계도 함께 삭제됩니다."
        else
            "선택한 ${items.size}개 항목을 삭제할까요?"
        AlertDialog.Builder(this)
            .setTitle("삭제")
            .setMessage(msg)
            .setPositiveButton("삭제") { _, _ ->
                viewModel.deleteMultiple(items)
                exitSelectionMode()
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun showSavePresetDialog() {
        val currentItems = viewModel.topLevelItems.value
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
            .setView(etName)
            .setPositiveButton("저장") { _, _ ->
                val name = etName.text?.toString()?.trim() ?: ""
                if (name.isEmpty()) Toast.makeText(this, "이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
                else {
                    viewModel.saveCurrentAsPreset(name)
                    Toast.makeText(this, "'$name'으로 저장했습니다.", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    // ---- 시작(사전 선택 → 평탄화 → 요약 → 실행) ----
    private fun startSession() {
        viewModel.loadTree { tree ->
            if (tree.nodes.isEmpty()) {
                Toast.makeText(this, "루틴을 먼저 추가해주세요.", Toast.LENGTH_SHORT).show()
                return@loadTree
            }
            val invalid = validateTree(tree)
            if (invalid != null) {
                AlertDialog.Builder(this)
                    .setTitle("갈래 설정 확인")
                    .setMessage(invalid)
                    .setPositiveButton("확인", null)
                    .show()
                return@loadTree
            }
            val choices = tree.nodes.filterIsInstance<RoutineNode.Choice>()
            if (choices.isEmpty()) {
                launchFlattened(flatten(tree, emptyMap()))
            } else {
                selectChoices(tree, choices, 0, HashMap())
            }
        }
    }

    /** 트리 불변식 검사. 문제 없으면 null, 있으면 안내 메시지. */
    private fun validateTree(tree: RoutineTree): String? {
        for (node in tree.nodes) {
            if (node is RoutineNode.Choice) {
                if (node.branches.size < 2)
                    return "'${node.item.name}' 선택에는 갈래가 2개 이상 필요합니다."
                val empty = node.branches.firstOrNull { it.steps.isEmpty() }
                if (empty != null)
                    return "'${empty.branch.label}' 갈래에 단계가 하나도 없습니다. 각 갈래는 최소 1개의 단계가 필요합니다."
            }
        }
        return null
    }

    private fun selectChoices(
        tree: RoutineTree,
        choices: List<RoutineNode.Choice>,
        index: Int,
        selections: HashMap<Int, Int>
    ) {
        if (index >= choices.size) {
            confirmAndStart(flatten(tree, selections))
            return
        }
        val choice = choices[index]
        val labels = choice.branches.map { "${it.branch.label} (${it.totalMinutes()}분)" }.toTypedArray()
        val defaultIdx = choice.branches.indexOfFirst { it.branch.isDefault }.let { if (it >= 0) it else 0 }
        val picked = intArrayOf(defaultIdx)
        AlertDialog.Builder(this)
            .setTitle("${choice.item.name} — 갈래 선택 (${index + 1}/${choices.size})")
            .setSingleChoiceItems(labels, defaultIdx) { _, which -> picked[0] = which }
            .setPositiveButton("다음") { _, _ ->
                selections[choice.item.id] = choice.branches[picked[0]].branch.id
                selectChoices(tree, choices, index + 1, selections)
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun confirmAndStart(steps: List<RoutineItem>) {
        if (steps.isEmpty()) {
            Toast.makeText(this, "실행할 단계가 없습니다.", Toast.LENGTH_SHORT).show()
            return
        }
        val (totalMin, count) = summarize(steps)
        AlertDialog.Builder(this)
            .setTitle("오늘 루틴")
            .setMessage("총 ${totalMin}분, ${count}단계로 진행합니다.")
            .setPositiveButton("시작") { _, _ -> launchFlattened(steps) }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun launchFlattened(steps: List<RoutineItem>) {
        if (steps.isEmpty()) {
            Toast.makeText(this, "실행할 단계가 없습니다.", Toast.LENGTH_SHORT).show()
            return
        }
        startActivity(Intent(this, SessionActivity::class.java).apply {
            putParcelableArrayListExtra(SessionActivity.EXTRA_ITEMS, ArrayList(steps))
        })
    }

    companion object {
        const val EXTRA_START_NOW = "EXTRA_START_NOW"
    }
}
