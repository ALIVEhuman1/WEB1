package com.practice.routine.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [RoutineItem::class, RoutinePreset::class, PresetItem::class, PracticeLog::class],
    version = 5,
    exportSchema = false
)
abstract class RoutineDatabase : RoomDatabase() {
    abstract fun routineDao(): RoutineDao
    abstract fun presetDao(): PresetDao
    abstract fun practiceLogDao(): PracticeLogDao

    companion object {
        @Volatile private var INSTANCE: RoutineDatabase? = null

        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL(
                    "CREATE TABLE IF NOT EXISTS `routine_presets` " +
                    "(`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                    "`name` TEXT NOT NULL, `createdAt` INTEGER NOT NULL)"
                )
                database.execSQL(
                    "CREATE TABLE IF NOT EXISTS `preset_items` " +
                    "(`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                    "`presetId` INTEGER NOT NULL, `name` TEXT NOT NULL, " +
                    "`durationMinutes` INTEGER NOT NULL, `order` INTEGER NOT NULL)"
                )
            }
        }

        // 단계별 메모(note) 컬럼 추가. nullable 컬럼이라 기존 데이터는 그대로 보존됨.
        private val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE `routine_items` ADD COLUMN `note` TEXT")
                database.execSQL("ALTER TABLE `preset_items` ADD COLUMN `note` TEXT")
            }
        }

        // 단계 반복(세트) 컬럼 추가. NOT NULL DEFAULT 1 이라 기존 항목은 1세트로 채워짐.
        private val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE `routine_items` ADD COLUMN `repeatCount` INTEGER NOT NULL DEFAULT 1")
                database.execSQL("ALTER TABLE `preset_items` ADD COLUMN `repeatCount` INTEGER NOT NULL DEFAULT 1")
            }
        }

        // 연습 기록 테이블 추가. 기존 테이블에는 영향 없음.
        private val MIGRATION_4_5 = object : Migration(4, 5) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL(
                    "CREATE TABLE IF NOT EXISTS `practice_logs` " +
                    "(`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                    "`routineName` TEXT NOT NULL, `completedAt` INTEGER NOT NULL, " +
                    "`durationSeconds` INTEGER NOT NULL, `stepCount` INTEGER NOT NULL)"
                )
            }
        }

        fun getInstance(context: Context): RoutineDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    RoutineDatabase::class.java,
                    "routine_db"
                )
                .addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5)
                .build().also { INSTANCE = it }
            }
    }
}
