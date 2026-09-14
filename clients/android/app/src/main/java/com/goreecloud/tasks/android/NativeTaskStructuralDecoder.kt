package com.goreecloud.tasks.android

/**
 * Decoder for already-parsed generic data structures.
 *
 * This is intentionally not a JSON parser and performs no I/O. It converts maps/lists/primitives
 * into the typed native response models only when every object has exactly the expected fields and
 * every value has the expected primitive/container type. Semantic authorization and task invariants
 * remain the responsibility of [NativeTaskResponseContract] after structural decoding succeeds.
 */
sealed interface NativeTaskDecodeResult<out T> {
    data class Decoded<T>(val value: T) : NativeTaskDecodeResult<T>
    data class Rejected(val path: String, val reason: String) : NativeTaskDecodeResult<Nothing>
}

object NativeTaskStructuralDecoder {
    fun decodeListEnvelope(value: Any?): NativeTaskDecodeResult<NativeTaskListEnvelope> = decodeResult {
        val root = objectAt(value, "$", NativeTaskResponseContract.LIST_TOP_LEVEL_FIELDS)
        NativeTaskListEnvelope(
            schema = stringAt(root, "schema", "$.schema"),
            version = intAt(root, "version", "$.version"),
            generatedAt = stringAt(root, "generated_at", "$.generated_at"),
            authorization = decodeAuthorization(root["authorization"], "$.authorization"),
            filters = decodeFilters(root["filters"], "$.filters"),
            returned = intAt(root, "returned", "$.returned"),
            tasks = listAt(root, "tasks", "$.tasks").mapIndexed { index, task ->
                decodeSummary(task, "$.tasks[$index]")
            },
        )
    }

    fun decodeDetailEnvelope(value: Any?): NativeTaskDecodeResult<NativeTaskDetailEnvelope> = decodeResult {
        val root = objectAt(value, "$", NativeTaskResponseContract.DETAIL_TOP_LEVEL_FIELDS)
        NativeTaskDetailEnvelope(
            schema = stringAt(root, "schema", "$.schema"),
            version = intAt(root, "version", "$.version"),
            generatedAt = stringAt(root, "generated_at", "$.generated_at"),
            authorization = decodeAuthorization(root["authorization"], "$.authorization"),
            task = decodeDetailTask(root["task"], "$.task"),
        )
    }

    private fun decodeAuthorization(value: Any?, path: String): NativeTaskAuthorizationWire {
        val obj = objectAt(value, path, NativeTaskResponseContract.AUTHORIZATION_FIELDS)
        return NativeTaskAuthorizationWire(
            identity = stringAt(obj, "identity", "$path.identity"),
            scope = stringAt(obj, "scope", "$path.scope"),
        )
    }

    private fun decodeFilters(value: Any?, path: String): NativeTaskListFiltersWire {
        val obj = objectAt(value, path, NativeTaskResponseContract.FILTER_FIELDS)
        return NativeTaskListFiltersWire(
            state = stringAt(obj, "state", "$path.state"),
            status = nullableStringAt(obj, "status", "$path.status"),
            project = nullableLongAt(obj, "project", "$path.project"),
            limit = intAt(obj, "limit", "$path.limit"),
        )
    }

    private fun decodeSummary(value: Any?, path: String): NativeTaskSummaryWire {
        val obj = objectAt(value, path, NativeTaskResponseContract.SUMMARY_FIELDS)
        return decodeSummaryObject(obj, path)
    }

    private fun decodeDetailTask(value: Any?, path: String): NativeTaskDetailWire {
        val obj = objectAt(value, path, NativeTaskResponseContract.DETAIL_TASK_FIELDS)
        return NativeTaskDetailWire(
            summary = decodeSummaryObject(obj, path),
            description = stringAt(obj, "description", "$path.description"),
            creator = decodeUser(required(obj, "creator", "$path.creator"), "$path.creator"),
            labels = listAt(obj, "labels", "$path.labels").mapIndexed { index, label ->
                decodeLabel(label, "$path.labels[$index]")
            },
        )
    }

    private fun decodeSummaryObject(obj: Map<String, Any?>, path: String): NativeTaskSummaryWire =
        NativeTaskSummaryWire(
            id = longAt(obj, "id", "$path.id"),
            title = stringAt(obj, "title", "$path.title"),
            project = nullableObjectValue(obj, "project", "$path.project")?.let {
                decodeProject(it, "$path.project")
            },
            parentId = nullableLongAt(obj, "parent_id", "$path.parent_id"),
            assignee = nullableObjectValue(obj, "assignee", "$path.assignee")?.let {
                decodeUser(it, "$path.assignee")
            },
            priority = decodeIntChoice(required(obj, "priority", "$path.priority"), "$path.priority"),
            status = decodeStringChoice(required(obj, "status", "$path.status"), "$path.status"),
            dueAt = nullableStringAt(obj, "due_at", "$path.due_at"),
            recurrence = decodeStringChoice(
                required(obj, "recurrence", "$path.recurrence"),
                "$path.recurrence",
            ),
            editable = booleanAt(obj, "editable", "$path.editable"),
            completedAt = nullableStringAt(obj, "completed_at", "$path.completed_at"),
            createdAt = stringAt(obj, "created_at", "$path.created_at"),
            updatedAt = stringAt(obj, "updated_at", "$path.updated_at"),
        )

