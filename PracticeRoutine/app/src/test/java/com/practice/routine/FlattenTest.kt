package com.practice.routine

import com.practice.routine.data.Branch
import com.practice.routine.data.BranchNode
import com.practice.routine.data.ItemType
import com.practice.routine.data.RoutineItem
import com.practice.routine.data.RoutineNode
import com.practice.routine.data.RoutineTree
import com.practice.routine.data.flatten
import com.practice.routine.data.timeRange
import org.junit.Assert.assertEquals
import org.junit.Test

class FlattenTest {

    private fun step(id: Int, name: String, min: Int, repeat: Int = 1) =
        RoutineItem(id = id, name = name, durationMinutes = min, repeatCount = repeat, type = ItemType.STEP)

    private fun choice(id: Int) =
        RoutineItem(id = id, name = "선택", durationMinutes = 0, type = ItemType.CHOICE)

    // 최상위: [A(5)] [CHOICE( 갈래1:[B(10)] 기본, 갈래2:[C(15), D(5)] )] [E(5)]
    private fun sampleTree(): RoutineTree {
        val b1 = Branch(id = 1, choiceItemId = 100, order = 0, label = "짧게", isDefault = true)
        val b2 = Branch(id = 2, choiceItemId = 100, order = 1, label = "풀버전", isDefault = false)
        return RoutineTree(
            listOf(
                RoutineNode.Step(step(1, "A", 5)),
                RoutineNode.Choice(
                    choice(100),
                    listOf(
                        BranchNode(b1, listOf(step(10, "B", 10))),
                        BranchNode(b2, listOf(step(11, "C", 15), step(12, "D", 5)))
                    )
                ),
                RoutineNode.Step(step(2, "E", 5))
            )
        )
    }

    @Test
    fun flatten_usesDefaultBranch_whenNoSelection() {
        val steps = flatten(sampleTree(), emptyMap())
        assertEquals(listOf("A", "B", "E"), steps.map { it.name })
        // 모두 STEP, branchId=null, order 재부여
        assertEquals(listOf(0, 1, 2), steps.map { it.order })
        assertEquals(true, steps.all { it.type == ItemType.STEP && it.branchId == null })
    }

    @Test
    fun flatten_usesSelectedBranch() {
        val steps = flatten(sampleTree(), mapOf(100 to 2))
        assertEquals(listOf("A", "C", "D", "E"), steps.map { it.name })
        assertEquals(listOf(0, 1, 2, 3), steps.map { it.order })
    }

    @Test
    fun flatten_fallsBackToFirstBranch_whenSelectionInvalid() {
        // 기본 갈래가 없다고 가정: 첫 갈래(짧게) 사용
        val tree = RoutineTree(
            listOf(
                RoutineNode.Choice(
                    choice(100),
                    listOf(
                        BranchNode(Branch(id = 1, choiceItemId = 100, order = 0, label = "짧게", isDefault = false), listOf(step(10, "B", 10))),
                        BranchNode(Branch(id = 2, choiceItemId = 100, order = 1, label = "풀", isDefault = false), listOf(step(11, "C", 15)))
                    )
                )
            )
        )
        val steps = flatten(tree, mapOf(100 to 999)) // 존재하지 않는 branchId
        assertEquals(listOf("B"), steps.map { it.name })
    }

    @Test
    fun timeRange_spansMinAndMaxBranch() {
        // A(5) + [10 .. 20] + E(5) = 20 .. 30
        val (min, max) = timeRange(sampleTree())
        assertEquals(20, min)
        assertEquals(30, max)
    }

    @Test
    fun timeRange_singleValue_whenNoChoice() {
        val tree = RoutineTree(listOf(RoutineNode.Step(step(1, "A", 5, repeat = 3)), RoutineNode.Step(step(2, "B", 10))))
        val (min, max) = timeRange(tree)
        assertEquals(25, min) // 5*3 + 10
        assertEquals(25, max)
    }
}
