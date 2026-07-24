package com.practice.routine.ui

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import com.practice.routine.R
import com.practice.routine.data.RoutineDatabase
import com.practice.routine.data.RoutineItem
import com.practice.routine.data.RoutineNode
import com.practice.routine.data.RoutineRepository
import com.practice.routine.data.RoutineTree
import com.practice.routine.data.flatten
import com.practice.routine.data.summarize
import com.practice.routine.data.totalMinutes
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

        // 좌상단 메뉴 버튼 → 저장/불러오기/기록/설정
        binding.toolbar.setNavigationOnClickListener { showMainMenu() }
        binding.toolbar.inflateMenu(R.menu.menu_map)
        binding.toolbar.setOnMenuItemClickListener {
            if (it.itemId == R.id.action_reset_view) { binding.mindMap.resetView(); true } else false
        }

        binding.fabAdd.setOnClickListener { showStepDialog(null) } // ＋ = 단계 추가
        binding.btnStart.setOnClickListener { startSession() }

        binding.mindMap.onChoiceTap = { choiceItemId -> openBranchEditor(choiceItemId) }
        binding.mindMap.onStepTap = { itemId -> editStep(itemId) }
        binding.mindMap.onStepLongPress = { itemId -> showStepContextMenu(itemId) }
        binding.mindMap.onChoiceLongPress = { choiceItemId -> showChoiceContextMenu(choiceItemId) }
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

    private fun openBranchEditor(choiceItemId: Int) {
        startActivity(Intent(this, BranchEditActivity::class.java).apply {
            putExtra(BranchEditActivity.EXTRA_CHOICE_ITEM_ID, choiceItemId)
        })
    }

    // ---- 좌상단 메뉴 ----
    private fun showMainMenu() {
        AlertDialog.Builder(this)
            .setTitle("메뉴")
            .setItems(arrayOf("루틴 저장하기", "불러오기", "연습 기록", "설정")) { _, which ->
                when (which) {
                    0 -> showSavePresetDialog()
                    1 -> startActivity(Intent(this, PresetListActivity::class.java))
                    2 -> startActivity(Intent(this, StatsActivity::class.java))
                    3 -> startActivity(Intent(this, SettingsActivity::class.java))
                }
            }
            .show()
    }

    private fun showSavePresetDialog() {
        lifecycleScope.launch {
            val empty = withContext(Dispatchers.IO) { db.routineDao().getTopLevelOnce().isEmpty() }
            if (empty) {
                Toast.makeText(this@MapActivity, "저장할 루틴이 없습니다. 먼저 추가해주세요.", Toast.LENGTH_SHORT).show()
                return@launch
            }
            val etName = EditText(this@MapActivity).apply {
                hint = "루틴 이름 (예: 아침 연습)"
                setPadding(48, 24, 48, 8)
            }
            AlertDialog.Builder(this@MapActivity)
                .setTitle("루틴 저장하기")
                .setView(etName)
                .setPositiveButton("저장") { _, _ ->
                    val name = etName.text?.toString()?.trim() ?: ""
                    if (name.isEmpty()) {
                        Toast.makeText(this@MapActivity, "이름을 입력해주세요.", Toast.LENGTH_SHORT).show()
                    } else {
                        lifecycleScope.launch {
                            withContext(Dispatchers.IO) { repo.savePreset(name) }
                            Toast.makeText(this@MapActivity, "'$name'으로 저장했습니다.", Toast.LENGTH_SHORT).show()
                        }
                    }
                }
                .setNegativeButton("취소", null)
                .show()
        }
    }

    private fun addChoice() {
        lifecycleScope.launch {
            val id = withContext(Dispatchers.IO) { repo.addChoice() }
            openBranchEditor(id)
        }
    }

    // ---- 노드 롱프레스 컨텍스트 메뉴 ----
    private fun showStepContextMenu(itemId: Int) {
        AlertDialog.Builder(this)
            .setItems(arrayOf("편집", "삭제", "갈래 추가")) { _, which ->
                when (which) {
                    0 -> editStep(itemId)
                    1 -> deleteStepById(itemId)
                    2 -> addChoice()
                }
            }
            .show()
    }

    private fun showChoiceContextMenu(choiceItemId: Int) {
        AlertDialog.Builder(this)
            .setItems(arrayOf("갈래 편집", "삭제", "갈래 추가")) { _, which ->
                when (which) {
                    0 -> openBranchEditor(choiceItemId)
                    1 -> deleteChoiceById(choiceItemId)
                    2 -> addChoice()
                }
            }
            .show()
    }

    private fun editStep(itemId: Int) {
        lifecycleScope.launch {
            val item = withContext(Dispatchers.IO) { db.routineDao().getById(itemId) } ?: return@launch
            showStepDialog(item)
        }
    }

    private fun deleteStepById(itemId: Int) {
        lifecycleScope.launch {
            val item = withContext(Dispatchers.IO) { db.routineDao().getById(itemId) } ?: return@launch
            confirmDeleteStep(item)
        }
    }

    private fun deleteChoiceById(choiceItemId: Int) {
        lifecycleScope.launch {
            val item = withContext(Dispatchers.IO) { db.routineDao().getById(choiceItemId) } ?: return@launch
            val branches = withContext(Dispatchers.IO) { repo.branchesForOnce(choiceItemId) }
            val stepCount = withContext(Dispatchers.IO) {
                branches.sumOf { db.routineDao().getItemsInBranchOnce(it.id).size }
            }
            AlertDialog.Builder(this@MapActivity)
                .setTitle("선택(갈래) 삭제")
                .setMessage("이 선택과 하위 갈래 ${branches.size}개, 항목 ${stepCount}개가 함께 삭제됩니다. 계속할까요?")
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

    /** existing == null 이면 최상위에 새 단계 추가, 아니면 해당 단계 수정. */
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

    // ---- 시작 (사전 선택 → 평탄화 → 요약 → 실행) ----
    private fun startSession() {
        lifecycleScope.launch {
            val tree = withContext(Dispatchers.IO) { repo.buildTree() }
            if (tree.nodes.isEmpty()) {
                Toast.makeText(this@MapActivity, "루틴을 먼저 추가해주세요.", Toast.LENGTH_SHORT).show()
                return@launch
            }
            val invalid = validateTree(tree)
            if (invalid != null) {
                AlertDialog.Builder(this@MapActivity)
                    .setTitle("갈래 설정 확인").setMessage(invalid)
                    .setPositiveButton("확인", null).show()
                return@launch
            }
            val choices = tree.nodes.filterIsInstance<RoutineNode.Choice>()
            if (choices.isEmpty()) launchFlattened(flatten(tree, emptyMap()))
            else selectChoices(tree, choices, 0, HashMap())
        }
    }

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
        if (index >= choices.size) { confirmAndStart(flatten(tree, selections)); return }
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
        if (steps.isEmpty()) { Toast.makeText(this, "실행할 단계가 없습니다.", Toast.LENGTH_SHORT).show(); return }
        val (totalMin, count) = summarize(steps)
        AlertDialog.Builder(this)
            .setTitle("오늘 루틴")
            .setMessage("총 ${totalMin}분, ${count}단계로 진행합니다.")
            .setPositiveButton("시작") { _, _ -> launchFlattened(steps) }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun launchFlattened(steps: List<RoutineItem>) {
        if (steps.isEmpty()) { Toast.makeText(this, "실행할 단계가 없습니다.", Toast.LENGTH_SHORT).show(); return }
        startActivity(Intent(this, SessionActivity::class.java).apply {
            putParcelableArrayListExtra(SessionActivity.EXTRA_ITEMS, ArrayList(steps))
        })
    }
}
