package com.practice.routine.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "practice_logs")
data class PracticeLog(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val routineName: String,
    val completedAt: Long,        // epoch millis
    val durationSeconds: Int,     // 계획 총 시간(분*60*세트의 합)
    val stepCount: Int = 0
)

/** 날짜별 집계(향후 캘린더 히트맵용). day 는 로컬 타임존 기준 'yyyy-MM-dd'. */
data class DailyStat(
    val day: String,
    val count: Int,
    val totalSeconds: Int
)
