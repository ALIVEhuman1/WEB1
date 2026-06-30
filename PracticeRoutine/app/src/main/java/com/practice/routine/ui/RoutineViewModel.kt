package com.practice.routine.ui

import android.app.Application
import androidx.lifecycle.*
import com.practice.routine.data.*
import kotlinx.coroutines.launch

class RoutineViewModel(app: Application) : AndroidViewModel(app) {
    private val db = RoutineDatabase.getInstance(app)
    private val repo = RoutineRepository(db.routineDao(), db.presetDao())

    val items: LiveData<List<RoutineItem>> = repo.allItems.asLiveData()
    val presets: LiveData<List<RoutinePreset>> = repo.allPresets.asLiveData()
    val presetSummaries: LiveData<List<PresetSummary>> = repo.presetSummaries.asLiveData()

    fun add(name: String, minutes: Int, note: String? = null, repeatCount: Int = 1) = viewModelScope.launch {
        val currentCount = repo.getAllOnce().size
        repo.insert(RoutineItem(name = name, durationMinutes = minutes, order = currentCount, note = note, repeatCount = repeatCount))
    }

    fun update(item: RoutineItem) = viewModelScope.launch { repo.update(item) }

    fun delete(item: RoutineItem) = viewModelScope.launch { repo.delete(item) }

    fun reorder(items: List<RoutineItem>) = viewModelScope.launch { repo.reorder(items) }

    fun saveCurrentAsPreset(name: String) = viewModelScope.launch {
        val currentItems = repo.getAllOnce()
        if (currentItems.isNotEmpty()) {
            repo.savePreset(name, currentItems)
        }
    }

    fun loadPreset(preset: RoutinePreset) = viewModelScope.launch {
        val items = repo.loadPreset(preset.id)
        repo.replaceAllItems(items)
    }

    fun deletePreset(preset: RoutinePreset) = viewModelScope.launch {
        repo.deletePreset(preset)
    }

    fun deleteMultiple(items: List<RoutineItem>) = viewModelScope.launch {
        items.forEach { repo.delete(it) }
    }

    fun deleteMultiplePresets(presets: List<RoutinePreset>) = viewModelScope.launch {
        presets.forEach { repo.deletePreset(it) }
    }
}
