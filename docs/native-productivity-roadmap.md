# Native Productivity Roadmap

GoreeCloud Tasks is a first-party GoreeCloud application. The goal is to build original productivity capabilities that cover the useful workflows associated with mature task managers without copying proprietary code, assets, wording, product identity, or interface layouts.

## Product direction

The application should become a complete private productivity workspace spanning tasks, planning, calendar-aware work, focus sessions, reminders, collaboration, portable data, appearance, and accessible capture across supported device classes. These capabilities remain native GoreeCloud features and preserve the existing authorization, self-hosting, backup, recovery, and interoperability model.

GoreeCloud Tasks and GoreeCloud Calendar are peer first-party applications and must integrate in both directions. Tasks remains authoritative for task content, task workflow, assignment, project membership, completion, recurrence, and task-specific authorization. Calendar remains authoritative for native calendar events, calendar membership, event scheduling semantics, and calendar-specific metadata. Neither application may bypass the other's authorization model or directly couple to the other's database.

## Experience benchmark translation

Reference productivity interfaces are useful as workflow benchmarks, not as implementation templates. GoreeCloud Tasks should translate the useful ideas into an original Glaze UI 2.2 experience with GoreeCloud-owned information architecture, components, copy, interaction details, and visual identity.

The benchmark patterns worth carrying forward are:

- fast capture that is always easy to reach without overwhelming the reading surface;
- a first-class Today workspace for immediate work;
- an Upcoming or agenda workspace that makes future commitments easy to scan;
- day and week planning views that combine task timing with authorized calendar context;
- clear Inbox, project, label, saved-view, and shared-work navigation;
- project organization through sections, hierarchy, favorites, and purposeful counts;
- compact task rows that surface due time, project, assignee, labels, recurrence, and priority without turning every task into a heavy card;
- rapid completion, rescheduling, and assignment workflows;
- collaboration surfaces for comments, mentions, activity, and attributable feedback;
- purpose-built mobile navigation and reachability rather than a shrunken desktop shell;
- appearance controls that use Glaze UI semantic appearance, accent, material, contrast, and density capabilities rather than product-local theme systems;
- optional voice-assisted capture that always presents a reviewable structured task before committing changes.

These patterns do not authorize cloning another product's sidebar, calendar geometry, task editor, mobile dock, marketing artwork, colors, icons, strings, animations, or other distinctive expression.

## Glaze UI 2.2 interaction direction

GoreeCloud Tasks should use the current Stable Glaze UI 2.2 contract as the design foundation for every supported user-facing surface. The task content layer should remain stable and readable while navigation, compact toolbars, menus, sheets, transient feedback, and reachable mobile controls use selective Glaze materials where the hierarchy benefits from them.

Desktop should be workspace-first, information-capable, pointer-and-keyboard friendly, and comfortable with persistent navigation. Mobile should be touch-first and reachability-first with progressive disclosure, a compact task-focused composition, and reachable frequent navigation. Tablet should use available space intentionally through pane-aware layouts where useful instead of stretching the mobile composition.

Accessibility is part of the product behavior: 48-pixel ordinary actionable targets, the current Touch Assistance target contract where enabled, visible focus, keyboard operation, reduced motion, reduced transparency, forced-colors resilience, increased contrast, and 200-percent text reflow must remain release gates. Glaze Motion remains Experimental and must not become a Stable Tasks dependency unless separately promoted.

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

Build a first-class Today surface that combines overdue awareness and work due today, with intentional ordering and rapid completion/rescheduling. Add Upcoming and agenda-style planning views so users can move naturally between immediate work and future commitments.

The first visual tranche should favor a calm Glaze workspace shell, persistent desktop task navigation, compact capture, solid task reading surfaces, useful inline metadata, and a purpose-built mobile dock. This presentation work must not imply that later timeline, duration, voice, or calendar capabilities are already implemented.

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

A true time-block planner should be introduced only after task duration or equivalent scheduling semantics are modeled explicitly. The interface must not fabricate duration from a due time alone.

### 3. Rich recurrence

Extend the accepted daily/weekly/monthly recurrence foundation with custom intervals, selected weekdays, end dates or occurrence limits, exceptions, skip/reschedule semantics, and predictable handling of recurring subtask trees. Preserve compatibility with existing recurrence records.

### 4. Checklists and richer task composition

Keep hierarchical subtasks while adding lightweight checklist items for cases where users need simple completion steps rather than independently scheduled tasks. Add progress summaries derived from checklist/subtask completion.

### 5. Focus sessions

Add a native focus timer associated with an optional task. Initial presets should support common focus/break durations while allowing user-defined durations. Store session history locally in GoreeCloud so focus statistics do not depend on a commercial service.

