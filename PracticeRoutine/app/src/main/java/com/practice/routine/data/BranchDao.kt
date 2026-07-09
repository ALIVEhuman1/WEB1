package com.practice.routine.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface BranchDao {
    @Insert
    suspend fun insert(branch: Branch): Long

    @Update
    suspend fun update(branch: Branch)

    @Delete
    suspend fun delete(branch: Branch)

    @Query("SELECT * FROM branches WHERE choiceItemId = :choiceItemId ORDER BY `order` ASC")
    fun getBranchesFor(choiceItemId: Int): Flow<List<Branch>>

    @Query("SELECT * FROM branches WHERE choiceItemId = :choiceItemId ORDER BY `order` ASC")
    suspend fun getBranchesForOnce(choiceItemId: Int): List<Branch>

    @Query("SELECT * FROM branches ORDER BY `order` ASC")
    suspend fun getAllOnce(): List<Branch>

    @Query("UPDATE branches SET `order` = :order WHERE id = :id")
    suspend fun updateOrder(id: Int, order: Int)

    @Query("UPDATE branches SET isDefault = (id = :branchId) WHERE choiceItemId = :choiceItemId")
    suspend fun setDefault(choiceItemId: Int, branchId: Int)

    @Query("DELETE FROM branches WHERE choiceItemId = :choiceItemId")
    suspend fun deleteBranchesFor(choiceItemId: Int)

    @Query("DELETE FROM branches")
    suspend fun deleteAll()
}
