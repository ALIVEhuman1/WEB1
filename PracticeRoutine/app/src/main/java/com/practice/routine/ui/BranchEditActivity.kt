package com.practice.routine.ui

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.ItemTouchHelper
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.tabs.TabLayout
import com.google.android.material.textfield.TextInputEditText
import com.practice.routine.R
import com.practice.routine.data.Branch
import com.practice.routine.data.RoutineDatabase
import com.practice.routine.data.RoutineItem
import com.practice.routine.data.RoutineRepository
import com.practice.routine.databinding.ActivityBranchEditBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class BranchEditActivity : AppCompatActivity() {

    private lateinit var binding: ActivityBranchEditBinding
    private val db by lazy { RoutineDatabase.getInstance(this) }
    private val repo by lazy { RoutineRepository(db.routineDao(), db.presetDao(), db.branchDao()) }
    private lateinit var adapter: RoutineAdapter

    private var choiceItemId = -1
    private var branches: List<Branch> = emptyList()
    private var currentBranch: Branch? = null

    private val tabListener = object : TabLayout.OnTabSelectedListener {
        override fun onTabSelected(tab: TabLayout.Tab) {
            branches.getOrNull(tab.position)?.let {
                currentBranch = it
                loadItems()
            }
        }
        override fun onTabUnselected(tab: TabLayout.Tab) {}
        override fun onTabReselected(tab: TabLayout.Tab) {}
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityBranchEditBinding.inflate(layoutInflater)
        setContentView(binding.root)

        choiceItemId = intent.getIntExtra(EXTRA_CHOICE_ITEM_ID, -1)
        if (choiceItemId < 0) { finish(); return }

        binding.toolbar.setNavigationOnClickListener { finish() }
        binding.toolbar.inflateMenu(R.menu.menu_branch_edit)
        binding.toolbar.setOnMenuItemClickListener { onMenu(it.itemId) }

        setupRecyclerView()
        binding.fabAddStep.setOnClickListener { showStepDialog(null) }

        loadBranches(0)
    }

    private fun setupRecyclerView() {
        adapter = RoutineAdapter(
            onEdit = { showStepDialog(it) },
            onDelete = { confirmDeleteStep(it) },
            onReorder = { items -> lifecycleScope.launch { withContext(Dispatchers.IO) { repo.reorderContainer(items) }; loadItems() } },
            selectable = false
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

    private fun loadBranches(selectIndex: Int) {
        lifecycleScope.launch {
            branches = withContext(Dispatchers.IO) { repo.branchesForOnce(choiceItemId) }

            binding.tabLayout.removeOnTabSelectedListener(tabListener)
            binding.tabLayout.removeAllTabs()
            branches.forEach { b ->
                val tab = binding.tabLayout.newTab()
                tab.text = if (b.isDefault) "${b.label} ★" else b.label
                binding.tabLayout.addTab(tab, false)
            }
            binding.tabLayout.addOnTabSelectedListener(tabListener)

            updateDefaultHint()

            if (branches.isEmpty()) {
                currentBranch = null
                adapter.submitList(emptyList())
                binding.tvEmpty.visibility = View.VISIBLE
                return@launch
            }
            val idx = selectIndex.coerceIn(0, branches.size - 1)
            currentBranch = branches[idx]
            binding.tabLayout.selectTab(binding.tabLayout.getTabAt(idx))
            loadItems()
        }
    }

    private fun currentIndex(): Int =
        branches.indexOfFirst { it.id == currentBranch?.id }.coerceAtLeast(0)

    private fun loadItems() {
        val b = currentBranch ?: return
        lifecycleScope.launch {
            val items = withContext(Dispatchers.IO) { db.routineDao().getItemsInBranchOnce(b.id) }
            adapter.submitList(items)
            binding.tvEmpty.visibility = if (items.isEmpty()) View.VISIBLE else View.GONE
        }
    }

    private fun updateDefaultHint() {
        val d = branches.firstOrNull { it.isDefault }
        binding.tvDefaultHint.text =
            if (d != null) "기본 갈래: ${d.label} (시작 시 미리 선택됨)" else "기본 갈래가 지정되지 않았습니다"
    }

    private fun onMenu(id: Int): Boolean = when (id) {
        R.id.action_add_branch -> { promptAddBranch(); true }
        R.id.action_rename_branch -> { promptRenameBranch(); true }
        R.id.action_set_default -> { setDefault(); true }
        R.id.action_delete_branch -> { deleteBranch(); true }
        else -> false
    }

    private fun promptAddBranch() {
        val et = EditText(this).apply {
            hint = "갈래 이름"
            setText("갈래 ${branches.size + 1}")
            setPadding(48, 24, 48, 8)
        }
        AlertDialog.Builder(this)
            .setTitle("갈래 추가")
            .setView(et)
            .setPositiveButton("추가") { _, _ ->
                val label = et.text?.toString()?.trim().orEmpty().ifEmpty { "갈래 ${branches.size + 1}" }
                lifecycleScope.launch {
                    withContext(Dispatchers.IO) { repo.addBranch(choiceItemId, label) }
                    loadBranches(branches.size) // 새 갈래 선택
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun promptRenameBranch() {
        val b = currentBranch ?: return
        val et = EditText(this).apply {
            setText(b.label)
            setPadding(48, 24, 48, 8)
        }
        AlertDialog.Builder(this)
            .setTitle("갈래 이름 변경")
            .setView(et)
            .setPositiveButton("변경") { _, _ ->
                val label = et.text?.toString()?.trim().orEmpty().ifEmpty { b.label }
                val keep = currentIndex()
                lifecycleScope.launch {
                    withContext(Dispatchers.IO) { repo.renameBranch(b, label) }
                    loadBranches(keep)
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun setDefault() {
        val b = currentBranch ?: return
        val keep = currentIndex()
        lifecycleScope.launch {
            withContext(Dispatchers.IO) { repo.setDefaultBranch(choiceItemId, b.id) }
            loadBranches(keep)
        }
    }

    private fun deleteBranch() {
        val b = currentBranch ?: return
        if (branches.size <= 2) {
            Toast.makeText(this, "갈래는 2개 이상 유지해야 합니다.", Toast.LENGTH_SHORT).show()
            return
        }
        AlertDialog.Builder(this)
            .setTitle("갈래 삭제")
            .setMessage("'${b.label}' 갈래와 그 안의 단계가 모두 삭제됩니다. 계속할까요?")
            .setPositiveButton("삭제") { _, _ ->
                lifecycleScope.launch {
                    withContext(Dispatchers.IO) { repo.deleteBranch(b) }
                    loadBranches(0)
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun confirmDeleteStep(item: RoutineItem) {
        AlertDialog.Builder(this)
            .setTitle("삭제")
            .setMessage("'${item.name}'을(를) 삭제할까요?")
            .setPositiveButton("삭제") { _, _ ->
                lifecycleScope.launch {
                    withContext(Dispatchers.IO) { repo.deleteItem(item) }
                    loadItems()
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun showStepDialog(existing: RoutineItem?) {
        val branch = currentBranch ?: return
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
                            if (existing == null) repo.insertStep(name, mins, note, sets, branch.id)
                            else repo.update(existing.copy(name = name, durationMinutes = mins, note = note, repeatCount = sets))
                        }
                        loadItems()
                    }
                }
            }
            .setNegativeButton("취소", null)

        if (existing != null) {
            builder.setNeutralButton("이동") { _, _ -> showMoveDialog(existing) }
        }
        builder.show()
    }

    private fun showMoveDialog(item: RoutineItem) {
        val others = branches.filter { it.id != currentBranch?.id }
        val labels = mutableListOf("최상위로 이동")
        val targets = mutableListOf<Int?>(null)
        others.forEach { labels.add("‘${it.label}’ 갈래로 이동"); targets.add(it.id) }

        AlertDialog.Builder(this)
            .setTitle("항목 이동")
            .setItems(labels.toTypedArray()) { _, which ->
                lifecycleScope.launch {
                    withContext(Dispatchers.IO) { repo.moveItemToContainer(item, targets[which]) }
                    loadItems()
                }
            }
            .show()
    }

    companion object {
        const val EXTRA_CHOICE_ITEM_ID = "EXTRA_CHOICE_ITEM_ID"
    }
}
