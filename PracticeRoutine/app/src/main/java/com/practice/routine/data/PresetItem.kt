package com.practice.routine.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "preset_items")
data class PresetItem(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val presetId: Int,
    val name: String,
    val durationMinutes: Int,
    val order: Int = 0
)
