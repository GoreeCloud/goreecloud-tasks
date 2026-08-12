# Portable export and import boundary

## Purpose

This increment creates the first machine-readable portability path for GoreeCloud Tasks without turning ordinary read access into a new bulk-exfiltration permission.

## Export format

Exports use UTF-8 JSON with the format identifier `goreecloud.tasks.export` and schema version `1`. Every document includes an export timestamp, an explicit scope, and application-owned records grouped by users, projects, memberships, labels, tasks, comments, and activity.

The current schema preserves object identifiers and relationship identifiers so a future importer can remap projects, parents, labels, creators, assignees, membership records, comments, and activity into a restored installation. Timestamps are ISO 8601 values. Task status and priority use their stored stable codes/values rather than presentation text.

## User archive boundary

A user's archive contains private personal tasks and labels plus projects owned by that user and the records contained by those owned projects. A project owned by somebody else is excluded even when the exporter currently has Manager, Member, or Viewer access. Normal read access does not automatically become a bulk-export right over another person's project.

## Project archive boundary

Project archive download is owner-only in v0.1. It contains the selected project and its memberships, labels, tasks, comments, activity, and referenced users.

## Sensitive-data minimization

The export does not include passwords, password hashes, email addresses, sessions, authentication tokens, secret configuration, or unrelated account fields. User references contain only the local user ID and username. Comment bodies and task descriptions are included because they are application-owned task content inside the approved export scope.

Downloads are marked `private, no-store` and served as attachments.

## Import architecture

The `imports` package now defines a source-neutral normalization schema. Future external adapters must translate provider-specific exports into `NormalizedImportBundle` records before any database mutation. This keeps provider parsing separate from GoreeCloud Tasks persistence and authorization logic.

A `TodoistImportAdapter` boundary is present, but its parser intentionally raises `NotImplementedError`. GoreeCloud Tasks does not claim Todoist import compatibility until the selected Todoist export format has been verified, mapped, and covered by migration tests.

## Validation

Regression tests verify authentication, schema versioning, owner-only project export, exclusion of other users' private and other-owned shared work, relationship preservation, GoreeCloud operational-field preservation, sensitive account-field omission, and the non-claiming Todoist adapter boundary.
