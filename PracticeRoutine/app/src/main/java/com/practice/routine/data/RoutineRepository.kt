package com.practice.routine.data

import kotlinx.coroutines.flow.Flow

class RoutineRepository(private val dao: RoutineDao) {
    val allItems: Flow<List<RoutineItem>> = dao.getAllItems()

    suspend fun insert(item: RoutineItem) = dao.insert(item)
    suspend fun update(item: RoutineItem) = dao.update(item)
    suspend fun delete(item: RoutineItem) = dao.delete(item)
    suspend fun getAllOnce(): List<RoutineItem> = dao.getAllItemsOnce()

    suspend fun reorder(items: List<RoutineItem>) {
        items.forEachIndexed { index, item ->
            dao.updateOrder(item.id, index)
        }
    }
}
