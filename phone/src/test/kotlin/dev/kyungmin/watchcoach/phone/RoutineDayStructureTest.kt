package dev.kyungmin.watchcoach.phone

import org.junit.Assert.*
import org.junit.Test

class RoutineDayStructureTest {
    private fun def(id: String) = ExerciseDefinition(id, id, "", "", "덤벨")
    private fun item(id: String, vararg types: SetType, kg: Double = 10.0) =
        RoutineExercise(def(id), types.map { PlannedSet(kg, 10, setType = it) }.toMutableList())
    private val n = SetType.NORMAL

    @Test fun sameShapeWithDifferentWeightsChangesNothing() {
        val saved = listOf(item("row", n, n), item("curl", n))
        val day = listOf(item("row", n, n, kg = 99.0), item("curl", n, kg = 1.0))
        assertNull(RoutineDayStructure.carried(saved, day))
    }

    @Test fun removedExerciseLeavesTheSavedRoutine() {
        val saved = listOf(item("row", n), item("curl", n))
        val carried = RoutineDayStructure.carried(saved, listOf(item("row", n)))!!
        assertEquals(listOf("row"), carried.map { it.exercise.id })
        assertSame(saved[0], carried[0])   // untouched exercises keep their saved sets and ids
    }

    @Test fun addedExerciseAppearsWithClearedSets() {
        val saved = listOf(item("row", n))
        val added = item("fly", n).also { it.sets[0].completed = true; it.sets[0].performedReps = 12 }
        val carried = RoutineDayStructure.carried(saved, listOf(saved[0], added))!!
        assertEquals(listOf("row", "fly"), carried.map { it.exercise.id })
        assertFalse(carried[1].sets[0].completed)
        assertNull(carried[1].sets[0].performedReps)
    }

    @Test fun extraSetGrowsTheTailAndKeepsSavedSetIds() {
        val saved = listOf(item("row", n, n))
        val carried = RoutineDayStructure.carried(saved, listOf(item("row", n, n, n)))!!
        assertEquals(3, carried[0].sets.size)
        assertEquals(saved[0].sets.map { it.setId }, carried[0].sets.take(2).map { it.setId })
    }

    @Test fun reorderingFollowsTheDay() {
        val saved = listOf(item("row", n), item("curl", n))
        val carried = RoutineDayStructure.carried(saved, listOf(saved[1], saved[0]))!!
        assertEquals(listOf("curl", "row"), carried.map { it.exercise.id })
    }
}
