package com.goreecloud.tasks.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeTaskStructuralDecoderTest {
    @Test
    fun exactListShapeDecodesThenPassesSemanticAcceptance() {
        val result = NativeTaskStructuralDecoder.decodeListEnvelope(validListEnvelope())
        assertTrue(result is NativeTaskDecodeResult.Decoded)

        val envelope = (result as NativeTaskDecodeResult.Decoded).value
        val semantic = NativeTaskResponseContract.acceptList(
            envelope = envelope,
            expectedIdentity = "alice",
            expectedQuery = NativeTaskListQuery(limit = 25),
        )
        assertEquals(NativeTaskResponseDecision.Accepted(1), semantic)
    }

    @Test
    fun exactDetailShapeDecodesThenPassesSemanticAcceptance() {
        val result = NativeTaskStructuralDecoder.decodeDetailEnvelope(validDetailEnvelope())
        assertTrue(result is NativeTaskDecodeResult.Decoded)

        val envelope = (result as NativeTaskDecodeResult.Decoded).value
        val semantic = NativeTaskResponseContract.acceptDetail(
            envelope = envelope,
            expectedIdentity = "alice",
            expectedTaskId = 7L,
        )
        assertEquals(NativeTaskResponseDecision.Accepted(1), semantic)
    }

    @Test
    fun unknownTopLevelAndNestedFieldsFailBeforeTypedAcceptance() {
        val top = validListEnvelope().toMutableMap().apply { put("credential", "secret") }
        assertRejectedAt(NativeTaskStructuralDecoder.decodeListEnvelope(top), "$")

        val nested = validListEnvelope().toMutableMap()
        val tasks = (nested.getValue("tasks") as List<*>).toMutableList()
        val task = (tasks.single() as Map<*, *>).entries.associate { it.key as String to it.value }.toMutableMap()
        task["private_note"] = "must not pass"
        tasks[0] = task
        nested["tasks"] = tasks
        assertRejectedAt(NativeTaskStructuralDecoder.decodeListEnvelope(nested), "$.tasks[0]")
    }

    @Test
    fun missingRequiredFieldFailsClosed() {
        val payload = validListEnvelope().toMutableMap()
        val authorization = map(payload.getValue("authorization")).toMutableMap()
        authorization.remove("scope")
        payload["authorization"] = authorization

        assertRejectedAt(
            NativeTaskStructuralDecoder.decodeListEnvelope(payload),
            "$.authorization",
        )
    }

    @Test
    fun floatingNumbersAndTruthyStringsAreNotCoerced() {
        val floatingId = validListEnvelope().toMutableMap()
        val tasks = (floatingId.getValue("tasks") as List<*>).toMutableList()
        val task = map(tasks.single()).toMutableMap()
        task["id"] = 7.0
        tasks[0] = task
        floatingId["tasks"] = tasks
        assertRejectedAt(
            NativeTaskStructuralDecoder.decodeListEnvelope(floatingId),
            "$.tasks[0].id",
        )

        val truthy = validListEnvelope().toMutableMap()
        val truthyTasks = (truthy.getValue("tasks") as List<*>).toMutableList()
        val truthyTask = map(truthyTasks.single()).toMutableMap()
        truthyTask["editable"] = "true"
        truthyTasks[0] = truthyTask
        truthy["tasks"] = truthyTasks
        assertRejectedAt(
            NativeTaskStructuralDecoder.decodeListEnvelope(truthy),
            "$.tasks[0].editable",
        )
    }

    @Test
    fun nullabilityIsExactRatherThanStringified() {
        val payload = validListEnvelope().toMutableMap()
        val filters = map(payload.getValue("filters")).toMutableMap()
        filters["project"] = "null"
        payload["filters"] = filters

        assertRejectedAt(
            NativeTaskStructuralDecoder.decodeListEnvelope(payload),
            "$.filters.project",
        )
    }

    @Test
    fun listSafeShapeCannotSmuggleDetailOnlyFields() {
        val payload = validListEnvelope().toMutableMap()
        val tasks = (payload.getValue("tasks") as List<*>).toMutableList()
        val task = map(tasks.single()).toMutableMap()
        task["description"] = "detail-only"
        tasks[0] = task
        payload["tasks"] = tasks

        assertRejectedAt(
            NativeTaskStructuralDecoder.decodeListEnvelope(payload),
            "$.tasks[0]",
        )
    }

    private fun assertRejectedAt(result: NativeTaskDecodeResult<*>, path: String) {
        assertTrue(result is NativeTaskDecodeResult.Rejected)
        assertEquals(path, (result as NativeTaskDecodeResult.Rejected).path)
    }

    private fun validListEnvelope(): Map<String, Any?> = linkedMapOf(
        "schema" to TasksNativeClientContract.LIST_SCHEMA,
        "version" to 1,
        "generated_at" to "2026-09-14T12:00:00Z",
        "authorization" to linkedMapOf(
            "identity" to "alice",
            "scope" to NativeTaskResponseContract.LIST_SCOPE,
        ),
        "filters" to linkedMapOf(
            "state" to "active",
            "status" to null,
            "project" to null,
            "limit" to 25,
        ),
        "returned" to 1,
        "tasks" to listOf(validSummary()),
    )

    private fun validDetailEnvelope(): Map<String, Any?> = linkedMapOf(
        "schema" to TasksNativeClientContract.DETAIL_SCHEMA,
        "version" to 1,
        "generated_at" to "2026-09-14T12:00:00Z",
        "authorization" to linkedMapOf(
            "identity" to "alice",
            "scope" to NativeTaskResponseContract.DETAIL_SCOPE,
        ),
        "task" to LinkedHashMap(validSummary()).apply {
            put("description", "A bounded task description")
            put("creator", linkedMapOf("id" to 1, "username" to "alice"))
            put("labels", listOf(linkedMapOf("id" to 4, "name" to "work")))
        },
    )

    private fun validSummary(): Map<String, Any?> = linkedMapOf(
        "id" to 7,
        "title" to "Prepare review",
        "project" to linkedMapOf("id" to 2, "name" to "GoreeCloud"),
        "parent_id" to null,
        "assignee" to linkedMapOf("id" to 1, "username" to "alice"),
        "priority" to linkedMapOf("value" to 2, "label" to "Medium"),
        "status" to linkedMapOf("value" to "ready", "label" to "Ready"),
        "due_at" to null,
        "recurrence" to linkedMapOf("value" to "none", "label" to "None"),
        "editable" to true,
        "completed_at" to null,
        "created_at" to "2026-09-14T10:00:00Z",
        "updated_at" to "2026-09-14T11:00:00Z",
    )

    private fun map(value: Any?): Map<String, Any?> =
        (value as Map<*, *>).entries.associate { it.key as String to it.value }
}
