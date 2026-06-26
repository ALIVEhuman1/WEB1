package com.practice.routine.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface RoutineDao {
    @Query("SELECT * FROM routine_items ORDER BY `order` ASC")
    fun getAllItems(): Flow<List<RoutineItem>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(item: RoutineItem)

    @Update
    suspend fun update(item: RoutineItem)

    @Delete
    suspend fun delete(item: RoutineItem)

    @Query("UPDATE routine_items SET `order` = :order WHERE id = :id")
    suspend fun updateOrder(id: Int, order: Int)

    @Query("SELECT * FROM routine_items ORDER BY `order` ASC")
    suspend fun getAllItemsOnce(): List<RoutineItem>

    @Query("DELETE FROM routine_items")
    suspend fun deleteAll()
}
