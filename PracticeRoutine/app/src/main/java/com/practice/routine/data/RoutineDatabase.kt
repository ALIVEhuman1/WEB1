package com.practice.routine.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [RoutineItem::class], version = 1, exportSchema = false)
abstract class RoutineDatabase : RoomDatabase() {
    abstract fun routineDao(): RoutineDao

    companion object {
        @Volatile private var INSTANCE: RoutineDatabase? = null

        fun getInstance(context: Context): RoutineDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    RoutineDatabase::class.java,
                    "routine_db"
                ).build().also { INSTANCE = it }
            }
    }
}
