package com.practice.routine.data

import android.os.Parcelable
import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey
import kotlinx.parcelize.Parcelize

@Parcelize
@Entity(tableName = "routine_items")
data class RoutineItem(
    @PrimaryKey(autoGenerate = true)
    val id: Int = 0,
    val name: String,
    val durationMinutes: Int,
    // 자기가 속한 컨테이너(최상위 or 특정 branch) 안에서의 순서
    val order: Int = 0,
    val note: String? = null,
    @ColumnInfo(defaultValue = "1")
    val repeatCount: Int = 1,
    // STEP=실제 단계, CHOICE=갈래 선택 노드
    @ColumnInfo(defaultValue = "STEP")
    val type: ItemType = ItemType.STEP,
    // null=최상위, 값=해당 Branch 소속. (branchId != null 인 항목은 CHOICE 가 될 수 없음)
    val branchId: Int? = null
) : Parcelable
