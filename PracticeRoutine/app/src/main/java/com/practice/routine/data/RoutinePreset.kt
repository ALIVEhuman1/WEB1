package com.practice.routine.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "routine_presets")
data class RoutinePreset(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val name: String,
    val createdAt: Long = System.currentTimeMillis()
)
