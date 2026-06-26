package com.practice.routine.ui

import android.app.Application
import androidx.lifecycle.*
import com.practice.routine.data.*
import kotlinx.coroutines.launch

class RoutineViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = RoutineRepository(
        RoutineDatabase.getInstance(app).routineDao()
    )

    val items: LiveData<List<RoutineItem>> = repo.allItems.asLiveData()

    fun add(name: String, minutes: Int) = viewModelScope.launch {
        val currentCount = repo.getAllOnce().size
        repo.insert(RoutineItem(name = name, durationMinutes = minutes, order = currentCount))
    }

    fun update(item: RoutineItem) = viewModelScope.launch { repo.update(item) }

    fun delete(item: RoutineItem) = viewModelScope.launch { repo.delete(item) }

    fun reorder(items: List<RoutineItem>) = viewModelScope.launch { repo.reorder(items) }
}
