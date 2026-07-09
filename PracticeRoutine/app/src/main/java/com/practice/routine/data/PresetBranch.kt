package com.practice.routine.data

import androidx.room.Entity
import androidx.room.PrimaryKey

/** 프리셋 안에 저장된 갈래(본 구조의 Branch 미러). */
@Entity(tableName = "preset_branches")
data class PresetBranch(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val presetId: Int,
    val choicePresetItemId: Int,   // 이 갈래가 속한 CHOICE PresetItem 의 id
    val order: Int = 0,
    val label: String,
    val isDefault: Boolean = false
)
