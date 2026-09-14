package com.goreecloud.tasks.android

import java.time.OffsetDateTime
import java.time.format.DateTimeParseException

data class NativeTaskProjectWire(
    val id: Long,
    val name: String,
)

data class NativeTaskUserWire(
    val id: Long,
    val username: String,
)

data class NativeTaskChoiceWire<T>(
    val value: T,
    val label: String,
)

data class NativeTaskLabelWire(
    val id: Long,
    val name: String,
)

data class NativeTaskSummaryWire(
    val id: Long,
    val title: String,
    val project: NativeTaskProjectWire?,
    val parentId: Long?,
    val assignee: NativeTaskUserWire?,
    val priority: NativeTaskChoiceWire<Int>,
    val status: NativeTaskChoiceWire<String>,
    val dueAt: String?,
    val recurrence: NativeTaskChoiceWire<String>,
    val editable: Boolean,
    val completedAt: String?,
    val createdAt: String,
    val updatedAt: String,
)

data class NativeTaskDetailWire(
    val summary: NativeTaskSummaryWire,
    val description: String,
    val creator: NativeTaskUserWire,
    val labels: List<NativeTaskLabelWire>,
)

data class NativeTaskAuthorizationWire(
    val identity: String,
    val scope: String,
)

data class NativeTaskListFiltersWire(
    val state: String,
    val status: String?,
    val project: Long?,
    val limit: Int,
)

data class NativeTaskListEnvelope(
    val schema: String,
    val version: Int,
    val generatedAt: String,
    val authorization: NativeTaskAuthorizationWire,
    val filters: NativeTaskListFiltersWire,
    val returned: Int,
    val tasks: List<NativeTaskSummaryWire>,
)

data class NativeTaskDetailEnvelope(
    val schema: String,
    val version: Int,
    val generatedAt: String,
    val authorization: NativeTaskAuthorizationWire,
    val task: NativeTaskDetailWire,
)

sealed interface NativeTaskResponseDecision {
    data class Accepted(val taskCount: Int) : NativeTaskResponseDecision
    data class Rejected(val reason: String) : NativeTaskResponseDecision
}

/**
 * Transport-neutral acceptance boundary for the minimized native Tasks API.
 *
 * This type deliberately performs no JSON parsing, HTTP, authentication, storage, caching,
 * mutation, or synchronization. A future decoder/transport must map exact wire fields into the
 * models above and must reject unknown fields using the allowlists below before calling this
 * policy. Server-side visible_to()/editable_by() authorization remains authoritative.
 */
object NativeTaskResponseContract {
    const val VERSION = 1
    const val LIST_SCOPE = "tasks visible to the authenticated GoreeCloud user"
    const val DETAIL_SCOPE = "one task visible to the authenticated GoreeCloud user"

    val LIST_TOP_LEVEL_FIELDS = setOf(
        "schema", "version", "generated_at", "authorization", "filters", "returned", "tasks",
    )
    val DETAIL_TOP_LEVEL_FIELDS = setOf(
        "schema", "version", "generated_at", "authorization", "task",
    )
    val AUTHORIZATION_FIELDS = setOf("identity", "scope")
    val FILTER_FIELDS = setOf("state", "status", "project", "limit")
    val SUMMARY_FIELDS = setOf(
        "id", "title", "project", "parent_id", "assignee", "priority", "status", "due_at",
        "recurrence", "editable", "completed_at", "created_at", "updated_at",
    )
    val DETAIL_ONLY_FIELDS = setOf("description", "creator", "labels")
    val DETAIL_TASK_FIELDS = SUMMARY_FIELDS + DETAIL_ONLY_FIELDS
    val PROJECT_FIELDS = setOf("id", "name")
    val USER_FIELDS = setOf("id", "username")
    val CHOICE_FIELDS = setOf("value", "label")
    val LABEL_FIELDS = setOf("id", "name")

    private val acceptedPriorityValues = setOf(0, 1, 2, 3, 4)
    private val acceptedStatusValues = setOf(
        "planned", "ready", "in_progress", "blocked", "delayed", "waiting", "completed", "cancelled",
    )
    private val acceptedRecurrenceValues = setOf("none", "daily", "weekly", "monthly")

    fun unexpectedFields(actual: Set<String>, allowed: Set<String>): Set<String> = actual - allowed

