package com.practice.routine.data

import android.os.Parcelable
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
    val order: Int = 0
) : Parcelable
