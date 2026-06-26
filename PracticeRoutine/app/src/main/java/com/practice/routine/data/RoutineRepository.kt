package com.practice.routine.data

import kotlinx.coroutines.flow.Flow

class RoutineRepository(private val dao: RoutineDao, private val presetDao: PresetDao) {
    val allItems: Flow<List<RoutineItem>> = dao.getAllItems()
    val allPresets: Flow<List<RoutinePreset>> = presetDao.getAllPresets()

    suspend fun insert(item: RoutineItem) = dao.insert(item)
    suspend fun update(item: RoutineItem) = dao.update(item)
    suspend fun delete(item: RoutineItem) = dao.delete(item)
    suspend fun getAllOnce(): List<RoutineItem> = dao.getAllItemsOnce()

    suspend fun reorder(items: List<RoutineItem>) {
        items.forEachIndexed { index, item ->
            dao.updateOrder(item.id, index)
        }
    }

    suspend fun savePreset(name: String, currentItems: List<RoutineItem>) {
        val presetId = presetDao.insertPreset(RoutinePreset(name = name)).toInt()
        currentItems.forEachIndexed { index, item ->
            presetDao.insertPresetItem(
                PresetItem(presetId = presetId, name = item.name, durationMinutes = item.durationMinutes, order = index)
            )
        }
    }

    suspend fun loadPreset(presetId: Int): List<RoutineItem> =
        presetDao.getPresetItems(presetId).mapIndexed { index, it ->
            RoutineItem(name = it.name, durationMinutes = it.durationMinutes, order = index)
        }

    suspend fun replaceAllItems(newItems: List<RoutineItem>) {
        dao.deleteAll()
        newItems.forEach { dao.insert(it) }
    }

    suspend fun deletePreset(preset: RoutinePreset) {
        presetDao.deletePresetItems(preset.id)
        presetDao.deletePreset(preset)
    }
}
