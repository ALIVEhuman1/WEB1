package com.practice.routine.data

import androidx.room.Entity
import androidx.room.PrimaryKey

/** CHOICE(갈래 선택 노드)에 속한 하나의 갈래. 갈래 안에는 STEP 항목들이 들어간다. */
@Entity(tableName = "branches")
data class Branch(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val choiceItemId: Int,          // 이 갈래가 속한 CHOICE 항목(RoutineItem)의 id
    val order: Int = 0,
    val label: String,
    val isDefault: Boolean = false
)
