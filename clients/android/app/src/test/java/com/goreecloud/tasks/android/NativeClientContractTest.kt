package com.goreecloud.tasks.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeClientContractTest {
    @Test
    fun defaultListQueryUsesBoundedNativeEndpoint() {
        assertEquals(
            "/api/v1/client/tasks/?state=active&limit=100",
            NativeTaskListQuery().toRelativePath(),
        )
    }

    @Test
    fun listQueryEncodesFiltersWithoutChangingAuthorizationPrincipal() {
        assertEquals(
            "/api/v1/client/tasks/?state=all&status=Needs%20Review&project=42&limit=200",
            NativeTaskListQuery(
                state = NativeTaskState.ALL,
                status = "Needs Review",
                projectId = 42,
                limit = 200,
            ).toRelativePath(),
        )
    }

    @Test
    fun invalidFilterBoundsFailBeforeTransport() {
        assertFails { NativeTaskListQuery(status = " ") }
        assertFails { NativeTaskListQuery(projectId = 0) }
        assertFails { NativeTaskListQuery(projectId = -1) }
        assertFails { NativeTaskListQuery(limit = 0) }
        assertFails { NativeTaskListQuery(limit = 201) }
    }

    @Test
    fun detailPathRequiresPositiveTaskIdentity() {
        assertEquals("/api/v1/client/tasks/17/", TasksNativeClientContract.taskDetailPath(17))
        assertFails { TasksNativeClientContract.taskDetailPath(0) }
        assertFails { TasksNativeClientContract.taskDetailPath(-9) }
    }

    @Test
    fun developmentCapabilitiesSeparateProofContractFromRuntimeAuthority() {
        val snapshot = TasksNativeClientContract.capabilitySnapshot()
        assertEquals(NativeCapabilityState.SOURCE_READY, snapshot.readApiContract)
        assertEquals(NativeCapabilityState.ADOPTION_IN_PROGRESS, snapshot.glazeUiV14)
        assertEquals(
            NativeCapabilityState.SOURCE_READY,
            snapshot.identityAcceptanceProofContract,
        )
        assertEquals(NativeCapabilityState.BLOCKED, snapshot.identitySessionExchange)
        assertEquals(NativeCapabilityState.BLOCKED, snapshot.remoteListRead)
        assertEquals(NativeCapabilityState.BLOCKED, snapshot.remoteDetailRead)
        assertEquals(NativeCapabilityState.NOT_IMPLEMENTED, snapshot.localCache)
        assertEquals(NativeCapabilityState.NOT_IMPLEMENTED, snapshot.mutations)
        assertEquals(NativeCapabilityState.NOT_IMPLEMENTED, snapshot.backgroundSync)

        val runtimeStates = listOf(
            snapshot.identitySessionExchange,
            snapshot.remoteListRead,
            snapshot.remoteDetailRead,
            snapshot.localCache,
            snapshot.mutations,
            snapshot.backgroundSync,
        )
        assertFalse(runtimeStates.contains(NativeCapabilityState.SOURCE_READY))
        assertEquals(
            "goreecloud.identity.native-application-session/v1",
            TasksNativeClientContract.IDENTITY_NATIVE_SESSION_SCHEMA,
        )
        assertTrue(TasksNativeClientContract.IDENTITY_CONTRACT_CANDIDATE_REVISION.length == 40)
        assertTrue(TasksNativeClientContract.GLAZE_UI_REFERENCE_REVISION.length == 40)
    }

    private fun assertFails(block: () -> Unit) {
        var failed = false
        try {
            block()
        } catch (_: IllegalArgumentException) {
            failed = true
        }
        assertTrue("expected IllegalArgumentException", failed)
    }
}
