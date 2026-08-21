# Native Productivity Roadmap

GoreeCloud Tasks is a first-party GoreeCloud application. The goal is to build original productivity capabilities that cover the useful workflows associated with mature task managers without copying proprietary code, assets, wording, or interface layouts.

## Product direction

The application should become a complete private productivity workspace spanning tasks, planning, calendar-aware work, focus sessions, reminders, collaboration, and portable data. These capabilities remain native GoreeCloud features and preserve the existing authorization, self-hosting, backup, recovery, and interoperability model.

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

### 2. Calendar workspace

Add native day, week, month, and agenda views backed by GoreeCloud Tasks data. Calendar presentation must remain usable without an external calendar provider. Later interoperability can use standards-based calendar exchange or DAV integration without making a third-party cloud mandatory.

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

Add a planning layer that can surface overdue items, unscheduled high-priority work, overloaded days, and tasks that need attention. Any future AI-assisted planning should be optional and additive; the core planner must work deterministically without AI or an external provider.

### 9. Collaboration expansion

Build on existing projects, membership, assignment, comments, and activity history with clearer shared-work surfaces, assignee-centric views, mentions, and notification controls. Authorization remains server-enforced and project-scoped.

### 10. Home-screen and native clients

Prepare stable APIs and interaction contracts for future first-party Android and Linux clients. Android should eventually support home-screen widgets and native notifications. Linux packaging should follow GoreeCloud application-delivery standards. The web application remains a complete client rather than a reduced administrative interface.

### 11. Interoperability

Prefer open standards and portable formats. Calendar interoperability should align with the GoreeCloud DAV architecture where appropriate. Import/export should continue to preserve user ownership and avoid lock-in.

## Delivery order

1. Today / Upcoming / agenda planning surfaces.
2. Calendar workspace.
3. Rich recurrence.
4. Checklist items and progress.
5. Focus sessions.
6. Natural-language Quick Add.
7. Smart views and saved filters.
8. Collaboration and notification refinements.
9. Native-client APIs, Android widgets, and Linux integration.
10. Optional planning intelligence and broader interoperability.

## Design constraints

- Keep the implementation first-party and original.
- Do not copy proprietary application source code, artwork, screenshots, strings, or layouts.
- Preserve GoreeCloud privacy-by-default and self-hosted operation.
- Do not require a commercial cloud for core task, calendar, reminder, focus, or planning features.
- Preserve authorization boundaries across every new view and API.
- Keep exports/restores forward-compatible as the schema evolves.
- Add migrations, regression tests, and recovery coverage for persistent feature changes.
- Treat native Android/Linux delivery as clients of the same GoreeCloud task model, not separate incompatible products.
