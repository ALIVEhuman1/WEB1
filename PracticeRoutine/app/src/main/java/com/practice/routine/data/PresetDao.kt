package com.practice.routine.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface PresetDao {
    @Query("SELECT p.id, p.name, p.createdAt, COUNT(i.id) as itemCount, COALESCE(SUM(i.durationMinutes), 0) as totalMinutes FROM routine_presets p LEFT JOIN preset_items i ON p.id = i.presetId GROUP BY p.id ORDER BY p.createdAt DESC")
    fun getPresetSummaries(): Flow<List<PresetSummary>>

    @Query("SELECT * FROM routine_presets ORDER BY createdAt DESC")
    fun getAllPresets(): Flow<List<RoutinePreset>>

    @Insert
    suspend fun insertPreset(preset: RoutinePreset): Long

    @Update
    suspend fun updatePreset(preset: RoutinePreset)

    @Query("UPDATE routine_presets SET name = :name WHERE id = :id")
    suspend fun updatePresetNameById(id: Int, name: String)

    @Insert
    suspend fun insertPresetItem(item: PresetItem): Long

    @Query("SELECT * FROM preset_items WHERE presetId = :presetId ORDER BY `order` ASC")
    suspend fun getPresetItems(presetId: Int): List<PresetItem>

    @Insert
    suspend fun insertPresetBranch(branch: PresetBranch): Long

    @Query("SELECT * FROM preset_branches WHERE presetId = :presetId ORDER BY `order` ASC")
    suspend fun getPresetBranches(presetId: Int): List<PresetBranch>

    @Delete
    suspend fun deletePreset(preset: RoutinePreset)

    @Query("DELETE FROM preset_items WHERE presetId = :presetId")
    suspend fun deletePresetItems(presetId: Int)

    @Query("DELETE FROM preset_branches WHERE presetId = :presetId")
    suspend fun deletePresetBranches(presetId: Int)
}
