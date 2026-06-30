package com.practice.routine.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface PracticeLogDao {

    @Insert
    suspend fun insert(log: PracticeLog)

    @Query("SELECT * FROM practice_logs ORDER BY completedAt DESC")
    fun getAllLogs(): Flow<List<PracticeLog>>

    @Query("SELECT * FROM practice_logs ORDER BY completedAt DESC LIMIT :limit")
    fun getRecentLogs(limit: Int): Flow<List<PracticeLog>>

    @Query("SELECT COUNT(*) FROM practice_logs")
    fun getTotalCount(): Flow<Int>

    @Query("SELECT COALESCE(SUM(durationSeconds), 0) FROM practice_logs")
    fun getTotalSeconds(): Flow<Int>

    @Query("SELECT COUNT(*) FROM practice_logs WHERE completedAt >= :since")
    fun getCountSince(since: Long): Flow<Int>

    @Query("SELECT COALESCE(SUM(durationSeconds), 0) FROM practice_logs WHERE completedAt >= :since")
    fun getSecondsSince(since: Long): Flow<Int>

    // 향후 캘린더 히트맵용: 로컬 타임존 기준 일자별 집계
    @Query(
        "SELECT strftime('%Y-%m-%d', completedAt / 1000, 'unixepoch', 'localtime') AS day, " +
        "COUNT(*) AS count, COALESCE(SUM(durationSeconds), 0) AS totalSeconds " +
        "FROM practice_logs GROUP BY day ORDER BY day DESC"
    )
    fun getDailyStats(): Flow<List<DailyStat>>

    @Delete
    suspend fun delete(log: PracticeLog)

    @Query("DELETE FROM practice_logs")
    suspend fun deleteAll()
}
