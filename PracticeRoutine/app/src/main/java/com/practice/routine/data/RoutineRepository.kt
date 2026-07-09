package com.practice.routine.data

import kotlinx.coroutines.flow.Flow

class RoutineRepository(
    private val dao: RoutineDao,
    private val presetDao: PresetDao,
    private val branchDao: BranchDao
) {
    // 최상위 항목(STEP/CHOICE)만 — 메인 리스트
    val topLevelItems: Flow<List<RoutineItem>> = dao.getTopLevelItems()
    val allPresets: Flow<List<RoutinePreset>> = presetDao.getAllPresets()
    val presetSummaries: Flow<List<PresetSummary>> = presetDao.getPresetSummaries()

    fun itemsInBranch(branchId: Int): Flow<List<RoutineItem>> = dao.getItemsInBranch(branchId)
    fun branchesFor(choiceItemId: Int): Flow<List<Branch>> = branchDao.getBranchesFor(choiceItemId)
    suspend fun branchesForOnce(choiceItemId: Int): List<Branch> = branchDao.getBranchesForOnce(choiceItemId)

    // ---- 항목 CRUD (컨테이너 인지) ----
    suspend fun insertStep(name: String, minutes: Int, note: String?, repeatCount: Int, branchId: Int?) {
        val count = if (branchId == null) dao.getTopLevelOnce().size else dao.getItemsInBranchOnce(branchId).size
        dao.insert(
            RoutineItem(
                name = name, durationMinutes = minutes, order = count,
                note = note, repeatCount = repeatCount, type = ItemType.STEP, branchId = branchId
            )
        )
    }

    suspend fun update(item: RoutineItem) = dao.update(item)

    /** CHOICE 삭제 시 하위 Branch + STEP 까지 cascade 삭제. */
    suspend fun deleteItem(item: RoutineItem) {
        if (item.type == ItemType.CHOICE) {
            val branches = branchDao.getBranchesForOnce(item.id)
            branches.forEach { dao.deleteItemsInBranch(it.id) }
            branchDao.deleteBranchesFor(item.id)
        }
        dao.delete(item)
    }

    suspend fun deleteItems(items: List<RoutineItem>) {
        items.forEach { deleteItem(it) }
    }

    /** 최상위에 CHOICE 노드 + 기본 갈래 2개를 만들고 CHOICE id 를 반환. */
    suspend fun addChoice(): Int {
        val count = dao.getTopLevelOnce().size
        val choiceId = dao.insert(
            RoutineItem(name = "선택", durationMinutes = 0, order = count, type = ItemType.CHOICE, branchId = null)
        ).toInt()
        branchDao.insert(Branch(choiceItemId = choiceId, order = 0, label = "갈래 1", isDefault = true))
        branchDao.insert(Branch(choiceItemId = choiceId, order = 1, label = "갈래 2", isDefault = false))
        return choiceId
    }

    /** 같은 컨테이너 안의 순서 저장(최상위 또는 특정 branch). */
    suspend fun reorderContainer(items: List<RoutineItem>) {
        items.forEachIndexed { index, item -> dao.updateOrder(item.id, index) }
    }

    /** STEP 을 다른 컨테이너로 이동(최상위=null 또는 다른 branch). */
    suspend fun moveItemToContainer(item: RoutineItem, newBranchId: Int?) {
        val count = if (newBranchId == null) dao.getTopLevelOnce().size else dao.getItemsInBranchOnce(newBranchId).size
        dao.moveItem(item.id, newBranchId, count)
    }

    // ---- Branch ops ----
    suspend fun addBranch(choiceItemId: Int, label: String): Int {
        val count = branchDao.getBranchesForOnce(choiceItemId).size
        return branchDao.insert(Branch(choiceItemId = choiceItemId, order = count, label = label)).toInt()
    }

    suspend fun renameBranch(branch: Branch, newLabel: String) = branchDao.update(branch.copy(label = newLabel))

    suspend fun deleteBranch(branch: Branch) {
        dao.deleteItemsInBranch(branch.id)
        branchDao.delete(branch)
    }

    suspend fun setDefaultBranch(choiceItemId: Int, branchId: Int) = branchDao.setDefault(choiceItemId, branchId)

    // ---- Tree ----
    suspend fun buildTree(): RoutineTree {
        val top = dao.getTopLevelOnce()
        val nodes = top.map { item ->
            if (item.type == ItemType.CHOICE) {
                val branchNodes = branchDao.getBranchesForOnce(item.id).map { b ->
                    BranchNode(b, dao.getItemsInBranchOnce(b.id))
                }
                RoutineNode.Choice(item, branchNodes)
            } else {
                RoutineNode.Step(item)
            }
        }
        return RoutineTree(nodes)
    }

    // ---- Preset (tree, mirror tables) ----
    suspend fun savePreset(name: String) {
        val tree = buildTree()
        val presetId = presetDao.insertPreset(RoutinePreset(name = name)).toInt()
        tree.nodes.forEachIndexed { index, node ->
            when (node) {
                is RoutineNode.Step -> {
                    val it = node.item
                    presetDao.insertPresetItem(
                        PresetItem(presetId = presetId, name = it.name, durationMinutes = it.durationMinutes,
                            order = index, note = it.note, repeatCount = it.repeatCount, type = ItemType.STEP, branchId = null)
                    )
                }
                is RoutineNode.Choice -> {
                    val pChoiceId = presetDao.insertPresetItem(
                        PresetItem(presetId = presetId, name = node.item.name, durationMinutes = 0,
                            order = index, type = ItemType.CHOICE, branchId = null)
                    ).toInt()
                    node.branches.forEachIndexed { bIndex, bn ->
                        val pBranchId = presetDao.insertPresetBranch(
                            PresetBranch(presetId = presetId, choicePresetItemId = pChoiceId,
                                order = bIndex, label = bn.branch.label, isDefault = bn.branch.isDefault)
                        ).toInt()
                        bn.steps.forEachIndexed { sIndex, s ->
                            presetDao.insertPresetItem(
                                PresetItem(presetId = presetId, name = s.name, durationMinutes = s.durationMinutes,
                                    order = sIndex, note = s.note, repeatCount = s.repeatCount, type = ItemType.STEP, branchId = pBranchId)
                            )
                        }
                    }
                }
            }
        }
    }

    /** 프리셋을 현재 루틴으로 복원(트리 전체 교체). */
    suspend fun loadPreset(presetId: Int) {
        val pItems = presetDao.getPresetItems(presetId)
        val pBranches = presetDao.getPresetBranches(presetId)

        // 현재 트리 전체 삭제
        dao.deleteAll()
        branchDao.deleteAll()

        val topItems = pItems.filter { it.branchId == null }.sortedBy { it.order }
        for (pItem in topItems) {
            if (pItem.type == ItemType.CHOICE) {
                val newChoiceId = dao.insert(
                    RoutineItem(name = pItem.name, durationMinutes = 0, order = pItem.order,
                        type = ItemType.CHOICE, branchId = null)
                ).toInt()
                val branchesOfChoice = pBranches.filter { it.choicePresetItemId == pItem.id }.sortedBy { it.order }
                for (pBranch in branchesOfChoice) {
                    val newBranchId = branchDao.insert(
                        Branch(choiceItemId = newChoiceId, order = pBranch.order,
                            label = pBranch.label, isDefault = pBranch.isDefault)
                    ).toInt()
                    val stepsOfBranch = pItems.filter { it.branchId == pBranch.id }.sortedBy { it.order }
                    for (s in stepsOfBranch) {
                        dao.insert(
                            RoutineItem(name = s.name, durationMinutes = s.durationMinutes, order = s.order,
                                note = s.note, repeatCount = s.repeatCount, type = ItemType.STEP, branchId = newBranchId)
                        )
                    }
                }
            } else {
                dao.insert(
                    RoutineItem(name = pItem.name, durationMinutes = pItem.durationMinutes, order = pItem.order,
                        note = pItem.note, repeatCount = pItem.repeatCount, type = ItemType.STEP, branchId = null)
                )
            }
        }
    }

    suspend fun updatePresetName(preset: RoutinePreset) = presetDao.updatePreset(preset)

    /** 프리셋 편집 화면 저장(현 구조는 단순 STEP 리스트만 지원). */
    suspend fun replacePresetItems(presetId: Int, items: List<RoutineItem>) {
        presetDao.deletePresetItems(presetId)
        presetDao.deletePresetBranches(presetId)
        items.forEachIndexed { index, item ->
            presetDao.insertPresetItem(
                PresetItem(presetId = presetId, name = item.name, durationMinutes = item.durationMinutes,
                    order = index, note = item.note, repeatCount = item.repeatCount, type = ItemType.STEP, branchId = null)
            )
        }
    }

    /** 프리셋 편집 화면 로드용(최상위 STEP 만). */
    suspend fun getPresetTopLevelSteps(presetId: Int): List<PresetItem> =
        presetDao.getPresetItems(presetId).filter { it.branchId == null && it.type == ItemType.STEP }.sortedBy { it.order }

    suspend fun deletePreset(preset: RoutinePreset) {
        presetDao.deletePresetItems(preset.id)
        presetDao.deletePresetBranches(preset.id)
        presetDao.deletePreset(preset)
    }
}