### 6. Natural-language quick capture

Enhance Quick Add with deterministic parsing for common phrases such as today, tomorrow, weekday names, dates, times, priorities, labels, and repeat rules. Parsing must be inspectable and reversible: users should always see the structured result before or after saving and be able to correct it normally.

### 7. Voice-assisted capture

Add optional voice input as another entry method into the same native capture pipeline rather than creating a separate task model. Microphone use must require explicit user action and applicable privacy permission. Transcription and parsing boundaries must be visible, reviewable, and compatible with GoreeCloud privacy requirements.

The application must show the structured interpretation before committing material fields when transcription or parsing confidence is uncertain. Core task management must never depend on voice services or a commercial cloud provider.

### 8. Smart views and saved filters

Add user-defined views composed from supported task properties: project, assignee, creator, label, priority, status, due window, recurrence, completion state, and GoreeCloud operational metadata. Filters should be represented as application data rather than executable expressions.

Favorites and pinned destinations should build on this view model so frequently used projects and saved views can be reached without duplicating underlying task data.

### 9. Project organization

Expand native project organization with sections, nested project relationships where the data model can preserve clear authorization, project favorites, archive visibility, meaningful counts, and predictable reorder semantics. Hierarchy must not allow a user to infer inaccessible project names or membership through navigation structure.

### 10. Planning assistance

Add a planning layer that can surface overdue items, unscheduled high-priority work, overloaded days, and tasks that need attention. Authorized GoreeCloud Calendar busy/event context may inform planning suggestions without being copied into Tasks as authoritative event data. Any future AI-assisted planning should be optional and additive; the core planner must work deterministically without AI or an external provider.

### 11. Collaboration expansion

Build on existing projects, membership, assignment, comments, and activity history with clearer shared-work surfaces, assignee-centric views, mentions, lightweight reactions where useful, and notification controls. Authorization remains server-enforced and project-scoped.

### 12. Appearance and information density

Expose supported Glaze UI appearance options through GoreeCloud-native settings rather than inventing an independent Tasks theme engine. Planned controls may include system/light/dark appearance, supported accent personalization, reduced-transparency behavior, and comfortable/standard/compact information density where the current Stable Glaze UI contract permits them.

Semantic colors for success, warning, danger, privacy, security, and other protected meanings must not be recolored by a task theme or project color.

### 13. Home-screen and native clients

Prepare stable APIs and interaction contracts for future first-party Android and Linux clients. Android should eventually support home-screen widgets, native notifications, share-target capture, and device-appropriate quick actions. Linux packaging should follow GoreeCloud application-delivery standards. The web application remains a complete client rather than a reduced administrative interface.

### 14. Interoperability

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

1. Today / Upcoming / agenda workspace composition and adaptive Glaze navigation.
2. Bidirectional GoreeCloud Tasks ↔ GoreeCloud Calendar API contract and task projection model.
3. Calendar workspace using Tasks data plus authorized GoreeCloud Calendar context.
4. Task duration/scheduling semantics required for a true time-block planner.
5. Rich recurrence.
6. Checklist items and progress.
7. Focus sessions.
8. Natural-language Quick Add.
9. Voice-assisted capture through the reviewed native capture pipeline.
10. Smart views, saved filters, favorites, and richer project organization.
11. Collaboration and notification refinements.
12. GoreeCloud-native appearance and density settings backed by Glaze UI.
13. Native-client APIs, Android widgets/share capture, and Linux integration.
14. Optional planning intelligence and broader interoperability.

## Design constraints

- Keep the implementation first-party and original.
- Do not copy proprietary application source code, artwork, screenshots, strings, icons, animations, or layouts.
- Treat external screenshots and competing products as workflow and quality benchmarks only.
- Use current Stable Glaze UI semantic tokens and shared components instead of creating a parallel Tasks design language.
- Keep durable reading/content surfaces solid enough for sustained clarity; reserve Glaze materials primarily for navigation, controls, and transient interaction layers.
- Preserve GoreeCloud privacy-by-default and self-hosted operation.
- Do not require a commercial cloud for core task, calendar, reminder, focus, capture, or planning features.
- Preserve authorization boundaries across every new view and API.
- Treat GoreeCloud Tasks and GoreeCloud Calendar as separate authoritative services with explicit APIs.
- Do not share application databases or bypass application-level permissions.
- Keep exports/restores forward-compatible as the schema evolves.
- Add migrations, regression tests, and recovery coverage for persistent feature changes.
- Treat native Android/Linux delivery as clients of the same GoreeCloud task model, not separate incompatible products.
- Do not present planned timeline, theme, voice, intelligence, or native-client behavior as implemented until source and validation evidence exists.
