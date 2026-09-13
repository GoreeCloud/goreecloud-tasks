package com.goreecloud.tasks.android

import java.time.Instant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TasksIdentityBindingTest {
    private val now = Instant.parse("2026-09-13T18:00:00Z")
    private val expectation = TasksIdentityExpectation(principalId = "identity-subject-17")

    @Test
    fun missingProofFailsClosed() {
        assertEquals(
            TasksIdentityBindingDecision.MissingProof,
            TasksIdentityBindingPolicy.evaluate(null, expectation, now),
        )
    }

    @Test
    fun exactCurrentProofBindsWithoutCreatingTransportAuthority() {
        val decision = TasksIdentityBindingPolicy.evaluate(
            proof = TasksIdentityProof(
                principalId = "identity-subject-17",
                audience = TasksIdentityExpectation.ANDROID_TASKS_AUDIENCE,
                issuedAt = now.minusSeconds(30),
                expiresAt = now.plusSeconds(300),
            ),
            expectation = expectation,
            now = now,
        )

        assertTrue(decision is TasksIdentityBindingDecision.Bound)
        decision as TasksIdentityBindingDecision.Bound
        assertEquals("identity-subject-17", decision.principalId)
        assertEquals(now.plusSeconds(300), decision.expiresAt)
    }

    @Test
    fun malformedIdentityInputsAreRejectedInsteadOfNormalized() {
        listOf(
            TasksIdentityExpectation(principalId = " identity-subject-17"),
            TasksIdentityExpectation(principalId = "identity-subject-17\n"),
            TasksIdentityExpectation(principalId = ""),
            TasksIdentityExpectation(
                principalId = "identity-subject-17",
                audience = " ${TasksIdentityExpectation.ANDROID_TASKS_AUDIENCE}",
            ),
        ).forEach { invalidExpectation ->
            assertEquals(
                TasksIdentityBindingDecision.InvalidExpectation,
                TasksIdentityBindingPolicy.evaluate(null, invalidExpectation, now),
            )
        }
    }

    @Test
    fun principalAndAudienceMismatchFailIndependently() {
        val base = TasksIdentityProof(
            principalId = "identity-subject-17",
            audience = TasksIdentityExpectation.ANDROID_TASKS_AUDIENCE,
            issuedAt = now.minusSeconds(10),
            expiresAt = now.plusSeconds(60),
        )

        assertEquals(
            TasksIdentityBindingDecision.PrincipalMismatch,
            TasksIdentityBindingPolicy.evaluate(
                base.copy(principalId = "identity-subject-18"),
                expectation,
                now,
            ),
        )
        assertEquals(
            TasksIdentityBindingDecision.AudienceMismatch,
            TasksIdentityBindingPolicy.evaluate(
                base.copy(audience = "goreecloud-calendar-android"),
                expectation,
                now,
            ),
        )
    }

    @Test
    fun lifetimeMustBePositiveCurrentAndExpiryIsExclusive() {
        val validIdentity = TasksIdentityProof(
            principalId = "identity-subject-17",
            audience = TasksIdentityExpectation.ANDROID_TASKS_AUDIENCE,
            issuedAt = now,
            expiresAt = now.plusSeconds(60),
        )

        assertEquals(
            TasksIdentityBindingDecision.InvalidProof,
            TasksIdentityBindingPolicy.evaluate(
                validIdentity.copy(expiresAt = now),
                expectation,
                now,
            ),
        )
        assertEquals(
            TasksIdentityBindingDecision.NotYetValid,
            TasksIdentityBindingPolicy.evaluate(
                validIdentity.copy(
                    issuedAt = now.plusSeconds(1),
                    expiresAt = now.plusSeconds(61),
                ),
                expectation,
                now,
            ),
        )
        assertEquals(
            TasksIdentityBindingDecision.Expired,
            TasksIdentityBindingPolicy.evaluate(
                validIdentity.copy(
                    issuedAt = now.minusSeconds(60),
                    expiresAt = now,
                ),
                expectation,
                now,
            ),
        )
    }
}
