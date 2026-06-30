package com.practice.routine.ui

import android.app.Application
import androidx.lifecycle.*
import com.practice.routine.data.PracticeLog
import com.practice.routine.data.RoutineDatabase
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.WeekFields
import java.util.Locale

class StatsViewModel(app: Application) : AndroidViewModel(app) {
    private val dao = RoutineDatabase.getInstance(app).practiceLogDao()

    // 로컬 타임존 기준 '이번 주' 시작 epoch millis
    private val weekStart: Long = run {
        val zone = ZoneId.systemDefault()
        val firstDay = WeekFields.of(Locale.getDefault()).firstDayOfWeek
        val today = LocalDate.now(zone)
        val daysBack = (today.dayOfWeek.value - firstDay.value + 7) % 7
        today.minusDays(daysBack.toLong()).atStartOfDay(zone).toInstant().toEpochMilli()
    }

    val recentLogs: LiveData<List<PracticeLog>> = dao.getRecentLogs(100).asLiveData()
    val totalCount: LiveData<Int> = dao.getTotalCount().asLiveData()
    val totalSeconds: LiveData<Int> = dao.getTotalSeconds().asLiveData()
    val weekCount: LiveData<Int> = dao.getCountSince(weekStart).asLiveData()
    val weekSeconds: LiveData<Int> = dao.getSecondsSince(weekStart).asLiveData()

    fun delete(log: PracticeLog) = viewModelScope.launch { dao.delete(log) }
    fun deleteAll() = viewModelScope.launch { dao.deleteAll() }
}
