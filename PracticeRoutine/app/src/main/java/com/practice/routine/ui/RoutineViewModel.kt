package com.practice.routine.ui

import android.app.Application
import androidx.lifecycle.*
import com.practice.routine.data.*
import kotlinx.coroutines.launch

class RoutineViewModel(app: Application) : AndroidViewModel(app) {
    private val db = RoutineDatabase.getInstance(app)
    private val repo = RoutineRepository(db.routineDao(), db.presetDao(), db.branchDao())

    // 최상위 항목(STEP/CHOICE)
    val topLevelItems: LiveData<List<RoutineItem>> = repo.topLevelItems.asLiveData()
    val presetSummaries: LiveData<List<PresetSummary>> = repo.presetSummaries.asLiveData()

    fun add(name: String, minutes: Int, note: String? = null, repeatCount: Int = 1) = viewModelScope.launch {
        repo.insertStep(name, minutes, note, repeatCount, branchId = null)
    }

    fun update(item: RoutineItem) = viewModelScope.launch { repo.update(item) }

    fun delete(item: RoutineItem) = viewModelScope.launch { repo.deleteItem(item) }

    fun deleteMultiple(items: List<RoutineItem>) = viewModelScope.launch { repo.deleteItems(items) }

    fun reorder(items: List<RoutineItem>) = viewModelScope.launch { repo.reorderContainer(items) }

    fun addChoice(onCreated: (Int) -> Unit) = viewModelScope.launch {
        val id = repo.addChoice()
        onCreated(id)
    }

    fun saveCurrentAsPreset(name: String) = viewModelScope.launch { repo.savePreset(name) }

    fun loadPreset(preset: RoutinePreset) = viewModelScope.launch { repo.loadPreset(preset.id) }

    fun deletePreset(preset: RoutinePreset) = viewModelScope.launch { repo.deletePreset(preset) }

    fun deleteMultiplePresets(presets: List<RoutinePreset>) = viewModelScope.launch {
        presets.forEach { repo.deletePreset(it) }
    }

    /** 현재 루틴 트리를 비동기로 로드(메인 리스트 렌더/시간범위/시작 선택에 사용). */
    fun loadTree(onLoaded: (RoutineTree) -> Unit) = viewModelScope.launch {
        onLoaded(repo.buildTree())
    }
}
