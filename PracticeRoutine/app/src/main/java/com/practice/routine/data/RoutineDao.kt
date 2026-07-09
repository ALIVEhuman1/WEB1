package com.practice.routine.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface RoutineDao {
    // 최상위(branchId IS NULL) 컨테이너의 항목들 — 메인 리스트에 표시
    @Query("SELECT * FROM routine_items WHERE branchId IS NULL ORDER BY `order` ASC")
    fun getTopLevelItems(): Flow<List<RoutineItem>>

    @Query("SELECT * FROM routine_items WHERE branchId IS NULL ORDER BY `order` ASC")
    suspend fun getTopLevelOnce(): List<RoutineItem>

    // 특정 갈래 안의 항목들
    @Query("SELECT * FROM routine_items WHERE branchId = :branchId ORDER BY `order` ASC")
    fun getItemsInBranch(branchId: Int): Flow<List<RoutineItem>>

    @Query("SELECT * FROM routine_items WHERE branchId = :branchId ORDER BY `order` ASC")
    suspend fun getItemsInBranchOnce(branchId: Int): List<RoutineItem>

    // 트리 구성/직렬화용 전체 조회
    @Query("SELECT * FROM routine_items ORDER BY `order` ASC")
    suspend fun getAllItemsOnce(): List<RoutineItem>

    @Query("SELECT * FROM routine_items WHERE id = :id")
    suspend fun getById(id: Int): RoutineItem?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(item: RoutineItem): Long

    @Update
    suspend fun update(item: RoutineItem)

    @Delete
    suspend fun delete(item: RoutineItem)

    @Query("UPDATE routine_items SET `order` = :order WHERE id = :id")
    suspend fun updateOrder(id: Int, order: Int)

    @Query("UPDATE routine_items SET branchId = :branchId, `order` = :order WHERE id = :id")
    suspend fun moveItem(id: Int, branchId: Int?, order: Int)

    @Query("DELETE FROM routine_items WHERE branchId = :branchId")
    suspend fun deleteItemsInBranch(branchId: Int)

    @Query("DELETE FROM routine_items")
    suspend fun deleteAll()
}