    private fun decodeProject(value: Any?, path: String): NativeTaskProjectWire {
        val obj = objectAt(value, path, NativeTaskResponseContract.PROJECT_FIELDS)
        return NativeTaskProjectWire(
            id = longAt(obj, "id", "$path.id"),
            name = stringAt(obj, "name", "$path.name"),
        )
    }

    private fun decodeUser(value: Any?, path: String): NativeTaskUserWire {
        val obj = objectAt(value, path, NativeTaskResponseContract.USER_FIELDS)
        return NativeTaskUserWire(
            id = longAt(obj, "id", "$path.id"),
            username = stringAt(obj, "username", "$path.username"),
        )
    }

    private fun decodeLabel(value: Any?, path: String): NativeTaskLabelWire {
        val obj = objectAt(value, path, NativeTaskResponseContract.LABEL_FIELDS)
        return NativeTaskLabelWire(
            id = longAt(obj, "id", "$path.id"),
            name = stringAt(obj, "name", "$path.name"),
        )
    }

    private fun decodeIntChoice(value: Any?, path: String): NativeTaskChoiceWire<Int> {
        val obj = objectAt(value, path, NativeTaskResponseContract.CHOICE_FIELDS)
        return NativeTaskChoiceWire(
            value = intAt(obj, "value", "$path.value"),
            label = stringAt(obj, "label", "$path.label"),
        )
    }

    private fun decodeStringChoice(value: Any?, path: String): NativeTaskChoiceWire<String> {
        val obj = objectAt(value, path, NativeTaskResponseContract.CHOICE_FIELDS)
        return NativeTaskChoiceWire(
            value = stringAt(obj, "value", "$path.value"),
            label = stringAt(obj, "label", "$path.label"),
        )
    }

    private inline fun <T> decodeResult(block: () -> T): NativeTaskDecodeResult<T> = try {
        NativeTaskDecodeResult.Decoded(block())
    } catch (failure: DecodeFailure) {
        NativeTaskDecodeResult.Rejected(failure.path, failure.message ?: "invalid value")
    }

    private fun objectAt(value: Any?, path: String, expectedFields: Set<String>): Map<String, Any?> {
        val raw = value as? Map<*, *> ?: fail(path, "expected object")
        val objectValue = LinkedHashMap<String, Any?>(raw.size)
        raw.forEach { (key, fieldValue) ->
            val fieldName = key as? String ?: fail(path, "object field names must be strings")
            if (objectValue.put(fieldName, fieldValue) != null || raw.keys.count { it == key } > 1) {
                fail(path, "duplicate field $fieldName")
            }
        }
        val actualFields = objectValue.keys
        val unknown = actualFields - expectedFields
        if (unknown.isNotEmpty()) fail(path, "unknown fields: ${unknown.sorted().joinToString(",")}")
        val missing = expectedFields - actualFields
        if (missing.isNotEmpty()) fail(path, "missing fields: ${missing.sorted().joinToString(",")}")
        return objectValue
    }

    private fun required(obj: Map<String, Any?>, field: String, path: String): Any? {
        if (!obj.containsKey(field)) fail(path, "field is missing")
        return obj[field]
    }

    private fun stringAt(obj: Map<String, Any?>, field: String, path: String): String =
        required(obj, field, path) as? String ?: fail(path, "expected string")

    private fun nullableStringAt(obj: Map<String, Any?>, field: String, path: String): String? {
        val value = required(obj, field, path)
        if (value == null) return null
        return value as? String ?: fail(path, "expected string or null")
    }

    private fun booleanAt(obj: Map<String, Any?>, field: String, path: String): Boolean =
        required(obj, field, path) as? Boolean ?: fail(path, "expected boolean")

    private fun intAt(obj: Map<String, Any?>, field: String, path: String): Int {
        val value = required(obj, field, path)
        return when (value) {
            is Byte -> value.toInt()
            is Short -> value.toInt()
            is Int -> value
            is Long -> if (value in Int.MIN_VALUE..Int.MAX_VALUE) value.toInt() else fail(path, "integer is out of range")
            else -> fail(path, "expected integral number")
        }
    }

    private fun longAt(obj: Map<String, Any?>, field: String, path: String): Long =
        integralLong(required(obj, field, path), path)

    private fun nullableLongAt(obj: Map<String, Any?>, field: String, path: String): Long? {
        val value = required(obj, field, path)
        if (value == null) return null
        return integralLong(value, path)
    }

    private fun integralLong(value: Any?, path: String): Long = when (value) {
        is Byte -> value.toLong()
        is Short -> value.toLong()
        is Int -> value.toLong()
        is Long -> value
        else -> fail(path, "expected integral number")
    }

    private fun listAt(obj: Map<String, Any?>, field: String, path: String): List<Any?> {
        val value = required(obj, field, path)
        val raw = value as? List<*> ?: fail(path, "expected array")
        return raw.toList()
    }

    private fun nullableObjectValue(obj: Map<String, Any?>, field: String, path: String): Any? {
        val value = required(obj, field, path)
        if (value == null) return null
        if (value !is Map<*, *>) fail(path, "expected object or null")
        return value
    }

    private fun fail(path: String, reason: String): Nothing = throw DecodeFailure(path, reason)

    private class DecodeFailure(val path: String, reason: String) : IllegalArgumentException(reason)
}
