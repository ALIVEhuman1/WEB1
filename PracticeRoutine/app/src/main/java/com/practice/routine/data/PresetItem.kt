package com.practice.routine.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "preset_items")
data class PresetItem(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val presetId: Int,
    val name: String,
    val durationMinutes: Int,
    val order: Int = 0,
    val note: String? = null,
    @ColumnInfo(defaultValue = "1")
    val repeatCount: Int = 1,
    @ColumnInfo(defaultValue = "STEP")
    val type: ItemType = ItemType.STEP,
    // null=최상위, 값=이 프리셋 안의 PresetBranch.id (프리셋 로컬)
    val branchId: Int? = null
)
