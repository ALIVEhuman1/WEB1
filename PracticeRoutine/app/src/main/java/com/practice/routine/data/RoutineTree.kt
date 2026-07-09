package com.practice.routine.data

/**
 * 루틴 트리(순수 데이터 모델). 안드로이드 의존성이 없어 단위 테스트가 가능하다.
 * 실행 경계: 선택(selections) → 평탄화(flatten) → 실행(평면 STEP 리스트를 서비스에 전달).
 */

data class BranchNode(
    val branch: Branch,
    val steps: List<RoutineItem>
)

sealed class RoutineNode {
    data class Step(val item: RoutineItem) : RoutineNode()
    data class Choice(val item: RoutineItem, val branches: List<BranchNode>) : RoutineNode()
}

data class RoutineTree(val nodes: List<RoutineNode>)

/** 한 STEP 항목이 차지하는 총 시간(분) = 시간 × 세트수. */
fun RoutineItem.totalMinutes(): Int = durationMinutes * repeatCount.coerceAtLeast(1)

/** 한 갈래(branch)의 총 시간(분). */
fun BranchNode.totalMinutes(): Int = steps.sumOf { it.totalMinutes() }

/**
 * 선택에 따라 트리를 평면 STEP 리스트로 평탄화한다. (순수 함수)
 * @param selections choiceItemId -> 선택된 branchId. 없으면 기본 갈래, 그마저 없으면 첫 갈래를 사용.
 * 결과 항목은 전부 type=STEP, branchId=null, order 재부여된 리스트.
 */
fun flatten(tree: RoutineTree, selections: Map<Int, Int>): List<RoutineItem> {
    val out = ArrayList<RoutineItem>()
    for (node in tree.nodes) {
        when (node) {
            is RoutineNode.Step -> out.add(node.item)
            is RoutineNode.Choice -> {
                val chosenId = selections[node.item.id]
                val branch = node.branches.firstOrNull { it.branch.id == chosenId }
                    ?: node.branches.firstOrNull { it.branch.isDefault }
                    ?: node.branches.firstOrNull()
                branch?.steps?.forEach { out.add(it) }
            }
        }
    }
    return out.mapIndexed { index, item ->
        item.copy(order = index, type = ItemType.STEP, branchId = null)
    }
}

/** 트리의 예상 시간 범위(분). 갈래는 최소/최대 갈래 합을 사용. min==max 면 단일 값. */
fun timeRange(tree: RoutineTree): Pair<Int, Int> {
    var min = 0
    var max = 0
    for (node in tree.nodes) {
        when (node) {
            is RoutineNode.Step -> {
                val t = node.item.totalMinutes()
                min += t; max += t
            }
            is RoutineNode.Choice -> {
                val totals = node.branches.map { it.totalMinutes() }
                if (totals.isNotEmpty()) {
                    min += totals.min()
                    max += totals.max()
                }
            }
        }
    }
    return min to max
}

/** 선택 확정 후 플랫 리스트의 총 시간(분)/단계 수 요약. */
fun summarize(steps: List<RoutineItem>): Pair<Int, Int> {
    val totalMin = steps.sumOf { it.totalMinutes() }
    return totalMin to steps.size
}
