package com.goreecloud.tasks.android

import java.time.Instant

/**
 * Non-secret acceptance metadata that a future GoreeCloud Identity exchange must establish before
 * the Tasks Android client can consider authenticated remote reads.
 *
 * This model intentionally contains no bearer token, refresh token, password, browser cookie,
 * service credential, or transport implementation.
 */
data class TasksIdentityProof(
    val principalId: String,
    val audience: String,
    val issuedAt: Instant,
    val expiresAt: Instant,
)

data class TasksIdentityExpectation(
    val principalId: String,
    val audience: String = ANDROID_TASKS_AUDIENCE,
) {
    companion object {
        const val ANDROID_TASKS_AUDIENCE = "goreecloud-tasks-android"
    }
}

sealed interface TasksIdentityBindingDecision {
    /** Metadata is internally consistent; native Identity exchange and transport stay separate. */
    data class Bound(
        val principalId: String,
        val expiresAt: Instant,
    ) : TasksIdentityBindingDecision

    data object MissingProof : TasksIdentityBindingDecision
    data object InvalidExpectation : TasksIdentityBindingDecision
    data object InvalidProof : TasksIdentityBindingDecision
    data object PrincipalMismatch : TasksIdentityBindingDecision
    data object AudienceMismatch : TasksIdentityBindingDecision
    data object NotYetValid : TasksIdentityBindingDecision
    data object Expired : TasksIdentityBindingDecision
}

/**
 * Pure, fail-closed consumer acceptance policy aligned to the GoreeCloud Identity native-session
 * source contract candidate. A Bound result is not authentication and cannot bypass server-side
 * visible_to()/editable_by() authorization.
 */
object TasksIdentityBindingPolicy {
    fun evaluate(
        proof: TasksIdentityProof?,
        expectation: TasksIdentityExpectation,
        now: Instant,
    ): TasksIdentityBindingDecision {
        if (!isExactIdentity(expectation.principalId) || !isExactIdentity(expectation.audience)) {
            return TasksIdentityBindingDecision.InvalidExpectation
        }

        proof ?: return TasksIdentityBindingDecision.MissingProof

        if (!isExactIdentity(proof.principalId) ||
            !isExactIdentity(proof.audience) ||
            !proof.issuedAt.isBefore(proof.expiresAt)
        ) {
            return TasksIdentityBindingDecision.InvalidProof
        }

        if (proof.principalId != expectation.principalId) {
            return TasksIdentityBindingDecision.PrincipalMismatch
        }
        if (proof.audience != expectation.audience) {
            return TasksIdentityBindingDecision.AudienceMismatch
        }
        if (now.isBefore(proof.issuedAt)) {
            return TasksIdentityBindingDecision.NotYetValid
        }
        if (!now.isBefore(proof.expiresAt)) {
            return TasksIdentityBindingDecision.Expired
        }

        return TasksIdentityBindingDecision.Bound(
            principalId = proof.principalId,
            expiresAt = proof.expiresAt,
        )
    }

    private fun isExactIdentity(value: String): Boolean =
        value.isNotBlank() && value == value.trim() && value.none(Char::isISOControl)
}
