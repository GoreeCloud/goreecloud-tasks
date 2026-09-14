package com.goreecloud.tasks.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeTaskResponseContractTest {
    @Test
    fun acceptsExactMinimizedListEnvelope() {
        val query = NativeTaskListQuery(
            state = NativeTaskState.ACTIVE,
            status = "ready",
            projectId = 7,
            limit = 25,
        )
        val envelope = NativeTaskListEnvelope(
            schema = TasksNativeClientContract.LIST_SCHEMA,
            version = 1,
            generatedAt = "2026-09-14T01:00:00+00:00",
            authorization = NativeTaskAuthorizationWire(
                identity = "alice",
                scope = NativeTaskResponseContract.LIST_SCOPE,
            ),
            filters = NativeTaskListFiltersWire(
                state = "active",
                status = "ready",
                project = 7,
                limit = 25,
            ),
            returned = 1,
            tasks = listOf(summary()),
        )

        assertEquals(
            NativeTaskResponseDecision.Accepted(1),
            NativeTaskResponseContract.acceptList(envelope, "alice", query),
        )
    }

    @Test
    fun acceptsExactDetailEnvelopeWithDetailOnlyFields() {
        val detail = NativeTaskDetailEnvelope(
            schema = TasksNativeClientContract.DETAIL_SCHEMA,
            version = 1,
            generatedAt = "2026-09-14T01:00:00+00:00",
            authorization = NativeTaskAuthorizationWire(
                identity = "alice",
                scope = NativeTaskResponseContract.DETAIL_SCOPE,
            ),
            task = NativeTaskDetailWire(
                summary = summary(),
                description = "Review the native response contract.\nNo transport authority yet.",
                creator = NativeTaskUserWire(3, "alice"),
                labels = listOf(
                    NativeTaskLabelWire(11, "Android"),
                    NativeTaskLabelWire(12, "Development"),
                ),
            ),
        )

        assertEquals(
            NativeTaskResponseDecision.Accepted(1),
            NativeTaskResponseContract.acceptDetail(detail, "alice", 42),
        )
    }

    @Test
    fun rejectsAuthorizationAndFilterDrift() {
        val query = NativeTaskListQuery(limit = 10)
        val wrongIdentity = listEnvelope(
            authorization = NativeTaskAuthorizationWire("mallory", NativeTaskResponseContract.LIST_SCOPE),
            filters = NativeTaskListFiltersWire("active", null, null, 10),
        )
        val wrongLimit = listEnvelope(
            authorization = NativeTaskAuthorizationWire("alice", NativeTaskResponseContract.LIST_SCOPE),
            filters = NativeTaskListFiltersWire("active", null, null, 11),
        )

        assertRejected(NativeTaskResponseContract.acceptList(wrongIdentity, "alice", query))
        assertRejected(NativeTaskResponseContract.acceptList(wrongLimit, "alice", query))
    }

    @Test
    fun rejectsCountDuplicateAndTaskStateDrift() {
        val query = NativeTaskListQuery(limit = 10)
        val countMismatch = listEnvelope(returned = 2)
        val duplicateIds = listEnvelope(tasks = listOf(summary(), summary()), returned = 2)
        val invalidStatus = listEnvelope(
            tasks = listOf(summary(status = NativeTaskChoiceWire("unknown", "Unknown"))),
        )
        val impossibleCompletion = listEnvelope(
            tasks = listOf(summary(status = NativeTaskChoiceWire("ready", "Ready"), completedAt = "2026-09-14T01:30:00+00:00")),
        )

        assertRejected(NativeTaskResponseContract.acceptList(countMismatch, "alice", query))
        assertRejected(NativeTaskResponseContract.acceptList(duplicateIds, "alice", query))
        assertRejected(NativeTaskResponseContract.acceptList(invalidStatus, "alice", query))
        assertRejected(NativeTaskResponseContract.acceptList(impossibleCompletion, "alice", query))
    }

    @Test
    fun rejectsInvalidTimestampsAndRecurringTaskWithoutDueTime() {
        val query = NativeTaskListQuery(limit = 10)
        val backwards = listEnvelope(
            tasks = listOf(summary(createdAt = "2026-09-14T02:00:00+00:00", updatedAt = "2026-09-14T01:00:00+00:00")),
        )
        val recurringWithoutDue = listEnvelope(
            tasks = listOf(summary(recurrence = NativeTaskChoiceWire("weekly", "Weekly"), dueAt = null)),
        )

        assertRejected(NativeTaskResponseContract.acceptList(backwards, "alice", query))
        assertRejected(NativeTaskResponseContract.acceptList(recurringWithoutDue, "alice", query))
    }

    @Test
    fun fieldAllowlistsExcludeDetailAndSensitiveServerStateFromList() {
        assertTrue(NativeTaskResponseContract.DETAIL_ONLY_FIELDS.intersect(NativeTaskResponseContract.SUMMARY_FIELDS).isEmpty())
        assertTrue(NativeTaskResponseContract.unexpectedFields(setOf("id", "title", "comments"), NativeTaskResponseContract.SUMMARY_FIELDS).contains("comments"))
        assertTrue(NativeTaskResponseContract.unexpectedFields(setOf("id", "title", "reminder_state"), NativeTaskResponseContract.SUMMARY_FIELDS).contains("reminder_state"))
        assertTrue(NativeTaskResponseContract.unexpectedFields(setOf("id", "title", "operational_notes"), NativeTaskResponseContract.SUMMARY_FIELDS).contains("operational_notes"))
        assertTrue(NativeTaskResponseContract.unexpectedFields(setOf("schema", "version", "tasks", "credential"), NativeTaskResponseContract.LIST_TOP_LEVEL_FIELDS).contains("credential"))
    }

    @Test
    fun detailRejectsProbeMismatchAndDuplicateLabels() {
        val mismatchedId = NativeTaskDetailEnvelope(
            schema = TasksNativeClientContract.DETAIL_SCHEMA,
            version = 1,
            generatedAt = "2026-09-14T01:00:00+00:00",
            authorization = NativeTaskAuthorizationWire("alice", NativeTaskResponseContract.DETAIL_SCOPE),
            task = NativeTaskDetailWire(summary = summary(), description = "", creator = NativeTaskUserWire(3, "alice"), labels = emptyList()),
        )
        val duplicateLabels = mismatchedId.copy(
            task = mismatchedId.task.copy(
                labels = listOf(NativeTaskLabelWire(1, "One"), NativeTaskLabelWire(1, "Duplicate")),
            ),
        )

        assertRejected(NativeTaskResponseContract.acceptDetail(mismatchedId, "alice", 99))
        assertRejected(NativeTaskResponseContract.acceptDetail(duplicateLabels, "alice", 42))
    }

    private fun listEnvelope(
        authorization: NativeTaskAuthorizationWire = NativeTaskAuthorizationWire("alice", NativeTaskResponseContract.LIST_SCOPE),
        filters: NativeTaskListFiltersWire = NativeTaskListFiltersWire("active", null, null, 10),
        returned: Int = 1,
        tasks: List<NativeTaskSummaryWire> = listOf(summary()),
    ) = NativeTaskListEnvelope(
        schema = TasksNativeClientContract.LIST_SCHEMA,
        version = 1,
        generatedAt = "2026-09-14T01:00:00+00:00",
        authorization = authorization,
        filters = filters,
        returned = returned,
        tasks = tasks,
    )

    private fun summary(
        status: NativeTaskChoiceWire<String> = NativeTaskChoiceWire("ready", "Ready"),
        recurrence: NativeTaskChoiceWire<String> = NativeTaskChoiceWire("none", "Does not repeat"),
        dueAt: String? = "2026-09-15T12:00:00+00:00",
        completedAt: String? = null,
        createdAt: String = "2026-09-13T12:00:00+00:00",
        updatedAt: String = "2026-09-14T00:30:00+00:00",
    ) = NativeTaskSummaryWire(
        id = 42,
        title = "Validate Android response contract",
        project = NativeTaskProjectWire(7, "GoreeCloud"),
        parentId = null,
        assignee = NativeTaskUserWire(3, "alice"),
        priority = NativeTaskChoiceWire(2, "P2 — High"),
        status = status,
        dueAt = dueAt,
        recurrence = recurrence,
        editable = true,
        completedAt = completedAt,
        createdAt = createdAt,
        updatedAt = updatedAt,
    )

    private fun assertRejected(decision: NativeTaskResponseDecision) {
        assertTrue(decision is NativeTaskResponseDecision.Rejected)
    }
}
