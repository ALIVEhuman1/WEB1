package com.practice.routine.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface PresetDao {
    @Query("SELECT * FROM routine_presets ORDER BY createdAt DESC")
    fun getAllPresets(): Flow<List<RoutinePreset>>

    @Insert
    suspend fun insertPreset(preset: RoutinePreset): Long

    @Insert
    suspend fun insertPresetItem(item: PresetItem)

    @Query("SELECT * FROM preset_items WHERE presetId = :presetId ORDER BY `order` ASC")
    suspend fun getPresetItems(presetId: Int): List<PresetItem>

    @Delete
    suspend fun deletePreset(preset: RoutinePreset)

    @Query("DELETE FROM preset_items WHERE presetId = :presetId")
    suspend fun deletePresetItems(presetId: Int)
}
