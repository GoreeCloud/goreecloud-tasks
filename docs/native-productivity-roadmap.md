# Native Productivity Roadmap

GoreeCloud Tasks is a first-party GoreeCloud application. The goal is to build original productivity capabilities that cover the useful workflows associated with mature task managers without copying proprietary code, assets, wording, or interface layouts.

## Product direction

The application should become a complete private productivity workspace spanning tasks, planning, calendar-aware work, focus sessions, reminders, collaboration, and portable data. These capabilities remain native GoreeCloud features and preserve the existing authorization, self-hosting, backup, recovery, and interoperability model.

GoreeCloud Tasks and GoreeCloud Calendar are peer first-party applications and must integrate in both directions. Tasks remains authoritative for task content, task workflow, assignment, project membership, completion, recurrence, and task-specific authorization. Calendar remains authoritative for native calendar events, calendar membership, event scheduling semantics, and calendar-specific metadata. Neither application may bypass the other's authorization model or directly couple to the other's database.

## Existing foundation

The current application already provides a strong base for this work:

- personal and project-scoped tasks;
- priorities and workflow statuses;
- labels;
- subtasks;
- due dates and times;
- reminders and ntfy delivery;
- comments and activity history;
- assignments and project collaboration;
- daily, weekly, and monthly recurrence;
- JSON portability and restore;
- optional GoreeCloud operational metadata;
- authorization-aware task visibility and editing.

## Native feature tracks

### 1. Today and planning workspace

Build a first-class Today surface that combines overdue work and work due today, with intentional ordering and rapid completion/rescheduling. Add Upcoming and agenda-style planning views so users can move naturally between immediate work and future commitments.

### 2. Calendar workspace and GoreeCloud Calendar integration

Add native day, week, month, and agenda views backed by GoreeCloud Tasks data while also integrating with GoreeCloud Calendar as a peer application.

The first-party integration contract should provide:

- authorized task projection from Tasks into Calendar for tasks with due dates/times;
- clear visual distinction between task projections and native calendar events;
- links from a Calendar task projection back to the authoritative task detail;
- links from Tasks planning surfaces into the corresponding Calendar date/time context;
- Calendar-initiated creation of a new task through a Tasks API rather than direct database access;
- Calendar-initiated rescheduling of an authorized task through a Tasks API;
- Tasks access to authorized Calendar busy/event context for planning without assuming ownership of Calendar data;
- stable cross-application identifiers so a task projection never becomes a duplicate independent event by accident;
- explicit deletion semantics: deleting a Calendar projection must not silently delete the task, and deleting/completing a task must remove or update its projection predictably;
- recurrence mapping that preserves Tasks as the recurrence authority for recurring tasks;
- user-specific authorization at every read and mutation boundary;
- service-to-service credentials scoped to the minimum API permissions required;
- no direct Tasks-to-Calendar or Calendar-to-Tasks database access.

Calendar presentation inside Tasks must remain usable if GoreeCloud Calendar is temporarily unavailable. Likewise, GoreeCloud Calendar must continue to function for native events if Tasks is temporarily unavailable.

### 3. Rich recurrence

Extend the accepted daily/weekly/monthly recurrence foundation with custom intervals, selected weekdays, end dates or occurrence limits, exceptions, skip/reschedule semantics, and predictable handling of recurring subtask trees. Preserve compatibility with existing recurrence records.

### 4. Checklists and richer task composition

Keep hierarchical subtasks while adding lightweight checklist items for cases where users need simple completion steps rather than independently scheduled tasks. Add progress summaries derived from checklist/subtask completion.

### 5. Focus sessions

Add a native focus timer associated with an optional task. Initial presets should support common focus/break durations while allowing user-defined durations. Store session history locally in GoreeCloud so focus statistics do not depend on a commercial service.

### 6. Natural-language quick capture

Enhance Quick Add with deterministic parsing for common phrases such as today, tomorrow, weekday names, dates, times, priorities, labels, and repeat rules. Parsing must be inspectable and reversible: users should always see the structured result before or after saving and be able to correct it normally.

### 7. Smart views and saved filters

Add user-defined views composed from supported task properties: project, assignee, creator, label, priority, status, due window, recurrence, completion state, and GoreeCloud operational metadata. Filters should be represented as application data rather than executable expressions.

### 8. Planning assistance

Add a planning layer that can surface overdue items, unscheduled high-priority work, overloaded days, and tasks that need attention. Authorized GoreeCloud Calendar busy/event context may inform planning suggestions without being copied into Tasks as authoritative event data. Any future AI-assisted planning should be optional and additive; the core planner must work deterministically without AI or an external provider.

### 9. Collaboration expansion

Build on existing projects, membership, assignment, comments, and activity history with clearer shared-work surfaces, assignee-centric views, mentions, and notification controls. Authorization remains server-enforced and project-scoped.

### 10. Home-screen and native clients

Prepare stable APIs and interaction contracts for future first-party Android and Linux clients. Android should eventually support home-screen widgets and native notifications. Linux packaging should follow GoreeCloud application-delivery standards. The web application remains a complete client rather than a reduced administrative interface.

### 11. Interoperability

Prefer open standards and portable formats. GoreeCloud Calendar is the preferred first-party calendar integration. Standards-based calendar interoperability and DAV support should align with the GoreeCloud DAV architecture where appropriate and should complement, not replace, the richer first-party Tasks ↔ Calendar contract. Import/export should continue to preserve user ownership and avoid lock-in.

## Initial Tasks ↔ Calendar API boundary

The first integration version should use versioned HTTP APIs and stable application identities.

Tasks should expose authorization-scoped endpoints conceptually equivalent to:

- list scheduled task projections for an authorized user and time window;
- read one visible task projection;
- create a task from Calendar context;
- reschedule an editable task;
- optionally update task duration/calendar-display metadata when that model is introduced.

Calendar should expose authorization-scoped endpoints conceptually equivalent to:

- list busy/event context for an authorized user and time window;
- read calendar display metadata required by Tasks planning views;
- provide a stable Calendar deep link for a date, event, or planning context.

Exact routes and schemas should be versioned and documented before implementation. Cross-application calls must use application-level APIs, never shared database credentials.

## Delivery order

1. Today / Upcoming / agenda planning surfaces.
2. Bidirectional GoreeCloud Tasks ↔ GoreeCloud Calendar API contract and task projection model.
3. Calendar workspace using Tasks data plus authorized GoreeCloud Calendar context.
4. Rich recurrence.
5. Checklist items and progress.
6. Focus sessions.
7. Natural-language Quick Add.
8. Smart views and saved filters.
9. Collaboration and notification refinements.
10. Native-client APIs, Android widgets, and Linux integration.
11. Optional planning intelligence and broader interoperability.

## Design constraints

- Keep the implementation first-party and original.
- Do not copy proprietary application source code, artwork, screenshots, strings, or layouts.
- Preserve GoreeCloud privacy-by-default and self-hosted operation.
- Do not require a commercial cloud for core task, calendar, reminder, focus, or planning features.
- Preserve authorization boundaries across every new view and API.
- Treat GoreeCloud Tasks and GoreeCloud Calendar as separate authoritative services with explicit APIs.
- Do not share application databases or bypass application-level permissions.
- Keep exports/restores forward-compatible as the schema evolves.
- Add migrations, regression tests, and recovery coverage for persistent feature changes.
- Treat native Android/Linux delivery as clients of the same GoreeCloud task model, not separate incompatible products.
