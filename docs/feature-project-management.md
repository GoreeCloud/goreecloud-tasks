# Project and Membership Management — v0.1 Development Note

This development increment turns the existing project and membership data model into a usable multi-user interface without broadening the established privacy boundary.

## Implemented

- Projects navigation and visible-project listing.
- Private-by-default project creation.
- Owner-controlled project name and visibility settings.
- Project detail pages with open task presentation and effective access state.
- Explicit membership administration by exact username.
- Manager, Member, and Viewer role controls.
- Owner-only membership and project-settings administration.
- Immediate membership revocation through `is_active=false` rather than record deletion.
- Automatic active-membership revocation when a shared project is changed to Private.
- Read-only task presentation for Viewer membership.
- Authorized project preselection in the full task-creation workflow.
- Historical task creator and assignee retention after membership revocation so existing work remains operable while future access remains revoked.
- Functional and regression tests covering project privacy, sharing, role changes, membership removal, Viewer behavior, and historical task actors.

## Authorization Boundary

A project owner controls project settings and membership. Manager and Member roles may edit project task content under the existing task authorization rules, while Viewer remains read-only. A user who is not the owner and does not have an active membership receives no normal application access to shared project content. Private projects remain owner-only.

Changing a project from Shared to Private deactivates every active collaborator membership. Sharing is never automatically re-enabled later; the owner must explicitly add or reactivate collaborators again.

Membership revocation does not rewrite historical task creator or assignee fields. Existing tasks may retain a now-inactive collaborator as their recorded creator or assignee, but new creator or assignee relationships continue to require current project authorization and active membership.

## Production Boundary

This increment validates project and membership behavior for development only. Production publication remains blocked on the broader v0.1 release gates, including comments/activity history, labels, subtasks, search, operational metadata, export/import, backup and restoration validation, monitoring, private publication, security review, upgrade/rollback procedures, and multi-user acceptance testing.
