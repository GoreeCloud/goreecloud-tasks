# Task Assignment Authorization Boundary

## Purpose

This document defines the GoreeCloud Tasks rule for assigning new work to a user while preserving historical task responsibility after a user's eligibility changes.

The assignment boundary complements project visibility and task-edit authorization. Read access to a project is not sufficient authority to receive newly assigned work.

## New assignment rule

A new project-task assignment is valid only when the selected assignee:

- has an active GoreeCloud Tasks account; and
- is the project owner, or has an active `Manager` or `Member` membership in that exact project.

A `Viewer` is intentionally excluded because Viewer is a read-only project role and cannot perform the normal task mutations associated with assigned work.

A user whose account is disabled is also excluded even when an active project membership record still exists.

Membership in another editable project does not make a user assignable in the selected project.

For a private personal task, the only valid assignee is the task creator.

## Central authorization source

`ProjectMembership.EDIT_ROLES` is the shared project-edit role set used by task-query and assignment logic. `Project.can_receive_assigned_work(user)` combines current account activity with `Project.can_edit(user)` and is the authoritative predicate for a new project assignment.

Both the form and model layers consume this project-level predicate rather than maintaining separate copies of the eligibility rule. This keeps Viewer behavior, Manager/Member behavior, owner behavior, and disabled-account handling aligned if the role model changes later.

## Historical-assignment retention

Assignment eligibility is evaluated differently when editing an existing task.

If the persisted assignee later becomes ineligible because the account is disabled, the membership is revoked, or the project role is reduced to Viewer, the existing assignment may remain unchanged. This preserves historical responsibility and prevents an unrelated task edit from silently rewriting task history.

The retained historical assignee does not regain edit authority through the assignment. Current project membership and role continue to control task mutation and visibility.

Changing the assignee to a different user always evaluates the new assignee against the current assignment rule.

## Enforcement layers

The rule is enforced at two application layers:

1. `TaskForm` scopes the assignee field to the selected project and validates the submitted assignee through the centralized project predicate.
2. `Task.clean()` applies the same project predicate at the model boundary so a crafted request or direct model save cannot create an unauthorized new assignment.

The edit form deliberately includes the already-persisted assignee even when that user is no longer currently eligible, allowing historical retention without broadening the normal choice list.

## Regression coverage

`tests/test_task_assignment_boundaries.py` covers:

- Owner, Manager, and Member eligibility.
- Viewer exclusion and rejection.
- Disabled-account exclusion and rejection.
- Cross-project assignment rejection.
- Private-task self-assignment scope.
- Bound-form scoping to the submitted project.
- Model-level enforcement independent of form validation.
- Historical assignment retention after Viewer downgrade.
- Historical assignment retention after account disablement.
- Existing ineligible assignee presence in the edit form for retention.

## Production boundary

This source change does not modify production accounts, memberships, tasks, credentials, deployment state, networking, monitoring, backups, or service activation.

The change must not be treated as accepted repository state until the normal exact-head GitHub Actions validation requirements complete successfully on the candidate branch, the pull request, and the resulting `main` merge commit.