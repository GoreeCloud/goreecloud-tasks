package com.goreecloud.tasks.android

import java.net.URLEncoder
import java.nio.charset.StandardCharsets

enum class NativeCapabilityState {
    SOURCE_READY,
    ADOPTION_IN_PROGRESS,
    BLOCKED,
    NOT_IMPLEMENTED,
}

data class NativeClientCapabilitySnapshot(
    val readApiContract: NativeCapabilityState,
    val glazeUiV14: NativeCapabilityState,
    val identitySessionExchange: NativeCapabilityState,
    val remoteListRead: NativeCapabilityState,
    val remoteDetailRead: NativeCapabilityState,
    val localCache: NativeCapabilityState,
    val mutations: NativeCapabilityState,
    val backgroundSync: NativeCapabilityState,
)

enum class NativeTaskState(val wireValue: String) {
    ACTIVE("active"),
    COMPLETED("completed"),
    ALL("all"),
}

data class NativeTaskListQuery(
    val state: NativeTaskState = NativeTaskState.ACTIVE,
    val status: String? = null,
    val projectId: Long? = null,
    val limit: Int = DEFAULT_LIMIT,
) {
    init {
        require(status == null || status.isNotBlank()) { "status must be non-blank when supplied" }
        require(projectId == null || projectId > 0) { "projectId must be positive when supplied" }
        require(limit in 1..MAX_LIMIT) { "limit must be between 1 and $MAX_LIMIT" }
    }

    fun toRelativePath(): String {
        val parameters = buildList {
            add("state=${encode(state.wireValue)}")
            status?.let { add("status=${encode(it)}") }
            projectId?.let { add("project=$it") }
            add("limit=$limit")
        }
        return "${TasksNativeClientContract.TASK_LIST_PATH}?${parameters.joinToString("&")}" 
    }

    private fun encode(value: String): String =
        URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20")

    companion object {
        const val DEFAULT_LIMIT = 100
        const val MAX_LIMIT = 200
    }
}

object TasksNativeClientContract {
    const val API_FAMILY = "/api/v1/client/"
    const val TASK_LIST_PATH = "/api/v1/client/tasks/"
    const val LIST_SCHEMA = "goreecloud.tasks.client-task-list.v1"
    const val DETAIL_SCHEMA = "goreecloud.tasks.client-task-detail.v1"

    const val GLAZE_UI_VERSION = "1.4.0"
    const val GLAZE_UI_REFERENCE_REVISION = "84cb3db4884042f0fa25ed6d475a127fb110f596"

    fun taskDetailPath(taskId: Long): String {
        require(taskId > 0) { "taskId must be positive" }
        return "/api/v1/client/tasks/$taskId/"
    }

    fun capabilitySnapshot(): NativeClientCapabilitySnapshot = NativeClientCapabilitySnapshot(
        readApiContract = NativeCapabilityState.SOURCE_READY,
        glazeUiV14 = NativeCapabilityState.ADOPTION_IN_PROGRESS,
        identitySessionExchange = NativeCapabilityState.BLOCKED,
        remoteListRead = NativeCapabilityState.BLOCKED,
        remoteDetailRead = NativeCapabilityState.BLOCKED,
        localCache = NativeCapabilityState.NOT_IMPLEMENTED,
        mutations = NativeCapabilityState.NOT_IMPLEMENTED,
        backgroundSync = NativeCapabilityState.NOT_IMPLEMENTED,
    )
}