    fun acceptList(
        envelope: NativeTaskListEnvelope,
        expectedIdentity: String,
        expectedQuery: NativeTaskListQuery,
    ): NativeTaskResponseDecision {
        if (!validIdentity(expectedIdentity)) return reject("expected identity is invalid")
        if (envelope.schema != TasksNativeClientContract.LIST_SCHEMA) return reject("list schema mismatch")
        if (envelope.version != VERSION) return reject("list version mismatch")
        if (!validTimestamp(envelope.generatedAt)) return reject("generated_at is invalid")
        if (envelope.authorization.identity != expectedIdentity) return reject("authorization identity mismatch")
        if (envelope.authorization.scope != LIST_SCOPE) return reject("authorization scope mismatch")

        val filters = envelope.filters
        if (filters.state != expectedQuery.state.wireValue) return reject("state filter mismatch")
        if (filters.status != expectedQuery.status) return reject("status filter mismatch")
        if (filters.project != expectedQuery.projectId) return reject("project filter mismatch")
        if (filters.limit != expectedQuery.limit) return reject("limit filter mismatch")
        if (filters.limit !in 1..NativeTaskListQuery.MAX_LIMIT) return reject("limit is out of bounds")

        if (envelope.returned < 0) return reject("returned is negative")
        if (envelope.returned != envelope.tasks.size) return reject("returned does not match tasks size")
        if (envelope.returned > expectedQuery.limit) return reject("response exceeds requested limit")
        if (envelope.tasks.map { it.id }.toSet().size != envelope.tasks.size) return reject("duplicate task id")

        envelope.tasks.forEachIndexed { index, task ->
            validateSummary(task)?.let { return reject("task[$index]: $it") }
        }
        return NativeTaskResponseDecision.Accepted(envelope.tasks.size)
    }

    fun acceptDetail(
        envelope: NativeTaskDetailEnvelope,
        expectedIdentity: String,
        expectedTaskId: Long,
    ): NativeTaskResponseDecision {
        if (!validIdentity(expectedIdentity)) return reject("expected identity is invalid")
        if (expectedTaskId <= 0) return reject("expected task id is invalid")
        if (envelope.schema != TasksNativeClientContract.DETAIL_SCHEMA) return reject("detail schema mismatch")
        if (envelope.version != VERSION) return reject("detail version mismatch")
        if (!validTimestamp(envelope.generatedAt)) return reject("generated_at is invalid")
        if (envelope.authorization.identity != expectedIdentity) return reject("authorization identity mismatch")
        if (envelope.authorization.scope != DETAIL_SCOPE) return reject("authorization scope mismatch")
        if (envelope.task.summary.id != expectedTaskId) return reject("task id mismatch")

        validateSummary(envelope.task.summary)?.let { return reject("task: $it") }
        if (!validText(envelope.task.creator.username)) return reject("creator username is invalid")
        if (envelope.task.creator.id <= 0) return reject("creator id is invalid")
        if (hasDisallowedControl(envelope.task.description)) return reject("description contains disallowed controls")
        if (envelope.task.labels.map { it.id }.toSet().size != envelope.task.labels.size) {
            return reject("duplicate label id")
        }
        envelope.task.labels.forEachIndexed { index, label ->
            if (label.id <= 0) return reject("label[$index] id is invalid")
            if (!validText(label.name)) return reject("label[$index] name is invalid")
        }
        return NativeTaskResponseDecision.Accepted(1)
    }

    private fun validateSummary(task: NativeTaskSummaryWire): String? {
        if (task.id <= 0) return "id is invalid"
        if (!validText(task.title) || task.title.length > 500) return "title is invalid"
        if (task.parentId != null && task.parentId <= 0) return "parent_id is invalid"
        task.project?.let {
            if (it.id <= 0) return "project id is invalid"
            if (!validText(it.name)) return "project name is invalid"
        }
        task.assignee?.let {
            if (it.id <= 0) return "assignee id is invalid"
            if (!validText(it.username)) return "assignee username is invalid"
        }
        if (task.priority.value !in acceptedPriorityValues) return "priority value is invalid"
        if (!validText(task.priority.label)) return "priority label is invalid"
        if (task.status.value !in acceptedStatusValues) return "status value is invalid"
        if (!validText(task.status.label)) return "status label is invalid"
        if (task.recurrence.value !in acceptedRecurrenceValues) return "recurrence value is invalid"
        if (!validText(task.recurrence.label)) return "recurrence label is invalid"

        val due = task.dueAt?.let(::parseTimestamp)
        if (task.dueAt != null && due == null) return "due_at is invalid"
        if (task.recurrence.value != "none" && due == null) return "recurring task is missing due_at"

        val created = parseTimestamp(task.createdAt) ?: return "created_at is invalid"
        val updated = parseTimestamp(task.updatedAt) ?: return "updated_at is invalid"
        if (updated.isBefore(created)) return "updated_at precedes created_at"

        val completed = task.completedAt?.let(::parseTimestamp)
        if (task.completedAt != null && completed == null) return "completed_at is invalid"
        if (task.status.value == "completed" && completed == null) return "completed task is missing completed_at"
        if (task.status.value != "completed" && completed != null) return "non-completed task has completed_at"
        return null
    }

    private fun validIdentity(value: String): Boolean = validText(value) && value.length <= 150

    private fun validText(value: String): Boolean =
        value.isNotEmpty() && value == value.trim() && !hasDisallowedControl(value)

    private fun hasDisallowedControl(value: String): Boolean = value.any { character ->
        character.isISOControl() && character != '\n' && character != '\r' && character != '\t'
    }

    private fun validTimestamp(value: String): Boolean = parseTimestamp(value) != null

    private fun parseTimestamp(value: String): OffsetDateTime? = try {
        OffsetDateTime.parse(value)
    } catch (_: DateTimeParseException) {
        null
    }

    private fun reject(reason: String): NativeTaskResponseDecision.Rejected =
        NativeTaskResponseDecision.Rejected(reason)
}
