# GoreeCloud Waypoint

GoreeCloud Waypoint is the umbrella capability identity for the work-management experience delivered through GoreeCloud Tasks.

GoreeCloud Tasks remains the application, data authority, permission boundary, and task-management platform. Waypoint does not create a second task engine, database, permission model, or standalone application. It provides a coherent name and vocabulary for durable capability families implemented through Tasks and approved first-party integrations.

Preferred product presentation:

> GoreeCloud Tasks — Powered by Waypoint

Alternative capability presentation:

> Waypoint by GoreeCloud
>
> The work-management system behind GoreeCloud Tasks.

## Canonical hierarchy

```text
GoreeCloud Suite
└── GoreeCloud Tasks
    └── GoreeCloud Waypoint
        └── Waypoint capability families
```

## Capability families

| Family | Capability domain |
| --- | --- |
| **Waypoint Capture** | Inbox, Quick Add, rapid task creation, and low-friction work capture. |
| **Waypoint Focus** | Today, priorities, overdue work, and work requiring current attention. |
| **Waypoint Horizon** | Upcoming work, future commitments, and longer-range planning. |
| **Waypoint Projects** | Projects, sections, subtasks, dependencies, and structured bodies of work. |
| **Waypoint Rhythm** | Recurring tasks, repeating schedules, routines, and recurrence behavior. |
| **Waypoint Pulse** | Reminders, notifications, deadlines, and attention signals. |
| **Waypoint Compass** | Search, filters, labels, saved views, classification, and navigation through work. |
| **Waypoint Together** | Shared projects, assignments, comments, membership, collaboration, and attributable shared work. |
| **Waypoint Operations** | GoreeCloud operational work, P0–P4 semantics, systems, services, blockers, resume conditions, prerequisites, recovery, validation, documentation, maintenance windows, and related infrastructure/change relationships. |
| **Waypoint Timeline** | Scheduling and first-party GoreeCloud Calendar interoperability, including task projections, planning context, busy-time awareness, and scheduling relationships. |
| **Waypoint Trail** | Activity history, attributable changes, and historical task/project context. |
| **Waypoint Archive** | Portable exports, migration, preserved task history, and long-term task-data continuity. |

## User-interface rule

Waypoint is an umbrella identity, not a requirement to rename every familiar task-management control. Conventional terms such as Inbox, Today, Upcoming, Projects, Due date, Priority, Labels, Subtasks, Search, Comments, and Settings should remain where they provide the clearest experience.

Waypoint names are appropriate when they improve feature grouping, product identity, navigation, onboarding, documentation, or conceptual understanding. They must not make ordinary task actions harder to discover.

## Authority boundaries

### GoreeCloud Tasks

Tasks remains authoritative for task content, workflow, assignment, project membership, completion, due scheduling, recurrence, subtasks, labels, comments, activity, reminders, operational metadata, and task-specific authorization.

### GoreeCloud Calendar

Waypoint Timeline names the planning and scheduling experience that links Tasks and GoreeCloud Calendar. Tasks remains authoritative for tasks and recurring-task behavior. Calendar remains authoritative for native events, calendar membership, event authorization, calendar-specific metadata, and busy-time context. The integration must use explicit versioned application interfaces rather than direct database coupling.

### GoreeCloud Manager

Waypoint Operations names the operational-work experience that may be surfaced through GoreeCloud Manager. Manager may display or interact with authorized work only through controlled interfaces that preserve Tasks authorization. Manager does not become authoritative for task content by displaying Waypoint Operations data.

## Relationship to other GoreeCloud identities

Waypoint complements rather than replaces other GoreeCloud identities:

- **Glaze UI** — shared visual and interaction language.
- **Wardveil Security** — platform security identity.
- **Privacy Shield** — privacy protection identity.
- **Everkeep** — resilience, recovery, preservation, and digital-legacy identity.
- **GoreeCloud Quill** — intelligent writing and text-editing capability identity.
- **GoreeCloud Waypoint** — work-management capability identity centered on GoreeCloud Tasks.
- **GoreeCloud Suite** — integrated user-facing application ecosystem.

## Expansion rule

A new Waypoint family should be added only when a durable capability domain emerges and a new name materially improves organization or understanding. Individual buttons, fields, settings, and ordinary task actions should not receive branded names merely for branding's sake.

## Visual direction

Waypoint should eventually receive a consistent mark that works with Glaze UI and GoreeCloud application identity standards. The visual concept should communicate direction, progress, destination, navigation, or coordinated movement without collapsing into a generic map-pin symbol. It must remain recognizable at small navigation and application-icon sizes and must visually complement GoreeCloud Tasks rather than imply an unrelated product.

## Source of truth

The authoritative governance record is the GoreeCloud Google Drive document **Standard — Waypoint Identity**. This repository document mirrors the software-facing contract so source code, interface work, documentation, and tests can use the same vocabulary without relying on undocumented memory.
