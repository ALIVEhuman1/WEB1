package com.practice.routine.data

import androidx.room.TypeConverter

/** 루틴 항목 종류. STEP=실제 연습 단계, CHOICE=갈래(분기) 선택 노드. */
enum class ItemType { STEP, CHOICE }

class Converters {
    @TypeConverter
    fun fromItemType(type: ItemType): String = type.name

    @TypeConverter
    fun toItemType(value: String): ItemType =
        runCatching { ItemType.valueOf(value) }.getOrDefault(ItemType.STEP)
}
