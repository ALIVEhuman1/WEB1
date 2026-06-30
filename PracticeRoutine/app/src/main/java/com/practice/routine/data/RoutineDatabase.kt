package com.practice.routine.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [RoutineItem::class, RoutinePreset::class, PresetItem::class],
    version = 3,
    exportSchema = false
)
abstract class RoutineDatabase : RoomDatabase() {
    abstract fun routineDao(): RoutineDao
    abstract fun presetDao(): PresetDao

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

        fun getInstance(context: Context): RoutineDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    RoutineDatabase::class.java,
                    "routine_db"
                )
                .addMigrations(MIGRATION_1_2, MIGRATION_2_3)
                .build().also { INSTANCE = it }
            }
    }
}
